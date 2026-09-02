#!/usr/bin/env python3
"""Convert Dag Heward-Mills EPUBs to chapter-split markdown in Books/.

Splits by the EPUB spine (each internal XHTML doc = one chapter) rather than
markdown headings, since heading levels are inconsistent across the books.
"""
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import unquote

VAULT = Path(__file__).resolve().parent.parent
BOOKS_OUT = VAULT / "Books"
SOURCES = [Path("/Users/joshuagbafa/Downloads/132-dagbooks-en"),
           Path("/tmp/dagbooks-extra")]

IMG_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
XHTML_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\.x?html?[^)]*\)")
SKIP_TITLES = {"contents", "table of contents", "toc", "copyright", "cover"}


def book_meta(stem):
    m = re.match(r"(\d+)-en-(.+)", stem)
    num, slug = (m.group(1), m.group(2)) if m else ("", stem)
    title = re.sub(r"\bs\b", "'s", slug.replace("-", " ")).title()
    return num, title


def fname_safe(s, cap=80):
    s = re.sub(r'[<>:"/\\|?*#\[\]^]', "", s).strip(". ")
    return re.sub(r"\s+", " ", s)[:cap].strip() or "untitled"


def spine_docs(zf):
    """hrefs of content documents in reading order."""
    ns = {"c": "urn:oasis:names:tc:opendocument:xmlns:container",
          "o": "http://www.idpf.org/2007/opf"}
    container = ET.fromstring(zf.read("META-INF/container.xml"))
    opf_path = container.find(".//c:rootfile", ns).get("full-path")
    opf = ET.fromstring(zf.read(opf_path))
    base = str(Path(opf_path).parent)
    manifest = {i.get("id"): i.get("href")
                for i in opf.findall(".//o:manifest/o:item", ns)}
    hrefs = []
    for ref in opf.findall(".//o:spine/o:itemref", ns):
        href = manifest.get(ref.get("idref"))
        if href and re.search(r"\.x?html?$", href, re.I):
            hrefs.append(unquote(str((Path(base) / href)).lstrip("/")))
    return hrefs


def to_md(xhtml_bytes):
    r = subprocess.run(["pandoc", "-f", "html", "-t", "gfm-raw_html", "--wrap=none"],
                       input=xhtml_bytes, capture_output=True, timeout=120)
    if r.returncode != 0:
        return ""
    text = IMG_RE.sub("", r.stdout.decode("utf-8", "replace"))
    text = XHTML_LINK_RE.sub(r"\1", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def section_title(md, fallback):
    lines = [re.sub(r"[#*_`\[\]\\=-]", "", ln).strip() for ln in md.splitlines()]
    lines = [ln for ln in lines if ln]
    if not lines:
        return fallback
    first = lines[0]
    # "Chapter N" alone: real title is usually the next short line
    if re.fullmatch(r"chapter \d+", first, re.I) and len(lines) > 1 and len(lines[1].split()) <= 10:
        return f"{first} - {lines[1]}"[:120]
    if len(first.split()) > 12:  # body text, not a heading (e.g. copyright page)
        return "Front Matter" if fallback else first[:120]
    return first[:120]


def convert(epub):
    num, title = book_meta(epub.stem)
    out_dir = BOOKS_OUT / fname_safe(f"{num} {title}", 100)
    if out_dir.exists() and any(out_dir.iterdir()):
        return "skip"
    try:
        with zipfile.ZipFile(epub) as zf:
            docs = [(h, to_md(zf.read(h))) for h in spine_docs(zf) if h in zf.namelist()]
    except Exception as e:
        return f"FAIL: {e}"
    chapters = []
    for href, md in docs:
        if len(md.split()) < 20:
            continue
        heading = section_title(md, Path(href).stem)
        if heading.lower().strip() in SKIP_TITLES:
            continue
        chapters.append((heading, md))
    if not chapters:
        return "FAIL: no content"
    out_dir.mkdir(parents=True, exist_ok=True)
    for n, (heading, body) in enumerate(chapters, 1):
        fm = (f'---\ntitle: "{fname_safe(heading, 150)}"\nbook: "{title}"\n'
              f'book_number: "{num}"\nchapter_number: {n}\ntype: book\n---\n\n')
        (out_dir / f"{n:02d} {fname_safe(heading)}.md").write_text(
            fm + body + "\n", encoding="utf-8")
    return f"ok ({len(chapters)} ch)"


def main():
    seen, jobs = set(), []
    for src in SOURCES:
        if not src.exists():
            continue
        for epub in sorted(src.glob("*.epub")):
            if epub.stem not in seen:
                seen.add(epub.stem)
                jobs.append(epub)
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(zip(jobs, ex.map(convert, jobs)))
    fails = [(e.stem, r) for e, r in results if r.startswith("FAIL")]
    print(f"{len(results)} books, {len(fails)} failed")
    for s, r in fails:
        print(" ", s, r)


if __name__ == "__main__":
    sys.exit(main())
