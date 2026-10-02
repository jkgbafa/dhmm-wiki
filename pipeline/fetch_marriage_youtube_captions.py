#!/usr/bin/env python3
"""Fetch English captions for marriage-priority Meeting God videos.

The original JSON3 caption is kept under ``Marriage Wiki/raw/captions`` and a
timestamped Markdown transcript is generated under ``Marriage Wiki/sources``.
Metadata-only candidates come from ``build_marriage_inventory.py``.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WIKI = ROOT / "Marriage Wiki"
MANIFEST = WIKI / "raw" / "manifests" / "joshua-heward-mills.jsonl"
CAPTIONS = WIKI / "raw" / "captions" / "Joshua Heward-Mills"
SOURCES = WIKI / "sources" / "Joshua Heward-Mills"

CUE_RE = re.compile(r"\[[^\]]+\]", re.I)
SPACE_RE = re.compile(r"\s+")


def safe_filename(title: str) -> str:
    title = re.sub(r'[<>:"/\\|?*]', "", title).strip(". ")
    return title[:180] or "untitled"


def timestamp(milliseconds: int) -> str:
    seconds = max(0, milliseconds // 1000)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def clean_caption(text: str) -> str:
    text = CUE_RE.sub(" ", text.replace(">>", " "))
    return SPACE_RE.sub(" ", text).strip()


def caption_blocks(payload):
    cues = []
    for event in payload.get("events", []):
        text = clean_caption("".join(segment.get("utf8", "") for segment in event.get("segs", [])))
        if not text:
            continue
        cues.append((int(event.get("tStartMs", 0)), text))

    blocks = []
    block_start = None
    block_text = []
    words = 0
    for start, text in cues:
        if block_start is None:
            block_start = start
        if block_text and (start - block_start >= 45_000 or words + len(text.split()) > 120):
            blocks.append((block_start, " ".join(block_text)))
            block_start, block_text, words = start, [], 0
        block_text.append(text)
        words += len(text.split())
    if block_text:
        blocks.append((block_start, " ".join(block_text)))
    return blocks


def download_caption(entry):
    CAPTIONS.mkdir(parents=True, exist_ok=True)
    video_id = entry["video_id"]
    existing = sorted(CAPTIONS.glob(f"{video_id}.*.json3"))
    if existing:
        return existing[0]
    target = CAPTIONS / f"{video_id}.%(ext)s"
    for language in ("en-orig", "en"):
        command = [
            "yt-dlp",
            "--skip-download",
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs", language,
            "--sub-format", "json3",
            "--no-warnings",
            "--no-progress",
            "-o", str(target),
            entry["url"],
        ]
        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError:
            continue
        matches = sorted(CAPTIONS.glob(f"{video_id}.*.json3"))
        if matches:
            return matches[0]
    return None


def write_source(entry, caption_path: Path):
    payload = json.loads(caption_path.read_text(encoding="utf-8"))
    blocks = caption_blocks(payload)
    SOURCES.mkdir(parents=True, exist_ok=True)
    note_path = SOURCES / f"{safe_filename(entry['title'])} [{entry['video_id']}].md"
    frontmatter = {
        "title": entry["title"],
        "source_id": entry["source_id"],
        "speaker": ["Joshua Heward-Mills"],
        "series": entry["series"],
        "platform": entry["platform"],
        "source_url": entry["url"],
        "published": entry.get("published"),
        "duration_seconds": entry.get("duration_seconds"),
        "transcript_method": "youtube_auto_captions",
        "transcript_status": "unverified",
        "topics": entry.get("topics", []),
        "raw_caption": str(caption_path.relative_to(WIKI)),
    }
    lines = ["---"]
    for key, value in frontmatter.items():
        if value is not None:
            lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    lines += [
        "---",
        "",
        f"# {entry['title']}",
        "",
        f"[Watch on YouTube]({entry['url']})",
        "",
        "> [!warning] Automated transcript",
        "> This transcript comes from YouTube automatic captions and has not been human-reviewed. Verify wording against the audio before relying on a quotation.",
        "",
        "## Transcript",
        "",
    ]
    for start, text in blocks:
        seconds = start // 1000
        lines.append(f"[{timestamp(start)}]({entry['url']}&t={seconds}s) {text}")
        lines.append("")
    note_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return note_path, len(blocks)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="fetch every channel video, not just high-priority marriage candidates")
    args = parser.parse_args()
    entries = [json.loads(line) for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not args.all:
        entries = [entry for entry in entries if entry.get("marriage_relevance") == "high"]
    written = skipped = 0
    for entry in entries:
        try:
            caption_path = download_caption(entry)
        except Exception as error:
            print(f"Caption error: {entry['title']} ({error})")
            skipped += 1
            continue
        if not caption_path:
            print(f"No English captions: {entry['title']}")
            skipped += 1
            continue
        note_path, blocks = write_source(entry, caption_path)
        print(f"Wrote {note_path.relative_to(ROOT)} ({blocks} timestamped blocks)")
        written += 1
    print(f"Done: {written} transcript notes; {skipped} without captions.")


if __name__ == "__main__":
    main()
