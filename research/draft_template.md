# SmartDistServe: a reproducible simulation study of slack, duration, and aging in disaggregated LLM serving

Research prototype draft, 13 October 2026. **All evaluated workloads are synthetic. All service coefficients are uncalibrated assumptions. No GPU inference or actual benchmark dataset was used.** This workspace contained no existing draft, so this document establishes the draft and replaces its results section programmatically with measured experiment output.

## Abstract

SmartDistServe studies how queued-request ordering changes latency, joint SLO success, and fairness in a simplified disaggregated serving model. It compares phase-local FCFS, estimated SJF, EDF, and a heuristic combining normalized slack, estimated duration, and queue aging. The artifact supplies deterministic event processing, application-inspired synthetic workload profiles, paired seeded experiments, serialized traces and request outcomes, independent metric auditing, and replay. The measured results below determine the conclusions; no throughput gains from another paper or a physical serving system are attributed to this prototype. The study evaluates an integration of established scheduling ideas, not an established novel scheduling algorithm.

## Motivation and relation to DistServe

[DistServe (Zhong et al., OSDI 2024)](https://www.usenix.org/system/files/osdi24-zhong-yinmin.pdf) separates prefill and decoding onto different GPUs, uses FCFS runtime ordering with queue/load-based routing, and optimizes placement and resource allocation. Its runtime section discusses convoy effects and complementary scheduling changes. SmartDistServe adopts separate phase resources, first-token generation during prefill, and a simplified shortest-queue/least-occupancy FCFS reference. It does not implement DistServe's placement optimizer, tensor/pipeline parallelism, CUDA kernels, KV memory manager, or engine. Comparing policies here does not measure improvement over the published DistServe system.

## Previous scheduling work and scope of the contribution

Priority, short-job scheduling, deadline ordering, and aging are established techniques. The following primary sources further rule out claiming that output-length estimates or differentiated SLO priorities are new to LLM serving:

- [Qiu et al., Efficient Interactive LLM Serving with Proxy Model-based Sequence Length Prediction (2024)](https://arxiv.org/abs/2404.08509) uses a proxy predictor for speculative SJF.
- [Fu et al., Efficient LLM Scheduling by Learning to Rank (2024)](https://arxiv.org/abs/2408.15792) predicts relative output-length ranks for scheduling.
- [Sun et al., Llumnix (OSDI 2024)](https://www.usenix.org/conference/osdi24/presentation/sun-biao) supports runtime rescheduling, differentiated priorities, and SLOs across instances.
- [Huang et al., SLO-Aware Scheduling for Large Language Model Inferences (2025)](https://arxiv.org/abs/2504.14966) considers request SLOs, input lengths, and possible output lengths when choosing priority order.
- [Wu et al., FastServe (NSDI 2026)](https://www.usenix.org/conference/nsdi26/presentation/wu-bingyang) uses token-level preemption and a skip-join feedback scheduler. This prototype does not reproduce its preemption or offload machinery.

The contribution is an inspectable experimental artifact combining these ideas with explicit disaggregated queues and fairness diagnostics. Its particular score is a study heuristic, with no proof of optimality or literature-backed novelty claim. Experiments compare only FCFS, estimated SJF, and EDF, not implementations of the related systems above. Establishing a stronger contribution would require calibrated inference measurements, actual traces, stronger scheduling baselines, and a broader literature review.

## Model and policies

Two prefill GPUs and one decode GPU are provisioned in the reference configuration. A request routes at arrival to the prefill GPU with the smallest number of queued plus running requests; ties use GPU ID. Each GPU processes one prefill at a time, nonpreemptively. Prefill completion emits token 1. The modeled KV transfer then completes independently, with no shared-link contention. A request routes to the decode GPU with the fewest active plus queued requests. Decode admits requests between iterations into at most 16 active slots and generates one token per active request per iteration. An admitted request keeps its slot until completion; priority only changes admission. At coincident timestamps, completions release resources before transfers and arrivals route, and all events are processed before dispatch. All policies share routing, batching, hardware, SLOs, and realized traces. They do not drop requests or cancel requests with expired deadlines.

For prompt length L, current batch B, and maximum active context C:

```text
prefill(L) = 0.005 + L/8000 + 0.01*(L/4096)^2          seconds
transfer(L) = 0.002 + L*131072/25000000000             seconds
decode_step(B,C) = 0.012 + 0.0006*(B-1) + 0.00000025*C seconds
```

These functions are deliberately simple synthetic cost assumptions. GPU counts mean one abstract worker per GPU; model parallelism and model-fit feasibility are not represented.

FCFS orders by phase enqueue time. Estimated SJF orders by estimated service for the phase (prefill duration or predicted remaining decode duration). EDF orders by the phase deadline. Prefill deadline is arrival plus TTFT SLO. Decode uses a proxy completion deadline `first_token + max(1, estimated_output_tokens-1)*TPOT_SLO`; exact output length is unknown to the scheduler, so this is not an oracle EDF or a guarantee of TPOT success.

Let e be phase enqueue time, d the phase deadline, s the estimated remaining phase service, D the estimated duration (prefill + transfer + decode before prefill, remaining decode before decode admission), and b the phase SLO budget. At time t, Smart selects the smallest score:

```text
slack = d - t - s
score = (slack + 0.1*D - 0.2*(t-e)) / b
```

Each score normalizes by its request's budget: TTFT SLO for prefill, estimated post-first-token count times TPOT SLO for decode. Negative slack remains eligible and can get high priority. Before scoring, any request waiting at least five seconds is promoted; the oldest eligible request wins. Ties use enqueue time then request ID. This aging rule gives eventual admission with bounded service and a finite number of older requests, but it provides no fixed waiting-time bound under overload and cannot interrupt long running prefill or decode requests. SJF and EDF do not receive aging; the ablation removes it from Smart to expose that difference.

## Workloads and estimates

ShareGPT-inspired chat, HumanEval-inspired code, and LongBench-inspired long-context profiles are **generated distributions**, not samples from these datasets. No data download, tokenizer, or benchmark evaluation occurred. Input/output lengths are independent rounded, clipped lognormal samples; configured means are pre-clipping means. Default `(input mean, output mean, TTFT SLO seconds, TPOT SLO seconds)` are `(755,200,1.5,0.08)`, `(171,98,0.35,0.10)`, and `(8192,91,8.0,0.06)`. The long profile is intentionally a long-context scenario, not DistServe's context-capped LongBench workload. Distribution widths, bounds, and SLOs are configurable in `configs/experiment.json`.

Prefill estimates use known input length and the cost model, multiplied by mean-one lognormal noise with sigma 0.3. Output estimates use only the profile mean and independently sampled lognormal noise, not realized output tokens. Therefore sigma zero gives exact modeled prefill and a profile output prior, not perfect output-length prediction. No learned predictor is implemented or claimed. Separate arrival, length, and estimate random streams preserve realized arrivals and lengths across predictor-noise ablations.

Arrivals follow a Poisson process unless the burst ablation enables a periodic two-level rate via thinning. Its low/high rates are normalized to the configured average over a full period. The main grid uses four rates per profile and mixed workload. Mixed request probabilities are 50% chat, 25% code, and 25% long-context. Each run accepts arrivals for 90 simulated seconds. Only arrivals in `[15,90)` enter the measured cohort; the first 15 seconds warm up queues, and every arrival is fully drained afterward. The measurement is transient and finite, especially at overloaded rates. Five seeds are shared across all policies. Ablations at mixed rate 3 req/s remove aging, remove the duration term, use a profile prior without extra noise, increase noise, enable bursts, and slow KV transfer. No parameters were selected to force a desired outcome.

## Metric definitions

- TTFT = first-token timestamp minus arrival, including prefill queue wait.
- TPOT = `(completion-first_token)/(output_tokens-1)`, including transfer and decode admission wait. One-token requests have undefined TPOT, omitted from TPOT averages and treated as satisfying the TPOT constraint. Max observed token gap is retained because average TPOT can hide a long initial decode stall.
- Joint SLO attainment = fraction of cohort requests satisfying both TTFT and average TPOT limits, with a `1e-12`-second numerical boundary tolerance.
- Cohort per-GPU goodput = joint successes divided by `(90-15)` seconds and all provisioned GPUs. It counts successes for cohort arrivals even if they finish during drain. It is neither token throughput nor steady-state maximum sustainable rate.
- Waiting = prefill queue wait plus decode admission wait. Transfer and active service are excluded; P95 uses linear interpolation.
- Fairness = Jain index over per-profile and fixed prompt-size-bin joint SLO attainment rates. Prompt bins are `<=512`, `513..2048`, and `>2048`; empty bins are omitted. All-zero group attainment maps to zero. Single populated-group Jain equals one and cannot establish fairness; differing per-group SLOs also limit interpretation. Per-group counts, waiting tails, max wait, and P95 size-normalized slowdown supplement the index.
- Slowdown uses end-to-end latency divided by this model's isolated request service; it is a diagnostic, not a tenant service-share guarantee.

{{MEASURED_RESULTS}}

## Limitations and interpretation

The numerical results are conditional on the stated synthetic distributions, arbitrary cost model, SLOs, GPU allocation, batch limit, and heuristic weights. They do not estimate physical GPU throughput, DistServe speedup, dataset fidelity, energy, cost, or production viability. There is no KV capacity limit, memory fragmentation, swap, preemption, prefix reuse, speculative decoding, transfer contention, pipeline/tensor communication, admission rejection, model quality, tokenization, hardware variance, or scheduler computation overhead. Active decode and prefill work cannot be displaced. Shared local queues can cause routing imbalance; queue length is not remaining work. CPU runtime is not converted to simulated scheduling overhead.

The workload has no tenants beyond application groups, no correlated input/output lengths, and no learned estimates. Five seeds yield broad uncertainty for some cases. No confidence interval represents cost-model uncertainty. The suite is a fixed finite grid; capacity diagnostics do not locate the exact saturation boundary, and complete draining is not a substitute for long steady-state runs. Fairness indices of SLO outcomes differ from resource fairness and can rise even when all groups perform poorly. The reference reports absolute SLO rates and group details so this cannot be hidden by a single index.

Results establish only how the implemented policies behave within this simulator. Scheduling can change which requests meet their SLOs and can trade aggregate success against tail wait or group outcomes. The tables include regressions and ties. A claim that Smart always outperforms FCFS, SJF, or EDF is unsupported. The next research steps are measured service profiling, licensed trace acquisition with tokenizer provenance, learned or rank-based estimate evaluation, strong SLO/fair scheduling baselines, explicit memory and link models, load-duration sensitivity, and eventual GPU validation.

## Reproducibility and review

The README supplies commands for tests, experiments, plots, independent audit, and exact metric replay. `manifest.json` records configuration, seeds, trace hashes, numeric output hashes, source hashes, Python version, and platform. `requests.csv.gz` contains per-request outcomes; `traces.jsonl.gz` contains complete input traces. `summary.csv` and `paired_contrasts.json` retain seed uncertainty. Graphs are generated only from measured JSON. `research/REVIEW.md` records the final code and result review, discovered issues, fixes, and checks actually executed. Passing these checks supports internal consistency, not real-world validity.
