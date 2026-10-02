#!/usr/bin/env python3
"""Match First Love Conversations podcast episodes to YouTube and fetch captions."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from fetch_adelaide_youtube_captions import match_entries
from fetch_marriage_youtube_captions import caption_blocks
from transcribe_marriage_podcasts import safe_filename, timestamp


ROOT = Path(__file__).resolve().parent.parent
WIKI = ROOT / "Marriage Wiki"
MANIFEST = WIKI / "raw" / "manifests" / "first-love-conversations.jsonl"
CHANNEL_URL = "https://www.youtube.com/channel/UCEBUZZ9Gyaek_l92J728Yuw/videos"
CAPTIONS = WIKI / "raw" / "captions" / "First Love Conversations"
SOURCES = WIKI / "sources" / "First Love Conversations"
REPORT = WIKI / "_meta" / "first-love-youtube-matches.jsonl"
YTDLP = "/opt/homebrew/bin/yt-dlp"


def youtube_inventory():
    result = subprocess.run(
        [YTDLP, "--flat-playlist", "--dump-single-json", "--no-warnings", CHANNEL_URL],
        check=True, capture_output=True, text=True,
    )
    return json.loads(result.stdout).get("entries", [])


def note_path(entry):
    short_id = entry["source_id"].split(":", 1)[-1]
    return SOURCES / f"{safe_filename(entry['title'])} [{short_id}].md"


def already_done(entry):
    path = note_path(entry)
    suffix = f" [{entry['source_id'].split(':', 1)[-1]}].md"
    return path.exists() or (SOURCES.exists() and any(candidate.name.endswith(suffix) for candidate in SOURCES.glob("*.md")))


def download_caption(video):
    CAPTIONS.mkdir(parents=True, exist_ok=True)
    video_id = video["id"]
    existing = sorted(CAPTIONS.glob(f"{video_id}.*.json3"))
    if existing:
        return existing[0]
    url = f"https://www.youtube.com/watch?v={video_id}"
    for language in ("en-orig", "en"):
        try:
            subprocess.run([
                YTDLP, "--skip-download", "--write-subs", "--write-auto-subs",
                "--sub-langs", language, "--sub-format", "json3", "--no-warnings", "--no-progress",
                "-o", str(CAPTIONS / f"{video_id}.%(ext)s"), url,
            ], check=True)
        except subprocess.CalledProcessError:
            continue
        matches = sorted(CAPTIONS.glob(f"{video_id}.*.json3"))
        if matches:
            return matches[0]
    return None


def write_note(entry, video, caption_path):
    payload = json.loads(caption_path.read_text(encoding="utf-8"))
    blocks = caption_blocks(payload)
    video_url = f"https://www.youtube.com/watch?v={video['id']}"
    metadata = {
        "title": entry["title"], "source_id": entry["source_id"],
        "speaker": [], "speaker_attribution": "not_identified",
        "series": entry["series"], "platform": "Podcast + YouTube",
        "source_url": entry["url"], "audio_url": entry.get("audio_url"),
        "video_url": video_url, "video_id": video["id"],
        "published": entry.get("published"), "duration_seconds": entry.get("duration_seconds"),
        "transcript_method": "youtube_auto_captions", "transcript_status": "unverified",
        "topics": entry.get("topics", []), "raw_caption": str(caption_path.relative_to(WIKI)),
    }
    lines = ["---"]
    for key, value in metadata.items():
        if value is not None:
            lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    lines += [
        "---", "", f"# {entry['title']}", "",
        f"[Open the podcast episode]({entry['url']}) · [Watch the matching YouTube episode]({video_url})", "",
        "> [!warning] Automated transcript",
        "> This transcript comes from YouTube automatic captions and has not been human-reviewed. Verify wording against the episode before relying on a quotation.",
        "", "## Transcript", "",
    ]
    for start, text in blocks:
        seconds = start // 1000
        lines += [f"[{timestamp(seconds)}]({video_url}&t={seconds}s) {text}", ""]
    path = note_path(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path, len(blocks)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    podcasts = [json.loads(line) for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line.strip()]
    videos = youtube_inventory()
    matches = match_entries(podcasts, videos)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for podcast, video, score, title_score, duration_score in matches:
        rows.append({
            "podcast_source_id": podcast["source_id"], "podcast_title": podcast["title"],
            "youtube_id": video["id"], "youtube_title": video.get("title"),
            "score": round(score, 4), "title_score": round(title_score, 4),
            "duration_score": round(duration_score, 4),
        })
    REPORT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    print(f"Matched {len(matches)}/{len(podcasts)} podcast episodes to {len(videos)} YouTube uploads.")
    if args.dry_run:
        return
    queue = [(podcast, video) for podcast, video, *_ in matches if not already_done(podcast)]
    if args.limit is not None:
        queue = queue[:args.limit]
    written = skipped = 0
    for index, (podcast, video) in enumerate(queue, 1):
        print(f"[{index}/{len(queue)}] {podcast['title']} ↔ {video.get('title')}", flush=True)
        try:
            caption = download_caption(video)
            if not caption:
                print("  no English captions", flush=True)
                skipped += 1
                continue
            path, blocks = write_note(podcast, video, caption)
            print(f"  wrote {path.relative_to(ROOT)} ({blocks} blocks)", flush=True)
            written += 1
        except Exception as error:
            print(f"  ERROR: {error}", flush=True)
            skipped += 1
    print(f"Done: {written} transcripts; {skipped} matched videos without usable captions.")


if __name__ == "__main__":
    main()
