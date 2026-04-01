"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import clsx from "clsx";
import type { Message } from "@/types";
import MemoryUpdateCard from "./MemoryUpdateCard";
import FuturoLogo from "@/components/shared/FuturoLogo";

interface Props {
  message: Message;
}

const INTENT_LABELS: Record<string, string> = {
  BQ:       "BQ Coach",
  STORY:    "Story Builder",
  RESUME:   "Resume Editor",
  INTAKE:   "Intake",
  DEBRIEF:  "Interview Debrief",
  STRATEGY: "Strategy Review",
  GENERAL:  "",
};

export default function MessageBubble({ message }: Props) {
  const [hiddenUpdates, setHiddenUpdates] = useState<number[]>([]);
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%] px-4 py-2.5 bg-futuro-500 text-white rounded-2xl rounded-tr-sm text-sm leading-relaxed">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3 max-w-[85%]">
      {/* Avatar */}
      <FuturoLogo
        size={28}
        className="mt-0.5 h-7 w-7 flex-shrink-0 rounded-full object-cover"
      />

      <div className="flex-1 min-w-0">
        {/* Intent badge */}
        {message.intent && INTENT_LABELS[message.intent] && (
          <span className="inline-block text-xs text-futuro-600 bg-futuro-50 border border-futuro-100 px-2 py-0.5 rounded-full mb-2">
            {INTENT_LABELS[message.intent]}
          </span>
        )}

        {/* Message content */}
        <div
          className={clsx(
            "prose prose-sm max-w-none text-gray-800",
            message.streaming && "streaming-cursor"
          )}
        >
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              // Style code blocks
              code: ({ children, className }) => {
                const isBlock = className?.includes("language-");
                return isBlock ? (
                  <code className="block bg-gray-100 rounded-lg px-3 py-2 text-xs font-mono overflow-x-auto">
                    {children}
                  </code>
                ) : (
                  <code className="bg-gray-100 px-1 py-0.5 rounded text-xs font-mono">
                    {children}
                  </code>
                );
              },
              // Tighten paragraph spacing
              p: ({ children }) => (
                <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>
              ),
              // Style lists
              ul: ({ children }) => (
                <ul className="list-disc list-inside space-y-1 mb-2">{children}</ul>
              ),
              ol: ({ children }) => (
                <ol className="list-decimal list-inside space-y-1 mb-2">{children}</ol>
              ),
            }}
          >
            {message.content}
          </ReactMarkdown>
        </div>

        {/* Memory update cards */}
        {message.proposedUpdates?.map((update, i) => (
          hiddenUpdates.includes(i) ? null : (
          <MemoryUpdateCard
            key={i}
            update={update}
            onDismiss={() => setHiddenUpdates((current) => [...current, i])}
          />
          )
        ))}
      </div>
    </div>
  );
}
