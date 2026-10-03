"use client";

import { useState } from "react";
import {
  ChatContainerRoot,
  ChatContainerContent,
} from "@/components/ui/chat-container";
import {
  Message,
  MessageContent,
} from "@/components/ui/message";
import { Markdown } from "@/components/ui/markdown";
import {
  PromptInput,
  PromptInputTextarea,
  PromptInputActions,
  PromptInputAction,
} from "@/components/ui/prompt-input";
import { Loader } from "@/components/ui/loader";
import { ScrollButton } from "@/components/ui/scroll-button";
import { Button } from "@/components/ui/button";
import { ArrowUp } from "lucide-react";

type Msg = { role: "user" | "assistant"; content: string };

const SUGGESTIONS = [
  "What does Bishop Dag teach about the anointing?",
  "What has been said about a wife submitting to her husband?",
  "Summarize the Margaret story and where it is told",
  "What does Joshua Heward-Mills teach about prayer?",
];

export default function Chat() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  async function send(text?: string) {
    const q = (text ?? input).trim();
    if (!q || busy) return;
    const next: Msg[] = [...messages, { role: "user", content: q }];
    setMessages([...next, { role: "assistant", content: "" }]);
    setInput("");
    setBusy(true);
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: next }),
      });
      if (!res.ok || !res.body) {
        const err = await res.text();
        setMessages([...next, { role: "assistant", content: `⚠️ ${err}` }]);
        return;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let acc = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        acc += decoder.decode(value, { stream: true });
        setMessages([...next, { role: "assistant", content: acc }]);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-dvh flex-col">
      <header className="border-b px-6 py-3">
        <h1 className="text-lg font-semibold">Dag Heward-Mills Ministry Wiki</h1>
        <p className="text-sm text-muted-foreground">
          Chat with 6,700+ messages, 133 books, and the Marriage Wiki — answers cite their sources.
        </p>
      </header>

      <ChatContainerRoot className="relative flex-1 overflow-y-auto">
        <ChatContainerContent className="mx-auto w-full max-w-3xl space-y-6 px-4 py-6">
          {messages.length === 0 && (
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
          {messages.map((m, i) =>
            m.role === "user" ? (
              <Message key={i} className="justify-end">
                <MessageContent className="bg-primary text-primary-foreground">
                  {m.content}
                </MessageContent>
              </Message>
            ) : (
              <Message key={i} className="justify-start">
                <div className="prose max-w-none flex-1 rounded-lg">
                  {m.content ? (
                    <Markdown>{m.content}</Markdown>
                  ) : (
                    <Loader variant="typing" />
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
  );
}
