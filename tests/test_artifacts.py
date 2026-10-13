from contextlib import redirect_stdout
from dataclasses import asdict
import csv
import gzip
import io
import json
from pathlib import Path
import tempfile
import unittest

from smartdistserve.cli import main
from smartdistserve.config import default_profiles
from smartdistserve.experiments import run_experiments
from smartdistserve.reporting import report
from smartdistserve.workloads import load_trace
from test_simulator import request


class ArtifactTests(unittest.TestCase):
    def test_experiments_reproduce_gzip_and_numeric_artifacts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = asdict(default_profiles()["sharegpt"])
            profile.pop("name")
            cfg = {"profiles": {"sharegpt": profile}, "workload": {"duration": 3, "warmup": .5},
                   "seeds": [1, 2], "workloads": {"sharegpt": {"weights": {"sharegpt": 1}, "rates": [2]}}}
            (root / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
            for out in ("a", "b"):
                run_experiments(root / "config.json", root / out, progress=lambda _: None)
                report(root / out)
            for name in ("runs.json", "runs.csv", "requests.csv.gz", "traces.jsonl.gz", "summary.csv"):
                self.assertEqual((root / "a" / name).read_bytes(), (root / "b" / name).read_bytes())
            with gzip.open(root / "a" / "requests.csv.gz", "rt", newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertTrue(rows)
            self.assertEqual({r["source"] for r in rows}, {"synthetic"})

    def test_import_requires_provenance_and_validates_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "trace.csv"
            data = asdict(request())
            with path.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(data))
                w.writeheader()
                w.writerow(data)
            self.assertEqual(load_trace(path, source="synthetic", provenance="test"), [request()])
            with self.assertRaises(ValueError):
                load_trace(path, source="empirical", provenance="")

    def test_cli_run(self):
        with tempfile.TemporaryDirectory() as temp, redirect_stdout(io.StringIO()):
            main(["run", "--duration", "2", "--warmup", "0", "--rate", "2", "--output", temp])
            data = json.loads((Path(temp) / "run.json").read_text())
            self.assertEqual(data["source"], "synthetic")
            self.assertEqual(data["hardware"]["prefill_gpus"], 2)

    def test_cli_respects_config_and_explicit_overrides(self):
        with tempfile.TemporaryDirectory() as temp, redirect_stdout(io.StringIO()):
            root = Path(temp)
            cfg = root / "config.json"
            cfg.write_text(json.dumps({"workload": {"duration": 2, "warmup": 0, "rate": 1, "seed": 77}}))
            main(["run", "--config", str(cfg), "--rate", "2", "--output", temp])
            data = json.loads((root / "run.json").read_text())
            self.assertEqual(data["workload"]["duration"], 2)
            self.assertEqual(data["workload"]["seed"], 77)
            self.assertEqual(data["workload"]["rate"], 2)


if __name__ == "__main__":
    unittest.main()
