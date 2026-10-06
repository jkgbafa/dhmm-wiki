# Chatbot corpus

Each JSONL row is one timestamped evidence chunk. Use `text` for retrieval and preserve `source_url`, `timestamp_url`, `title`, `speaker`, and `start_seconds` when generating citations.

Never treat an unverified automatic transcript as an exact quotation without checking the source audio.

- `adelaide-heward-mills.jsonl` — 18069 chunks
- `first-love-conversations.jsonl` — 3525 chunks
- `joshua-heward-mills.jsonl` — 32634 chunks
