#!/usr/bin/env python3
"""Build human indexes and chatbot-ready JSONL from timestamped source notes."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WIKI = ROOT / "Marriage Wiki"
MANIFESTS = WIKI / "raw" / "manifests"
SOURCES = WIKI / "sources"
INDEX_DIR = WIKI / "wiki" / "Sources"
CHATBOT_DIR = WIKI / "_chatbot"

SERIES = (
    ("Adelaide Heward-Mills", "adelaide-heward-mills.jsonl", "adelaide-heward-mills.jsonl"),
    ("First Love Conversations", "first-love-conversations.jsonl", "first-love-conversations.jsonl"),
    ("Joshua Heward-Mills — Meeting God", "joshua-heward-mills.jsonl", "joshua-heward-mills.jsonl"),
)

FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
BLOCK_RE = re.compile(r"^\[(\d{2}):(\d{2}):(\d{2})\](?:\(([^)]+)\))?\s+(.*)$")

TOPIC_PATTERNS = {
    "Biblical foundations and purpose": r"\bmarriage\b|marital|godly home|marriage covenant|genesis 2|ephesians 5",
    "Choosing a partner": r"choos\w* (?:a |your )?(?:partner|wife|husband)|who (?:to|should) marry|marry the right",
    "Dating and courtship": r"\bdating\b|courtship|boyfriend|girlfriend|romantic relationship|relationship tips",
    "Readiness, expectations, and premarital preparation": r"premarital|marriage school|ready (?:for|to) marry|prepare\w* for marriage|expectations? in marriage",
    "Communication and listening": r"communicat\w*|listen\w* to (?:your|my) (?:wife|husband|spouse)|silent treatment",
    "Conflict resolution and problem solving": r"conflict resolution|problem solving|quarrel\w*|fighting (?:in|with)|argument\w*|resolve\w* conflict",
    "Roles, partnership, and service": r"spousal dut\w*|gender roles|wives submit|submit\w* to (?:your|their) husband|husbands love|help ?meet|head of the wife",
    "Love, friendship, and emotional connection": r"love life|rekindl\w*|emotional connection|affection|companionship|friendship in marriage|love language",
    "Trust, faithfulness, forgiveness, and reconciliation": r"unfaithful\w*|faithfulness in marriage|marital faithfulness|forgiv\w* (?:your|my) (?:wife|husband|spouse)|reconcil\w*|renewing vows|trust (?:your|my) (?:wife|husband|spouse)",
    "Sex, intimacy, pornography, and purity": r"\bsex(?:ual|ually)?\b|intimacy|porn(?:ography)?|fornicat\w*|adulter\w*|marriage bed|conjugal|kissing",
    "Temperaments and emotional maturity": r"temperaments?|emotional intelligence|emotional maturity|self[ -]control in marriage",
    "Money, work, home, and practical responsibilities": r"finances? in marriage|money and marriage|household responsibilit|provid\w* for (?:the|your) family|domestic dut",
    "Ministry and family balance": r"ministry (?:life )?and family|family and ministry|balanc\w* ministry|pastor.s (?:wife|husband|family)",
    "In-laws and extended family": r"in[ -]?laws?|mother[ -]in[ -]law|father[ -]in[ -]law|extended family",
    "Parenting, motherhood, and fatherhood": r"\bparent(?:s|ing|hood)?\b|motherhood|fatherhood|raising (?:a |your )?child|bring\w* up (?:a |your )?child|childhood trauma",
    "Seasons, hardship, healing, and renewal": r"changing seasons|healing hearts|marriage work|restore\w* (?:a |your |the )?marriage|wounded (?:wife|husband|spouse)|difficult marriage",
    "Separation, divorce, remarriage, and widowhood": r"\bdivorc\w*|separat\w* from (?:your|my) (?:wife|husband|spouse)|remarri\w*|widowhood|widower",
    "Singleness": r"\bsingleness\b|single (?:man|woman|person|people|christian)|unmarried",
    "Abuse, coercion, danger, and safeguarding": r"domestic abuse|domestic violence|abusive (?:wife|husband|spouse|marriage)|coercive control|sexual assault|physical violence",
}
COMPILED_TOPICS = {name: re.compile(pattern, re.I) for name, pattern in TOPIC_PATTERNS.items()}


def parse_frontmatter(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    match = FM_RE.match(text)
    if not match:
        return {}, text
    metadata = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        try:
            metadata[key] = json.loads(value)
        except json.JSONDecodeError:
            metadata[key] = value
    return metadata, text[match.end():]


def source_notes():
    notes = {}
    for path in SOURCES.rglob("*.md"):
        metadata, body = parse_frontmatter(path)
        source_id = metadata.get("source_id")
        if source_id:
            notes[source_id] = (path, metadata, body)
    return notes


def classify_document(metadata, body):
    title = metadata.get("title", "")
    words = max(len(body.split()), 200)
    topics = []
    for topic, pattern in COMPILED_TOPICS.items():
        title_hit = bool(pattern.search(title))
        hits = len(pattern.findall(body))
        if title_hit or hits >= 8 or (hits >= 4 and hits * 1000 / words >= 1.5):
            topics.append(topic)
    return topics


def enrich_topics(notes):
    enriched = {}
    for source_id, (path, metadata, body) in notes.items():
        metadata = dict(metadata)
        metadata["topics"] = classify_document(metadata, body)
        enriched[source_id] = (path, metadata, body)
    return enriched


def load_manifest(filename):
    path = MANIFESTS / filename
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def duration_label(seconds):
    if not seconds:
        return "duration unknown"
    hours, remainder = divmod(int(seconds), 3600)
    minutes = remainder // 60
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"


def obsidian_link(path, label):
    relative = path.relative_to(WIKI).with_suffix("")
    label = label.replace("|", "—")
    return f"[[{relative}|{label}]]"


def markdown_label(value):
    return value.replace("[", "(").replace("]", ")")


def build_indexes(notes):
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    overview = ["# All Sources", "", "Every inventoried source has an external link to its original episode or video. A wiki link appears when a timestamped transcript is available.", ""]
    total = available = 0
    for label, manifest_name, _ in SERIES:
        entries = load_manifest(manifest_name)
        total += len(entries)
        have = sum(entry["source_id"] in notes for entry in entries)
        available += have
        page_path = INDEX_DIR / f"{label} Index.md"
        overview.append(f"- [[wiki/Sources/{label} Index|{label}]] — {have}/{len(entries)} timestamped transcripts available")
        lines = [f"# {label}", "", f"{len(entries)} inventoried sources; {have} currently have timestamped transcripts.", ""]
        for entry in entries:
            title = entry["title"]
            original = f"[original]({entry['url']})"
            details = [duration_label(entry.get("duration_seconds"))]
            if entry.get("published"):
                details.insert(0, entry["published"])
            if entry["source_id"] in notes:
                path, _, _ = notes[entry["source_id"]]
                transcript = obsidian_link(path, title)
                status = "transcript"
            else:
                transcript = markdown_label(title)
                status = "transcript pending"
            lines.append(f"- {transcript} · {original} · {' · '.join(details)} · {status}")
        page_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    overview.insert(2, f"{total} sources inventoried; {available} currently have timestamped transcripts.")
    (WIKI / "wiki" / "All Sources.md").write_text("\n".join(overview).rstrip() + "\n", encoding="utf-8")
    return total, available


def build_topic_indexes(notes):
    topic_dir = WIKI / "wiki" / "Topics"
    topic_dir.mkdir(parents=True, exist_ok=True)
    index = ["# Marriage Topics", "", "Topic membership is detected from transcript content and titles. Treat it as a discovery layer; verify teaching against the timestamped source.", ""]
    for topic in TOPIC_PATTERNS:
        matches = [(path, metadata) for path, metadata, _ in notes.values() if topic in metadata.get("topics", [])]
        index.append(f"- [[wiki/Topics/{topic}|{topic}]] — {len(matches)} sources")
        page = [f"# {topic}", "", f"{len(matches)} timestamped sources currently discuss this topic.", ""]
        for path, metadata in sorted(matches, key=lambda item: (item[1].get("series", ""), item[1].get("title", ""))):
            title = metadata.get("title", path.stem)
            page.append(f"- {obsidian_link(path, title)} · [original]({metadata.get('source_url', '')}) · {metadata.get('series', '')}")
        (topic_dir / f"{topic}.md").write_text("\n".join(page).rstrip() + "\n", encoding="utf-8")
    (topic_dir / "Marriage Topics.md").write_text("\n".join(index).rstrip() + "\n", encoding="utf-8")


def iter_chunks(path, metadata, body):
    for line in body.splitlines():
        match = BLOCK_RE.match(line.strip())
        if not match:
            continue
        hours, minutes, seconds, timestamp_url, text = match.groups()
        start_seconds = int(hours) * 3600 + int(minutes) * 60 + int(seconds)
        source_url = metadata.get("source_url", "")
        chunk_topics = [topic for topic, pattern in COMPILED_TOPICS.items() if pattern.search(text)]
        yield {
            "chunk_id": f"{metadata['source_id']}:{start_seconds}",
            "source_id": metadata["source_id"],
            "title": metadata.get("title", path.stem),
            "speaker": metadata.get("speaker", []),
            "speaker_attribution": metadata.get("speaker_attribution"),
            "series": metadata.get("series"),
            "platform": metadata.get("platform"),
            "published": metadata.get("published"),
            "document_topics": metadata.get("topics", []),
            "chunk_topics": chunk_topics,
            "transcript_method": metadata.get("transcript_method"),
            "transcript_status": metadata.get("transcript_status"),
            "start_seconds": start_seconds,
            "timestamp": f"{hours}:{minutes}:{seconds}",
            "source_url": source_url,
            "timestamp_url": timestamp_url or source_url,
            "source_note": str(path.relative_to(WIKI)),
            "text": text,
        }


def build_chatbot_corpus(notes):
    CHATBOT_DIR.mkdir(parents=True, exist_ok=True)
    counts = {}
    for label, _, output_name in SERIES:
        chunks = []
        for path, metadata, body in notes.values():
            note_label = "Joshua Heward-Mills — Meeting God" if metadata.get("series") == "Meeting God" else metadata.get("series")
            if note_label == label:
                chunks.extend(iter_chunks(path, metadata, body))
        chunks.sort(key=lambda chunk: (chunk["source_id"], chunk["start_seconds"]))
        output_path = CHATBOT_DIR / output_name
        output_path.write_text("".join(json.dumps(chunk, ensure_ascii=False, sort_keys=True) + "\n" for chunk in chunks), encoding="utf-8")
        counts[label] = len(chunks)
    readme = [
        "# Chatbot corpus", "",
        "Each JSONL row is one timestamped evidence chunk. Use `text` for retrieval and preserve `source_url`, `timestamp_url`, `title`, `speaker`, and `start_seconds` when generating citations.", "",
        "Never treat an unverified automatic transcript as an exact quotation without checking the source audio.", "",
    ]
    for label, count in counts.items():
        readme.append(f"- `{next(output for name, _, output in SERIES if name == label)}` — {count} chunks")
    (CHATBOT_DIR / "README.md").write_text("\n".join(readme).rstrip() + "\n", encoding="utf-8")
    return counts


def main():
    notes = enrich_topics(source_notes())
    total, available = build_indexes(notes)
    build_topic_indexes(notes)
    counts = build_chatbot_corpus(notes)
    print(f"Indexed {available}/{total} transcripts; wrote {sum(counts.values())} chatbot chunks.")


if __name__ == "__main__":
    main()
