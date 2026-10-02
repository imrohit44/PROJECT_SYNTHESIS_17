import { ShieldCheck, Sparkles } from "lucide-react";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { apiMessage, sendAssistantMessage } from "../lib/api";
import type { AssistantToolCall } from "../types/api";
import { Panel } from "../components/ui/Panel";
import { Button } from "../components/ui/Button";
import { Field } from "../components/ui/Field";
import { Empty, ErrorState } from "../components/ui/Feedback";

interface ChatEntry {
  role: "user" | "assistant";
  content: string;
  toolCalls: AssistantToolCall[];
}

export function Assistant() {
  const [message, setMessage] = useState("");
  const [thread, setThread] = useState<ChatEntry[]>([]);
  const [error, setError] = useState("");
  const chat = useMutation({
    mutationFn: sendAssistantMessage,
    onSuccess: (reply) => setThread((current) => [...current, { role: "assistant", content: reply.response, toolCalls: reply.tool_calls ?? [] }]),
    onError: (failure) => setError(apiMessage(failure, "The assistant is unavailable right now.")),
  });

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const question = message.trim();
    if (!question || chat.isPending) return;
    setError("");
    setThread((current) => [...current, { role: "user", content: question, toolCalls: [] }]);
    setMessage("");
    chat.mutate(question);
  }

  return <div className="narrow-page"><div className="page-heading"><div><span className="eyebrow">Assistant</span><h1>Ask Project Synthesis 17</h1><p className="muted">Look up your accounts, transactions and fraud assessments in plain language.</p></div><span className="secure"><ShieldCheck size={14} /> Read-only</span></div><Panel className="assistant-panel">{thread.length === 0 ? <Empty title="Ask a question" detail="Try asking about a balance, a recent transaction, or a flagged payment." /> : <div className="chat-thread" role="log" aria-live="polite">{thread.map((entry, index) => <MessageBubble key={`${entry.role}-${index}`} entry={entry} />)}</div>}{error && <ErrorState message={error} />}<form className="chat-form" onSubmit={submit}><Field id="assistant-message" label="Your question" placeholder="What is my balance?" maxLength={2000} value={message} onChange={(e) => setMessage(e.target.value)} hint="The assistant can read your data. It can never move money." /><Button type="submit" disabled={chat.isPending || message.trim() === ""}>{chat.isPending ? "Thinking…" : "Send"}<Sparkles size={16} /></Button></form></Panel></div>;
}

function MessageBubble({ entry }: { entry: ChatEntry }) {
  return <div className={`chat-bubble ${entry.role}`}><span className="chat-role">{entry.role === "user" ? "You" : "Project Synthesis 17 assistant"}</span><p>{entry.content}</p>{entry.toolCalls.length > 0 && <div className="chat-tools">{entry.toolCalls.map((call, index) => <span className={`chat-tool ${call.status}`} key={`${call.tool}-${index}`}>{call.tool} · {call.status}</span>)}</div>}</div>;
}
