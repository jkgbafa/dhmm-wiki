#!/usr/bin/env python3
"""Match Adelaide podcast episodes to her YouTube uploads and fetch captions.

The podcast episode remains the canonical source record. When a matching
YouTube upload exists, its captions provide a faster timestamped transcript and
clickable timestamp citations. Unmatched episodes remain queued for Whisper.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import subprocess
import unicodedata
from pathlib import Path

from fetch_marriage_youtube_captions import caption_blocks
from transcribe_marriage_podcasts import safe_filename, timestamp


ROOT = Path(__file__).resolve().parent.parent
WIKI = ROOT / "Marriage Wiki"
MANIFEST = WIKI / "raw" / "manifests" / "adelaide-heward-mills.jsonl"
CHANNEL_URL = "https://www.youtube.com/channel/UCenqWBA8Z_nMMg4gcJzaUhQ/videos"
CAPTIONS = WIKI / "raw" / "captions" / "Adelaide Heward-Mills"
SOURCES = WIKI / "sources" / "Adelaide Heward-Mills"
REPORT = WIKI / "_meta" / "adelaide-youtube-matches.jsonl"
YTDLP = "/opt/homebrew/bin/yt-dlp"
# These records share generic sermon wording with a different event recording.
# Keep them on the podcast-audio transcription path so citations remain exact.
EXCLUDED_PODCAST_IDS = {"podcast:65c553119cb1a8b4"}


def normalize(value):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = value.lower().replace("&", " and ")
    value = re.sub(r"^\s*\d+[.:-]?\s*", "", value)
    value = re.sub(r"\bs\d+\s*e\d+\b", " ", value)
    value = re.sub(r"\b(?:episode|ep)\.?\s*\d+\b", " ", value)
    value = re.sub(r"\bfirst love conversations\b", " ", value)
    value = re.sub(r"\bspecial edition\b", " ", value)
    value = re.sub(r"\b(?:part|pt)\.?\s*(\d+)\b", r" part \1 ", value)
    value = re.sub(r"\bquestions?\s*(?:and|&)\s*answers?\b", " q and a ", value)
    value = re.sub(r"\bq\s*(?:and|&)\s*a\b", " q and a ", value)
    return " ".join(re.findall(r"[a-z0-9]+", value))


def youtube_inventory():
    result = subprocess.run(
        [YTDLP, "--flat-playlist", "--dump-single-json", "--no-warnings", CHANNEL_URL],
        check=True, capture_output=True, text=True,
    )
    return json.loads(result.stdout).get("entries", [])


def similarity(podcast, video):
    left, right = normalize(podcast["title"]), normalize(video.get("title", ""))
    sequence_score = difflib.SequenceMatcher(None, left, right).ratio()
    left_tokens, right_tokens = set(left.split()), set(right.split())
    overlap = len(left_tokens & right_tokens) / max(1, min(len(left_tokens), len(right_tokens)))
    title_score = max(sequence_score, overlap * 0.96)
    p_duration = podcast.get("duration_seconds") or 0
    v_duration = video.get("duration") or 0
    duration_score = min(p_duration, v_duration) / max(p_duration, v_duration) if p_duration and v_duration else 0.5
    score = title_score * 0.88 + duration_score * 0.12
    return score, title_score, duration_score


def match_entries(podcasts, videos):
    candidates = []
    for p_index, podcast in enumerate(podcasts):
        for v_index, video in enumerate(videos):
            score, title_score, duration_score = similarity(podcast, video)
            left = normalize(podcast["title"])
            right = normalize(video.get("title", ""))
            sequence_score = difflib.SequenceMatcher(None, left, right).ratio()
            # Token overlap is useful for long titles, but it can make a
            # one-word title such as "Grace" look like a strong match for an
            # unrelated longer message. Require close wording for short titles
            # and a conservative floor for every automatic match.
            short_title_safe = min(len(left.split()), len(right.split())) > 3 or sequence_score >= 0.78
            if title_score >= 0.80 and short_title_safe and (duration_score >= 0.55 or title_score >= 0.94):
                candidates.append((score, title_score, duration_score, p_index, v_index))
    used_podcasts, used_videos, matches = set(), set(), []
    for score, title_score, duration_score, p_index, v_index in sorted(candidates, reverse=True):
        if p_index in used_podcasts or v_index in used_videos:
            continue
        used_podcasts.add(p_index)
        used_videos.add(v_index)
        matches.append((podcasts[p_index], videos[v_index], score, title_score, duration_score))
    return sorted(matches, key=lambda item: podcasts.index(item[0]))


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
        "speaker": ["Adelaide Heward-Mills"], "speaker_attribution": "feed_and_channel_creator_unverified",
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
        f"[Open the podcast episode]({entry['url']}) · [Watch the matching YouTube message]({video_url})", "",
        "> [!warning] Automated transcript",
        "> This transcript comes from YouTube automatic captions and has not been human-reviewed. Verify wording against the message before relying on a quotation.",
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
    matches = [item for item in matches if item[0]["source_id"] not in EXCLUDED_PODCAST_IDS]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    report_rows = []
    for podcast, video, score, title_score, duration_score in matches:
        report_rows.append({
            "podcast_source_id": podcast["source_id"], "podcast_title": podcast["title"],
            "youtube_id": video["id"], "youtube_title": video.get("title"),
            "score": round(score, 4), "title_score": round(title_score, 4),
            "duration_score": round(duration_score, 4),
        })
    REPORT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in report_rows), encoding="utf-8")
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
