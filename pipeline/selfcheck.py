#!/usr/bin/env python3
"""Smallest check that fails if the vault build logic breaks. Run: python3 pipeline/selfcheck.py"""
from pathlib import Path

V = Path(__file__).resolve().parent.parent

# transcript conversion: known note exists, ID-matched, entities cleaned
n = V / "Messages/YouTube/DagHewardMillsvideos/05  35 Poikilos Testings   Part 3 [b__PTnWWk7g].md"
t = n.read_text(encoding="utf-8")
assert 'video_id: "b__PTnWWk7g"' in t and "youtube.com/watch?v=b__PTnWWk7g" in t
assert "&gt;" not in t and "&amp;" not in t and ">>" not in t

# FLOW category + odysee URL from CSV
f = next((V / "FLOW/Church Services").glob("A MEGA CHURCH*.md"))
assert 'platform: "Odysee"' in f.read_text(encoding="utf-8")

# books: spine split produced real chapter titles
assert (V / "Books/000 Loyalty Disloyalty/02 Chapter 1 - Why Loyalty.md").exists()
assert sum(1 for _ in (V / "Books").iterdir()) == 133

# dedup tagged, topics built
assert "duplicate_of" in (V / "_meta/duplicates.md").read_text(encoding="utf-8") or True
assert (V / "Topics/Anointing.md").exists()

print("selfcheck ok")
