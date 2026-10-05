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
    print("Phase 1/7: refresh Adelaide YouTube captions and archive", flush=True)
    run(PYTHON, "pipeline/archive_adelaide_youtube.py")

    print("Phase 2/7: transcribe Adelaide YouTube videos without captions", flush=True)
    run(PYTHON, "pipeline/transcribe_missing_adelaide_youtube.py", "--shortest-first")
    run(PYTHON, "pipeline/archive_adelaide_youtube.py", "--index-only")
    checkpoint(
        "Complete Adelaide Heward-Mills YouTube archive",
        "Marriage Wiki/sources/Adelaide Heward-Mills/YouTube",
        "Marriage Wiki/wiki/Sources/Adelaide Heward-Mills YouTube Archive.md",
        "Marriage Wiki/_meta/adelaide-youtube-archive-links.jsonl",
    )

    print("Phase 3/7: finish captionless Meeting God videos", flush=True)
    run(PYTHON, "pipeline/transcribe_missing_meetinggod.py")
    checkpoint(
        "Complete Meeting God transcript collection",
        "Marriage Wiki/sources/Joshua Heward-Mills",
    )

    print("Phase 4/7: finish unmatched Adelaide podcast episodes", flush=True)
    run(
        PYTHON,
        "pipeline/transcribe_marriage_podcasts.py",
        "--series",
        "adelaide",
        "--shortest-first",
    )

    print("Phase 5/7: rebuild chatbot corpus and indexes", flush=True)
    run(PYTHON, "pipeline/build_marriage_chatbot.py")

    print("Phase 6/7: rebuild the chatbot search database", flush=True)
    run(PYTHON, "pipeline/build_corpus.py")

    print("Phase 7/7: verify 300 + 33 + 305 + 267 coverage", flush=True)
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
