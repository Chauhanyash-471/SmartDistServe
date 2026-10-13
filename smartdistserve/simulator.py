"""Deterministic heap-based discrete-event simulator with complete draining.

    Prefill produces token 1. KV transfer follows. Decode produces tokens 2..O
    using continuous batches; active requests retain a slot until completion.
    Events at the same timestamp release resources before routing new work;
    all are processed before dispatch.
"""
from dataclasses import dataclass, field
import heapq
import math

from .config import Hardware, SchedulerConfig
from .scheduling import Candidate, POLICIES, select
from .workloads import Request


@dataclass
class Record:
    request: Request
    prefill_gpu: int = -1
    decode_gpu: int = -1
    prefill_start: float | None = None
    first_token: float | None = None
    decode_ready: float | None = None
    decode_start: float | None = None
    completion: float | None = None
    generated: int = 0
    max_token_gap: float = 0.0
    last_token: float | None = None

    @property
    def ttft(self):
        return self.first_token - self.request.arrival

    @property
    def tpot(self):
        # Single-token requests have no post-first-token interval.
        if self.request.output_tokens == 1:
            return None
        return (self.completion - self.first_token) / (self.request.output_tokens - 1)

    @property
    def waiting(self):
        return (self.prefill_start - self.request.arrival
                + (0.0 if self.decode_start is None else self.decode_start - self.decode_ready))

    @property
    def slo_met(self):
        return (self.ttft <= self.request.ttft_slo + 1e-12
                and (self.tpot is None or self.tpot <= self.request.tpot_slo + 1e-12))

    def row(self):
        r = self.request
        return {"request_id": r.request_id, "profile": r.profile, "arrival": r.arrival,
                "input_tokens": r.input_tokens, "output_tokens": r.output_tokens,
                "estimated_prefill": r.estimated_prefill,
                "estimated_output_tokens": r.estimated_output_tokens,
                "ttft_slo": r.ttft_slo, "tpot_slo": r.tpot_slo,
                "prefill_gpu": self.prefill_gpu, "decode_gpu": self.decode_gpu,
                "prefill_start": self.prefill_start, "first_token": self.first_token,
                "decode_ready": self.decode_ready, "decode_start": self.decode_start,
                "completion": self.completion, "ttft_s": self.ttft, "tpot_s": self.tpot,
                "waiting_s": self.waiting, "max_token_gap_s": self.max_token_gap,
                "slo_met": int(self.slo_met)}


@dataclass
class SimulationResult:
    records: list[Record]
    end_time: float
    events_processed: int
    max_prefill_queue: int
    max_decode_queue: int
    prefill_busy_seconds: list[float] = field(default_factory=list)
    decode_busy_seconds: list[float] = field(default_factory=list)


