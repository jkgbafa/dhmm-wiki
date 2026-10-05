#!/usr/bin/env python3
"""Build source inventories and a marriage-first catalog.

Run from any directory:
    python3 pipeline/build_marriage_inventory.py

If a Homebrew Python installation has a broken expat module on macOS, use:
    /usr/bin/python3 pipeline/build_marriage_inventory.py

This script downloads metadata only. It does not download audio or videos.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WIKI = ROOT / "Marriage Wiki"
MANIFESTS = WIKI / "raw" / "manifests"
CATALOG = WIKI / "wiki" / "Source Catalog.md"

PODCASTS = (
    {
        "slug": "adelaide-heward-mills",
        "series": "Adelaide Heward-Mills",
        "creator": "Adelaide Heward-Mills",
        "feed": "https://feed.podbean.com/adelaidehewardmills/feed.xml",
        "apple": "https://podcasts.apple.com/gb/podcast/adelaide-heward-mills/id745002006",
    },
    {
        "slug": "first-love-conversations",
        "series": "First Love Conversations",
        "creator": "First Love Church HQ",
        "feed": "https://feed.podbean.com/firstlovecpodcast/feed.xml",
        "apple": "https://podcasts.apple.com/gb/podcast/first-love-conversations/id1761275461",
    },
)

YOUTUBE = (
    {
        "slug": "joshua-heward-mills",
        "series": "Meeting God",
        "creator": "Joshua Heward-Mills",
        "url": "https://www.youtube.com/@MeetingGod_/videos",
    },
    {
        "slug": "adelaide-heward-mills-youtube",
        "series": "Adelaide Heward-Mills — YouTube",
        "creator": "Adelaide Heward-Mills",
        "url": "https://www.youtube.com/@ladyrev.adelaideheward-mil9109/videos",
    },
)

TOPICS = {
    "Choosing a partner": r"choos(?:e|ing).*(?:partner|wife|husband)|who (?:should|to) marry",
    "Dating and courtship": r"\b(?:dating|courtship|marry early|love life|relationships?)\b",
    "Communication and listening": r"\bcommunicat(?:e|ion|ing)|\blistening\b",
    "Conflict resolution and problem solving": r"conflict resolution|problem solving|without fighting|quarrel",
    "Roles, partnership, and service": r"spousal duties|gender roles|\b(?:wife|wives|husband|spouse)\b",
    "Love, friendship, and emotional connection": r"rekindling|emotional (?:connection|intelligence)|three kinds of love|too late for love",
    "Trust, faithfulness, forgiveness, and reconciliation": r"faithfulness|unfaithfulness|forgiveness|reconciliation|renewing vows|acceptance",
    "Sex, intimacy, pornography, and purity": r"\b(?:sex|intimacy|porn(?:ography)?|purity|kissing|adulter\w*|fornicat\w*)\b|how far is too far",
    "Temperaments and emotional maturity": r"temperaments?|emotional intelligence|emotional maturity",
    "Ministry and family balance": r"ministry (?:life )?and family|family and ministry|balancing ministry",
    "Parenting, motherhood, and fatherhood": r"\b(?:parent(?:s|ing)?|mother(?:s|hood)?|father(?:s|hood)?|childhood)\b",
    "Seasons, hardship, healing, and renewal": r"changing seasons|healing hearts|renewing vows|rekindling|marriage work",
    "Singleness": r"\b(?:single|singleness)\b",
    "Biblical foundations and purpose": r"\bmarriage\b|godly home",
}
COMPILED_TOPICS = {name: re.compile(pattern, re.I) for name, pattern in TOPICS.items()}
MARRIAGE_CUE = re.compile(
    r"\b(?:marriage|marriages|married|spousal|spouse|dating|courtship|partner|"
    r"relationships|porn(?:ography)?|sex|intimacy|purity|kissing|fornicat\w*|adulter\w*|"
    r"parent(?:s|ing)?|mother(?:s|hood)?|father(?:s|hood)?|childhood|temperaments?)\b|"
    r"godly home|love life|too late for love|gender roles|renewing vows|rekindling|"
    r"ministry (?:life )?and family|family and ministry|balancing ministry|"
    r"choos(?:e|ing).*(?:partner|wife|husband)|your (?:wife|husband)|wives|husbands",
    re.I,
)
TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "dhmm-wiki-inventory/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def clean_html(value: str) -> str:
    return SPACE_RE.sub(" ", html.unescape(TAG_RE.sub(" ", value or ""))).strip()


def child_text(node: ET.Element, local_name: str) -> str:
    for child in node:
        if child.tag.rsplit("}", 1)[-1] == local_name:
            return (child.text or "").strip()
    return ""


def parse_duration(value: str):
    value = (value or "").strip()
    if not value:
        return None
    if value.isdigit():
        return int(value)
    try:
        pieces = [int(piece) for piece in value.split(":")]
    except ValueError:
        return None
    seconds = 0
    for piece in pieces:
        seconds = seconds * 60 + piece
    return seconds


def iso_date(value: str):
    try:
        return parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError, OverflowError):
        return None


def classify(title: str, description: str):
    title_topics = [name for name, pattern in COMPILED_TOPICS.items() if pattern.search(title)]
    full_topics = set(title_topics)
    full_topics.update(name for name, pattern in COMPILED_TOPICS.items() if pattern.search(description))
    relevance = "high" if MARRIAGE_CUE.search(title) else "medium" if MARRIAGE_CUE.search(description) else "none"
    return sorted(full_topics), relevance


def stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def podcast_entries(config):
    root = ET.fromstring(fetch(config["feed"]))
    items = root.findall("./channel/item")
    entries = []
    for item in items:
        title = child_text(item, "title")
        description = clean_html(child_text(item, "description") or child_text(item, "summary"))
        guid = child_text(item, "guid")
        page_url = child_text(item, "link")
        enclosure = next((child for child in item if child.tag.rsplit("}", 1)[-1] == "enclosure"), None)
        audio_url = enclosure.get("url", "") if enclosure is not None else ""
        duration = parse_duration(child_text(item, "duration"))
        topics, relevance = classify(title, description)
        identity = guid or audio_url or page_url or title
        entries.append({
            "source_id": stable_id("podcast", identity),
            "series": config["series"],
            "creator": config["creator"],
            "platform": "Podcast",
            "title": title,
            "url": page_url or config["apple"],
            "apple_podcasts_url": config["apple"],
            "audio_url": audio_url,
            "published": iso_date(child_text(item, "pubDate")),
            "duration_seconds": duration,
            "description": description,
            "topics": topics,
            "marriage_relevance": relevance,
        })
    return entries


def youtube_entries(config):
    command = ["/opt/homebrew/bin/yt-dlp", "--flat-playlist", "--dump-single-json", "--no-warnings", config["url"]]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    entries = []
    for item in payload.get("entries", []):
        video_id = item.get("id", "")
        title = item.get("title", "")
        description = clean_html(item.get("description") or "")
        topics, relevance = classify(title, description)
        entries.append({
            "source_id": f"youtube:{video_id}",
            "series": config["series"],
            "creator": config["creator"],
            "platform": "YouTube",
            "title": title,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "video_id": video_id,
            "published": None,
            "duration_seconds": item.get("duration"),
            "description": description,
            "topics": topics,
            "marriage_relevance": relevance,
        })
    return entries


def write_jsonl(path: Path, entries):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n" for entry in entries)
    path.write_text(text, encoding="utf-8")


def duration_label(seconds):
    if not seconds:
        return "duration unknown"
    hours, remainder = divmod(int(seconds), 3600)
    minutes = remainder // 60
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"


def write_catalog(collections):
    lines = [
        "# Source Catalog",
        "",
        "Generated from the public podcast feeds and the Meeting God YouTube channel. "
        "`High` means the episode title directly matches the marriage taxonomy; `medium` means only its description matches. "
        "Classification is a discovery aid and must be confirmed from the transcript.",
        "",
    ]
    for label, entries in collections:
        high = [entry for entry in entries if entry["marriage_relevance"] == "high"]
        medium = [entry for entry in entries if entry["marriage_relevance"] == "medium"]
        lines += [f"## {label}", "", f"{len(entries)} total sources; {len(high)} high-priority and {len(medium)} medium-priority marriage candidates.", ""]
        for entry in high:
            topics = ", ".join(entry["topics"])
            published = f" · {entry['published']}" if entry.get("published") else ""
            lines.append(f"- [{entry['title']}]({entry['url']}) — {duration_label(entry.get('duration_seconds'))}{published} · {topics}")
        if not high:
            lines.append("- No title-level marriage matches found.")
        lines.append("")
    CATALOG.parent.mkdir(parents=True, exist_ok=True)
    CATALOG.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main():
    MANIFESTS.mkdir(parents=True, exist_ok=True)
    collections = []
    for config in PODCASTS:
        entries = podcast_entries(config)
        write_jsonl(MANIFESTS / f"{config['slug']}.jsonl", entries)
        collections.append((config["series"], entries))
    for config in YOUTUBE:
        entries = youtube_entries(config)
        write_jsonl(MANIFESTS / f"{config['slug']}.jsonl", entries)
        collections.append((f"{config['creator']} / {config['series']}", entries))
    write_catalog(collections)
    total = sum(len(entries) for _, entries in collections)
    priority = sum(1 for _, entries in collections for entry in entries if entry["marriage_relevance"] == "high")
    print(f"Wrote {total} source records; {priority} high-priority marriage candidates.")


if __name__ == "__main__":
    main()
