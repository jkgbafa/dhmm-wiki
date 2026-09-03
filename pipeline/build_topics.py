#!/usr/bin/env python3
"""Tag every note by CONTENT (not just title) and build Topics/ hub pages.

Scans full transcript/chapter text against a two-level taxonomy. A note gets a
subtopic when the body discusses it enough (absolute hits or density per 1000
words), so untitled themes still surface. Writes `topics:` + nested `tags:`
into frontmatter (idempotent) and regenerates Topics/ pages: index -> topic
page -> subtopic sections.

ponytail: keyword-density tagging, not semantic; upgrade path is an LLM/embedding
pass refining the same frontmatter fields.
"""
import json
import re
from collections import defaultdict
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent
FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)

# topic -> (topic-level pattern, {subtopic: pattern})
TAXONOMY = {
    "Anointing": (r"\banoint", {
        "Impartation and Mantles": r"impartation|\bmantle|\belisha\b|\belijah\b|laying on of hands",
        "Kinds and Waves of the Anointing": r"anointing of|kinds of anointing|waves of",
        "Catching the Anointing": r"catch the anointing|steps to the anointing",
    }),
    "Loyalty and Disloyalty": (r"\bloyal|disloyal|treacher", {
        "Judas and Betrayal": r"\bjudas\b|betray|thirty pieces",
        "Stages and Signs of Disloyalty": r"stages of disloyalty|signs of disloyalty|independent spirit|familiarity",
        "Faithfulness": r"\bfaithful",
    }),
    "Church Growth": (r"church growth|grow the church", {
        "Mega Church": r"mega ?church|church of thousands",
        "Church Planting": r"church plant|plant(ing)? churches",
        "Visitation and Follow-up": r"visitation|follow[ -]up|house to house",
    }),
    "Prayer": (r"\bpray", {
        "Intercession": r"intercess|travail",
        "Praying in Tongues": r"\btongues\b|pray in the spirit",
        "Answered Prayer": r"answer(ed|s)? (to )?prayer",
        "All-night Prayer": r"all[ -]night|\bvigil",
    }),
    "Fasting": (r"\bfast(ing|ed|s)?\b", {}),
    "Wealth and Finances": (r"\bwealth|\bmoney\b|financial", {
        "Tithing and Giving": r"\btith|offerings?\b|giv(e|ing) to god|sow(ing)? (a )?seed",
        "Prosperity and Poverty": r"prosperity|\bpoverty\b|becom(e|ing) rich|financial breakthrough|\briches\b",
    }),
    "Marriage and Family": (r"marriage|married", {
        "Choosing a Partner": r"choos\w* (a )?(wife|husband|partner)|who (to|you) marry",
        "Husbands and Wives": r"your (husband|wife)|husbands?, love|submit to (your )?husband|marital|good wife|good husband",
        "Sexuality and Purity": r"fornicat|adulter|\blust\b|\bsex\b|strange woman|immorality",
        "Children and Parenting": r"parent(s|ing)\b|train up|rais(e|ing) (your )?children|bring(ing)? up (your )?children",
    }),
    "Leadership": (r"leader", {
        "Art of Leadership": r"art of leadership|qualities of a leader|good leader",
        "Generals and History Makers": r"\ba good general|generals\b|napoleon|history maker",
    }),
    "Soul Winning and Evangelism": (r"soul[ -]?winn|evangeli|the lost\b", {
        "Crusades": r"crusade|altar call",
        "Anagkazo and Compelling": r"anagkazo|compel",
        "Witnessing": r"witness(ing|es)?\b|preach the gospel",
    }),
    "Salvation": (r"salvation", {
        "The New Birth": r"born again|new birth|convert(ed|s)?\b",
        "Repentance": r"repent",
        "Backsliding": r"backslid",
    }),
    "The Holy Spirit": (r"holy spirit|holy ghost", {
        "Baptism of the Spirit": r"baptism of the (holy )?spirit|filled with the spirit",
        "Gifts of the Spirit": r"gifts of the spirit|word of knowledge|prophec\w+|prophetic",
    }),
    "The Call of God": (r"call of god|\bcalling\b", {
        "Responding to the Call": r"respond\w* to (the|your) call|answer\w* (the|your) call|full[ -]time ministry",
    }),
    "Ministry and Pastoring": (r"\bministry\b|\bminister\b", {
        "Shepherding and Pastoral Care": r"pastoral|shepherd|\bsheep\b|\bflock\b",
        "Ministerial Ethics": r"ministerial ethics|ethics of",
        "Lay Ministry": r"lay (people|person|ministry|pastor)|laikos",
    }),
    "Wisdom": (r"\bwisdom\b|\bwise\b", {}),
    "Faith": (r"\bfaith\b", {}),
    "Spiritual Warfare": (r"spiritual warfare|\bwarfare\b", {
        "Demonology": r"\bdemon|evil spirit|unclean spirit|possess(ed|ion)|principalities",
        "Deliverance": r"deliverance|cast (out|ing out)|set free",
        "Curses": r"\bcurse",
        "Satan and His Devices": r"\bsatan\b|lucifer|devices of the devil|the devil's",
        "Witchcraft and Jezebel": r"jezebel|witch",
    }),
    "Heaven, Hell and Eternity": (r"eternity|eternal life", {
        "Heaven": r"\bheaven\b",
        "Hell": r"\bhell\b|lake of fire",
        "Judgment": r"judgment seat|give (an )?account|day of judgment",
    }),
    "The Word and Books": (r"word of god", {
        "Bible Study": r"read(ing)? (your|the) bible|study the (word|bible)|meditat",
        "Books and Reading": r"read(ing)? books|\blibrary\b",
    }),
    "Work and Diligence": (r"hard[ -]work|diligen", {
        "Laziness": r"\blaz(y|iness)|slothful",
    }),
    "Missions": (r"missionar\w+|mission field|\bmissions\b", {
        "The Nations": r"the nations\b|every nation|ends of the earth",
    }),
    "Vision and Direction": (r"\bvision\b", {
        "Hearing God": r"hear(ing)? (from )?god|voice of god|art of hearing",
        "The Will of God": r"will of god",
    }),
}

