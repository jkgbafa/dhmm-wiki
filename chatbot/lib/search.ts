import Database from "better-sqlite3";
import path from "path";

export type Chunk = {
  corpus: string;
  speaker: string;
  title: string;
  url: string;
  timestamp_url: string;
  text: string;
};

let db: Database.Database | null = null;

function getDb() {
  if (!db) {
    const file = process.env.CORPUS_DB || path.join(process.cwd(), "corpus.db");
    db = new Database(file, { readonly: true });
  }
  return db;
}

const STOP = new Set(
  "the and for with that this have from she her his him how what when why who are was were will would can could should does did isnt dont not like also often gets goes into very much more some been they them you your out".split(" ")
);

function run(match: string, limit: number): Chunk[] {
  return getDb()
    .prepare(
      `SELECT corpus, speaker, title, url, timestamp_url, text
       FROM chunks WHERE chunks MATCH ? ORDER BY bm25(chunks, 0, 0, 2.0, 0, 0, 1.0) LIMIT ?`
    )
    .all(match, limit) as Chunk[];
}

const dfCache = new Map<string, number>();
function df(term: string): number {
  if (!dfCache.has(term)) {
    try {
      dfCache.set(
        term,
        (getDb()
          .prepare(`SELECT count(*) n FROM chunks WHERE chunks MATCH ?`)
          .get(`"${term}"`) as { n: number }).n
      );
    } catch {
      dfCache.set(term, 0);
    }
  }
  return dfCache.get(term)!;
}

// FTS5 lexical retrieval. Terms are ranked by corpus rarity so distinctive
// words ("melancholic", "phlegmatic") drive the search and chatty words
// ("handle", "often") are dropped; AND of the rarest terms first, OR of the
// distinctive set as fallback. ponytail: no embeddings — upgrade path is a
// vector column; the app layer doesn't change.
export function search(query: string, limit = 14): Chunk[] {
  const raw = [...new Set(query.toLowerCase().match(/[a-z']{3,}/g) || [])].filter(
    (t) => !STOP.has(t)
  );
  // keep terms that appear but aren't ubiquitous (<~20% of chunks)
  const ranked = raw
    .map((t) => ({ t, n: df(t) }))
    .filter((x) => x.n > 0 && x.n < 45000)
    .sort((a, b) => a.n - b.n)
    .slice(0, 8)
    .map((x) => x.t);
  if (!ranked.length) return [];
  const quoted = ranked.map((t) => `"${t.replace(/'/g, "''")}"`);
  const candidates: Chunk[] = [];
  const seen = new Set<string>();
  const queries: string[] = [];
  if (quoted.length >= 3) queries.push(quoted.slice(0, 3).join(" AND "));
  // pair each of the 3 rarest terms with every other kept term, so a rare
  // topic word still meets the mid-frequency word that carries the intent
  // (e.g. "melancholic" AND "wife")
  for (let i = 0; i < Math.min(3, quoted.length); i++)
    for (let j = i + 1; j < quoted.length; j++)
      queries.push(`NEAR(${quoted[i]} ${quoted[j]}, 10)`);
  for (let i = 0; i < Math.min(3, quoted.length); i++)
    for (let j = i + 1; j < quoted.length; j++)
      queries.push(`${quoted[i]} AND ${quoted[j]}`);
  queries.push(quoted.slice(0, 8).join(" OR "));
  for (const q of queries) {
    try {
      for (const c of run(q, limit * 5)) {
        const key = c.title + c.text.slice(0, 80);
        if (!seen.has(key)) {
          seen.add(key);
          candidates.push(c);
        }
      }
    } catch {
      /* fall through to the next query form */
    }
  }
  // re-rank: chunks containing more distinct query terms win
  const scored = candidates.map((c, i) => {
    const hay = (c.title + " " + c.text).toLowerCase();
    let hits = 0;
    for (const t of ranked) if (hay.includes(t.slice(0, Math.max(4, t.length - 2)))) hits++;
    return { c, hits, i };
  });
  scored.sort((a, b) => b.hits - a.hits || a.i - b.i);
  return scored.slice(0, limit).map((s) => s.c);
}
