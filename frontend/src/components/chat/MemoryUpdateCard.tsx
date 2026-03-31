"use client";

import { useState } from "react";
import { CheckCircle, X, ChevronDown, ChevronUp, Pencil } from "lucide-react";
import { memory as memoryApi } from "@/lib/api";
import type { MemoryUpdate } from "@/types";

interface Props {
  update: MemoryUpdate;
  onDismiss: () => void;
}

export default function MemoryUpdateCard({ update, onDismiss }: Props) {
  const [expanded, setExpanded]   = useState(false);
  const [editing,  setEditing]    = useState(false);
  const [editText, setEditText]   = useState(update.content);
  const [saving,   setSaving]     = useState(false);
  const [saved,    setSaved]      = useState(false);

  async function accept(content = editText) {
    setSaving(true);
    try {
      await memoryApi.applyUpdate(update.file, {
        section: update.section,
        action:  update.action,
        content,
        reason:  update.reason,
      });
      setSaved(true);
      setTimeout(onDismiss, 800);
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  }

  const previewLines = update.content.split("\n").slice(0, 4).join("\n");
  const hasMore      = update.content.split("\n").length > 4;

  return (
    <div className="mt-3 border border-amber-200 bg-amber-50 rounded-xl overflow-hidden text-sm">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-2.5 bg-amber-100/60">
        <span className="text-amber-700 font-medium">📝 Update: {update.file}</span>
        <span className="ml-auto text-amber-600 text-xs capitalize">{update.action}</span>
      </div>

      {/* Reason */}
      <div className="px-4 pt-2 text-amber-800 text-xs">{update.reason}</div>

      {/* Content preview */}
      {!editing ? (
        <div className="px-4 py-2">
          <pre className="text-xs text-gray-700 font-mono whitespace-pre-wrap break-words leading-relaxed">
            {expanded ? update.content : previewLines}
          </pre>
          {hasMore && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="flex items-center gap-1 text-xs text-amber-700 mt-1 hover:underline"
            >
              {expanded ? <><ChevronUp size={12}/> Show less</> : <><ChevronDown size={12}/> Show more</>}
            </button>
          )}
        </div>
      ) : (
        <div className="px-4 py-2">
          <textarea
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            className="w-full text-xs font-mono border border-amber-300 rounded-lg p-2 focus:outline-none focus:ring-2 focus:ring-amber-400 resize-y min-h-[80px] bg-white"
          />
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 px-4 pb-3">
        {saved ? (
          <span className="text-xs text-green-600 flex items-center gap-1">
            <CheckCircle size={12}/> Saved
          </span>
        ) : (
          <>
            <button
              onClick={() => (editing ? accept(editText) : accept())}
              disabled={saving}
              className="flex items-center gap-1 px-3 py-1.5 bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-xs rounded-lg transition-colors"
            >
              <CheckCircle size={12}/>
              {saving ? "Saving…" : "Accept"}
            </button>

            {!editing && (
              <button
                onClick={() => setEditing(true)}
                className="flex items-center gap-1 px-3 py-1.5 border border-amber-300 hover:bg-amber-100 text-amber-800 text-xs rounded-lg transition-colors"
              >
                <Pencil size={12}/> Edit
              </button>
            )}

            <button
              onClick={onDismiss}
              className="ml-auto flex items-center gap-1 px-3 py-1.5 text-gray-500 hover:text-gray-700 text-xs rounded-lg transition-colors"
            >
              <X size={12}/> Skip
            </button>
          </>
        )}
      </div>
    </div>
  );
}
