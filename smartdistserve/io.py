"""Portable JSON and deterministic gzip artifacts."""
from contextlib import contextmanager
import gzip
import io
import json
from pathlib import Path


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
                    encoding="utf-8")


@contextmanager
def gzip_text(path):
    # Suppress timestamp and filename metadata to make bytes reproducible.
    with Path(path).open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, filename="", mode="wb", mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as text:
                yield text