def simulate(requests: list[Request], hardware: Hardware | None = None, policy="fcfs",
             scheduler: SchedulerConfig | None = None):
    h, sc = hardware or Hardware(), scheduler or SchedulerConfig()
    if policy not in POLICIES:
        raise ValueError(f"unknown policy: {policy}")
    if len({r.request_id for r in requests}) != len(requests):
        raise ValueError("duplicate request IDs")
    states = {r.request_id: Record(r) for r in requests}
    pq = [[] for _ in range(h.prefill_gpus)]
    dq = [[] for _ in range(h.decode_gpus)]
    pre_busy = [False] * h.prefill_gpus
    dec_busy = [False] * h.decode_gpus
    active = [[] for _ in range(h.decode_gpus)]
    pre_seconds = [0.0] * h.prefill_gpus
    dec_seconds = [0.0] * h.decode_gpus
    events, serial = [], 0
    count, max_pq, max_dq = 0, 0, 0

    def push(time, kind, rid, gpu):
        nonlocal serial
        if not math.isfinite(time):
            raise ValueError("event time overflow; reduce lengths/rates or service coefficients")
        # Completions release slots before coincident transfers/arrivals route.
        # Otherwise routing could depend on how far in advance an event was
        # inserted, and an arriving request could miss a just-freed worker.
        priority = {"prefill_done": 0, "decode_done": 0, "transfer_done": 1, "arrival": 2}[kind]
        heapq.heappush(events, (time, priority, serial, kind, rid, gpu))
        serial += 1

    for r in sorted(requests, key=lambda r: (r.arrival, r.request_id)):
        push(r.arrival, "arrival", r.request_id, -1)

    def candidate(rid, phase):
        s, r = states[rid], states[rid].request
        step = h.decode_step(h.decode_batch_size, r.input_tokens + r.estimated_output_tokens)
        remaining = max(1, r.estimated_output_tokens - max(1, s.generated))
        decode_est = remaining * step
        total_est = r.estimated_prefill + h.transfer_time(r.input_tokens) + decode_est
        if phase == "prefill":
            return Candidate(rid, r.arrival, r.arrival + r.ttft_slo,
                             r.estimated_prefill, total_est, r.ttft_slo)
        budget = max(1, r.estimated_output_tokens - 1) * r.tpot_slo
        return Candidate(rid, s.decode_ready, s.first_token + budget,
                         decode_est, decode_est, budget)

    def pop(queue, phase, now):
        rid = select([candidate(rid, phase) for rid in queue], now, policy, sc)
        queue.remove(rid)
        return rid

    now = 0.0
    while events:
        now = events[0][0]
        # Includes newly inserted zero-transfer events at this timestamp.
        while events and events[0][0] == now:
            _, _, _, kind, rid, gpu = heapq.heappop(events)
            count += 1
            if kind == "arrival":
                gpu = min(range(h.prefill_gpus), key=lambda g: (len(pq[g]) + pre_busy[g], g))
                states[rid].prefill_gpu = gpu
                pq[gpu].append(rid)
                max_pq = max(max_pq, sum(map(len, pq)))
            elif kind == "prefill_done":
                pre_busy[gpu] = False
                s = states[rid]
                s.first_token, s.last_token, s.generated = now, now, 1
                if s.request.output_tokens == 1:
                    s.completion = now
                else:
                    push(now + h.transfer_time(s.request.input_tokens), "transfer_done", rid, -1)
            elif kind == "transfer_done":
                gpu = min(range(h.decode_gpus), key=lambda g: (len(dq[g]) + len(active[g]), g))
                s = states[rid]
                s.decode_gpu, s.decode_ready = gpu, now
                dq[gpu].append(rid)
                max_dq = max(max_dq, sum(map(len, dq)))
            elif kind == "decode_done":
                dec_busy[gpu] = False
                survivors = []
                for current in active[gpu]:
                    s = states[current]
                    s.generated += 1
                    s.max_token_gap = max(s.max_token_gap, now - s.last_token)
                    s.last_token = now
                    if s.generated == s.request.output_tokens:
                        s.completion = now
                    else:
                        survivors.append(current)
                active[gpu] = survivors
            else:
                raise RuntimeError(f"unknown event: {kind}")
        for gpu in range(h.prefill_gpus):
            if not pre_busy[gpu] and pq[gpu]:
                rid = pop(pq[gpu], "prefill", now)
                s = states[rid]
                s.prefill_start = now
                service = h.prefill_time(s.request.input_tokens)
                pre_busy[gpu] = True
                pre_seconds[gpu] += service
                push(now + service, "prefill_done", rid, gpu)
        for gpu in range(h.decode_gpus):
            if dec_busy[gpu]:
                continue
            while dq[gpu] and len(active[gpu]) < h.decode_batch_size:
                rid = pop(dq[gpu], "decode", now)
                states[rid].decode_start = now
                active[gpu].append(rid)
            if active[gpu]:
                context = max(states[rid].request.input_tokens + states[rid].generated
                              for rid in active[gpu])
                service = h.decode_step(len(active[gpu]), context)
                dec_busy[gpu] = True
                dec_seconds[gpu] += service
                push(now + service, "decode_done", -1, gpu)
    records = [states[rid] for rid in sorted(states)]
    if any(s.completion is None or s.generated != s.request.output_tokens for s in records):
        raise RuntimeError("simulation failed to drain all requests")
    return SimulationResult(records, now, count, max_pq, max_dq, pre_seconds, dec_seconds)
