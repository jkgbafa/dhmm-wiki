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

// FTS5 lexical retrieval. ponytail: no embeddings — each meaningful query term
// is OR-ed so partial matches still rank; upgrade path is a vector column.
export function search(query: string, limit = 14): Chunk[] {
  const terms = (query.toLowerCase().match(/[a-z']{3,}/g) || []).slice(0, 12);
  if (!terms.length) return [];
  const match = terms.map((t) => `"${t.replace(/'/g, "''")}"`).join(" OR ");
  return getDb()
    .prepare(
      `SELECT corpus, speaker, title, url, timestamp_url, text
       FROM chunks WHERE chunks MATCH ? ORDER BY bm25(chunks, 0, 0, 2.0, 0, 0, 1.0) LIMIT ?`
    )
    .all(match, limit) as Chunk[];
}
