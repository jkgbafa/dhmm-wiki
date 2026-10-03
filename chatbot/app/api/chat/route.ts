import { search } from "@/lib/search";

export const runtime = "nodejs";

// Any OpenAI-compatible endpoint works. Free defaults: Groq free tier, or
// local Ollama (OPENAI_BASE_URL=http://localhost:11434/v1, LLM_MODEL=llama3.1).
const BASE_URL = process.env.OPENAI_BASE_URL || "https://api.groq.com/openai/v1";
const API_KEY = process.env.OPENAI_API_KEY || "ollama";
const MODEL = process.env.LLM_MODEL || "llama-3.3-70b-versatile";

const SYSTEM = `You are the research assistant for the Dag Heward-Mills ministry wiki: Bishop Dag Heward-Mills' messages and books, plus the Marriage Wiki of Adelaide Heward-Mills, Joshua Heward-Mills and First Love Conversations.

Rules (non-negotiable, from the wiki's schema):
- Answer ONLY from the provided evidence chunks. If the evidence doesn't cover the question, say so plainly — silence in the corpus is not agreement, disagreement, or advice.
- Every teaching claim needs provenance: cite the source as a markdown link using the chunk's URL (prefer timestamped URLs), e.g. [Title](url).
- Never merge speakers into one voice. Attribute each point to the specific speaker (Dag Heward-Mills, Adelaide Heward-Mills, Joshua Heward-Mills, or a First Love Conversations panelist).
- Transcripts are automated and unverified: paraphrase their substance rather than presenting them as exact quotations, and keep any wording you do echo short.
- Answer the asker's ACTUAL situation. If the evidence describes a different case (e.g. it discusses a melancholic husband but the asker has a melancholic wife), say so explicitly and only carry over what genuinely applies — never silently swap who it is about.
- STAY CLOSE TO THE MATERIAL. Build the answer from the evidence's own concepts, terms and examples, naming where each point comes from inline (e.g. "In Model Marriage, Dag Heward-Mills teaches that…", "Preaching at FLOW, he said…"). Do not add generic self-help advice the sources don't contain.
- Be warm, clear and concise. Group the answer by speaker or by theme, whichever reads better.`;

export async function POST(req: Request) {
  const { messages } = (await req.json()) as {
    messages: { role: "user" | "assistant"; content: string }[];
  };
  const question = messages.filter((m) => m.role === "user").at(-1)?.content || "";
  const recent = messages.slice(-6);

  const chunks = search(question);
  const evidence = chunks
    .map(
      (c, i) =>
        `[${i + 1}] speaker: ${c.speaker} | corpus: ${c.corpus} | title: ${c.title} | url: ${c.timestamp_url || c.url}\n${c.text}`
    )
    .join("\n\n---\n\n");

  const upstream = await fetch(`${BASE_URL}/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${API_KEY}`,
    },
    body: JSON.stringify({
      model: MODEL,
      stream: true,
      messages: [
        { role: "system", content: SYSTEM },
        ...recent.slice(0, -1),
        {
          role: "user",
          content: `Evidence chunks:\n\n${evidence || "(no matches found in the corpus)"}\n\nQuestion: ${question}`,
        },
      ],
    }),
  });

  if (!upstream.ok || !upstream.body) {
    const detail = await upstream.text().catch(() => "");
    return new Response(`The AI backend returned an error (${upstream.status}). ${detail.slice(0, 300)}`, {
      status: 502,
    });
  }

  // First frame: the real retrieved sources as JSON (the UI renders these as
  // chips regardless of whether the model cites). Then the streamed text.
  const seen = new Set<string>();
  const sources = chunks
    .filter((c) => {
      const key = c.title;
      if (!c.url || seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .slice(0, 8)
    .map((c) => ({
      title: c.title,
      url: c.timestamp_url || c.url,
      speaker: c.speaker,
      corpus: c.corpus,
    }));
  const header = new TextEncoder().encode(JSON.stringify({ sources }) + "\n\n");

  const reader = upstream.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let sentHeader = false;
  const stream = new ReadableStream({
    async pull(controller) {
      if (!sentHeader) {
        controller.enqueue(header);
        sentHeader = true;
        return;
      }
      const { done, value } = await reader.read();
      if (done) {
        controller.close();
        return;
      }
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop() || "";
      for (const line of lines) {
        const data = line.replace(/^data: /, "").trim();
        if (!data || data === "[DONE]") continue;
        try {
          const delta = JSON.parse(data).choices?.[0]?.delta?.content;
          if (delta) controller.enqueue(new TextEncoder().encode(delta));
        } catch {
          /* partial line */
        }
      }
    },
  });
  return new Response(stream, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
