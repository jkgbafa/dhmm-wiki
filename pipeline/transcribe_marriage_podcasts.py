#!/usr/bin/env python3
"""Resume-safe local transcription for the two marriage-wiki podcast feeds.

Uses MLX Whisper on Apple Silicon, retains segment timestamps, writes a compact
ASR record, and deletes each temporary audio file after processing.

Recommended invocation on this Mac:
    /usr/bin/python3 pipeline/transcribe_marriage_podcasts.py --series all
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WIKI = ROOT / "Marriage Wiki"
MANIFESTS = WIKI / "raw" / "manifests"
ASR_ROOT = WIKI / "raw" / "asr"
SOURCE_ROOT = WIKI / "sources"
STATE_PATH = WIKI / "_meta" / "podcast-transcription-state.json"
TMP = ROOT / "pipeline" / "tmp" / "marriage-podcasts"
MODEL = "mlx-community/whisper-large-v3-turbo"

os.environ["PATH"] = "/Users/joshuagbafa/Library/Python/3.9/bin:/Users/joshuagbafa/.local/bin:" + os.environ.get("PATH", "")

SERIES = {
    "first-love": {
        "manifest": "first-love-conversations.jsonl",
        "folder": "First Love Conversations",
        "speakers": [],
        "speaker_attribution": "not_identified",
    },
    "adelaide": {
        "manifest": "adelaide-heward-mills.jsonl",
        "folder": "Adelaide Heward-Mills",
        "speakers": ["Adelaide Heward-Mills"],
        "speaker_attribution": "feed_creator_unverified",
    },
}

CUE_RE = re.compile(r"\[[^\]]+\]", re.I)
SPACE_RE = re.compile(r"\s+")


def load_entries(key):
    config = SERIES[key]
    path = MANIFESTS / config["manifest"]
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def safe_filename(value):
    value = re.sub(r'[<>:"/\\|?*]', "", value)
    value = SPACE_RE.sub(" ", value).strip(". ")
    return value[:175] or "untitled"


def short_id(entry):
    return entry["source_id"].split(":", 1)[-1]


def output_path(key, entry):
    return WIKI / "sources" / SERIES[key]["folder"] / f"{safe_filename(entry['title'])} [{short_id(entry)}].md"


def completed(key, entry):
    expected = output_path(key, entry)
    if expected.exists():
        return True
    folder = expected.parent
    suffix = f" [{short_id(entry)}].md"
    return folder.exists() and any(path.name.endswith(suffix) for path in folder.glob("*.md"))


def clean_text(value):
    value = CUE_RE.sub(" ", value or "")
    return SPACE_RE.sub(" ", value).strip()


def timestamp(seconds):
    seconds = max(0, int(seconds))
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def normalize_segments(result):
    segments = []
    for segment in result.get("segments", []):
        text = clean_text(segment.get("text", ""))
        if not text:
            continue
        segments.append({
            "start": round(float(segment.get("start", 0)), 3),
            "end": round(float(segment.get("end", segment.get("start", 0))), 3),
            "text": text,
        })
    return segments


def transcript_blocks(segments):
    blocks = []
    start = None
    text_parts = []
    words = 0
    for segment in segments:
        if start is None:
            start = segment["start"]
        segment_words = len(segment["text"].split())
        if text_parts and (segment["start"] - start >= 45 or words + segment_words > 120):
            blocks.append((start, " ".join(text_parts)))
            start, text_parts, words = segment["start"], [], 0
        text_parts.append(segment["text"])
        words += segment_words
    if text_parts:
        blocks.append((start, " ".join(text_parts)))
    return blocks


def download_audio(entry, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    original = destination.with_suffix(".download")
    normalized = destination.with_suffix(".m4a")
    subprocess.run([
        "curl", "--fail", "--location", "--retry", "3", "--retry-delay", "2",
        "--silent", "--show-error", "--output", str(original), entry["audio_url"],
    ], check=True, timeout=1800)
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(original),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "aac", "-b:a", "32k", str(normalized),
    ], check=True, timeout=1800)
    original.unlink(missing_ok=True)
    if not normalized.exists() or normalized.stat().st_size < 10_000:
        raise RuntimeError("normalized audio is missing or too small")
    return normalized


def save_asr(key, entry, result, segments):
    folder = ASR_ROOT / SERIES[key]["folder"]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{short_id(entry)}.json"
    payload = {
        "source_id": entry["source_id"],
        "model": MODEL,
        "language": result.get("language", "en"),
        "text": clean_text(result.get("text", "")),
        "segments": segments,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_source(key, entry, asr_path, segments):
    config = SERIES[key]
    path = output_path(key, entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "title": entry["title"],
        "source_id": entry["source_id"],
        "speaker": config["speakers"],
        "speaker_attribution": config["speaker_attribution"],
        "series": entry["series"],
        "platform": entry["platform"],
        "source_url": entry["url"],
        "audio_url": entry.get("audio_url"),
        "published": entry.get("published"),
        "duration_seconds": entry.get("duration_seconds"),
        "transcript_method": "mlx_whisper_large_v3_turbo",
        "transcript_status": "unverified",
        "topics": entry.get("topics", []),
        "raw_asr": str(asr_path.relative_to(WIKI)),
    }
    lines = ["---"]
    for name, value in metadata.items():
        if value is not None:
            lines.append(f"{name}: {json.dumps(value, ensure_ascii=False)}")
    lines += [
        "---", "", f"# {entry['title']}", "", f"[Open the original episode]({entry['url']})", "",
        "> [!warning] Automated transcript",
        "> This transcript was generated by speech-to-text and has not been human-reviewed. Verify wording against the audio before relying on a quotation.",
        "", "## Transcript", "",
    ]
    for start, text in transcript_blocks(segments):
        lines += [f"[{timestamp(start)}] {text}", ""]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def write_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state["updated"] = datetime.now(timezone.utc).isoformat()
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    global STATE_PATH
    parser = argparse.ArgumentParser()
    parser.add_argument("--series", choices=("first-love", "adelaide", "all"), default="all")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--shortest-first", action="store_true")
    args = parser.parse_args()
    STATE_PATH = WIKI / "_meta" / f"podcast-transcription-state-{args.series}.json"

    try:
        import mlx_whisper
    except ImportError as error:
        raise SystemExit("mlx_whisper is unavailable; run this script with /usr/bin/python3 on this Mac") from error

    keys = ["first-love", "adelaide"] if args.series == "all" else [args.series]
    queue = []
    for key in keys:
        entries = load_entries(key)
        if args.shortest_first:
            entries.sort(key=lambda entry: entry.get("duration_seconds") or 10**9)
        queue.extend((key, entry) for entry in entries if not completed(key, entry))
    if args.limit is not None:
        queue = queue[:args.limit]

    state = {"model": MODEL, "total_queued": len(queue), "completed": 0, "failed": 0, "current": None, "errors": []}
    write_state(state)
    TMP.mkdir(parents=True, exist_ok=True)
    started = time.time()

    for index, (key, entry) in enumerate(queue, 1):
        sid = short_id(entry)
        state["current"] = {"index": index, "series": key, "source_id": entry["source_id"], "title": entry["title"]}
        write_state(state)
        audio_path = None
        try:
            print(f"[{index}/{len(queue)}] {key}: {entry['title']}", flush=True)
            audio_path = download_audio(entry, TMP / sid)
            result = mlx_whisper.transcribe(str(audio_path), path_or_hf_repo=MODEL, language="en", verbose=False)
            segments = normalize_segments(result)
            if not segments:
                raise RuntimeError("speech-to-text returned no timestamped segments")
            asr_path = save_asr(key, entry, result, segments)
            note_path = write_source(key, entry, asr_path, segments)
            state["completed"] += 1
            elapsed = max(time.time() - started, 1)
            rate = state["completed"] / elapsed * 3600
            print(f"  wrote {note_path.relative_to(ROOT)} ({len(segments)} segments, {rate:.1f} episodes/hour)", flush=True)
        except KeyboardInterrupt:
            state["current"] = "interrupted"
            write_state(state)
            raise
        except Exception as error:
            state["failed"] += 1
            state["errors"].append({"source_id": entry["source_id"], "title": entry["title"], "error": str(error)[:500]})
            state["errors"] = state["errors"][-100:]
            print(f"  ERROR: {error}", flush=True)
        finally:
            if audio_path:
                audio_path.unlink(missing_ok=True)
            (TMP / sid).with_suffix(".download").unlink(missing_ok=True)
            state["current"] = None
            write_state(state)

    state["status"] = "complete"
    state["elapsed_seconds"] = round(time.time() - started, 1)
    write_state(state)
    print(f"Done: {state['completed']} completed; {state['failed']} failed.")


if __name__ == "__main__":
    main()
