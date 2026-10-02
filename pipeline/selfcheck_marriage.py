#!/usr/bin/env python3
"""Sanity checks for the separate marriage wiki and its generated inventories."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WIKI = ROOT / "Marriage Wiki"
MANIFESTS = WIKI / "raw" / "manifests"


def load(name):
    return [json.loads(line) for line in (MANIFESTS / name).read_text(encoding="utf-8").splitlines() if line.strip()]


adelaide = load("adelaide-heward-mills.jsonl")
first_love = load("first-love-conversations.jsonl")
joshua = load("joshua-heward-mills.jsonl")

assert len(adelaide) >= 300
assert len(first_love) >= 33
assert len(joshua) >= 300
assert all(entry.get("source_id") and entry.get("url") for entry in adelaide + first_love + joshua)
assert sum(entry.get("marriage_relevance") == "high" for entry in adelaide + first_love + joshua) >= 50

source_dir = WIKI / "sources" / "Joshua Heward-Mills"
notes = sorted(source_dir.glob("*.md"))
captions = sorted((WIKI / "raw" / "captions" / "Joshua Heward-Mills").glob("*.json3"))
assert len(notes) >= 3 and len(captions) >= 3
for note in notes:
    text = note.read_text(encoding="utf-8")
    assert 'transcript_status: "unverified"' in text
    assert "youtube.com/watch?v=" in text and "&t=" in text
    assert "## Transcript" in text

schema = (WIKI / "SCHEMA.md").read_text(encoding="utf-8")
assert "Raw sources are immutable" in schema
assert "Marriage-chatbot safety rules" in schema

print("marriage wiki selfcheck ok")
