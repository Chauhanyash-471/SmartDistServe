from dataclasses import replace
import unittest

from smartdistserve.config import Hardware, SchedulerConfig, WorkloadConfig, default_profiles
from smartdistserve.metrics import evaluate, jain, percentile
from smartdistserve.reporting import METRICS, interval, summarize
from smartdistserve.scheduling import Candidate, POLICIES, select
from smartdistserve.simulator import simulate
from smartdistserve.workloads import Request, generate, trace_hash


def request(rid=0, arrival=0, tokens=1000, output=4, ttft=10, tpot=1, est=None):
    return Request(rid, arrival, "test", tokens, output, ttft, tpot,
                   tokens / 1000 if est is None else est, output)


def constant_hardware(**overrides):
    return Hardware(**{**dict(prefill_gpus=1, decode_gpus=1, decode_batch_size=2,
                              prefill_overhead=0, prefill_tokens_per_second=1000,
                              prefill_quadratic=0, decode_base=.1, decode_batch_increment=0,
                              decode_context_increment=0, transfer_latency=.2,
                              kv_bytes_per_token=0), **overrides})


class AnalyticalTimingTests(unittest.TestCase):
    def test_single_request_with_transfer(self):
        s = simulate([request()], constant_hardware()).records[0]
        self.assertAlmostEqual(s.first_token, 1)
        self.assertAlmostEqual(s.decode_ready, 1.2)
        self.assertAlmostEqual(s.completion, 1.5)
        self.assertAlmostEqual(s.tpot, .5 / 3)
        self.assertAlmostEqual(s.waiting, 0)
        self.assertAlmostEqual(s.max_token_gap, .3)

    def test_single_token_no_decode_or_transfer(self):
        result = simulate([request(output=1)], constant_hardware())
        s = result.records[0]
        self.assertEqual(s.completion, 1)
        self.assertIsNone(s.tpot)
        self.assertIsNone(s.decode_ready)
        self.assertEqual(result.decode_busy_seconds, [0])
        self.assertEqual(s.waiting, 0)

    def test_prefill_head_of_line_blocking(self):
        rs = [request(0, output=1), request(1, arrival=.1, tokens=100, output=1)]
        result = simulate(rs, constant_hardware())
        self.assertAlmostEqual(result.records[1].prefill_start, 1)
        self.assertAlmostEqual(result.records[1].ttft, 1)
        self.assertAlmostEqual(result.records[1].waiting, .9)

    def test_decode_batch_and_parallel_prefill(self):
        h = constant_hardware(prefill_gpus=2)
        result = simulate([request(0, output=3), request(1, output=3)], h)
        self.assertEqual([s.first_token for s in result.records], [1, 1])
        for s in result.records:
            self.assertAlmostEqual(s.completion, 1.4)
        self.assertAlmostEqual(result.decode_busy_seconds[0], .2)

    def test_arrival_during_decode_step_waits_for_boundary(self):
        h = constant_hardware(transfer_latency=0)
        rs = [request(0), request(1, arrival=1.2, tokens=50, output=2)]
        result = simulate(rs, h)
        self.assertAlmostEqual(result.records[1].first_token, 1.25)
        self.assertAlmostEqual(result.records[1].decode_start, 1.3)
        self.assertAlmostEqual(result.records[1].completion, 1.4)
        self.assertAlmostEqual(result.records[1].waiting, .05)

    def test_saturated_decode_admission_is_fcfs_by_ready_time(self):
        h = constant_hardware(decode_batch_size=1, transfer_latency=0)
        rs = [request(0, tokens=100, output=5), request(1, arrival=.01, tokens=100, output=2)]
        s = simulate(rs, h).records[1]
        self.assertAlmostEqual(s.decode_ready, .2)
        self.assertAlmostEqual(s.decode_start, .5)
        self.assertAlmostEqual(s.completion, .6)

    def test_all_coincident_arrivals_visible_before_dispatch(self):
        rs = [request(0, tokens=1000, output=1), request(1, tokens=10, output=1)]
        result = simulate(rs, constant_hardware(), "sjf")
        self.assertEqual(result.records[1].prefill_start, 0)
        self.assertAlmostEqual(result.records[0].prefill_start, .01)

    def test_multiple_decode_gpus(self):
        h = constant_hardware(prefill_gpus=2, decode_gpus=2, decode_batch_size=1)
        result = simulate([request(0), request(1)], h)
        self.assertEqual([s.decode_gpu for s in result.records], [0, 1])
        self.assertAlmostEqual(result.records[0].completion, result.records[1].completion)

    def test_coincident_prefill_completion_releases_before_arrival_routing(self):
        h = constant_hardware(prefill_gpus=2)
        rs = [request(0, tokens=1000, output=1), request(1, tokens=2000, output=1),
              request(2, arrival=.1, tokens=100, output=1),
              request(3, arrival=1, tokens=100, output=1)]
        result = simulate(rs, h)
        self.assertEqual(result.records[3].prefill_gpu, 0)
        self.assertAlmostEqual(result.records[3].prefill_start, 1.1)

    def test_coincident_decode_completion_releases_before_transfer_routing(self):
        h = constant_hardware(prefill_gpus=2, decode_gpus=2, decode_batch_size=1, transfer_latency=0)
        result = simulate([request(0, tokens=100, output=2), request(1, tokens=200, output=2)], h)
        self.assertEqual(result.records[1].decode_gpu, 0)
        self.assertAlmostEqual(result.records[1].decode_start, .2)

    def test_no_prefill_decode_resource_interference(self):
        h = constant_hardware(transfer_latency=0)
        rs = [request(0, tokens=100, output=5), request(1, arrival=.2, tokens=5000, output=1)]
        result = simulate(rs, h)
        self.assertAlmostEqual(result.records[0].completion, .5)
        self.assertAlmostEqual(result.records[1].completion, 5.2)

    def test_empty_trace(self):
        result = simulate([])
        self.assertEqual(result.end_time, 0)
        self.assertEqual(result.events_processed, 0)
        self.assertIsNone(evaluate(result, Hardware(), start=0, stop=1)["slo_attainment"])


