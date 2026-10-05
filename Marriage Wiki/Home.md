# Marriage and Relationships Wiki

An evidence-backed knowledge base compiled from the teaching of Adelaide Heward-Mills, Joshua Heward-Mills, and First Love Conversations.

This is a separate, self-contained wiki inside the larger ministry vault. It is designed primarily for a chatbot that answers questions about marriage and relationships while linking every substantive claim back to a source episode and timestamp.

## Start here

- [[index|Wiki index]]
- [[SCHEMA|Ingestion, citation, and safety rules]]
- [[wiki/Source Catalog|Source catalog]]
- [[wiki/All Sources|All sources and original-message links]]
- [[wiki/Sources/Adelaide Heward-Mills YouTube Archive|Adelaide Heward-Mills YouTube Archive]]
- [[log|Ingestion log]]

## Knowledge layers

- `raw/manifests/` — machine-readable inventories copied from the podcast RSS feeds and YouTube channel. These are source records, not interpreted teaching.
- `raw/captions/` — original caption files when a platform supplies them.
- `sources/` — timestamped, readable transcripts derived from captions or speech-to-text.
- `wiki/` — LLM-maintained summaries, topic pages, comparisons, and question pages.
- `_chatbot/` — JSONL evidence chunks carrying source URLs, timestamps, speaker/series metadata, and transcript status.

The `raw/` and `sources/` layers preserve evidence. The `wiki/` layer is the compiled, interlinked knowledge base.

## Current status

The source inventories and marriage-first catalog are in place. Podcast audio still needs speech-to-text, and YouTube videos need caption collection or speech-to-text where captions are unavailable.
