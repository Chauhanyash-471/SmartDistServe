"""Synthetic workload generation and explicit, provenance-carrying CSV trace import."""
from dataclasses import asdict, dataclass
import csv
import hashlib
import json
import math
from pathlib import Path
import random

from .config import Hardware, Profile, WorkloadConfig, integer, positive


@dataclass(frozen=True)
class Request:
    request_id: int
    arrival: float
    profile: str
    input_tokens: int
    output_tokens: int
    ttft_slo: float
    tpot_slo: float
    estimated_prefill: float
    estimated_output_tokens: int

    def __post_init__(self):
        integer("request_id", self.request_id, zero=True)
        positive("arrival", self.arrival, zero=True)
        if not isinstance(self.profile, str) or not self.profile:
            raise ValueError("request profile must be a nonempty string")
        for name in ("input_tokens", "output_tokens", "estimated_output_tokens"):
            integer(name, getattr(self, name))
        for name in ("ttft_slo", "tpot_slo", "estimated_prefill"):
            positive(name, getattr(self, name))


def _stream(seed, label):
    digest = hashlib.sha256(f"{seed}:{label}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _length(rng, mean, sigma, low, high):
    # mean is the uncensored lognormal mean; clipping/rounding changes realized mean.
    x = rng.lognormvariate(math.log(mean) - sigma * sigma / 2, sigma)
    return min(high, max(low, round(x)))


def generate(config: WorkloadConfig, profiles: dict[str, Profile], weights: dict[str, float],
             hardware: Hardware):
    """Poisson or periodic nonhomogeneous Poisson arrivals, labeled synthetic.

    Estimates use known input length and profile-level output prior only. They never
    read realized output lengths. Separate RNG streams preserve lengths/arrivals
    when estimate error is changed, allowing paired ablations.
    """
    if not weights or set(weights) - set(profiles):
        raise ValueError("weights must name available profiles")
    for name, weight in weights.items():
        positive(f"weight {name}", weight, zero=True)
    if sum(weights.values()) <= 0:
        raise ValueError("at least one weight must be positive")
    names = sorted(weights)
    arng, lrng, erng = (_stream(config.seed, label) for label in ("arrivals", "lengths", "estimates"))
    duty, multiplier = config.burst_duty, config.burst_multiplier
    low_rate = config.rate / (1 + duty * (multiplier - 1))
    high_rate = low_rate * multiplier
    requests = []
    now = 0.0
    while True:
        now += arng.expovariate(high_rate)
        if now >= config.duration:
            break
        phase = (now % config.burst_period) / config.burst_period
        intensity = high_rate if phase < duty else low_rate
        if arng.random() > intensity / high_rate:
            continue
        name = lrng.choices(names, weights=[weights[n] for n in names], k=1)[0]
        p = profiles[name]
        input_tokens = _length(lrng, p.input_mean, p.input_sigma, p.input_min, p.input_max)
        output_tokens = _length(lrng, p.output_mean, p.output_sigma, p.output_min, p.output_max)
        sigma = config.estimate_sigma
        multiplier_error = erng.lognormvariate(-sigma * sigma / 2, sigma)
        output_estimate = _length(erng, p.output_mean, sigma, 1, p.output_max)
        requests.append(Request(len(requests), now, name, input_tokens, output_tokens,
                                p.ttft_slo, p.tpot_slo,
                                hardware.prefill_time(input_tokens) * multiplier_error,
                                output_estimate))
    return requests


def trace_hash(requests):
    data = json.dumps([asdict(r) for r in requests], sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode()
    return hashlib.sha256(data).hexdigest()


def load_trace(path, *, source, provenance):
    """Import token-length traces, without claiming they are verified benchmark data.

    CSV fields match Request. Estimates must be supplied independently by the user.
    provenance is a required descriptive source, tokenizer, and collection note.
    """
    if source not in ("synthetic", "empirical") or not provenance.strip():
        raise ValueError("source synthetic/empirical and nonempty provenance are required")
    with Path(path).open(newline="", encoding="utf-8") as f:
        result = []
        for row in csv.DictReader(f):
            data = {name: row[name] for name in Request.__dataclass_fields__}
            for name in ("request_id", "input_tokens", "output_tokens", "estimated_output_tokens"):
                data[name] = int(data[name])
            for name in ("arrival", "ttft_slo", "tpot_slo", "estimated_prefill"):
                data[name] = float(data[name])
            result.append(Request(**data))
    if len({r.request_id for r in result}) != len(result):
        raise ValueError("duplicate request IDs")
    return result
