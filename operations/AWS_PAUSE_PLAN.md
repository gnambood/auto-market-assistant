# AWS cost reduction: reversible pause plan

**Status: NOT EXECUTED.** The reviewed source records one ECS Express Mode/Fargate service with 1 vCPU, 4 GiB RAM, minimum/maximum 1 running task; private S3 artifacts, ECR images, managed HTTPS ingress, and CloudWatch are additional possible costs. The user's connected AWS resource inventory and current bill **have not been verified**. No live AWS changes should be made until the full application and static fallback are tested.

## Lowest-cost viable portfolio configuration

1. Keep the GitHub Pages case study and precomputed, verified examples. Label the fallback **Offline example**, not live inference.
2. Run Docker and full model/RAG evaluation on demand, on a developer machine; keep trained artifacts in backed-up, versioned storage.
3. Do not permanently host the 4 GiB ECS task solely for an occasional portfolio visitor.
4. Re-enable live AWS inference only when a specific demonstration, experiment or usage requirement justifies ongoing charges.

GitHub Pages serves static assets, not arbitrary FastAPI/FAISS inference. The demo must be honest about that distinction.

## Inventory before any pause

Read actual daily charges and resources before acting:

- Cost Explorer by **service, region and day**: Fargate/ECS, Elastic Load Balancing, VPC/public IPv4/NAT, CloudWatch, ECR, S3, Athena, Glue, data transfer and taxes.
- ECS Express Mode service, managed tasks/cluster, capacity, ingress and associated target groups/load balancers.
- Public IPv4 addresses, NAT gateways, network interfaces and CloudWatch log groups.
- S3 buckets, versioning, prefixes, object counts and size; ECR repositories/image digests and lifecycle settings.
- The active deployment workflow in the **original portfolio repo** `gnambood/gnambood.github.io/.github/workflows/auto-market-deploy.yml`. The copy in this standalone repo under `deploy/workflows/` is intentionally inactive.
- CloudFormation stacks and every dependency that might be shared by another application.

Do not assume that scaling an ECS task count to zero stops load balancer, public IP, storage or log charges.

## Safe sequence after validation

1. Run **all** repository tests, compare inference behavior with saved reference examples, confirm the alternative/offline web experience works, and validate model/review artifact backups.
2. Save an infrastructure inventory: service JSON/config, AWS region/account reference, container image digest, required environment-variable names, non-secret artifact locations and a restoration checklist. Never publish credentials or sensitive identifiers.
3. Disable automatic AWS deployment triggers or remove deployment authority **only after** identifying the correct source workflow and ensuring an intentional relaunch remains possible.
4. Prefer a non-destructive service pause **if supported by the actual Express Mode configuration**. Verify resulting task count and managed ingress separately. If the cloud service still incurs unavoidable ingress charges, present a **separate approval request** for deleting only the disposable serving infrastructure. Do not delete S3 data, model artifacts, the Athena catalog or historic research evidence as part of a pause.
5. Test the static portfolio from outside AWS once live inference is unavailable. Confirm user-facing messaging does not falsely imply live predictions.
6. Verify after the pause: no running compute, orphaned load balancers/NAT/public IPv4, unexpected deployment triggers or increasing service charges. Cost Explorer can lag.
7. Retain the backup and a tested restoration command/runbook for the next demonstration.

### Stop conditions

Do not pause if the full integration tests fail, the static demo is misleading or broken, critical model/source artifacts lack backup, resource ownership is uncertain, or the only available action would delete shared infrastructure.

## Which option to pick

| Option | Ongoing cost | Limitations |
| --- | --- | --- |
| GitHub Pages + static validated demo | Very low incremental hosting cost | No live personalized inference |
| Local Docker on demand | No AWS compute/ALB cost | Public visitors cannot invoke it |
| ECS tasks at zero (if supported) | Task compute can stop | Managed ingress, networking and storage may remain billable |
| Remove disposable ECS serving resources after review | Retained S3/ECR/cloud logs still cost money | Requires explicit destructive-action approval and recovery evidence |
| On-demand instance | Compute can stop when unused | EBS and public IPv4 may still cost money; security and patching burden |

No actual monthly saving is quoted until Cost Explorer exposes the current invoice/usage.

References: [ECS Express Mode](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-overview.html), [Fargate pricing](https://aws.amazon.com/fargate/pricing/), [S3 pricing](https://aws.amazon.com/s3/pricing/).
