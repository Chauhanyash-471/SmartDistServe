# SmartDistServe code and results review

Completed 13 October 2026. Assessment: **share as a synthetic simulation prototype with the stated caveats**. This is a self-review supported by analytical tests, independently implemented metric auditing, and exact trace replay; it is not external peer review or GPU validation.

## Scope and findings

Reviewed event ordering, phase resource ownership, routing, continuous batch admission, estimator inputs, fairness mechanisms, validation, statistical aggregation, artifact provenance, README commands, draft claims, and all six rendered figures.

Two correctness issues were found and fixed before delivery:

1. CLI defaults initially overwrote explicitly supplied JSON workload values. Options now override the config only when passed; a regression test checks config duration/seed and explicit rate precedence.
2. Coincident completion and arrival/transfer events could route against stale occupancy because insertion order determined which event ran first. Completion events now release resources before transfer/arrival routing. Regression tests cover both prefill and decode. The full suite was rerun after this fix. All four numerical/input output files retained their original SHA-256 hashes, because the correction did not affect the reference stochastic traces.

The scheduler candidate interface excludes realized output length and future completion. Generated estimates use known input length and a profile prior. Actual output length is used by the environment to terminate generation and by the evaluator after completion. Predictor-noise ablations preserve arrivals and realized lengths through separate random streams. All policies share routing, hardware, batch limit, SLOs, and traces within each condition. No policy drops expired requests.

The simulator drains every accepted request, including overloaded cases. Analytical tests validate first-token generation, transfer placement, token-count denominators, batch boundaries, parallel workers, nonpreemption, resource independence, and simultaneous-event conventions. Aging is tested with a competing backlog, with the guarantee restricted to eventual admission under bounded service and finite older backlog.

Inputs use finite numeric validation, positive lengths, valid bounds, unique IDs/seeds/conditions, and explicit empirical provenance requirements. Local CSV/JSON import does not execute input code. There are no serving endpoints, credentials, model downloads, network calls, or external message sends in the prototype. Queue selection scans local queues and removes selected elements linearly; scaling to very large backlogs can be quadratic. This CPU overhead is not charged to simulated latency, and that omission is documented.

## Executed validation

| Check | Observed outcome |
|---|---|
| `python -m unittest discover -s tests -v` | 38 tests passed on the final simulator |
| Reference experiment suite | 440 policy runs, 110 synthetic traces, five seeds |
| Independent serialized-timeline audit | 1,505,479 checks, zero failures, 149,400 request rows |
| Full corrected-suite trace replay | All 440 runs reproduced exact metrics |
| Small-suite byte reproducibility test | Numeric JSON/CSV, trace gzip, request gzip, and summary CSV matched across reruns |
| Post-event-order correction rerun | Numeric/input output hashes matched the first complete run |
| Figure generation | Six PNGs and six PDFs generated from measured JSON |
| Figure visual review | All six PNGs inspected; readable labels/legends, consistent policy colors, zero baselines, synthetic/uncalibrated labels, seed uncertainty shown |

Evidence is retained in `results/reference/audit.json`, `replay.json`, `tests.log`, `manifest.json`, `experiment.log`, `replay.log`, and `plot_environment.json`. Exact plotting dependencies are pinned in `requirements-plots.txt`. The installer initially stalled downloading a replacement NumPy; the final plotting environment uses bundled NumPy/Pillow and installed Matplotlib dependencies. This changed no simulation results.

The independent audit does not call the simulator's metric evaluator. It recomputes TTFT, TPOT, joint and individual SLO attainment, queue waiting, goodput denominators, percentiles, group rates/Jain indices, and isolated-service slowdown from serialized timestamps and input traces. It also checks input identity, completion counts, source/output/trace hashes, prefill service, transfer duration, worker overlap, cohort inclusion, and policy coverage. Replay uses the simulator and provides a separate determinism check, not an independent proof of its physical model.

## Results and claim review

Smart has higher mean SLO attainment than FCFS in four of sixteen main conditions, lower attainment in four, and ties in eight. Paired differences range from -1.382 to +3.899 percentage points. These counts describe means and are not a significance claim. All conditions, including regressions, are printed in the draft.

At mixed rate 6 req/s, mean SLO attainment is 9.55% (FCFS), 13.45% (Smart), 55.30% (estimated SJF), and 25.64% (EDF). Mean run P95 queue wait is 28.709, 28.096, 61.711, and 30.222 seconds respectively. SJF's attainment gain comes with substantially higher waiting tails in this case. Removing Smart's duration term at mixed rate 3 raises mean attainment from 90.41% to 91.52%; the draft explicitly reports this unfavorable component result and avoids claiming a general benefit.

Student t intervals are computed on independent seed-level metrics, with paired contrasts sharing seeds/traces. Percentiles are averaged across runs, not pooled. Some unconstrained t interval bounds extend beyond natural metric ranges; figures use zero-baseline axes and full numeric bounds remain available in the summaries. Five seeds and uncorrected multiple comparisons warrant cautious interpretation. No claims of hardware-model uncertainty coverage or universal improvement are made.

Jain indices describe SLO outcome parity across application groups or fixed prompt bins. They do not prove tenant resource fairness. Empty bins are omitted, one-group values are uninformative, and all-zero success maps to zero. Group counts/rates, waiting tails, and slowdown remain inspectable. Cohort goodput counts fully drained successes per arrival-window second and all GPUs; the separately labeled tested-grid capacity diagnostic is not a steady-state saturation measurement. All policies have the same conservative qualified grid rate for each profile in this evaluation.

The draft cites primary prior work on DistServe, proxy SJF, learning-to-rank scheduling, Llumnix priorities, multi-SLO scheduling, and FastServe preemption. It describes this artifact as an integration and evaluation of established ideas, with no established algorithmic novelty. No previous system's measured speedup is attributed to SmartDistServe.

## Required interpretation limits

All evaluated workloads are synthetic application-inspired distributions, not actual ShareGPT, HumanEval, or LongBench data. Service times and GPU allocation are assumed rather than profiled. The model excludes KV capacity, shared-link contention, preemption/offload, placement/parallelism optimization, prefix reuse, scheduler overhead, model quality, and physical inference. Output estimates are profile priors, not a trained predictor. Overloaded finite runs with full drain do not establish sustainable production rates. These caveats are stated in both the README and draft.

No unresolved correctness defect was identified within the reviewed and tested model. Calibrated GPU measurements, verified empirical traces, stronger scheduling baselines, longer-run sensitivity, and external peer review remain research work beyond this delivered prototype.
