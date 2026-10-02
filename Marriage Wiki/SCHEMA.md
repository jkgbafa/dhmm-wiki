# Marriage Wiki schema

This file defines how an agent must ingest, maintain, and query this wiki. It instantiates Andrej Karpathy's LLM Wiki pattern for a marriage-focused ministry corpus.

## Non-negotiable principles

1. **Raw sources are immutable.** Never rewrite files under `raw/`. A refreshed upstream inventory may replace a generated manifest only through the inventory script.
2. **Transcripts are evidence, not doctrine summaries.** Keep the speaker's words, timestamps, and source URL. Mark automated transcripts as unverified until reviewed.
3. **The wiki is compiled knowledge.** Integrate each source into existing pages instead of creating isolated summaries only.
4. **Every teaching claim needs provenance.** Cite the source note and the nearest timestamp. Never cite an AI-written wiki page as the ultimate evidence.
5. **Separate speakers and sources.** Do not merge Adelaide Heward-Mills, Joshua Heward-Mills, First Love Conversations panelists, or Dag Heward-Mills into a single voice. Attribute agreements and disagreements explicitly.
6. **Do not invent a position.** Silence in the corpus is not agreement, disagreement, or advice.

## Directory contract

```text
raw/
  manifests/        Upstream episode/video records as JSONL
  captions/         Original VTT/JSON caption downloads
sources/
  Adelaide Heward-Mills/
  Joshua Heward-Mills/
  First Love Conversations/
wiki/
  People/            Speaker and panelist pages
  Sources/           One page per episode/message
  Topics/            Durable marriage concepts and guidance
  Questions/         User-language questions answered from evidence
  Comparisons/       Cross-source synthesis and differing emphases
index.md             Content-oriented catalog
log.md               Append-only operation history
```

## Required transcript frontmatter

```yaml
title: "Episode or message title"
source_id: "stable platform ID"
speaker: ["Named speaker", "Unknown panelist"]
series: "Adelaide Heward-Mills | Meeting God | First Love Conversations"
platform: "Podcast | YouTube"
source_url: "https://..."
published: "YYYY-MM-DD"
duration_seconds: 0
transcript_method: "publisher | captions | whisper"
transcript_status: "unverified | reviewed"
```

Each transcript paragraph must begin with a timestamp such as `[00:12:34]`. For YouTube, make it a clickable link with `?t=754`. For podcasts, retain the time even when the player cannot deep-link.

## Marriage taxonomy

Use one or more of these stable topic names:

- Biblical foundations and purpose
- Choosing a partner
- Dating and courtship
- Readiness, expectations, and premarital preparation
- Communication and listening
- Conflict resolution and problem solving
- Roles, partnership, and service
- Love, friendship, and emotional connection
- Trust, faithfulness, forgiveness, and reconciliation
- Sex, intimacy, pornography, and purity
- Temperaments and emotional maturity
- Money, work, home, and practical responsibilities
- Ministry and family balance
- In-laws and extended family
- Parenting, motherhood, and fatherhood
- Seasons, hardship, healing, and renewal
- Separation, divorce, remarriage, and widowhood
- Singleness
- Abuse, coercion, danger, and safeguarding

Do not force a source into a topic because it contains a single incidental word. Topic assignment should represent a meaningful section of the teaching.

## Compiled topic-page format

Every `wiki/Topics/*.md` page should contain:

1. A concise overview of the teaching in the corpus.
2. Clearly attributed guidance grouped by speaker/source.
3. Scripture references exactly as used by the source; distinguish quoted, paraphrased, and editor-added references.
4. Practical applications explicitly taught in the source.
5. Tensions, exceptions, or different emphases across sources.
6. `## Evidence` with timestamped source links.
7. `## Related` with Obsidian links to connected topics and questions.

## Question-page format

Question pages should use the language a chatbot user is likely to use, for example `How do we communicate without fighting.md`.

Each answer must:

- lead with a direct, compassionate synthesis;
- distinguish quotation, close paraphrase, and synthesis;
- cite at least two relevant passages when available;
- say when the corpus does not contain enough evidence;
- avoid presenting pastoral teaching as medical, legal, or emergency advice.

## Marriage-chatbot safety rules

- Never tell someone to remain in immediate danger, conceal abuse, or avoid emergency help.
- When a question suggests violence, coercive control, sexual assault, child danger, self-harm, or credible threats, prioritize immediate safety and appropriate local emergency/professional support before discussing the corpus.
- Do not diagnose mental illness, addiction, infertility, or sexual dysfunction.
- Do not provide jurisdiction-specific legal conclusions about divorce, custody, immigration, or property.
- State that the chatbot summarizes the indexed teaching and is not a substitute for a qualified pastor, counselor, clinician, lawyer, or emergency service.
- Preserve the distinction between descriptive statements made in a sermon and universally applicable advice.

## Ingest workflow

1. Refresh source inventories with `pipeline/build_marriage_inventory.py`.
2. Acquire publisher transcripts or captions; otherwise transcribe audio with timestamps.
3. Create or update the readable source note without altering the raw artifact.
4. Extract claims and themes with timestamped evidence.
5. Update all relevant topic, person, source, and question pages.
6. Update `index.md` and append one dated entry to `log.md`.
7. Run lint checks for missing citations, broken links, orphan pages, duplicate titles, and contradictory attributions.

## Query workflow

1. Read `index.md` first.
2. Search relevant topic and question pages.
3. Verify important claims against the timestamped transcript before answering.
4. Prefer direct evidence over a compiled summary when they conflict.
5. Return citations that identify the speaker, episode/message, and timestamp.

## Lint workflow

Periodically check for:

- compiled claims with no transcript citation;
- transcript citations whose timestamp or source no longer resolves;
- speaker attribution inferred from a show name alone;
- contradictions silently flattened into one answer;
- topics mentioned across multiple sources but lacking a synthesis page;
- high-priority marriage sources that have metadata but no transcript;
- obsolete or superseded summaries.

