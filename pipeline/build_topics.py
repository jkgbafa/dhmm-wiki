#!/usr/bin/env python3
"""Generate Topics/<Category>.md hub notes linking messages + book chapters.

v1: keyword match on titles (fast, transparent). A deeper AI content-tagging
pass can refine into subcategories later.
"""
import re
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent

TOPICS = {
    "Anointing": r"anoint",
    "Loyalty and Disloyalty": r"loyal|disloyal|betray|judas|treacher",
    "Church Growth": r"church growth|mega ?church|church plant|shepherding control|why is this church",
    "Prayer": r"\bpray|intercess|supplicat",
    "Fasting": r"\bfast(ing|ed|s)?\b",
    "Wealth and Finances": r"wealth|money|\briches\b|prosperity|tith(e|ing)|financial|poverty|frugal",
    "Marriage and Family": r"marriage|marry|husband|wife|family|divorce|fornicat|strange woman",
    "Leadership": r"leader|a good general|govern",
    "Soul Winning and Evangelism": r"soul[ -]?winn|evangeli|crusade|witness(ing)?\b|anagkazo",
    "Salvation": r"salvation|born again|\bsaved\b|repent",
    "The Holy Spirit": r"holy spirit|holy ghost",
    "The Call of God": r"call of god|calling|many are called|\bcalled\b",
    "Ministry and Pastoring": r"ministry|minister|pastor|shepherd|bishop|laikos|lay people",
    "Wisdom": r"\bwis(dom|e)\b",
    "Faith": r"\bfaith\b|believ(e|ing)",
    "Spiritual Warfare": r"demon|devil|satan|warfare|deliverance|curse|jezebel|invisible enemies|spiritual dangers",
    "Heaven, Hell and Eternity": r"heaven|\bhell\b|eternity|judgment|people who went",
    "The Word and Books": r"\bbible\b|scripture|word of god|\bbooks\b|memori[sz]ation",
    "Work and Diligence": r"hard work|diligen|\blazy|\bwork\b",
    "Missions": r"missions?\b|missionary|the nations\b|\bsend\b",
    "Vision and Direction": r"\bvision\b|will of god|art of hearing|direction",
}


def title_of(path):
    return re.sub(r" \[[A-Za-z0-9_-]{4,40}\]$", "", path.stem)


def link(path, alias=None):
    rel = str(path.relative_to(VAULT))[:-3]
    return f"[[{rel}|{alias or title_of(path)}]]"


def main():
    out_dir = VAULT / "Topics"
    out_dir.mkdir(exist_ok=True)
    messages = sorted(list((VAULT / "Messages").rglob("*.md")) + list((VAULT / "FLOW").rglob("*.md")))
    books = sorted(d for d in (VAULT / "Books").iterdir() if d.is_dir())

    index_lines = ["# Topics", ""]
    for topic, pattern in TOPICS.items():
        rx = re.compile(pattern, re.I)
        book_hits = [d for d in books if rx.search(d.name)]
        chapter_hits = [f for d in books if d not in book_hits
                        for f in sorted(d.glob("*.md")) if rx.search(title_of(f))]
        msg_hits = [f for f in messages if rx.search(title_of(f))]

        lines = [f"# {topic}", ""]
        if book_hits:
            lines.append("## Books")
            for d in book_hits:
                first = sorted(d.glob("*.md"))
                if first:
                    lines.append(f"- {link(first[0], d.name[4:] or d.name)} ({len(first)} chapters)")
            lines.append("")
        if chapter_hits:
            lines.append("## Book chapters")
            lines += [f"- {link(f)} — *{f.parent.name[4:]}*" for f in chapter_hits]
            lines.append("")
        if msg_hits:
            lines.append(f"## Messages ({len(msg_hits)})")
            current = None
            for f in msg_hits:
                chan = f.relative_to(VAULT).parts[:-1]
                label = " / ".join(chan)
                if label != current:
                    current = label
                    lines.append(f"\n### {label}")
                lines.append(f"- {link(f)}")
        (out_dir / f"{topic}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        index_lines.append(f"- [[Topics/{topic}|{topic}]] — {len(book_hits)} books, "
                           f"{len(chapter_hits)} chapters, {len(msg_hits)} messages")
    (out_dir / "Topics Index.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    print(f"{len(TOPICS)} topic hubs -> Topics/")


if __name__ == "__main__":
    main()
