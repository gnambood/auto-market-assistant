"""Historical asking-price and listing-count trends for comparable vehicles.

Descriptive only. This module does not forecast prices or change model inference.
"""
import argparse
import json
from pathlib import Path

import pandas as pd


GROUP = ["manufacturer", "model_family", "year"]
REQUIRED = set(GROUP + ["id", "posting_date", "price"])


def build_market_trends(vehicles, min_group=12, min_days=2, min_daily=3):
    """Return daily observations and data-quality coverage for curated listings."""
    missing = sorted(REQUIRED - set(vehicles.columns))
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))
    if min(min_group, min_days, min_daily) < 1:
        raise ValueError("Sample thresholds must be positive")

    data = vehicles[list(REQUIRED)].copy()
    initial_rows = len(data)
    data = data.drop_duplicates(subset="id", keep="first")
    duplicate_ids = initial_rows - len(data)

    data["posting_date"] = pd.to_datetime(
        data["posting_date"], utc=True, errors="coerce"
    )
    missing_dates = int(data["posting_date"].isna().sum())
    data["price"] = pd.to_numeric(data["price"], errors="coerce")
    data["year"] = pd.to_numeric(data["year"], errors="coerce")
    valid = (
        data["posting_date"].notna()
        & data["price"].gt(0)
        & data["year"].notna()
        & data["manufacturer"].notna()
        & data["model_family"].notna()
    )
    data = data.loc[valid].copy()
    data["date"] = data["posting_date"].dt.strftime("%Y-%m-%d")
    data["year"] = data["year"].astype(int)
    for key in GROUP[:2]:
        data[key] = data[key].astype(str).str.strip().str.lower()
    data = data.loc[
        data["manufacturer"].ne("") & data["model_family"].ne("")
    ]

    daily = (
        data.groupby(GROUP + ["date"], observed=True)
        .agg(listing_count=("id", "size"), median_asking_price=("price", "median"))
        .reset_index()
        .sort_values(GROUP + ["date"])
    )
    if daily.empty:
        coverage = pd.DataFrame(columns=GROUP + ["total_listings", "observed_days"])
    else:
        coverage = (
            daily.groupby(GROUP, observed=True)
            .agg(
                total_listings=("listing_count", "sum"),
                observed_days=("date", "nunique"),
            )
            .reset_index()
        )
    coverage["eligible"] = (
        coverage["total_listings"].ge(min_group)
        & coverage["observed_days"].ge(min_days)
    )
    daily = daily.merge(coverage, on=GROUP, how="left")
    daily["price_sample_sufficient"] = (
        daily["eligible"] & daily["listing_count"].ge(min_daily)
    )
    daily.loc[~daily["price_sample_sufficient"], "median_asking_price"] = float("nan")

    diagnostics = {
        "source_rows": int(initial_rows),
        "duplicate_listing_ids_removed": int(duplicate_ids),
        "missing_or_invalid_posting_dates": missing_dates,
        "valid_rows": int(len(data)),
        "total_groups": int(len(coverage)),
        "eligible_groups": int(coverage["eligible"].sum()),
        "suppressed_daily_price_observations": int(
            (~daily["price_sample_sufficient"]).sum()
        ),
        "thresholds": {
            "min_group_listings": min_group,
            "min_observed_days": min_days,
            "min_daily_listings_for_price": min_daily,
        },
    }
    return daily, coverage, diagnostics


def write_viewer(daily, destination):
    """Small, dependency-free offline chart viewer for eligible group histories."""
    records = daily.loc[daily["eligible"], GROUP + [
        "date", "listing_count", "median_asking_price"
    ]].copy()
    records["median_asking_price"] = records["median_asking_price"].where(
        records["median_asking_price"].notna(), None
    )
    payload = json.dumps(records.to_dict(orient="records"), allow_nan=False)
    payload = payload.replace("<", "\\u003c")
    template = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Historical Vehicle Market Trends</title>