COMPILED = {t: (re.compile(own, re.I), {s: re.compile(p, re.I) for s, p in subs.items()})
            for t, (own, subs) in TAXONOMY.items()}


def score(body, words, title):
    """Return sorted topic entries like 'Topic' / 'Topic/Sub'."""
    entries = set()
    per_k = 1000.0 / max(words, 200)
    for topic, (own_rx, subs) in COMPILED.items():
        own = len(own_rx.findall(body))
        total = own
        for sub, rx in subs.items():
            hits = len(rx.findall(body))
            total += hits
            if hits >= 10 or (hits >= 5 and hits * per_k >= 2.0) or rx.search(title):
                entries.add(f"{topic}/{sub}")
        if (total >= 15 and total * per_k >= 4.0) or own_rx.search(title) \
                or any(e.startswith(topic + "/") for e in entries):
            entries.add(topic)
    return sorted(entries)


def slug(s):
    return re.sub(r"[^a-z0-9/]+", "-", s.lower()).strip("-")


def retag(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    m = FM_RE.match(text)
    if not m:
        return []
    body = text[m.end():]
    title = re.sub(r" \[[A-Za-z0-9_-]{4,40}\]$", "", path.stem)
    entries = score(body, len(body.split()), title)
    fm = re.sub(r"^(topics|tags): .*\n", "", m.group(1) + "\n", flags=re.M).rstrip("\n")
    if entries:
        fm += f"\ntopics: {json.dumps(entries)}"
        fm += f"\ntags: {json.dumps(['topic/' + slug(e) for e in entries])}"
    path.write_text(f"---\n{fm}\n---\n{body}", encoding="utf-8")
    return entries


def main():
    tagged = defaultdict(list)  # entry -> [paths]
    roots = ["Messages", "FLOW", "Books"]
    n_notes = n_tagged = 0
    for root in roots:
        for f in sorted((VAULT / root).rglob("*.md")):
            entries = retag(f)
            n_notes += 1
            n_tagged += bool(entries)
            for e in entries:
                tagged[e].append(f)

    out = VAULT / "Topics"
    out.mkdir(exist_ok=True)
    for old in out.glob("*.md"):
        old.unlink()

    def link(p):
        title = re.sub(r" \[[A-Za-z0-9_-]{4,40}\]$", "", p.stem)
        return f"[[{str(p.relative_to(VAULT))[:-3]}|{title}]]"

    def section(paths):
        lines, cur = [], None
        for p in paths:
            group = "Books — " + p.parent.name if p.parts[len(VAULT.parts)] == "Books" \
                else " / ".join(p.relative_to(VAULT).parts[:-1])
            if group != cur:
                cur = group
                lines.append(f"\n#### {group}")
            lines.append(f"- {link(p)}")
        return lines

    index = ["# Topics", "", "Every topic and subtopic, tagged by message CONTENT — a note counts "
             "even when its title never mentions the topic. Also browsable via Obsidian's tag pane "
             "(`topic/...`).", ""]
    for topic in TAXONOMY:
        subs = [e for e in tagged if e.startswith(topic + "/")]
        general = [p for p in tagged.get(topic, [])
                   if not any(p in tagged[s] for s in subs)]
        page = [f"# {topic}", "", f"Tagged by content: `topic/{slug(topic)}`", ""]
        index.append(f"- **[[Topics/{topic}|{topic}]]** ({len(tagged.get(topic, []))})")
        for e in sorted(subs):
            sub = e.split("/", 1)[1]
            page += [f"\n## {sub} ({len(tagged[e])})"] + section(tagged[e])
            index.append(f"    - [[Topics/{topic}#{sub}|{sub}]] ({len(tagged[e])})")
        if general:
            page += [f"\n## General ({len(general)})"] + section(general)
        (out / f"{topic}.md").write_text("\n".join(page) + "\n", encoding="utf-8")
    (out / "Topics Index.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    print(f"{n_tagged}/{n_notes} notes tagged; {len(TAXONOMY)} topic pages -> Topics/")


if __name__ == "__main__":
    main()