class SchedulingTests(unittest.TestCase):
    def setUp(self):
        self.sc = SchedulerConfig(duration_weight=0, aging_rate=0, starvation_after=None)
        self.candidates = [Candidate(0, 0, 100, 10, 10, 100), Candidate(1, 1, 5, 2, 2, 5)]

    def test_fcfs_sjf_edf_smart(self):
        expected = {"fcfs": 0, "sjf": 1, "edf": 1, "smart": 1}
        for policy, rid in expected.items():
            self.assertEqual(select(self.candidates, 2, policy, self.sc), rid)

    def test_duration_estimates_affect_priority(self):
        cs = [Candidate(0, 0, 10, 1, 100, 10), Candidate(1, 0, 11, 1, 1, 10)]
        self.assertEqual(select(cs, 0, "smart", self.sc), 0)
        self.assertEqual(select(cs, 0, "smart", replace(self.sc, duration_weight=1)), 1)

    def test_soft_aging_changes_priority(self):
        cs = [Candidate(0, 0, 20, 1, 1, 10), Candidate(1, 9, 10, 1, 1, 10)]
        self.assertEqual(select(cs, 10, "smart", self.sc), 1)
        self.assertEqual(select(cs, 10, "smart", replace(self.sc, aging_rate=2)), 0)

    def test_hard_aging_and_fifo_within_aged(self):
        cs = [Candidate(0, 0, 1000, 100, 100, 1000), Candidate(1, 1, 2, 1, 1, 1),
              Candidate(2, 8, 0, 1, 1, 1)]
        self.assertEqual(select(cs, 10, "smart", replace(self.sc, starvation_after=5)), 0)

    def test_ties_are_deterministic(self):
        cs = [Candidate(i, 0, 10, 1, 1, 10) for i in (2, 0, 1)]
        for policy in POLICIES:
            self.assertEqual(select(cs, 0, policy, self.sc), 0)

    def test_unknown_policy_and_empty_queue(self):
        with self.assertRaises(ValueError):
            select(self.candidates, 0, "bad", self.sc)
        with self.assertRaises(ValueError):
            select([], 0, "fcfs", self.sc)

    def test_nonpreemptive_prefill(self):
        rs = [request(0, tokens=2000, output=1), request(1, arrival=.1, tokens=10, output=1, ttft=.1)]
        for policy in POLICIES:
            self.assertEqual(simulate(rs, constant_hardware(), policy).records[1].prefill_start, 2)

    def test_aging_promotes_long_request_in_competing_backlog(self):
        rs = [request(0, tokens=1000, output=1, ttft=100)]
        rs += [request(i, tokens=10, output=1, ttft=.01) for i in range(1, 201)]
        aged = simulate(rs, constant_hardware(), "smart",
                        replace(self.sc, starvation_after=.5)).records[0]
        unaged = simulate(rs, constant_hardware(), "smart", self.sc).records[0]
        self.assertLess(aged.prefill_start, .52)
        self.assertGreater(unaged.prefill_start, 1.9)


