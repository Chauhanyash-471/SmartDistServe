# Exact synthetic data used by SmartDistServe

No actual ShareGPT, HumanEval, or LongBench datasets were obtained or used.
These files contain generated token-length requests inspired by chat, code,
and long-context applications. They contain no actual prompts or answers.

- all_synthetic_requests.csv: all 37,350 input request instances across the 110 stored condition/seed trace instances.
- sharegpt_synthetic.csv: chat-profile input instances.
- humaneval_synthetic.csv: code-profile input instances.
- longbench_synthetic.csv: long-context input instances.
- all_policy_outcomes.csv: all 149,400 saved request outcomes from four policies, including warmup requests and failures.
- DATA_INDEX.json: counts, provenance, file sizes, and SHA-256 hashes.

The uncompressed outcome CSV is exported locally and included in the full ZIP
bundle. Git tracks its exact compressed original at
results/reference/requests.csv.gz to avoid a redundant large text file.
Run python output/package/build_bundle.py to recreate all CSV exports.

The three profile CSVs partition all_synthetic_requests.csv; they are not additional data.
Each input request has a composite identity (trace_id, request_id). Each outcome
has identity (trace_id, policy, request_id). Some trace instances deliberately
reuse the same realization for paired ablations; 110 stored instances have 95
distinct hashes when estimates are included. Do not treat repeated realizations
or the four policy outcomes as independent experimental samples.

Input fields include arrival time (seconds), input/output token counts,
request-specific TTFT/TPOT SLOs (seconds), prefill-duration estimates (seconds),
and output-token estimates. The scheduler does not receive realized output length.
The CSVs preserve the exact saved input values; workload definitions and all
random seeds are in configs/experiment.json and results/reference/manifest.json.
The original replayable inputs are results/reference/traces.jsonl.gz.

For importing one selected trace with the CLI, filter all_synthetic_requests.csv
to one trace_id first. Importing all traces as a single run is invalid because
request IDs and clocks reset for each experiment.
