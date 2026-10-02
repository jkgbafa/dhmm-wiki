#!/usr/bin/env python3
"""Finish the marriage corpus sequentially and checkpoint each series.

Safe to rerun after sleep or interruption: the underlying transcription
scripts skip source IDs whose Markdown transcript already exists.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PYTHON = "/usr/bin/python3"


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def checkpoint(message: str, *paths: str) -> None:
    run("git", "add", "--", *paths)
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=ROOT
    ).returncode
    if staged == 0:
        print(f"No new files for checkpoint: {message}", flush=True)
        return
    run("git", "commit", "-m", message)
    run("git", "push", "origin", "HEAD")


def main() -> None:
    print("Phase 1/4: finish captionless Meeting God videos", flush=True)
    run(PYTHON, "pipeline/transcribe_missing_meetinggod.py")
    checkpoint(
        "Complete Meeting God transcript collection",
        "Marriage Wiki/sources/Joshua Heward-Mills",
    )

    print("Phase 2/4: finish unmatched Adelaide podcast episodes", flush=True)
    run(
        PYTHON,
        "pipeline/transcribe_marriage_podcasts.py",
        "--series",
        "adelaide",
        "--shortest-first",
    )

    print("Phase 3/4: rebuild chatbot corpus and indexes", flush=True)
    run(PYTHON, "pipeline/build_marriage_chatbot.py")

    print("Phase 4/4: verify exact 300 + 33 + 305 coverage", flush=True)
    run(PYTHON, "pipeline/selfcheck_marriage.py")
    checkpoint(
        "Complete marriage chatbot corpus",
        "Marriage Wiki/sources/Adelaide Heward-Mills",
        "Marriage Wiki/sources/First Love Conversations",
        "Marriage Wiki/sources/Joshua Heward-Mills",
        "Marriage Wiki/_chatbot",
        "Marriage Wiki/wiki",
        "Marriage Wiki/Home.md",
        "Marriage Wiki/index.md",
        "Marriage Wiki/log.md",
        "pipeline/run_remaining_marriage_ingest.py",
    )
    print("Marriage wiki ingestion is complete and pushed.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted. Rerun this script to resume safely.", file=sys.stderr)
        raise SystemExit(130)
