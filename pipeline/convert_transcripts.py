#!/usr/bin/env python3
"""Convert scraped DHM transcripts (.txt) into Obsidian markdown notes.

Matches each transcript to its video ID by reproducing the scraper's
sanitize_filename() on CSV titles (deterministic join), cleans caption
artifacts, and writes notes with YAML frontmatter into the vault.
"""
import csv
import difflib
import html
import json
import re
import sys
from pathlib import Path

SRC = Path("/Users/joshuagbafa/Claude/Books-Channel-Youtube")
TRANSCRIPTS = SRC / "transcripts"
DATA = SRC / "data"
VAULT = Path(__file__).resolve().parent.parent

# (platform, folder) -> list of CSV filenames in DATA (first hit wins per title)
CHANNEL_CSVS = {
    ("youtube", "ChurchServices"): ["channel_videos_ChurchServices.csv"],
    ("youtube", "DagHewardMillsCrusades"): ["channel_videos_DagHewardMillsCrusades.csv"],
    ("youtube", "DagHewardMillsGTWC"): ["channel_videos_DagHewardMillsGTWC.csv"],
    ("youtube", "DagHewardMillsNations"): ["channel_videos_DagHewardMillsNations.csv"],
    ("youtube", "DagHewardMillscamps"): ["channel_videos_DagHewardMillscamps.csv"],
    ("youtube", "DagHewardMillsvideos"): ["channel_videos_DagHewardMillsvideos.csv"],
    ("youtube", "DagbooksChannel"): [],
    ("youtube", "DhmmInternationalMinistry"): [],
    ("odysee", "FlowChurchServices"): ["channel_videos_odysee_flow_church_services_urls.csv"],
    ("odysee", "FlowPrayerMeetings"): ["channel_videos_odysee_flow_prayer_meetings_urls.csv"],
    ("odysee", "ImpartationServices"): ["channel_videos_odysee_impartation_services_urls.csv"],
    ("odysee", "RevivalAt7"): ["channel_videos_odysee_revival_at_7_urls.csv"],
    ("rumble", "Conventions"): ["channel_videos_rumble_Conventions.csv"],
    ("rumble", "KorleGonno"): ["channel_videos_rumble_KorleGonno.csv"],
    ("rumble", "ShepherdsServices"): ["channel_videos_rumble_ShepherdsServices.csv"],
    ("rumble", "SoulWinnersServices"): ["channel_videos_rumble_SoulWinnersServices.csv"],
    ("rumble", "TuesdayServices"): ["channel_videos_rumble_TuesdayServices.csv"],
    ("rumble", "WisdomImpartationServices"): ["channel_videos_rumble_WisdomImpartationServices.csv"],
    ("bitchute", "IronSharpenethIron"): ["channel_videos_bitchute_IronSharpenethIron.csv"],
    ("bitchute", "LeadersServices"): ["channel_videos_bitchute_LeadersServices.csv"],
    ("bitchute", "MiracleWaveConventions"): ["channel_videos_bitchute_MiracleWaveConventions.csv"],
    ("bitchute", "OvercomersServices"): ["channel_videos_bitchute_OvercomersServices.csv"],
    ("bitchute", "Qodesh"): ["channel_videos_bitchute_Qodesh.csv"],
    ("bitchute", "UnquenchableFireServices"): ["channel_videos_bitchute_UnquenchableFireServices.csv"],
}

# master youtube CSV supplements per-channel ones
MASTER_YT = "all_youtube_channels_videos.csv"

# vault destination: FLOW gets its own top-level category
DEST = {
    ("odysee", "FlowChurchServices"): VAULT / "FLOW" / "Church Services",
    ("odysee", "FlowPrayerMeetings"): VAULT / "FLOW" / "Prayer Meetings",
}
PLATFORM_LABEL = {"youtube": "YouTube", "odysee": "Odysee", "rumble": "Rumble", "bitchute": "Bitchute"}


def sanitize_filename(title):  # exact copy of the scraper's function
    safe = re.sub(r'[<>:"/\\|?*]', "", title)
    safe = safe.strip(". ")
    return safe[:200] if safe else "untitled"


def make_url(platform, video_id, csv_url=""):
    if csv_url:
        return csv_url
    if platform == "youtube":
        return f"https://www.youtube.com/watch?v={video_id}"
    if platform == "bitchute":
        return f"https://www.bitchute.com/video/{video_id}/"
    if platform == "rumble":
        return f"https://rumble.com/{video_id}/"
    return ""


def load_index(platform, folder):
    """sanitized title -> (video_id, title, duration_s, url)"""
    index = {}
    rows = []
    for name in CHANNEL_CSVS.get((platform, folder), []):
        with open(DATA / name, encoding="utf-8") as f:
            rows.extend(csv.DictReader(f))
    if platform == "youtube":
        with open(DATA / MASTER_YT, encoding="utf-8") as f:
            rows.extend(r for r in csv.DictReader(f) if r.get("channel_name") == folder)
    for r in rows:
        title = (r.get("video_title") or "").strip()
        vid = (r.get("video_id") or "").strip()
        if not title or not vid:
            continue
        key = sanitize_filename(title)
        entry = (vid, title, r.get("duration_seconds", ""), (r.get("url") or "").strip())
        index.setdefault(key, entry)
        index.setdefault(norm(key), entry)
    return index


