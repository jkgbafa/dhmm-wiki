#!/usr/bin/env python3
"""Archive every Adelaide YouTube upload with links and timestamps.

Videos already matched to a podcast transcript reuse that evidence note. New
video-only uploads receive their own source note from YouTube captions. Any
upload without captions remains visible in the archive and is queued for the
local Whisper fallback script.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from build_marriage_chatbot import parse_frontmatter
from fetch_marriage_youtube_captions import caption_blocks
from transcribe_marriage_podcasts import safe_filename, timestamp


ROOT = Path(__file__).resolve().parent.parent
WIKI = ROOT / "Marriage Wiki"
MANIFEST = WIKI / "raw" / "manifests" / "adelaide-heward-mills-youtube.jsonl"
CAPTIONS = WIKI / "raw" / "captions" / "Adelaide Heward-Mills"
SOURCE_ROOT = WIKI / "sources" / "Adelaide Heward-Mills"
YOUTUBE_SOURCES = SOURCE_ROOT / "YouTube"
ARCHIVE = WIKI / "wiki" / "Sources" / "Adelaide Heward-Mills YouTube Archive.md"
LINK_REPORT = WIKI / "_meta" / "adelaide-youtube-archive-links.jsonl"
YTDLP = "/opt/homebrew/bin/yt-dlp"


def load_entries():
    return [json.loads(line) for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line.strip()]


def note_map():
    mapped = {}
    for path in SOURCE_ROOT.rglob("*.md"):
        metadata, _ = parse_frontmatter(path)
        video_id = metadata.get("video_id")
        if not video_id and str(metadata.get("source_id", "")).startswith("youtube:"):
            video_id = metadata["source_id"].split(":", 1)[1]
        if video_id:
            mapped[video_id] = (path, metadata)
    return mapped


def download_caption(entry):
    CAPTIONS.mkdir(parents=True, exist_ok=True)
    video_id = entry["video_id"]
    existing = sorted(CAPTIONS.glob(f"{video_id}.*.json3"))
    if existing:
        return existing[0]
    for language in ("en-orig", "en"):
        command = [
            YTDLP,
            "--skip-download",
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs", language,
            "--sub-format", "json3",
            "--no-warnings",
            "--no-progress",
            "--retries", "3",
            "-o", str(CAPTIONS / f"{video_id}.%(ext)s"),
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


def write_note(entry, caption_path):
    payload = json.loads(caption_path.read_text(encoding="utf-8"))
    blocks = caption_blocks(payload)
    if not blocks:
        raise ValueError("caption file contains no transcript text")
    metadata = {
        "title": entry["title"],
        "source_id": entry["source_id"],
        "speaker": ["Adelaide Heward-Mills"],
        "speaker_attribution": "channel_creator_unverified",
        "series": "Adelaide Heward-Mills",
        "collection": "Adelaide Heward-Mills — YouTube",
        "platform": "YouTube",
        "source_url": entry["url"],
        "video_url": entry["url"],
        "video_id": entry["video_id"],
        "published": entry.get("published"),
        "duration_seconds": entry.get("duration_seconds"),
        "transcript_method": "youtube_auto_captions",
        "transcript_status": "unverified",
        "topics": entry.get("topics", []),
        "raw_caption": str(caption_path.relative_to(WIKI)),
    }
    lines = ["---"]
    for key, value in metadata.items():
        if value is not None:
            lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    lines += [
        "---", "", f"# {entry['title']}", "", f"[Watch the original video]({entry['url']})", "",
        "> [!warning] Automated transcript",
        "> This transcript comes from YouTube automatic captions and has not been human-reviewed. Verify wording against the video before relying on a quotation.",
        "", "## Transcript", "",
    ]
    for start, text in blocks:
        seconds = start // 1000
        lines += [f"[{timestamp(seconds)}]({entry['url']}&t={seconds}s) {text}", ""]
    YOUTUBE_SOURCES.mkdir(parents=True, exist_ok=True)
    path = YOUTUBE_SOURCES / f"{safe_filename(entry['title'])} [{entry['video_id']}].md"
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path, len(blocks)


def obsidian_link(path, label):
    target = path.relative_to(WIKI).with_suffix("")
    return f"[[{target}|{label.replace('|', '—')}]]"


def write_archive(entries):
    mapped = note_map()
    rows = []
    lines = [
        "# Adelaide Heward-Mills YouTube Archive", "",
        "Every upload from the official Lady Rev. Adelaide Heward-Mills channel. Videos distributed through the podcast reuse the corresponding podcast transcript so the chatbot does not index duplicate words; video-only uploads have standalone transcript notes.", "",
    ]
    available = 0
    for entry in entries:
        linked = mapped.get(entry["video_id"])
        if linked:
            path, metadata = linked
            available += 1
            transcript = obsidian_link(path, entry["title"])
            method = metadata.get("transcript_method", "transcript")
            related = metadata.get("source_url") if str(metadata.get("source_id", "")).startswith("podcast:") else None
            suffix = f" · [related podcast]({related})" if related else ""
            lines.append(f"- {transcript} · [video]({entry['url']}){suffix} · {method}")
            rows.append({
                "video_id": entry["video_id"], "video_title": entry["title"],
                "video_url": entry["url"], "source_note": str(path.relative_to(WIKI)),
                "source_id": metadata.get("source_id"), "related_podcast_url": related,
                "transcript_method": method,
            })
        else:
            lines.append(f"- {entry['title'].replace('[', '(').replace(']', ')')} · [video]({entry['url']}) · transcript pending")
            rows.append({
                "video_id": entry["video_id"], "video_title": entry["title"],
                "video_url": entry["url"], "source_note": None,
                "source_id": entry["source_id"], "related_podcast_url": None,
                "transcript_method": None,
            })
    lines.insert(2, f"{len(entries)} videos inventoried; {available} have timestamped transcripts and {len(entries) - available} are pending local transcription.")
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    ARCHIVE.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    LINK_REPORT.parent.mkdir(parents=True, exist_ok=True)
    LINK_REPORT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return available


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--index-only", action="store_true")
    args = parser.parse_args()
    entries = load_entries()
    if not args.index_only:
        existing = note_map()
        queue = [entry for entry in entries if entry["video_id"] not in existing]
        if args.limit is not None:
            queue = queue[:args.limit]
        written = no_captions = 0
        for index, entry in enumerate(queue, 1):
            print(f"[{index}/{len(queue)}] {entry['title']}", flush=True)
            caption = download_caption(entry)
            if not caption:
                print("  no usable English captions", flush=True)
                no_captions += 1
                continue
            try:
                path, blocks = write_note(entry, caption)
            except ValueError as error:
                print(f"  unusable captions: {error}", flush=True)
                no_captions += 1
                continue
            print(f"  wrote {path.relative_to(ROOT)} ({blocks} blocks)", flush=True)
            written += 1
        print(f"Caption pass: {written} written; {no_captions} without usable captions.", flush=True)
    available = write_archive(entries)
    print(f"Archive coverage: {available}/{len(entries)} videos.", flush=True)


if __name__ == "__main__":
    main()
