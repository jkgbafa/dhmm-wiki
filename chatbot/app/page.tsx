"use client";

import { useEffect, useRef, useState } from "react";
import {
  ChatContainerRoot,
  ChatContainerContent,
} from "@/components/ui/chat-container";
import { Message, MessageContent } from "@/components/ui/message";
import { Markdown } from "@/components/ui/markdown";
import {
  PromptInput,
  PromptInputTextarea,
  PromptInputActions,
  PromptInputAction,
} from "@/components/ui/prompt-input";
import { Loader } from "@/components/ui/loader";
import { ScrollButton } from "@/components/ui/scroll-button";
import { Source, SourceTrigger, SourceContent } from "@/components/ui/source";
import { Button } from "@/components/ui/button";
import { ArrowUp, MessageSquarePlus, Trash2 } from "lucide-react";

type Src = { title: string; url: string; speaker: string; corpus: string };
type Msg = { role: "user" | "assistant"; content: string; sources?: Src[] };
type Chat = { id: string; title: string; messages: Msg[] };

const STORE = "dhmm-wiki-chats";

const SUGGESTIONS = [
  "What does Bishop Dag teach about catching the anointing?",
  "What has been said about a wife submitting to her husband?",
  "Where does Bishop Dag tell the story of Margaret?",
  "What does Joshua Heward-Mills teach about prayer?",
];

export default function Page() {
  const [chats, setChats] = useState<Chat[]>([]);
  const [activeId, setActiveId] = useState<string>("");
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const loaded = useRef(false);

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(STORE) || "[]") as Chat[];
      setChats(saved);
      if (saved[0]) setActiveId(saved[0].id);
    } catch {}
    loaded.current = true;
  }, []);
  useEffect(() => {
    if (loaded.current) localStorage.setItem(STORE, JSON.stringify(chats.slice(0, 50)));
  }, [chats]);

  const active = chats.find((c) => c.id === activeId);

  function newChat() {
    setActiveId("");
    setInput("");
  }

  function removeChat(id: string) {
    setChats((cs) => cs.filter((c) => c.id !== id));
    if (activeId === id) setActiveId("");
  }

  function upsert(id: string, title: string, messages: Msg[]) {
    setChats((cs) => {
      const rest = cs.filter((c) => c.id !== id);
      return [{ id, title, messages }, ...rest];
    });
  }

  async function send(text?: string) {
    const q = (text ?? input).trim();
    if (!q || busy) return;
    const id = activeId || crypto.randomUUID();
    const title = active?.title || q.slice(0, 48);
    const history: Msg[] = [...(active?.messages || []), { role: "user", content: q }];
    if (!activeId) setActiveId(id);
    upsert(id, title, [...history, { role: "assistant", content: "" }]);
    setInput("");
    setBusy(true);
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: history.map(({ role, content }) => ({ role, content })),
        }),
      });
      if (!res.ok || !res.body) {
        const err = await res.text();
        upsert(id, title, [...history, { role: "assistant", content: `⚠️ ${err}` }]);
        return;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let raw = "";
      let sources: Src[] | undefined;
      let body = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        raw += decoder.decode(value, { stream: true });
        if (!sources) {
          const cut = raw.indexOf("\n\n");
          if (cut === -1) continue;
          try {
            sources = (JSON.parse(raw.slice(0, cut)) as { sources: Src[] }).sources;
          } catch {
            sources = [];
          }
          body = raw.slice(cut + 2);
        } else {
          body = raw.slice(raw.indexOf("\n\n") + 2);
        }
        upsert(id, title, [...history, { role: "assistant", content: body, sources }]);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-dvh">
      {/* sidebar — previous chats */}
      <aside className="hidden w-64 shrink-0 flex-col border-r bg-muted/30 sm:flex">
        <div className="p-3">
          <Button variant="outline" className="w-full justify-start gap-2" onClick={newChat}>
            <MessageSquarePlus className="size-4" /> New chat
          </Button>
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto px-3 pb-3">
          {chats.map((c) => (
            <div
              key={c.id}
              className={`group flex cursor-pointer items-center justify-between rounded-md px-3 py-2 text-sm hover:bg-accent ${
                c.id === activeId ? "bg-accent font-medium" : "text-muted-foreground"
              }`}
              onClick={() => setActiveId(c.id)}
            >
              <span className="truncate">{c.title}</span>
              <button
                className="invisible ml-2 text-muted-foreground hover:text-destructive group-hover:visible"
                onClick={(e) => {
                  e.stopPropagation();
                  removeChat(c.id);
                }}
                aria-label="Delete chat"
              >
                <Trash2 className="size-3.5" />
              </button>
            </div>
          ))}
          {chats.length === 0 && (
            <p className="px-3 py-2 text-xs text-muted-foreground">
              Your chats are saved here, on this device.
            </p>
          )}
        </nav>
        <div className="border-t p-3 text-xs text-muted-foreground">
          Dag Heward-Mills Ministry Wiki
        </div>
      </aside>

      {/* main */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-b px-6 py-3">
          <h1 className="text-lg font-semibold">
            {active?.title || "Dag Heward-Mills Ministry Wiki"}
          </h1>
          <p className="text-sm text-muted-foreground">
            6,700+ messages, 133 books, and the Marriage Wiki — every answer shows its sources.
          </p>
        </header>

        <ChatContainerRoot className="relative flex-1 overflow-y-auto">
          <ChatContainerContent className="mx-auto w-full max-w-3xl space-y-6 px-4 py-6">
            {!active?.messages?.length && (
              <div className="mx-auto mt-16 max-w-md space-y-2 text-center">
                <p className="text-muted-foreground">Ask anything — for example:</p>
                {SUGGESTIONS.map((s) => (
                  <Button
                    key={s}
                    variant="outline"
                    className="h-auto w-full whitespace-normal py-2"
                    onClick={() => send(s)}
                  >
                    {s}
                  </Button>
                ))}
              </div>
            )}
            {active?.messages?.map((m, i) =>
              m.role === "user" ? (
                <Message key={i} className="justify-end">
                  <MessageContent className="bg-primary text-primary-foreground">
                    {m.content}
                  </MessageContent>
                </Message>
              ) : (
                <Message key={i} className="justify-start">
                  <div className="w-full min-w-0 flex-1">
                    {m.content ? (
                      <Markdown className="prose max-w-none">{m.content}</Markdown>
                    ) : (
                      <Loader variant="typing" />
                    )}
                    {!!m.sources?.length && (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {m.sources.map((s, j) => (
                          <Source key={j} href={s.url}>
                            <SourceTrigger showFavicon label={s.title.slice(0, 28)} />
                            <SourceContent
                              title={s.title}
                              description={`${s.speaker} — ${s.corpus}`}
                            />
                          </Source>
                        ))}
                      </div>
                    )}
                  </div>
                </Message>
              )
            )}
            <div className="absolute bottom-4 right-4">
              <ScrollButton />
            </div>
          </ChatContainerContent>
        </ChatContainerRoot>

        <div className="mx-auto w-full max-w-3xl px-4 pb-4">
          <PromptInput
            value={input}
            onValueChange={setInput}
            onSubmit={() => send()}
            isLoading={busy}
          >
            <PromptInputTextarea placeholder="Ask about any message, book, or marriage teaching…" />
            <PromptInputActions className="justify-end pt-2">
              <PromptInputAction tooltip="Send">
                <Button size="icon" className="rounded-full" onClick={() => send()} disabled={busy}>
                  <ArrowUp className="size-4" />
                </Button>
              </PromptInputAction>
            </PromptInputActions>
          </PromptInput>
        </div>
      </div>
    </div>
  );
}
