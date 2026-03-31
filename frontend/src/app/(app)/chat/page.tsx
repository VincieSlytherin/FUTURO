"use client";

import { useRef, useEffect, useState } from "react";
import { Send, Loader2, Paperclip, Link } from "lucide-react";
import { streamChat, intakeUrl } from "@/lib/api";
import { useChatStore } from "@/lib/store";
import MessageBubble from "@/components/chat/MessageBubble";
import FuturoLogo from "@/components/shared/FuturoLogo";

export default function ChatPage() {
  const [input, setInput]       = useState("");
  const [urlInput, setUrlInput] = useState("");
  const [showUrl, setShowUrl]   = useState(false);
  const bottomRef               = useRef<HTMLDivElement>(null);
  const textareaRef             = useRef<HTMLTextAreaElement>(null);

  const {
    messages, isStreaming, activeIntent,
    addUserMessage, startAssistantMessage, appendToken, finalizeMessage, setIntent,
  } = useChatStore();

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 160) + "px";
  }, [input]);

  function buildHistory() {
    return messages
      .filter((m) => !m.streaming)
      .map((m) => ({ role: m.role, content: m.content }));
  }

  async function send(text: string) {
    if (!text.trim() || isStreaming) return;
    setInput("");

    addUserMessage(text);
    const assistantId = startAssistantMessage();

    try {
      await streamChat(text, buildHistory(), {
        onIntent: (intent) => {
          setIntent(intent);
          // Patch the intent onto the message we just started
          useChatStore.setState((s) => ({
            messages: s.messages.map((m) =>
              m.id === assistantId ? { ...m, intent } : m
            ),
          }));
        },
        onToken: (token) => appendToken(assistantId, token),
        onComplete: (updates) => finalizeMessage(assistantId, updates),
        onError: (err) => {
          finalizeMessage(assistantId, []);
          useChatStore.setState((s) => ({
            messages: s.messages.map((m) =>
              m.id === assistantId
                ? { ...m, content: `Sorry, something went wrong: ${err.message}` }
                : m
            ),
          }));
        },
      });
    } catch (err) {
      finalizeMessage(assistantId, []);
    }
  }

  async function handleUrlIntake() {
    if (!urlInput.trim() || isStreaming) return;
    const url = urlInput.trim();
    setUrlInput("");
    setShowUrl(false);

    addUserMessage(`🔗 Intake: ${url}`);
    const assistantId = startAssistantMessage();

    await intakeUrl(url, {
      onToken: (t) => appendToken(assistantId, t),
      onComplete: () => finalizeMessage(assistantId, []),
      onError:   (e) => finalizeMessage(assistantId, []),
    });
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  }

  const isEmpty = messages.length === 0;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex-shrink-0 flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-white">
        <div className="flex items-center gap-2">
          <h1 className="font-semibold text-gray-900">Chat</h1>
          {activeIntent && activeIntent !== "GENERAL" && (
            <span className="text-xs text-futuro-600 bg-futuro-50 border border-futuro-100 px-2 py-0.5 rounded-full">
              {activeIntent.charAt(0) + activeIntent.slice(1).toLowerCase().replace("_", " ")}
            </span>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto scrollbar-thin px-6 py-6 space-y-6">
        {isEmpty && (
          <div className="flex flex-col items-center justify-center h-full text-center gap-4 pb-12">
            <FuturoLogo
              size={64}
              className="h-16 w-16 rounded-2xl object-cover shadow-sm"
            />
            <div>
              <p className="text-gray-900 font-medium text-lg">Hey — I'm Futuro.</p>
              <p className="text-gray-500 text-sm mt-1 max-w-xs">
                Your job search companion. How are you doing today?
              </p>
            </div>
            <div className="flex flex-wrap gap-2 justify-center mt-2">
              {[
                "Practice BQ questions",
                "Review my search strategy",
                "Help me tailor my resume",
                "I just finished an interview",
              ].map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="text-xs px-3 py-1.5 rounded-full border border-gray-200 text-gray-600 hover:bg-gray-100 hover:border-gray-300 transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* URL intake bar */}
      {showUrl && (
        <div className="flex-shrink-0 px-6 py-2 bg-amber-50 border-t border-amber-200 flex gap-2">
          <input
            type="url"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleUrlIntake()}
            placeholder="Paste a URL to process (article, JD, post…)"
            className="flex-1 text-sm px-3 py-1.5 border border-amber-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-400 bg-white"
            autoFocus
          />
          <button
            onClick={handleUrlIntake}
            disabled={!urlInput.trim() || isStreaming}
            className="px-4 py-1.5 bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-sm rounded-lg transition-colors"
          >
            Process
          </button>
          <button onClick={() => setShowUrl(false)} className="text-gray-400 hover:text-gray-600 px-1">✕</button>
        </div>
      )}

      {/* Input area */}
      <div className="flex-shrink-0 px-6 py-4 border-t border-gray-200 bg-white">
        <div className="flex items-end gap-3">
          {/* URL intake toggle */}
          <button
            onClick={() => setShowUrl(!showUrl)}
            title="Process a URL"
            className="flex-shrink-0 p-2 text-gray-400 hover:text-futuro-500 hover:bg-futuro-50 rounded-lg transition-colors"
          >
            <Link size={18} />
          </button>

          {/* Message input */}
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Message Futuro… (Enter to send, Shift+Enter for newline)"
              disabled={isStreaming}
              rows={1}
              className="w-full resize-none px-4 py-2.5 pr-12 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-futuro-500 focus:border-transparent disabled:bg-gray-50 disabled:cursor-not-allowed leading-relaxed scrollbar-thin"
            />
          </div>

          {/* Send button */}
          <button
            onClick={() => send(input)}
            disabled={!input.trim() || isStreaming}
            className="flex-shrink-0 p-2.5 bg-futuro-500 hover:bg-futuro-600 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-xl transition-colors"
          >
            {isStreaming
              ? <Loader2 size={18} className="animate-spin" />
              : <Send size={18} />
            }
          </button>
        </div>
        <p className="text-xs text-gray-400 mt-2 pl-11">
          Shift+Enter for newline · Futuro sees your memory files automatically
        </p>
      </div>
    </div>
  );
}