class WorkloadAndValidationTests(unittest.TestCase):
    def test_deterministic_rng_and_simulation(self):
        cfg = WorkloadConfig(duration=10, warmup=1, rate=5)
        h, ps = Hardware(), default_profiles()
        rs = generate(cfg, ps, {"sharegpt": 1}, h)
        self.assertEqual(rs, generate(cfg, ps, {"sharegpt": 1}, h))
        self.assertEqual(trace_hash(rs), trace_hash(generate(cfg, ps, {"sharegpt": 1}, h)))
        for policy in POLICIES:
            a, b = simulate(rs, h, policy), simulate(rs, h, policy)
            self.assertEqual([s.row() for s in a.records], [s.row() for s in b.records])
            self.assertTrue(all(s.completion is not None for s in a.records))

    def test_estimates_independent_of_actual_outputs(self):
        cfg, h, ps = WorkloadConfig(duration=10, warmup=1, rate=5), Hardware(), default_profiles()
        a = generate(cfg, ps, {"sharegpt": 1}, h)
        ps["sharegpt"] = replace(ps["sharegpt"], output_sigma=1.5)
        b = generate(cfg, ps, {"sharegpt": 1}, h)
        self.assertTrue(any(x.output_tokens != y.output_tokens for x, y in zip(a, b)))
        self.assertEqual([(x.arrival, x.input_tokens, x.estimated_prefill, x.estimated_output_tokens) for x in a],
                         [(x.arrival, x.input_tokens, x.estimated_prefill, x.estimated_output_tokens) for x in b])

    def test_estimate_ablations_preserve_realized_trace(self):
        cfg, h, ps = WorkloadConfig(duration=10, warmup=1, rate=5), Hardware(), default_profiles()
        a = generate(cfg, ps, {"sharegpt": 1}, h)
        b = generate(replace(cfg, estimate_sigma=1), ps, {"sharegpt": 1}, h)
        self.assertEqual([(r.arrival, r.input_tokens, r.output_tokens) for r in a],
                         [(r.arrival, r.input_tokens, r.output_tokens) for r in b])

    def test_low_load_policies_coincide(self):
        rs = [request(i, arrival=i * 10) for i in range(4)]
        baseline = [s.row() for s in simulate(rs, constant_hardware(), "fcfs").records]
        for policy in POLICIES:
            self.assertEqual(baseline, [s.row() for s in simulate(rs, constant_hardware(), policy).records])

    def test_invalid_configs(self):
        cases = [lambda: Hardware(prefill_gpus=0), lambda: Hardware(decode_batch_size=1.5),
                 lambda: Hardware(prefill_tokens_per_second=float("nan")),
                 lambda: WorkloadConfig(warmup=100), lambda: WorkloadConfig(rate=-1),
                 lambda: WorkloadConfig(burst_duty=1), lambda: SchedulerConfig(aging_rate=-1),
                 lambda: request(output=0), lambda: request(arrival=-1)]
        for case in cases:
            with self.assertRaises(ValueError):
                case()

    def test_invalid_weights_and_duplicate_ids(self):
        for weights in ({}, {"bad": 1}, {"sharegpt": 0}, {"sharegpt": -1}):
            with self.assertRaises(ValueError):
                generate(WorkloadConfig(), default_profiles(), weights, Hardware())
        with self.assertRaises(ValueError):
            simulate([request(), request()])

    def test_timeline_and_work_conservation_under_overload(self):
        h = Hardware(prefill_gpus=2, decode_gpus=2, decode_batch_size=4)
        cfg = WorkloadConfig(duration=5, warmup=1, rate=20)
        rs = generate(cfg, default_profiles(), {"sharegpt": .5, "longbench": .5}, h)
        for policy in POLICIES:
            result = simulate(rs, h, policy)
            self.assertEqual(len(result.records), len(rs))
            self.assertGreater(result.end_time, cfg.duration)
            for s in result.records:
                self.assertLessEqual(s.request.arrival, s.prefill_start)
                self.assertLessEqual(s.first_token, s.decode_ready)
                self.assertLessEqual(s.decode_ready, s.decode_start)
                self.assertLessEqual(s.decode_start, s.completion)
            for gpu in range(h.prefill_gpus):
                jobs = sorted((s.prefill_start, s.first_token) for s in result.records if s.prefill_gpu == gpu)
                self.assertTrue(all(a[1] <= b[0] + 1e-12 for a, b in zip(jobs, jobs[1:])))
            self.assertTrue(all(x <= result.end_time + 1e-9 for x in result.prefill_busy_seconds + result.decode_busy_seconds))


