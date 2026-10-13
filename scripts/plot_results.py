"""Generate six static figures from measured JSON (no invented graph values)."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from smartdistserve.reporting import summarize

COLORS = {"fcfs": "#555555", "sjf": "#0072B2", "edf": "#009E73", "smart": "#D55E00"}
LABELS = {"fcfs": "FCFS", "sjf": "Estimated SJF", "edf": "EDF", "smart": "Smart"}


def save(fig, folder, name):
    fig.savefig(folder / f"{name}.png", dpi=180, bbox_inches="tight")
    fig.savefig(folder / f"{name}.pdf", bbox_inches="tight", metadata={"CreationDate": None, "ModDate": None})
    plt.close(fig)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--results", default="results/reference")
    args = p.parse_args()
    folder = Path(args.results)
    runs = json.loads((folder / "runs.json").read_text(encoding="utf-8"))
    summary, _ = summarize(runs)
    charts = folder / "figures"
    charts.mkdir(exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": True, "grid.alpha": .2, "figure.facecolor": "white"})
    workloads = ["sharegpt", "humaneval", "longbench", "mixed"]
    metrics = [("slo_attainment", "Joint SLO attainment (%)", 100, "slo_attainment"),
               ("goodput_per_gpu", "Cohort goodput (req/s/GPU)", 1, "goodput"),
               ("waiting_p95_s", "Mean of run P95 queue wait (s)", 1, "waiting_tail"),
               ("jain_length_slo", "Jain index of prompt-bin SLO rates", 1, "fairness")]
    for metric, label, scale, name in metrics:
        fig, axs = plt.subplots(2, 2, figsize=(11, 7.2), constrained_layout=True)
        for ax, workload in zip(axs.flat, workloads):
            for policy in COLORS:
                rows = sorted((r for r in summary if r["suite"] == "main" and r["workload"] == workload
                               and r["policy"] == policy), key=lambda r: r["offered_rate"])
                rows = [r for r in rows if r[metric]["mean"] is not None]
                ax.errorbar([r["offered_rate"] for r in rows], [r[metric]["mean"] * scale for r in rows],
                            yerr=[(r[metric]["ci95_halfwidth"] or 0) * scale for r in rows],
                            label=LABELS[policy], color=COLORS[policy], marker="o", capsize=3, linewidth=1.5)
            ax.set_title(workload.title() + " (synthetic)")
            ax.set_xlabel("Offered arrival rate (req/s)")
            ax.set_ylabel(label)
            ax.set_ylim(bottom=0)
            if metric == "slo_attainment":
                ax.axhline(90, color="#777777", linestyle="--", linewidth=.8)
                ax.set_ylim(0, 110)  # Unclipped CI endpoints may extend beyond [0,100].
            if metric == "jain_length_slo":
                ax.set_ylim(0, 1.1)
        axs.flat[0].legend(fontsize=9)
        fig.suptitle(f"SmartDistServe: {label}\nSynthetic, uncalibrated model; seed means and 95% t intervals", fontsize=13)
        save(fig, charts, name)
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)
    for ax, metric, label in zip(axs, ("ttft_p95_s", "tpot_p95_s"), ("P95 TTFT (s)", "P95 TPOT (s)")):
        for policy in COLORS:
            rows = sorted((r for r in summary if r["suite"] == "main" and r["workload"] == "mixed"
                           and r["policy"] == policy), key=lambda r: r["offered_rate"])
            ax.errorbar([r["offered_rate"] for r in rows], [r[metric]["mean"] for r in rows],
                        yerr=[r[metric]["ci95_halfwidth"] or 0 for r in rows], label=LABELS[policy],
                        color=COLORS[policy], marker="o", capsize=3)
        ax.set_xlabel("Offered arrival rate (req/s)")
        ax.set_ylabel("Mean of run " + label)
        ax.set_ylim(bottom=0)
    axs[0].legend()
    fig.suptitle("Mixed synthetic workload: latency tails\nSeed means and 95% t intervals; uncalibrated model")
    save(fig, charts, "latency_tails")
    fig, ax = plt.subplots(figsize=(10, 4.5), constrained_layout=True)
    baseline = next(r for r in summary if r["suite"] == "main" and r["workload"] == "mixed"
                    and r["offered_rate"] == 3 and r["policy"] == "smart")
    rows = [baseline] + [r for r in summary if r["suite"] == "ablation" and r["policy"] == "smart"]
    names = ["default"] + [r["workload"].replace("_", "\n") for r in rows[1:]]
    ax.bar(names, [r["slo_attainment"]["mean"] * 100 for r in rows], color=COLORS["smart"],
           yerr=[(r["slo_attainment"]["ci95_halfwidth"] or 0) * 100 for r in rows], capsize=4)
    ax.set_ylim(0, 110)
    ax.set_ylabel("Joint SLO attainment (%)")
    ax.set_title("Smart policy ablations, mixed synthetic workload at 3 req/s\nSeed means and 95% t intervals; uncalibrated model")
    save(fig, charts, "ablations")
    print(f"Wrote 6 PNG/PDF figures to {charts}")


if __name__ == "__main__":
    main()