<style>
:root{color-scheme:dark;font:16px system-ui,sans-serif}
body{max-width:960px;margin:3rem auto;padding:0 1rem;background:#07111f;color:#eaf4ff}
header{margin-bottom:2rem}h1{font-size:clamp(2rem,5vw,3rem)}
p{color:#a7bbd2;line-height:1.6}
section{padding:1.4rem;background:#11243b;border:1px solid #2a4560;border-radius:18px}
label{display:block;margin-bottom:.7rem}
select{background:#07111f;color:#eaf4ff;border:1px solid #426782;border-radius:8px;padding:.7rem;width:100%}
svg{width:100%;height:310px;overflow:visible}
.tick{font:12px system-ui;fill:#b3c5d7}
small{color:#a7bbd2}a{color:#63e6be}
</style></head><body>
<header><small>Auto Market Assistant · descriptive analytics</small><h1>Historical market trends</h1>
<p>Observed asking-price medians and daily listing counts from historical Craigslist listings. Not transaction prices, live inventory, or forecasts.</p></header>
<section><label for="group">Compare a vehicle family and year</label>
<select id="group"></select><p id="status" role="status"></p>
<h2>Median daily asking price (USD)</h2><svg id="prices" role="img" aria-label="Daily asking-price median chart"></svg>
<h2>Observed daily listing count</h2><svg id="counts" role="img" aria-label="Daily listing counts chart"></svg>
</section><p><small>Dates with too few listings have no price estimate. Differences across days can reflect changes in listed vehicle condition, location or mileage. See the <a href="https://github.com/gnambood/auto-market-assistant/blob/main/MARKET_TRENDS.md">methodology and limitations</a>.</small></p>
<script>const rows=__PAYLOAD__;
const group=document.getElementById("group");
const names=[...new Set(rows.map(r=>r.manufacturer+" | "+r.model_family+" | "+r.year))].sort();
names.forEach(name=>{let option=document.createElement("option");option.value=name;option.textContent=name;group.append(option)});
function chart(id,items,field,money){
const svg=document.getElementById(id);svg.replaceChildren();
const vals=items.map(r=>r[field]);const valid=vals.filter(v=>v!==null&&Number.isFinite(v));
if(!valid.length){svg.textContent="No sufficiently sampled observations";return}
const max=Math.max(...valid,1);const w=850,h=250,m=45,step=(w-2*m)/Math.max(1,items.length-1);
function el(tag,attrs){let n=document.createElementNS("http://www.w3.org/2000/svg",tag);
Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,v));svg.append(n);return n}
for(let t=0;t<=4;t++){const y=m+(h-2*m)*t/4;
el("line",{x1:m,y1:y,x2:w-m,y2:y,stroke:"#33526e"});
let label=el("text",{x:0,y:y+4,class:"tick"});label.textContent=money?"$"+Math.round(max*(4-t)/4).toLocaleString():String(Math.round(max*(4-t)/4))}
let points=[];items.forEach((r,i)=>{const v=r[field];const x=m+i*step;
if(v===null||!Number.isFinite(v)){points=[];return}
const y=h-m-v/max*(h-2*m);if(money){points.push(x+","+y);el("circle",{cx:x,cy:y,r:3.5,fill:"#63e6be"})}
else{el("rect",{x:x-3,y:y,width:6,height:h-m-y,fill:"#7aa2ff"})}
});
if(money){let previous=[];items.forEach((r,i)=>{const v=r[field];if(v===null){if(previous.length>1)el("polyline",{points:previous.join(" "),fill:"none",stroke:"#63e6be","stroke-width":2});previous=[];return}
previous.push((m+i*step)+","+(h-m-v/max*(h-2*m)))});
if(previous.length>1)el("polyline",{points:previous.join(" "),fill:"none",stroke:"#63e6be","stroke-width":2})}
if(items.length){let a=el("text",{x:m,y:h+8,class:"tick"});a.textContent=items[0].date;
let b=el("text",{x:w-m,y:h+8,class:"tick","text-anchor":"end"});b.textContent=items[items.length-1].date}
svg.setAttribute("viewBox","0 0 850 280")}
function draw(){const items=rows.filter(r=>r.manufacturer+" | "+r.model_family+" | "+r.year===group.value);
document.getElementById("status").textContent=items.length+" observed posting dates; price omitted for undersampled days.";
chart("prices",items,"median_asking_price",true);chart("counts",items,"listing_count",false)}
group.addEventListener("change",draw);if(names.length)draw();else document.getElementById("status").textContent="No groups meet the configured sample thresholds.";
</script></body></html>"""
    Path(destination).write_text(template.replace("__PAYLOAD__", payload), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Curated vehicles Parquet file or directory")
    parser.add_argument("--output-dir", default="market-trends-output")
    parser.add_argument("--min-group", type=int, default=12)
    parser.add_argument("--min-days", type=int, default=2)
    parser.add_argument("--min-daily", type=int, default=3)
    args = parser.parse_args()

    vehicles = pd.read_parquet(args.input)
    daily, coverage, diagnostics = build_market_trends(
        vehicles, args.min_group, args.min_days, args.min_daily
    )
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    daily.to_csv(output / "daily_trends.csv", index=False)
    coverage.to_csv(output / "group_coverage.csv", index=False)
    (output / "diagnostics.json").write_text(
        json.dumps(diagnostics, indent=2), encoding="utf-8"
    )
    write_viewer(daily, output / "index.html")
    print(json.dumps(diagnostics, indent=2))


if __name__ == "__main__":
    main()
