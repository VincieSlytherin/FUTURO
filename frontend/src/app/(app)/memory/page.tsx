"use client";

import { useEffect, useState } from "react";
import { Save, GitCommit, ChevronRight } from "lucide-react";
import { memory as memoryApi } from "@/lib/api";
import type { MemoryFile } from "@/types";
import clsx from "clsx";

const FILES = [
  { key: "L0_identity.md",     label: "L0 Identity",    desc: "Who you are — stable" },
  { key: "L1_campaign.md",     label: "L1 Campaign",    desc: "Current search — updated each session" },
  { key: "L2_knowledge.md",    label: "L2 Knowledge",   desc: "Strategy + learnings" },
  { key: "stories_bank.md",    label: "Stories",        desc: "STAR story bank" },
  { key: "resume_versions.md", label: "Resume",         desc: "Version history + bullets" },
  { key: "interview_log.md",   label: "Interviews",     desc: "Log + patterns" },
];

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return "never";
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins  = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days  = Math.floor(diff / 86400000);
  if (mins  < 2)  return "just now";
  if (hours < 1)  return `${mins}m ago`;
  if (days  < 1)  return `${hours}h ago`;
  if (days  < 30) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

export default function MemoryPage() {
  const [active,   setActive]   = useState("L0_identity.md");
  const [content,  setContent]  = useState("");
  const [original, setOriginal] = useState("");
  const [saving,   setSaving]   = useState(false);
  const [saved,    setSaved]    = useState(false);
  const [files,    setFiles]    = useState<MemoryFile[]>([]);
  const [gitLog,   setGitLog]   = useState<Array<{ hash: string; message: string; timestamp: string; files_changed: string[] }>>([]);
  const [showLog,  setShowLog]  = useState(false);

  useEffect(() => {
    memoryApi.list().then(d => setFiles(d.files));
    memoryApi.gitLog().then(d => setGitLog(d.commits));
  }, []);

  useEffect(() => {
    memoryApi.get(active).then(d => {
      setContent(d.content);
      setOriginal(d.content);
      setSaved(false);
    });
  }, [active]);

  const isDirty = content !== original;

  async function handleSave() {
    setSaving(true);
    try {
      await memoryApi.write(active, content);
      setOriginal(content);
      setSaved(true);
      // Refresh file list and git log
      const [fl, gl] = await Promise.all([memoryApi.list(), memoryApi.gitLog()]);
      setFiles(fl.files);
      setGitLog(gl.commits);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  }

  const fileInfo = files.find(f => f.filename === active);
  const activeFile = FILES.find(f => f.key === active);

  return (
    <div className="flex h-full">
      {/* Sidebar - file list */}
      <div className="w-56 flex-shrink-0 bg-white border-r border-gray-200 flex flex-col overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100">
          <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Memory files</h2>
        </div>
        <nav className="flex-1 overflow-y-auto p-2 space-y-0.5">
          {FILES.map(f => {
            const info = files.find(fi => fi.filename === f.key);
            return (
              <button
                key={f.key}
                onClick={() => setActive(f.key)}
                className={clsx(
                  "w-full text-left px-3 py-2.5 rounded-lg transition-colors",
                  active === f.key
                    ? "bg-futuro-50 text-futuro-700"
                    : "text-gray-700 hover:bg-gray-100"
                )}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">{f.label}</span>
                  {active === f.key && <ChevronRight size={13} className="text-futuro-400" />}
                </div>
                <div className="text-xs text-gray-400 mt-0.5">{timeAgo(info?.last_modified ?? null)}</div>
              </button>
            );
          })}
        </nav>

        {/* Git log toggle */}
        <div className="border-t border-gray-100 p-2">
          <button
            onClick={() => setShowLog(!showLog)}
            className="flex items-center gap-1.5 w-full px-3 py-2 text-xs text-gray-500 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <GitCommit size={13} />
            Git history
          </button>
        </div>
      </div>

      {/* Editor */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Editor header */}
        <div className="flex-shrink-0 flex items-center justify-between px-5 py-3 border-b border-gray-200 bg-white">
          <div>
            <h1 className="font-medium text-gray-900 text-sm">{activeFile?.label}</h1>
            <p className="text-xs text-gray-400">
              {activeFile?.desc}
              {fileInfo?.last_commit && ` · ${fileInfo.last_commit}`}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {isDirty && <span className="text-xs text-amber-600">Unsaved changes</span>}
            {saved   && <span className="text-xs text-green-600">✓ Saved</span>}
            <button
              onClick={handleSave}
              disabled={!isDirty || saving}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-futuro-500 hover:bg-futuro-600 disabled:opacity-40 text-white text-xs rounded-lg transition-colors"
            >
              <Save size={13} />
              {saving ? "Saving…" : "Save + commit"}
            </button>
          </div>
        </div>

        {/* Textarea */}
        <div className="flex-1 overflow-hidden">
          <textarea
            value={content}
            onChange={e => setContent(e.target.value)}
            className="w-full h-full resize-none px-6 py-5 font-mono text-sm text-gray-800 leading-relaxed focus:outline-none bg-white border-0"
            spellCheck={false}
          />
        </div>
      </div>

      {/* Git log panel */}
      {showLog && (
        <div className="w-64 flex-shrink-0 bg-white border-l border-gray-200 flex flex-col overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">History</h3>
            <button onClick={() => setShowLog(false)} className="text-gray-400 hover:text-gray-600 text-xs">✕</button>
          </div>
          <div className="flex-1 overflow-y-auto scrollbar-thin p-3 space-y-2">
            {gitLog.length === 0 && (
              <p className="text-xs text-gray-400 text-center py-4">No commits yet</p>
            )}
            {gitLog.map(c => (
              <div key={c.hash} className="text-xs border border-gray-100 rounded-lg p-2.5">
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span className="font-mono text-gray-400">{c.hash}</span>
                  <span className="text-gray-400 ml-auto">{timeAgo(c.timestamp)}</span>
                </div>
                <p className="text-gray-700 leading-snug">{c.message}</p>
                {c.files_changed.length > 0 && (
                  <p className="text-gray-400 mt-1">{c.files_changed.join(", ")}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