def norm(s):
    return re.sub(r"\s+", " ", s).lower()


TAG_RE = re.compile(r"\[(?:music|applause|laughter|cheering|singing|__+)\]", re.I)
YEAR_RE = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")


def clean_text(raw):
    text = html.unescape(html.unescape(raw))
    text = text.replace(">>", " ")
    text = TAG_RE.sub(" ", text)
    lines = [re.sub(r" {2,}", " ", ln).strip() for ln in text.splitlines()]
    paras = [ln for ln in lines if ln]
    out = []
    for p in paras:
        words = p.split()
        if len(words) > 300:  # unpunctuated auto-caption blob: chunk for readability
            out.extend(" ".join(words[i:i + 100]) for i in range(0, len(words), 100))
        else:
            out.append(p)
    return "\n\n".join(out)


def frontmatter(d):
    lines = ["---"]
    for k, v in d.items():
        if v is None or v == "":
            continue
        lines.append(f"{k}: {json.dumps(v) if isinstance(v, str) else v}")
    lines.append("---")
    return "\n".join(lines)


def safe_id_suffix(vid):
    return f" [{vid}]" if re.fullmatch(r"[A-Za-z0-9_-]{4,40}", vid or "") else ""


def main():
    report, unmatched = [], []
    total = written = matched = fuzzy_n = 0
    for platform_dir in sorted(TRANSCRIPTS.iterdir()):
        if not platform_dir.is_dir():
            continue
        platform = platform_dir.name
        for chan_dir in sorted(platform_dir.iterdir()):
            if not chan_dir.is_dir() or chan_dir.name.startswith("."):
                continue
            folder = chan_dir.name
            files = sorted(chan_dir.glob("*.txt"))
            if not files:
                continue
            index = load_index(platform, folder)
            keys = [k for k in index if k == norm(k)] or list(index)
            dest = DEST.get((platform, folder),
                            VAULT / "Messages" / PLATFORM_LABEL.get(platform, platform) / folder)
            dest.mkdir(parents=True, exist_ok=True)
            c_match = c_fuzzy = c_miss = 0
            for f in files:
                total += 1
                stem = f.stem
                entry = index.get(stem) or index.get(norm(stem))
                how = "exact" if entry else None
                if not entry and index:
                    close = difflib.get_close_matches(norm(stem), keys, n=1, cutoff=0.9)
                    # digit guard: part numbers/years must agree or it's a different message
                    if close and re.findall(r"\d+", norm(stem)) == re.findall(r"\d+", close[0]):
                        entry, how = index[close[0]], "fuzzy"
                vid, title, dur, csv_url = entry if entry else ("", stem, "", "")
                url = make_url(platform, vid, csv_url) if vid else ""
                year = (YEAR_RE.findall(stem) or [None])[-1]
                fm = {
                    "title": title,
                    "channel": folder,
                    "platform": PLATFORM_LABEL.get(platform, platform),
                    "video_id": vid,
                    "url": url,
                    "year": int(year) if year else None,
                    "duration_min": round(float(dur_m.group()) / 60) if dur and (dur_m := re.search(r"\d+(?:\.\d+)?", dur)) else None,
                    "source": "autocaption" if platform == "youtube" else "whisper",
                    "match": how,
                }
                body = clean_text(f.read_text(encoding="utf-8", errors="replace"))
                note = dest / f"{stem}{safe_id_suffix(vid)}.md"
                note.write_text(frontmatter(fm) + "\n\n" + body + "\n", encoding="utf-8")
                written += 1
                if how == "exact":
                    matched += 1; c_match += 1
                elif how == "fuzzy":
                    matched += 1; fuzzy_n += 1; c_fuzzy += 1
                else:
                    c_miss += 1
                    unmatched.append(f"- {platform}/{folder}/{stem}")
            report.append(f"| {platform}/{folder} | {len(files)} | {c_match} | {c_fuzzy} | {c_miss} |")

    meta = VAULT / "_meta"
    meta.mkdir(exist_ok=True)
    (meta / "conversion-report.md").write_text(
        "# Transcript conversion report\n\n"
        f"Total: {total} txt → {written} notes. Video-ID matched: {matched} "
        f"({fuzzy_n} via fuzzy ≥0.9). Unmatched: {total - matched}.\n\n"
        "| channel | files | exact | fuzzy | unmatched |\n|---|---|---|---|---|\n"
        + "\n".join(report) + "\n", encoding="utf-8")
    (meta / "unmatched.md").write_text(
        "# Notes without a video-ID match\n\nThese have no `url` yet (no CSV row matched; "
        "DagbooksChannel & DhmmInternationalMinistry have no CSV at all).\n\n"
        + "\n".join(unmatched) + "\n", encoding="utf-8")
    print(f"done: {written} notes, {matched} matched ({fuzzy_n} fuzzy), {total - matched} unmatched")


if __name__ == "__main__":
    sys.exit(main())
