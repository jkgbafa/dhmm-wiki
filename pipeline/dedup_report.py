#!/usr/bin/env python3
"""Find duplicate messages across channels and write _meta/duplicates.md.

Rules (per owner): titles NEVER decide — only content. A duplicate is
(a) the exact same video_id appearing in more than one note, or
(b) transcript content >=95% similar (token-shingle Jaccard).
0.85-0.95 is reported separately as "possible". Longest note wins; shorter
ones get `duplicate_of` in frontmatter. Nothing is deleted.
"""
import re
from collections import defaultdict
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent
FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)


def load_notes():
    notes = []
    for root in ("Messages", "FLOW"):
        for f in sorted((VAULT / root).rglob("*.md")):
            text = f.read_text(encoding="utf-8", errors="replace")
            m = FM_RE.match(text)
            fm = dict(re.findall(r'^(\w+): "?([^"\n]*)"?$', m.group(1), re.M)) if m else {}
            body = text[m.end():] if m else text
            tokens = re.findall(r"[a-z']+", body.lower())
            notes.append({"path": f, "fm": fm, "tokens": tokens, "n": len(tokens)})
    return notes


def shingles(tokens, k=8):
    # ponytail: sampled 8-gram shingle sets, O(n^2) Jaccard within small
    # duration buckets; upgrade path is minhash if the vault grows 10x
    return {hash(" ".join(tokens[i:i + k])) for i in range(0, len(tokens) - k, 3)}


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def main():
    notes = load_notes()
    certain, possible = [], []

    by_vid = defaultdict(list)
    for nt in notes:
        vid = nt["fm"].get("video_id", "")
        if vid:
            by_vid[vid].append(nt)
    same_vid_pairs = set()
    for vid, group in by_vid.items():
        if len(group) > 1:
            group.sort(key=lambda x: -x["n"])
            for other in group[1:]:
                certain.append((group[0], other, 1.0, f"same video_id {vid}"))
                same_vid_pairs.add((group[0]["path"], other["path"]))

    buckets = defaultdict(list)
    for nt in notes:
        dur = nt["fm"].get("duration_min", "")
        key = int(dur) if dur.isdigit() else -round(nt["n"] / 400)  # fallback: length bucket
        buckets[key].append(nt)
    for nt in notes:
        nt["sh"] = None

    def sh(nt):
        if nt["sh"] is None:
            nt["sh"] = shingles(nt["tokens"])
        return nt["sh"]

    seen = set()
    for key, group in buckets.items():
        neigh = group + (buckets.get(key + 1, []) if key >= 0 else [])
        for i, a in enumerate(group):
            for b in neigh:
                if a is b:
                    continue
                pair = tuple(sorted((str(a["path"]), str(b["path"]))))
                if pair in seen:
                    continue
                seen.add(pair)
                if min(a["n"], b["n"]) < 200 or abs(a["n"] - b["n"]) / max(a["n"], b["n"]) > 0.15:
                    continue
                j = jaccard(sh(a), sh(b))
                if j >= 0.95:
                    x, y = (a, b) if a["n"] >= b["n"] else (b, a)
                    if (x["path"], y["path"]) not in same_vid_pairs:
                        certain.append((x, y, j, "content"))
                elif j >= 0.85:
                    possible.append((a, b, j))

    tagged = 0
    for keep, dup, j, why in certain:
        text = dup["path"].read_text(encoding="utf-8")
        if "duplicate_of:" not in text:
            rel = str(keep["path"].relative_to(VAULT))[:-3]
            text = text.replace("---\n\n", f'duplicate_of: "[[{rel}]]"\n---\n\n', 1)
            dup["path"].write_text(text, encoding="utf-8")
            tagged += 1

    def rel(nt):
        return str(nt["path"].relative_to(VAULT))

    lines = ["# Duplicate report", "",
             f"Certain duplicates: {len(certain)} (tagged `duplicate_of` in frontmatter; nothing deleted).",
             f"Possible (85-95% similar, NOT tagged - review): {len(possible)}", "",
             "## Certain (same video or >=95% same content) - kept | duplicate | reason"]
    lines += [f"- KEEP `{rel(k)}` | DUP `{rel(d)}` | {why} ({j:.2f})" for k, d, j, why in certain]
    lines += ["", "## Possible - review by hand"]
    lines += [f"- `{rel(a)}` ~ `{rel(b)}` ({j:.2f})" for a, b, j in possible]
    (VAULT / "_meta" / "duplicates.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(certain)} certain ({tagged} tagged), {len(possible)} possible -> _meta/duplicates.md")


if __name__ == "__main__":
    main()
