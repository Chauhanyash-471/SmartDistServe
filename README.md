# SmartDistServe

A Python research prototype for **reproducible discrete-event simulation** of scheduling in a disaggregated prefill/decode system inspired by [DistServe, OSDI 2024](https://www.usenix.org/system/files/osdi24-zhong-yinmin.pdf). This is a simulator, not a GPU inference engine. All bundled workloads are **synthetic** and all service-time coefficients are **uncalibrated assumptions**.

It implements FCFS, estimated shortest-job-first (SJF), earliest-deadline-first (EDF), and a TTFT/decode-slack priority heuristic with estimated durations, soft aging, and an oldest-first promotion threshold. Policies use the same GPU budget, routing, continuous decode batches, and request traces. The artifact measures TTFT, TPOT, joint SLO success, cohort goodput per GPU, P95 queue wait, prompt-bin/application fairness, and slowdown.

The reference evaluation is complete: 38 passing tests, 440 experiment runs, exact replay of all 440 runs, an independent audit of 149,400 request outcomes, and six PNG/PDF figures. Smart beats FCFS in mean SLO attainment in 4 of 16 main conditions, loses in 4, and ties in 8. See [the measured draft](research/SmartDistServe.md), [review record](research/REVIEW.md), and [SLO graph](results/reference/figures/slo_attainment.png).

The formal [research paper PDF](output/pdf/SmartDistServe_Research_Paper.pdf) and [synthetic dataset guide](data/synthetic/README.md) are included. The Git repository retains all original input traces and request outcomes in compressed form. The full code-and-data bundle additionally includes the uncompressed outcome CSV; it can be rebuilt with `python output/package/build_bundle.py`.

## Quick start

Python 3.11+ is required. The simulator, tests, experiment runner, reports, and audits use only the standard library. Plot generation needs Matplotlib. From the repository root:

```powershell
python -m unittest discover -s tests -v
python -m smartdistserve run --policy smart --profile mixed --rate 3 --seed 11
python -m smartdistserve experiment --config configs/experiment.json --output results/reference
python -m smartdistserve report --results results/reference --draft research/SmartDistServe.md
python scripts/audit_results.py --results results/reference
python scripts/replay_results.py --results results/reference
```

For plots, create an environment and install the pinned plotting dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-plots.txt
.\.venv\Scripts\python.exe scripts/plot_results.py --results results/reference
```

On Linux/macOS use `.venv/bin/python`. An editable installation (`python -m pip install -e .`) is optional; commands above run from the source checkout. Tests and experiments were executed with the runtime recorded in the saved manifest. Matplotlib/PDF rendering can differ across font/OS versions; replay checks numerical metrics rather than image bytes. Gzip inputs and request logs omit timestamps and filename metadata for deterministic bytes.

## Workloads and configuration

`configs/experiment.json` contains all distribution parameters, SLOs, workload mixes, rates, seeds, and ablations. The default reference suite runs **440 policy runs on 110 traces**: 320 main runs across three profiles plus a mix, and 120 ablation runs. Each run accepts arrivals for 90 seconds, excludes arrivals before 15 seconds from metrics, and drains all requests after arrivals stop.

| Synthetic profile | Input mean before clipping | Output mean before clipping | TTFT SLO s | TPOT SLO s |
|---|---:|---:|---:|---:|
| ShareGPT-inspired chat | 755 | 200 | 1.5 | 0.08 |
| HumanEval-inspired code | 171 | 98 | 0.35 | 0.10 |
| LongBench-inspired long context | 8192 | 91 | 8 | 0.06 |

These are application-inspired independent clipped lognormal distributions, not actual benchmark traces or fitted empirical distributions. There is no tokenizer or model-quality benchmark evaluation. The long-context profile differs from DistServe's capped LongBench setup. Arrivals are Poisson; an optional periodic burst multiplier uses a thinned nonhomogeneous Poisson process. The mixed profile samples 50% chat, 25% code, and 25% long-context requests.

Hardware defaults are two prefill workers and one decode worker, one abstract GPU each; decode batch limit is 16. The model functions and coefficients are in `smartdistserve/config.py`. Override individual `hardware`, `scheduler`, `workload`, or complete named `profiles` entries in JSON and pass `--config` to `run`. Explicit command-line options override config values. For example:

```powershell
python -m smartdistserve run --config configs/experiment.json --policy edf --profile longbench --rate 2 --duration 120 --warmup 20 --output results/long-edf
```

For empirical token-length data, import CSV with all fields from `Request` in `smartdistserve/workloads.py`: `request_id,arrival,profile,input_tokens,output_tokens,ttft_slo,tpot_slo,estimated_prefill,estimated_output_tokens`. Supply estimates without using future realized output lengths. Use:

```powershell
python -m smartdistserve run --trace my_trace.csv --source empirical --provenance "Dataset source; tokenizer/version; collection method; predictor method" --duration 120 --warmup 0
```

The tool records the supplied provenance and label; it cannot verify your source or that supplied estimates avoid leakage. No empirical data has been obtained for the bundled evaluation. IDs must be unique, arrivals nonnegative and inside the duration, lengths positive integers, and SLOs/service estimates finite and positive. A one-output-token request is supported.

## Scheduling and model semantics

Requests route to the prefill worker with the fewest queued plus running requests. Prefill is nonpreemptive and generates token 1. KV transfer is a fixed latency plus prompt-size/bandwidth cost. After transfer, a request routes to the least-occupied decode worker. New requests join continuous decode batches only at iteration boundaries; active requests retain their slot until completion. At coincident timestamps, completions release resources before transfers and arrivals route; all events are processed before dispatch. Ties use worker/request IDs. Schedulers reorder local queued work and decode admissions only.

SJF uses estimated phase service. EDF uses the absolute TTFT deadline before prefill, and a predicted completion deadline before decode admission. For the Smart heuristic, lower score wins:

```text
score = (deadline - now - estimated_phase_service
         + duration_weight*estimated_duration - aging_rate*phase_wait) / phase_SLO_budget
```

Default duration weight is 0.1, aging rate is 0.2, and starvation threshold is five seconds. A request that reaches the threshold is promoted ahead of younger work; oldest promoted work wins. Aging ensures eventual admission under bounded service and finite older backlog, without a fixed latency bound under overload. Negative-slack requests are still served. Prefill uses TTFT slack. Decode uses `first_token + max(1,estimated_output_tokens-1)*TPOT_SLO` as its proxy deadline, since the actual remaining output length is unknown.

Prefill estimates use known prompt length with mean-one lognormal noise. Output estimates use the profile mean and independent lognormal noise. They never read realized output length. Sigma zero means exact modeled prefill plus a profile output prior, not oracle output estimates. Separate RNG streams make predictor-noise ablations preserve actual arrivals and lengths. There is no trained predictor. The ablations remove aging/duration, vary estimate noise, add bursts, and slow transfer.

## Metrics and interpretation

TTFT includes prefill queuing and ends at prefill completion. TPOT is `(completion-first_token)/(output_tokens-1)` and includes transfer plus decode queue delay. Single-token requests are omitted from TPOT means and satisfy that SLO vacuously. SLO attainment requires both request-specific limits. Waiting excludes transfer and active compute. P95 uses linear interpolation. Max token gap is also saved because mean TPOT can hide an initial stall.

**Cohort goodput/GPU** is successful cohort requests divided by the measurement interval and **all** provisioned GPUs. Fully drained outcomes count even when completion is after the arrival window. It is a finite-run cohort measure. The report separately computes the highest tested offered rate with at least 90% success in every seed divided by GPUs, labeled a conservative tested-grid diagnostic. Neither measure demonstrates steady-state capacity or published DistServe goodput.

Fairness uses Jain indices of application-group and fixed prompt-size-bin SLO success rates (`<=512`, `513..2048`, `>2048`). Empty bins are omitted; all-zero attainment gives zero; a single populated group gives one and is uninformative. Group counts, success rates, waiting tails, maximum wait, and size-normalized slowdown are retained. This measures outcome disparities, not a formal resource-share or tenant-fairness guarantee. See the draft for the complete limitations.

Seed means and 95% Student t intervals describe sampling variability (the built-in critical-value table supports up to 31 seeds). Paired contrasts compare identical traces by seed. Intervals do not quantify hardware-model uncertainty or correct for multiple comparisons. High-load results are transient overload studies. The entire main grid, ties, and regressions are retained.

## Artifact map

| Path | Purpose |
|---|---|
| `smartdistserve/` | Simulator, validated configs, policies, workload generation/import, CLI, metrics, experiment/report code |
| `tests/` | Analytical timing, policy/fairness, reproducibility, validation, CLI and artifact tests |
| `scripts/plot_results.py` | Six measured-result PNG and PDF graphs |
| `scripts/audit_results.py` | Independent metric recomputation, timelines, counts and hashes |
| `scripts/replay_results.py` | Re-run saved traces and compare every metric exactly |
| `results/reference/runs.json`, `runs.csv` | Per-seed policy metrics and group statistics |
| `results/reference/traces.jsonl.gz` | Complete synthetic inputs, seeds and trace hashes |
| `results/reference/requests.csv.gz` | All request outcomes, timestamps, cohort flags and SLO failures |
| `results/reference/manifest.json` | Config, environment, source/output hashes |
| `results/reference/summary.csv`, `paired_contrasts.json` | Seed means, confidence intervals and paired deltas |
| `results/reference/figures/` | Static graphs from measured JSON only |
| `research/SmartDistServe.md` | Research draft with automatically generated measured tables |
| `research/REVIEW.md` | Code/results review and completed validation evidence |

`python -m smartdistserve report` rebuilds the draft from `research/draft_template.md`; edit the template to preserve prose changes. Experiment output directories are overwritten on rerun; use a fresh `--output` for a new study. No network access is needed to reproduce simulation results.

## Research scope

Disaggregation is inherited from DistServe. Estimated SJF, SLO priorities, deadline ordering, and aging predate this artifact; related primary sources are cited in the draft. The contribution here is a reproducible, inspectable combination and its measured tradeoffs. No new optimal scheduling algorithm, reproduced GPU result, or universal gain is claimed. The simulator omits memory limits, preemption, link contention, parallelism/placement optimization, scheduler overhead, prefix caching, and physical inference. Real traces and calibrated GPU measurements remain future work.
