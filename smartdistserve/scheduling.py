"""Phase-local scheduling: FCFS, estimated SJF, EDF, and slack + duration + aging."""
from dataclasses import dataclass

from .config import SchedulerConfig

POLICIES = ("fcfs", "sjf", "edf", "smart")


@dataclass(frozen=True)
class Candidate:
    # Deliberately excludes realized output length and future completion time.
    request_id: int
    enqueue_time: float
    deadline: float
    estimated_service: float
    estimated_total_duration: float
    budget: float


def select(candidates, now, policy, config: SchedulerConfig):
    if policy not in POLICIES:
        raise ValueError(f"unknown policy: {policy}")
    if not candidates:
        raise ValueError("cannot select from an empty queue")
    fifo = lambda c: (c.enqueue_time, c.request_id)
    if policy == "fcfs":
        return min(candidates, key=fifo).request_id
    if policy == "sjf":
        return min(candidates, key=lambda c: (c.estimated_service, *fifo(c))).request_id
    if policy == "edf":
        return min(candidates, key=lambda c: (c.deadline, *fifo(c))).request_id
    # Hard aging promotes eligible requests ahead of all younger work, in FCFS
    # order. It ensures eventual admission under bounded service/finite backlog,
    # but does not promise a fixed latency bound or fairness under infinite load.
    if config.starvation_after is not None:
        aged = [c for c in candidates if now - c.enqueue_time >= config.starvation_after]
        if aged:
            return min(aged, key=fifo).request_id

    def key(c):
        slack = c.deadline - now - c.estimated_service
        wait = max(0.0, now - c.enqueue_time)
        score = (slack + config.duration_weight * c.estimated_total_duration
                 - config.aging_rate * wait) / c.budget
        return score, *fifo(c)

    return min(candidates, key=key).request_id
