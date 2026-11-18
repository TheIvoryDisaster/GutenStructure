# Cost assumptions

Initial sample (2026-11-16): 67 RivalryCore CI runs over about three days; no retained Actions artifacts there. One six-platform MeitouClient package set totals about 0.38 GB. This is not an Azure billing measurement.

At 0.4 GB per uploaded build and three-day retention, average retained GB is `builds/day * 0.4 * 3`. East US Hot LRS retail capacity was $0.0208/GB-month at inspection: two builds/day costs about $0.05/month; 25 costs $0.62; 100 costs $2.50, before transactions, downloads, lifecycle delays and other workloads.

Internet egress can dominate. 25 sets/day downloaded once is about 300 GB/month. At $0.087/GB after the first 100 GB allowance, that is about $17.40, assuming the allowance is available. Check current rates and subscription usage before rollout.

Target $20/month for incremental Meitou Azure usage, with initial storage/transaction planning allowance of $1–$5 for selective downloads. Other projects share the existing account. Budget alerts notify; they do not cap spending. Short retention does not cap upload or download volume. Keep public distribution on GitHub Releases where suitable.

Standard hosted runner compute for public GitHub repositories is free; larger runners, artifacts and caches have separate billing rules. Use Azure compute only after a workload-specific estimate.

Sources: https://azure.microsoft.com/en-us/pricing/details/storage/blobs/ ; https://azure.microsoft.com/en-us/pricing/details/bandwidth/ ; https://docs.github.com/en/actions/concepts/billing-and-usage
