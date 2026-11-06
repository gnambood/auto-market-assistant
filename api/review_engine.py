"""Owner-review retrieval, abstention and optional generation."""

import re

from .runtime import ENABLE_GENERATION, ensure_artifacts, load_answerability_policy, normalize_model
from .vehicle_context import vehicle_context_conflict

class RagEngine:
    def __init__(self):
        import faiss
        import numpy as np
        import pandas as pd
        from sentence_transformers import SentenceTransformer

        self.faiss, self.np, self.pd = faiss, np, pd
        paths = ensure_artifacts()
        self.docs = pd.read_parquet(paths["review_documents.parquet"])
        self.known_vehicle_pairs = set(zip(self.docs["manufacturer"], self.docs["model_family"]))
        self.index = faiss.read_index(str(paths["review_index.faiss"]))

        if self.index.ntotal != len(self.docs):
            raise RuntimeError(
                f"FAISS/doc mismatch: {self.index.ntotal} != {len(self.docs)}"
            )

        self.embeddings = np.asarray(
            self.index.reconstruct_n(0, self.index.ntotal),
            dtype="float32",
        )
        self.embedder = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2"
        )
        self.policy = load_answerability_policy()
        self.tokenizer = None
        self.generator = None
        self.generator_name = None

    @staticmethod
    def _candidate_scope(docs, payload):
        """Keep owner evidence tied to the selected model family.

        Sparse evidence can widen the year window but never the model identity.
        A requested k greater than the available reviews is not a reason to
        substitute reviews of another model.
        """
        make = payload.manufacturer.lower().strip()
        family = " ".join(normalize_model(payload.model).split()[:2])
        family_mask = docs["manufacturer"].eq(make) & docs["model_family"].eq(family)

        if payload.year is not None:
            near_year = family_mask & docs["vehicle_year"].between(
                payload.year - 1, payload.year + 1
            )
            if near_year.any():
                return near_year, "same model family, year ±1"

        return family_mask, "same model family"

    def _retrieve(self, payload):
        mask, scope = self._candidate_scope(self.docs, payload)

        candidate_idx = self.np.flatnonzero(mask.to_numpy())

        if not len(candidate_idx):
            return self.docs.iloc[0:0].copy(), scope

        # Vehicle identity is already enforced by the candidate mask. Encoding
        # only the question keeps the cosine score about question↔review
        # relevance rather than inflating it with repeated make/model tokens.
        q = self.embedder.encode(
            [payload.question],
            normalize_embeddings=True,
            convert_to_numpy=True,
        ).astype("float32")

        local = self.faiss.IndexFlatIP(self.embeddings.shape[1])
        local.add(self.embeddings[candidate_idx])

        n = min(payload.k, len(candidate_idx))
        scores, ids = local.search(q, n)

        result = self.docs.iloc[candidate_idx[ids[0]]].copy()
        result["similarity"] = scores[0]
        return result.reset_index(drop=True), scope

    @staticmethod
    def _extract_citations(text, valid_ids):
        cited = set(
            re.findall(
                r"\[(edm_[a-f0-9]+)\]",
                str(text),
            )
        )
        return cited, bool(cited) and cited.issubset(valid_ids)

    @staticmethod
    def _scope_guard(question):
        """Block question types that model-level owner reviews cannot establish."""
        q = re.sub(r"\s+", " ", str(question).lower()).strip()

        specific_vehicle = bool(
            re.search(
                r"\b(?:this|that|my|the)\s+"
                r"(?:(?:specific|exact|particular|individual)\s+)?"
                r"(?:vehicle|car|truck|suv|van|listing)\b",
                q,
            )
        )

        specific_instance_fact = bool(
            re.search(
                r"\b("
                r"dent(?:ed)?|scratch(?:ed)?|crack(?:ed)?|damage(?:d)?|"
                r"accident|collision|paint chip|body damage|rust spot|"
                r"windshield|tire tread|flat tire|vin|carfax|"
                r"vehicle history|accident history|service history|"
                r"maintenance history|ownership history|previous owners?|"
                r"number of owners?|owner count|odometer rollback|"
                r"registration|license plate|current mileage|exact mileage|"
                r"current location|where is it|where is this|still for sale|"
                r"clean title|salvage title|exact trim|exact options|"
                r"paint color|exterior color|interior color"
                r")\b",
                q,
            )
        )

        exact_history_request = bool(
            re.search(
                r"\b("
                r"what(?:'s| is) the vin|vin number|carfax|"
                r"how many previous owners?|number of previous owners?|"
                r"ownership history|accident history|"
                r"service history for (?:this|that|the)|"
                r"maintenance history for (?:this|that|the)"
                r")\b",
                q,
            )
        )

        if (
            specific_vehicle
            and specific_instance_fact
        ) or exact_history_request:
            return {
                "reason_code": "specific_vehicle_fact",
                "reason": (
                    "This question asks for a fact about one specific vehicle. "
                    "The available evidence contains model-level owner reviews, "
                    "not listing-, inspection-, VIN-, or history-report data."
                ),
                "suggested_question": (
                    "What problems do owners commonly report for this model and year?"
                ),
            }

        insurance_or_finance = bool(
            re.search(
                r"\b("
                r"insurance|insurance premium|insurance quote|"
                r"finance|financing|loan|interest rate|apr|down payment"
                r")\b",
                q,
            )
        )

        dealer_inventory = bool(
            re.search(
                r"\b("
                r"in stock|dealer inventory|dealership inventory|"
                r"where can i buy|available near me|for sale near me|"
                r"which dealer|which dealership"
                r")\b",
                q,
            )
        )

        registration_or_tax = bool(
            re.search(
                r"\b("
                r"registration fee|registration cost|license fee|"
                r"sales tax|tax deductible|tax deduction|"
                r"how much tax|vehicle tax"
                r")\b",
                q,
            )
        )

        weather_request = bool(
            re.search(
                r"\b(weather|rain|snow|forecast|temperature)\b",
                q,
            )
            and re.search(
                r"\b(today|tomorrow|tonight|this week|next week|trip)\b",
                q,
            )
        )

        future_fuel_price = bool(
            re.search(
                r"\b(?:gas|gasoline|fuel)\s+prices?\b|"
                r"\bprice of (?:gas|gasoline|fuel)\b",
                q,
            )
            and re.search(
                r"\b(next|future|tomorrow|week|month|year|will|forecast|predict)\b",
                q,
            )
        )

        future_market_value = bool(
            re.search(
                r"\b("
                r"collectible value|future value|future resale value|"
                r"worth in (?:five|ten|\d+) years?|"
                r"value in (?:five|ten|\d+) years?"
                r")\b",
                q,
            )
        )

        if (
            insurance_or_finance
            or dealer_inventory
            or registration_or_tax
            or weather_request
            or future_fuel_price
            or future_market_value
        ):
            return {
                "reason_code": "requires_external_data",
                "reason": (
                    "This question requires current, transactional, regulatory, "
                    "or future-looking information that model-level owner reviews "
                    "do not provide."
                ),
                "suggested_question": (
                    "What do owners report about reliability, maintenance, comfort, "
                    "fuel economy, or common problems?"
                ),
            }

        strong_spec_phrase = bool(
            re.search(
                r"\b("
                r"lug nut torque|torque spec|oil capacity|fluid capacity|"
                r"factory paint code|oem part number|part number|curb weight|"
                r"wheelbase|tire pressure|official crash(?:-|\s)?test|"
                r"original msrp|factory msrp|official horsepower|"
                r"official towing capacity|epa rating|epa combined mpg"
                r")\b",
                q,
            )
        )

        authoritative_modifier = bool(
            re.search(
                r"\b("
                r"official|factory|oem|manufacturer[- ]specified|"
                r"exact specification"
                r")\b",
                q,
            )
        )

        specification_term = bool(
            re.search(
                r"\b("
                r"horsepower|torque|curb weight|wheelbase|oil capacity|"
                r"tire pressure|msrp|crash(?:-|\s)?test score|"
                r"part number|towing capacity|epa rating"
                r")\b",
                q,
            )
        )

        if (
            strong_spec_phrase
            or (
                authoritative_modifier
                and specification_term
            )
        ):
            return {
                "reason_code": "authoritative_specification",
                "reason": (
                    "This question asks for an authoritative vehicle specification. "
                    "The available evidence is owner-review text rather than "
                    "manufacturer or regulatory specification data."
                ),
                "suggested_question": (
                    "What do owners say about real-world performance, towing, "
                    "fuel economy, or everyday driving?"
                ),
            }

        return None

    @staticmethod
    def _retrieval_features(retrieved, support_threshold):
        if retrieved.empty:
            return {
                "max_similarity": None,
                "mean_top3_similarity": None,
                "support_source_count": 0,
            }

        scores = (
            retrieved["similarity"]
            .astype(float)
            .sort_values(ascending=False)
            .to_numpy()
        )

        return {
            "max_similarity": float(scores[0]),
            "mean_top3_similarity": float(
                scores[: min(3, len(scores))].mean()
            ),
            "support_source_count": int(
                (scores >= float(support_threshold)).sum()
            ),
        }

    @classmethod
    def _assess_retrieval(cls, retrieved, policy):
        support_threshold = float(
            policy["support_threshold"]
        )

        features = cls._retrieval_features(
            retrieved,
            support_threshold,
        )

        if (
            features["max_similarity"] is None
            or features["mean_top3_similarity"] is None
        ):
            return {
                "answerable": False,
                "reason_code": "no_review_evidence",
                "reason": (
                    "No owner-review evidence was retrieved for this vehicle selection."
                ),
                **features,
                "relevant_source_count": 0,
                "relevant_reviews": retrieved.iloc[0:0].copy(),
            }

        max_ok = (
            features["max_similarity"]
            >= float(policy["max_threshold"])
        )
        mean_ok = (
            features["mean_top3_similarity"]
            >= float(policy["mean_top3_threshold"])
        )
        support_ok = (
            features["support_source_count"]
            >= int(policy["min_support_sources"])
        )

        answerable = bool(
            max_ok
            and (
                mean_ok
                or support_ok
            )
        )

        if not answerable:
            return {
                "answerable": False,
                "reason_code": "low_retrieval_relevance",
                "reason": (
                    "The retrieved owner reviews do not provide enough "
                    "semantically relevant evidence to support a grounded answer."
                ),
                **features,
                "relevant_source_count": 0,
                "relevant_reviews": retrieved.iloc[0:0].copy(),
            }

        scores = retrieved["similarity"].astype(float)
        relevant = (
            retrieved.loc[scores >= support_threshold]
            .copy()
            .reset_index(drop=True)
        )

        if relevant.empty:
            relevant = (
                retrieved.head(1)
                .copy()
                .reset_index(drop=True)
            )

        return {
            "answerable": True,
            "reason_code": None,
            "reason": None,
            **features,
            "relevant_source_count": int(len(relevant)),
            "relevant_reviews": relevant,
        }

    @staticmethod
    def _fallback(retrieved):
        if retrieved.empty:
            return "Not enough review evidence for this vehicle."

        ids = [
            f"[{review_id}]"
            for review_id
            in retrieved["review_id"].head(3)
        ]

        cited = (
            ", ".join(ids[:-1])
            + (
                " and " + ids[-1]
                if len(ids) > 1
                else ids[0]
            )
        )

        return (
            f"Relevant owner-review evidence was found in {cited}. "
            "Live generation is disabled, so the strongest matching excerpts are "
            "shown below instead of being synthesized into a new claim."
        )

    def _load_generator(self):
        if self.generator is not None:
            return

        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        device = (
            "cuda"
            if torch.cuda.is_available()
            else "cpu"
        )
        name = (
            "Qwen/Qwen2.5-1.5B-Instruct"
            if device == "cuda"
            else "Qwen/Qwen2.5-0.5B-Instruct"
        )

        self.tokenizer = AutoTokenizer.from_pretrained(name)
        self.generator = AutoModelForCausalLM.from_pretrained(
            name,
            torch_dtype=(
                torch.float16
                if device == "cuda"
                else torch.float32
            ),
            device_map=(
                "auto"
                if device == "cuda"
                else None
            ),
        )

        if device == "cpu":
            self.generator.to("cpu")

        self.generator_name = name

    def _generate(self, question, retrieved):
        if not ENABLE_GENERATION:
            answer = self._fallback(retrieved)
            _, valid = self._extract_citations(
                answer,
                set(retrieved["review_id"]),
            )
            return (
                answer,
                valid,
                True,
                "retrieval-fallback",
            )

        # Production generation remains optional. The portfolio notebook is the
        # validated Qwen path; ECS currently runs retrieval-only to keep the CPU
        # service small and predictable.
        self._load_generator()

        evidence = []
        for _, row in retrieved.iterrows():
            excerpt = re.sub(
                r"\s+",
                " ",
                str(row["review_text"]),
            ).strip()[:850]

            evidence.append(
                f"SOURCE [{row['review_id']}]\n"
                f"Vehicle year: {row['vehicle_year']}\n"
                f"Rating: {row['rating']}\n"
                f"Title: {row['review_title']}\n"
                f"Review: {excerpt}"
            )

        messages = [
            {
                "role": "system",
                "content": (
                    "Use only supplied owner-review sources. "
                    "Every factual bullet must end with a source ID exactly "
                    "as written. If reviews disagree, say so. "
                    "Return 2 to 4 concise bullets."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question: {question}\n\n"
                    + "\n\n".join(evidence)
                ),
            },
        ]

        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=3500,
        ).to(self.generator.device)

        output = self.generator.generate(
            **inputs,
            max_new_tokens=220,
            do_sample=False,
            pad_token_id=self.tokenizer.eos_token_id,
        )
        generated = output[
            0,
            inputs["input_ids"].shape[1]:,
        ]
        answer = self.tokenizer.decode(
            generated,
            skip_special_tokens=True,
        ).strip()

        valid_ids = set(retrieved["review_id"])
        _, valid = self._extract_citations(
            answer,
            valid_ids,
        )
        fallback_used = False

        if not valid:
            answer = self._fallback(retrieved)
            _, valid = self._extract_citations(
                answer,
                valid_ids,
            )
            fallback_used = True

        return (
            answer,
            valid,
            fallback_used,
            self.generator_name or "qwen",
        )

    def ask(self, payload):
        mismatch = vehicle_context_conflict(
            payload.question,
            payload.manufacturer,
            payload.model,
            payload.year,
            self.known_vehicle_pairs,
        )
        if mismatch:
            return {
                "answer": mismatch,
                "scope": "vehicle selection conflicts with question",
                "citation_valid": False,
                "fallback_used": False,
                "generation_mode": "abstained-vehicle-mismatch",
                "sources": [],
                "answerable": False,
                "reason": mismatch,
                "reason_code": "vehicle_context_mismatch",
                "suggested_question": (
                    "What reliability and maintenance issues do owners report "
                    "for my selected vehicle?"
                ),
                "max_similarity": None,
                "mean_top3_similarity": None,
                "support_source_count": 0,
                "relevant_source_count": 0,
            }

        guard = self._scope_guard(payload.question)

        if guard:
            return {
                "answer": guard["reason"],
                "scope": "outside available owner-review evidence",
                "citation_valid": False,
                "fallback_used": False,
                "generation_mode": "abstained-out-of-scope",
                "sources": [],
                "answerable": False,
                "reason": guard["reason"],
                "reason_code": guard["reason_code"],
                "suggested_question": guard["suggested_question"],
                "max_similarity": None,
                "mean_top3_similarity": None,
                "support_source_count": 0,
                "relevant_source_count": 0,
            }

        retrieved, scope = self._retrieve(payload)

        if retrieved.empty:
            reason = (
                "No owner-review evidence was available for this vehicle selection."
            )
            return {
                "answer": reason,
                "scope": scope,
                "citation_valid": False,
                "fallback_used": False,
                "generation_mode": "no-evidence",
                "sources": [],
                "answerable": False,
                "reason": reason,
                "reason_code": "no_review_evidence",
                "suggested_question": (
                    "What do owners mention about reliability and common problems?"
                ),
                "max_similarity": None,
                "mean_top3_similarity": None,
                "support_source_count": 0,
                "relevant_source_count": 0,
            }

        assessment = self._assess_retrieval(
            retrieved,
            self.policy,
        )

        if not assessment["answerable"]:
            return {
                "answer": assessment["reason"],
                "scope": scope,
                "citation_valid": False,
                "fallback_used": False,
                "generation_mode": "abstained-low-relevance",
                "sources": [],
                "answerable": False,
                "reason": assessment["reason"],
                "reason_code": assessment["reason_code"],
                "suggested_question": (
                    "Try asking about reliability, maintenance, comfort, "
                    "fuel economy, or common problems."
                ),
                "max_similarity": assessment["max_similarity"],
                "mean_top3_similarity": assessment["mean_top3_similarity"],
                "support_source_count": assessment["support_source_count"],
                "relevant_source_count": 0,
            }

        relevant = assessment["relevant_reviews"]

        answer, valid, fallback_used, mode = self._generate(
            payload.question,
            relevant,
        )

        sources = []
        for _, row in relevant.iterrows():
            sources.append(
                {
                    "review_id": str(row["review_id"]),
                    "vehicle_year": (
                        int(row["vehicle_year"])
                        if self.pd.notna(row["vehicle_year"])
                        else None
                    ),
                    "rating": (
                        float(row["rating"])
                        if self.pd.notna(row["rating"])
                        else None
                    ),
                    "review_title": str(row["review_title"]),
                    "excerpt": re.sub(
                        r"\s+",
                        " ",
                        str(row["review_text"]),
                    ).strip()[:260],
                    "similarity": float(row["similarity"]),
                }
            )

        return {
            "answer": answer,
            "scope": scope,
            "citation_valid": bool(valid),
            "fallback_used": bool(fallback_used),
            "generation_mode": mode,
            "sources": sources,
            "answerable": True,
            "reason": None,
            "reason_code": None,
            "suggested_question": None,
            "max_similarity": assessment["max_similarity"],
            "mean_top3_similarity": assessment["mean_top3_similarity"],
            "support_source_count": assessment["support_source_count"],
            "relevant_source_count": assessment["relevant_source_count"],
        }
