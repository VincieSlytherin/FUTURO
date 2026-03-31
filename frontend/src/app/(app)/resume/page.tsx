"use client";

import { useEffect, useState } from "react";
import { memory as memoryApi } from "@/lib/api";

export default function ResumePage() {
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    memoryApi.get("resume_versions.md")
      .then(d => setContent(d.content))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="flex flex-col h-full">
      <div className="flex-shrink-0 px-6 py-4 border-b border-gray-200 bg-white">
        <h1 className="font-semibold text-gray-900">Resume</h1>
        <p className="text-xs text-gray-400 mt-0.5">Version-controlled resume history. Use Chat → Resume Editor to tailor for a specific JD.</p>
      </div>
      <div className="flex-1 overflow-y-auto scrollbar-thin p-6">
        {loading ? (
          <p className="text-gray-400 text-sm">Loading…</p>
        ) : (
          <pre className="text-sm text-gray-700 whitespace-pre-wrap font-sans leading-relaxed max-w-3xl">
            {content}
          </pre>
        )}
      </div>
    </div>
  );
}
