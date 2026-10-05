#!/usr/bin/env python3
"""Sanity checks for the separate marriage wiki and its generated inventories."""

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WIKI = ROOT / "Marriage Wiki"
MANIFESTS = WIKI / "raw" / "manifests"


def load(name):
    return [json.loads(line) for line in (MANIFESTS / name).read_text(encoding="utf-8").splitlines() if line.strip()]


adelaide = load("adelaide-heward-mills.jsonl")
first_love = load("first-love-conversations.jsonl")
joshua = load("joshua-heward-mills.jsonl")
adelaide_youtube = load("adelaide-heward-mills-youtube.jsonl")

assert len(adelaide) == 300
assert len(first_love) == 33
assert len(joshua) == 305
assert len(adelaide_youtube) == 267
assert all(entry.get("source_id") and entry.get("url") for entry in adelaide + first_love + joshua)
assert sum(entry.get("marriage_relevance") == "high" for entry in adelaide + first_love + joshua) >= 50

SOURCE_ID_RE = re.compile(r'^source_id:\s*"([^"]+)"', re.M)
VIDEO_ID_RE = re.compile(r'^video_id:\s*"([^"]+)"', re.M)
TIMESTAMP_RE = re.compile(r'^\[\d{2}:\d{2}:\d{2}\](?:\([^)]+\))?\s+', re.M)

series_sources = {
    "Adelaide Heward-Mills": adelaide,
    "First Love Conversations": first_love,
    "Joshua Heward-Mills": joshua,
}
all_notes = []
for folder, manifest in series_sources.items():
    notes = sorted((WIKI / "sources" / folder).glob("*.md"))
    actual_ids = []
    for note in notes:
        text = note.read_text(encoding="utf-8")
        match = SOURCE_ID_RE.search(text)
        assert match, f"missing source_id: {note}"
        actual_ids.append(match.group(1))
        assert 'transcript_status: "unverified"' in text
        assert 'source_url: "http' in text
        assert "## Transcript" in text
        assert TIMESTAMP_RE.search(text), f"missing timestamped transcript: {note}"
    expected_ids = {entry["source_id"] for entry in manifest}
    assert len(actual_ids) == len(set(actual_ids)), f"duplicate source_id in {folder}"
    assert set(actual_ids) == expected_ids, (
        f"incomplete {folder}: {len(actual_ids)}/{len(expected_ids)} notes; "
        f"missing={sorted(expected_ids - set(actual_ids))[:5]}"
    )
    all_notes.extend(notes)

captions = sorted((WIKI / "raw" / "captions" / "Joshua Heward-Mills").glob("*.json3"))
assert len(captions) >= 3
for note in (WIKI / "sources" / "Joshua Heward-Mills").glob("*.md"):
    text = note.read_text(encoding="utf-8")
    assert "youtube.com/watch?v=" in text and "&t=" in text

channel_video_ids = set()
video_to_source = {}
for note in (WIKI / "sources" / "Adelaide Heward-Mills").rglob("*.md"):
    text = note.read_text(encoding="utf-8")
    video_match = VIDEO_ID_RE.search(text)
    source_match = SOURCE_ID_RE.search(text)
    if video_match and source_match:
        channel_video_ids.add(video_match.group(1))
        video_to_source[video_match.group(1)] = source_match.group(1)
expected_video_ids = {entry["video_id"] for entry in adelaide_youtube}
assert channel_video_ids == expected_video_ids, (
    f"incomplete Adelaide YouTube archive: {len(channel_video_ids)}/{len(expected_video_ids)}; "
    f"missing={sorted(expected_video_ids - channel_video_ids)[:5]}"
)

chatbot_ids = set()
for chatbot_file in (WIKI / "_chatbot").glob("*.jsonl"):
    for line in chatbot_file.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            assert row.get("source_url") and row.get("timestamp_url")
            chatbot_ids.add(row["source_id"])
core_ids = {entry["source_id"] for entry in adelaide + first_love + joshua}
assert core_ids <= chatbot_ids
assert set(video_to_source.values()) <= chatbot_ids

schema = (WIKI / "SCHEMA.md").read_text(encoding="utf-8")
assert "Raw sources are immutable" in schema
assert "Marriage-chatbot safety rules" in schema

print("marriage wiki selfcheck ok")