class MetricTests(unittest.TestCase):
    def test_quantiles_and_jain(self):
        self.assertEqual(percentile([0, 10], .95), 9.5)
        self.assertEqual(percentile([4], .95), 4)
        self.assertIsNone(percentile([], .95))
        self.assertEqual(jain([1, 1]), 1)
        self.assertEqual(jain([0, 0]), 0)
        self.assertEqual(jain([1, 0]), .5)

    def test_measurement_cohort_and_goodput_denominator(self):
        rs = [request(0, arrival=0, output=1), request(1, arrival=2, output=1)]
        h = constant_hardware()
        m = evaluate(simulate(rs, h), h, start=1, stop=3)
        self.assertEqual(m["requests"], 1)
        self.assertEqual(m["goodput_per_gpu"], 1 / (2 * h.gpus))
        self.assertEqual(m["slo_attainment"], 1)
        self.assertIsNone(m["tpot_mean_s"])

    def test_joint_slo_requires_both(self):
        h = constant_hardware()
        a = simulate([request(ttft=.5)], h).records[0]
        b = simulate([request(tpot=.01)], h).records[0]
        self.assertFalse(a.slo_met)
        self.assertFalse(b.slo_met)

    def test_exact_slo_boundary(self):
        s = simulate([request(output=1, ttft=1)], constant_hardware()).records[0]
        self.assertTrue(s.slo_met)

    def test_tail_remains_in_cohort_after_drain(self):
        h = constant_hardware()
        rs = [request(i, arrival=.01 * i, output=1, ttft=.1) for i in range(10)]
        result = simulate(rs, h)
        m = evaluate(result, h, start=0, stop=1)
        self.assertEqual(m["requests"], 10)
        self.assertEqual(m["slo_attainment"], 0)
        self.assertGreater(m["waiting_p95_s"], 8)
        self.assertGreater(m["drain_seconds"], 8)

    def test_t_intervals(self):
        m = interval([1, 2, 3, 4, 5])
        self.assertEqual(m["mean"], 3)
        self.assertAlmostEqual(m["ci95_halfwidth"], 2.776 * (2.5 ** .5) / (5 ** .5))
        self.assertIsNone(interval([1])["ci95_halfwidth"])

    def test_paired_contrasts_validate_trace_identity(self):
        metrics = {m: 1 for m in METRICS}
        a = dict(suite="main", workload="x", offered_rate=1, seed=1, policy="fcfs", trace_sha256="a", metrics=metrics)
        b = {**a, "policy": "smart", "trace_sha256": "b"}
        with self.assertRaises(ValueError):
            summarize([a, b])


if __name__ == "__main__":
    unittest.main()
