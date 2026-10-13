"""Validated configuration. All times are seconds; lengths are tokens."""
from dataclasses import asdict, dataclass
import math


def positive(name, value, *, zero=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    if not math.isfinite(value) or (value < 0 if zero else value <= 0):
        raise ValueError(f"{name} must be finite and {'nonnegative' if zero else 'positive'}")


def integer(name, value, *, zero=False):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    positive(name, value, zero=zero)


@dataclass(frozen=True)
class Hardware:
    prefill_gpus: int = 2
    decode_gpus: int = 1
    decode_batch_size: int = 16
    prefill_overhead: float = 0.005
    prefill_tokens_per_second: float = 8000.0
    prefill_quadratic: float = 0.01
    decode_base: float = 0.012
    decode_batch_increment: float = 0.0006
    decode_context_increment: float = 0.00000025
    transfer_latency: float = 0.002
    kv_bytes_per_token: float = 131072.0
    transfer_bytes_per_second: float = 25_000_000_000.0

    def __post_init__(self):
        for name in ("prefill_gpus", "decode_gpus", "decode_batch_size"):
            integer(name, getattr(self, name))
        for name in ("prefill_tokens_per_second", "decode_base", "transfer_bytes_per_second"):
            positive(name, getattr(self, name))
        for name in ("prefill_overhead", "prefill_quadratic", "decode_batch_increment",
                     "decode_context_increment", "transfer_latency", "kv_bytes_per_token"):
            positive(name, getattr(self, name), zero=True)

    @property
    def gpus(self):
        return self.prefill_gpus + self.decode_gpus

    def prefill_time(self, tokens):
        return (self.prefill_overhead + tokens / self.prefill_tokens_per_second
                + self.prefill_quadratic * (tokens / 4096) ** 2)

    def transfer_time(self, tokens):
        return self.transfer_latency + tokens * self.kv_bytes_per_token / self.transfer_bytes_per_second

    def decode_step(self, batch_size, max_context):
        return (self.decode_base + self.decode_batch_increment * (batch_size - 1)
                + self.decode_context_increment * max_context)


@dataclass(frozen=True)
class Profile:
    name: str
    input_mean: float
    output_mean: float
    input_sigma: float
    output_sigma: float
    input_min: int
    input_max: int
    output_min: int
    output_max: int
    ttft_slo: float
    tpot_slo: float

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("profile name must be a nonempty string")
        for name in ("input_mean", "output_mean", "ttft_slo", "tpot_slo"):
            positive(name, getattr(self, name))
        for name in ("input_sigma", "output_sigma"):
            positive(name, getattr(self, name), zero=True)
        for name in ("input_min", "input_max", "output_min", "output_max"):
            integer(name, getattr(self, name))
        if self.input_min > self.input_max or self.output_min > self.output_max:
            raise ValueError("profile min must not exceed max")


def default_profiles():
    # Illustrative application profiles, not fitted distributions or dataset samples.
    return {
        "sharegpt": Profile("sharegpt", 755, 200, 0.9, 0.8, 16, 8192, 2, 1024, 1.5, 0.08),
        "humaneval": Profile("humaneval", 171, 98, 0.7, 0.7, 16, 2048, 2, 512, 0.35, 0.10),
        "longbench": Profile("longbench", 8192, 91, 0.6, 0.6, 1024, 32768, 2, 512, 8.0, 0.06),
    }


@dataclass(frozen=True)
class SchedulerConfig:
    duration_weight: float = 0.1
    aging_rate: float = 0.2
    starvation_after: float | None = 5.0

    def __post_init__(self):
        positive("duration_weight", self.duration_weight, zero=True)
        positive("aging_rate", self.aging_rate, zero=True)
        if self.starvation_after is not None:
            positive("starvation_after", self.starvation_after, zero=True)


@dataclass(frozen=True)
class WorkloadConfig:
    duration: float = 90.0
    warmup: float = 15.0
    rate: float = 3.0
    seed: int = 11
    estimate_sigma: float = 0.3
    burst_multiplier: float = 1.0
    burst_period: float = 10.0
    burst_duty: float = 0.25

    def __post_init__(self):
        for name in ("duration", "rate", "burst_multiplier", "burst_period"):
            positive(name, getattr(self, name))
        positive("warmup", self.warmup, zero=True)
        positive("estimate_sigma", self.estimate_sigma, zero=True)
        integer("seed", self.seed, zero=True)
        if self.warmup >= self.duration:
            raise ValueError("warmup must be smaller than duration")
        if self.burst_multiplier < 1:
            raise ValueError("burst_multiplier must be >= 1")
        positive("burst_duty", self.burst_duty)
        if self.burst_duty >= 1:
            raise ValueError("burst_duty must be < 1")


def config_dict(obj):
    return asdict(obj)
