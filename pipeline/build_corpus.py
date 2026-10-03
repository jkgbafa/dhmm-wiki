#!/usr/bin/env python3
"""Build chatbot/corpus.db — one SQLite FTS5 index over all three wikis.

Rows come from: Marriage Wiki chatbot JSONLs (already chunked + timestamped),
Bishop Dag's 6,730 message transcripts (chunked here), and the 133 books
(chunked per chapter). ponytail: lexical FTS5 retrieval, no embeddings —
upgrade path is adding a vector column later without changing the app.
"""
import json
import re
import sqlite3
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent
DB = VAULT / "chatbot" / "corpus.db"
FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
CHUNK_WORDS = 380


def fm_and_body(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    m = FM_RE.match(text)
    fm = dict(re.findall(r'^(\w+): "?([^"\n]*)"?$', m.group(1), re.M)) if m else {}
    return fm, (text[m.end():] if m else text)


def chunks(body):
    words, cur, n = [], [], 0
    for para in re.split(r"\n\s*\n", body):
        p = para.strip()
        if not p:
            continue
        w = len(p.split())
        if n + w > CHUNK_WORDS and cur:
            words.append("\n\n".join(cur))
            cur, n = [], 0
        cur.append(p)
        n += w
    if cur:
        words.append("\n\n".join(cur))
    return words


def rows():
    for f in sorted((VAULT / "Marriage Wiki" / "_chatbot").glob("*.jsonl")):
        corpus = f.stem
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            c = json.loads(line)
            yield (corpus, "; ".join(c.get("speaker") or []), c.get("title") or "",
                   c.get("source_url") or "", c.get("timestamp_url") or c.get("source_url") or "",
                   c.get("text") or "")
    for root, corpus in (("Messages", "dag-messages"), ("FLOW", "dag-messages")):
        for f in sorted((VAULT / root).rglob("*.md")):
            fm, body = fm_and_body(f)
            title = fm.get("title", f.stem)
            for ch in chunks(body):
                yield (corpus, "Dag Heward-Mills", title, fm.get("url", ""), fm.get("url", ""), ch)
    for f in sorted((VAULT / "Books").rglob("*.md")):
        fm, body = fm_and_body(f)
        title = f'{fm.get("book", f.parent.name)} — {fm.get("title", f.stem)}'
        link = f"https://github.com/jkgbafa/dhmm-wiki/blob/main/{f.relative_to(VAULT)}"
        for ch in chunks(body):
            yield ("dag-books", "Dag Heward-Mills", title, link, link, ch)


def main():
    DB.parent.mkdir(exist_ok=True)
    DB.unlink(missing_ok=True)
    db = sqlite3.connect(DB)
    db.execute("""CREATE VIRTUAL TABLE chunks USING fts5(
        corpus UNINDEXED, speaker UNINDEXED, title, url UNINDEXED,
        timestamp_url UNINDEXED, text, tokenize='porter unicode61')""")
    n = 0
    for batch in iter(lambda it=rows(): [r for _, r in zip(range(5000), it)], []):
        db.executemany("INSERT INTO chunks VALUES (?,?,?,?,?,?)", batch)
        n += len(batch)
    db.commit()
    counts = db.execute("SELECT corpus, count(*) FROM chunks GROUP BY corpus").fetchall()
    db.close()
    print(n, "chunks:", counts, f"-> {DB} ({DB.stat().st_size//1024//1024} MB)")


if __name__ == "__main__":
    main()
