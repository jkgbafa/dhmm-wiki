#!/usr/bin/env python3
"""Build Topics/Marriage/ — everything every book says about marriage.

Scans every book chapter (except the dedicated marriage books, which are
listed whole) for passages on marriage, submission in marriage, sex, husbands
and wives, etc. Qualifying paragraphs are quoted per book with links back to
the source chapter.
"""
import re
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent
OUT = VAULT / "Topics" / "Marriage"
FM_RE = re.compile(r"^---\n.*?\n---\n", re.S)

# fully-marriage books: linked whole, not parsed
CORE = ["104 Model Marriage A Marriage Counselling Handbook",
        "105 The Beauty The Beast And The Pastor",
        "124 The Strange Woman",
        "125 All About Fornication"]

MARRIAGE = re.compile(
    r"\bmarriage|\bmarry|\bmarried|marital|\bspouse|\bwife\b|\bwives\b|\bhusband"
    r"|\bwedding\b|\bdivorce|\bbride\b|courtship|polygam", re.I)
SEXUALITY = re.compile(r"\bsexual|\bsex\b|fornicat|adulter|strange woman|immorality", re.I)
SUBMIT = re.compile(r"submi\w+[^.]{0,80}(wife|wives|husband)|"
                    r"(wife|wives|husband)[^.]{0,80}submi\w+", re.I)
FALSE_POS = re.compile(r"bride of christ|married to (the lord|christ|jesus)", re.I)


def hits(par):
    if FALSE_POS.search(par) and not SUBMIT.search(par):
        p = FALSE_POS.sub("", par)
    else:
        p = par
    return len(MARRIAGE.findall(p)) + len(SEXUALITY.findall(p)) + 2 * len(SUBMIT.findall(p))


def chapter_blocks(path):
    body = FM_RE.sub("", path.read_text(encoding="utf-8", errors="replace"))
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    marks = [hits(p) for p in paras]
    blocks, i = [], 0
    while i < len(paras):
        if marks[i]:
            j = i
            while j + 1 < len(paras) and (marks[j + 1] or (j + 2 < len(paras) and marks[j + 2])):
                j += 1
            block = paras[i:j + 1]
            if sum(marks[i:j + 1]) >= 2:  # skip lone passing mentions
                blocks.append("\n".join(block))
            i = j + 1
        else:
            i += 1
    return blocks


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.md"):
        old.unlink()
    index = ["# Marriage — What Every Book Says", "",
             "A marriage world built from the whole library: the dedicated marriage books first, "
             "then every passage about marriage, submission in marriage, sex, husbands and wives "
             "pulled from every other book.", "", "## The dedicated marriage books (read whole)"]
    for name in CORE:
        chaps = sorted((VAULT / "Books" / name).glob("*.md"))
        index.append(f"- **[[{('Books/' + name + '/' + chaps[1].stem) if len(chaps) > 1 else ('Books/' + name + '/' + chaps[0].stem)}|{name[4:]}]]** ({len(chaps)} chapters)")
    index += ["", "## What the other books say about marriage"]

    total_books = total_blocks = 0
    for book_dir in sorted(d for d in (VAULT / "Books").iterdir() if d.is_dir() and d.name not in CORE):
        title = book_dir.name[4:]
        page, n_blocks = [f"# {title} — on Marriage", ""], 0
        for ch in sorted(book_dir.glob("*.md")):
            blocks = chapter_blocks(ch)
            if not blocks:
                continue
            page.append(f"\n## [[Books/{book_dir.name}/{ch.stem}|{ch.stem[3:] or ch.stem}]]")
            for b in blocks:
                page.append("\n> " + b.replace("\n", "\n> "))
            n_blocks += len(blocks)
        if n_blocks:
            fname = re.sub(r'[<>:"/\\|?*]', "", title)[:90]
            (OUT / f"{fname}.md").write_text("\n".join(page) + "\n", encoding="utf-8")
            index.append(f"- [[Topics/Marriage/{fname}|{title}]] ({n_blocks} passages)")
            total_books += 1
            total_blocks += n_blocks
    (OUT / "00 Marriage Index.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    print(f"{total_blocks} passages from {total_books} books -> Topics/Marriage/")


if __name__ == "__main__":
    main()
