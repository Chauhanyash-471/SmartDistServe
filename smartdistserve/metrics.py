"""Explicit cohort metrics; no censored tail or omitted failed requests."""
import math
from statistics import mean


def percentile(values, q):
    """Linear interpolation between ordered samples (inclusive endpoints)."""
    if not 0 <= q <= 1:
        raise ValueError("quantile must be in [0, 1]")
    if not values:
        return None
    x = sorted(values)
    index = (len(x) - 1) * q
    lo = math.floor(index)
    return x[lo] + (x[math.ceil(index)] - x[lo]) * (index - lo)


def jain(values):
    """Jain index; zero if all groups receive zero success, None if no groups."""
    if not values:
        return None
    denominator = len(values) * sum(x * x for x in values)
    return sum(values) ** 2 / denominator if denominator else 0.0


def evaluate(result, hardware, *, start, stop):
    if not math.isfinite(start) or not math.isfinite(stop) or start < 0 or stop <= start:
        raise ValueError("invalid measurement interval")
    cohort = [s for s in result.records if start <= s.request.arrival < stop]
    n = len(cohort)
    base = {"requests": n, "measurement_seconds": stop - start,
            "total_requests": len(result.records), "simulation_end_s": result.end_time,
            "drain_seconds": max(0.0, result.end_time - stop),
            "max_prefill_queue": result.max_prefill_queue,
            "max_decode_queue": result.max_decode_queue,
            "events_processed": result.events_processed}
    names = ("ttft_mean_s", "ttft_p95_s", "tpot_mean_s", "tpot_p95_s",
             "waiting_p95_s", "waiting_max_s", "slo_attainment", "ttft_attainment",
             "tpot_attainment", "goodput_per_gpu", "arrival_rate", "jain_profile_slo",
             "jain_length_slo", "slowdown_p95", "max_token_gap_p95_s")
    if not n:
        return {**base, **dict.fromkeys(names), "profile_metrics": {}, "length_metrics": {}}
    ttft = [s.ttft for s in cohort]
    tpot = [s.tpot for s in cohort if s.tpot is not None]
    waiting = [s.waiting for s in cohort]
    success = sum(s.slo_met for s in cohort)
    groups = {}
    for s in cohort:
        groups.setdefault(s.request.profile, []).append(s)
    profile_metrics = {
        name: {"requests": len(records), "slo_attainment": mean(s.slo_met for s in records),
               "waiting_p95_s": percentile([s.waiting for s in records], 0.95)}
        for name, records in sorted(groups.items())}
    # Fixed, a priori prompt size bins; no policy-dependent outcomes define groups.
    length_groups = {"short_<=512": [], "medium_513_2048": [], "long_>2048": []}
    for s in cohort:
        tokens = s.request.input_tokens
        group = "short_<=512" if tokens <= 512 else ("medium_513_2048" if tokens <= 2048 else "long_>2048")
        length_groups[group].append(s)
    length_metrics = {name: {"requests": len(records),
                             "slo_attainment": mean(s.slo_met for s in records),
                             "waiting_p95_s": percentile([s.waiting for s in records], .95)}
                      for name, records in length_groups.items() if records}
    slowdowns = []
    for s in cohort:
        r = s.request
        # Size-normalized latency diagnostic against isolated service on this model.
        isolated = hardware.prefill_time(r.input_tokens)
        if r.output_tokens > 1:
            isolated += hardware.transfer_time(r.input_tokens)
            isolated += sum(hardware.decode_step(1, r.input_tokens + k)
                            for k in range(1, r.output_tokens))
        slowdowns.append((s.completion - r.arrival) / isolated)
    return {**base, "ttft_mean_s": mean(ttft), "ttft_p95_s": percentile(ttft, .95),
            "tpot_mean_s": mean(tpot) if tpot else None, "tpot_p95_s": percentile(tpot, .95),
            "waiting_p95_s": percentile(waiting, .95), "waiting_max_s": max(waiting),
            "slo_attainment": success / n,
            "ttft_attainment": mean(s.ttft <= s.request.ttft_slo + 1e-12 for s in cohort),
            # Requests with one output token satisfy the TPOT SLO vacuously.
            "tpot_attainment": mean(s.tpot is None or s.tpot <= s.request.tpot_slo + 1e-12 for s in cohort),
            "goodput_per_gpu": success / ((stop - start) * hardware.gpus),
            "arrival_rate": n / (stop - start),
            "jain_profile_slo": jain([m["slo_attainment"] for m in profile_metrics.values()]),
            "jain_length_slo": jain([m["slo_attainment"] for m in length_metrics.values()]),
            "slowdown_p95": percentile(slowdowns, .95),
            "max_token_gap_p95_s": percentile([s.max_token_gap for s in cohort], .95),
            "profile_metrics": profile_metrics, "length_metrics": length_metrics}
