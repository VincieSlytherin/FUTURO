"use client";

import { useEffect, useState, useCallback } from "react";
import { Search, RefreshCw, MessageSquare } from "lucide-react";
import { stories as storiesApi } from "@/lib/api";
import { useRouter } from "next/navigation";
import type { StorySearchResult } from "@/types";
import clsx from "clsx";

const THEME_COLORS: Record<string, string> = {
  impact:           "bg-green-100 text-green-700",
  ambiguity:        "bg-yellow-100 text-yellow-700",
  technical:        "bg-blue-100 text-blue-700",
  innovation:       "bg-purple-100 text-purple-700",
  leadership:       "bg-rose-100 text-rose-700",
  collaboration:    "bg-teal-100 text-teal-700",
  conflict:         "bg-orange-100 text-orange-700",
  failure:          "bg-red-100 text-red-700",
  prioritization:   "bg-indigo-100 text-indigo-700",
  constraints:      "bg-gray-100 text-gray-700",
};

function ThemeTag({ theme }: { theme: string }) {
  const key = theme.toLowerCase().replace(/\s+/g, "");
  const match = Object.keys(THEME_COLORS).find(k => key.includes(k));
  const cls = match ? THEME_COLORS[match] : "bg-gray-100 text-gray-600";
  return (
    <span className={clsx("text-xs px-2 py-0.5 rounded-full font-medium", cls)}>
      {theme}
    </span>
  );
}

function StoryResultCard({ result, onPractice }: { result: StorySearchResult; onPractice: (id: string) => void }) {
  const similarity = Math.round((1 - result.distance) * 100);
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono text-gray-400">{result.story_id}</span>
            <span className="text-xs text-futuro-600 bg-futuro-50 px-1.5 py-0.5 rounded">{similarity}% match</span>
          </div>
          <h3 className="font-medium text-gray-900 text-sm">{result.title}</h3>
          <p className="text-sm text-gray-600 mt-1 leading-relaxed">{result.one_liner}</p>
          {result.result_metric && (
            <p className="text-xs text-green-700 bg-green-50 inline-block px-2 py-0.5 rounded mt-2">
              ✓ {result.result_metric}
            </p>
          )}
        </div>
      </div>
      <div className="flex items-center justify-between mt-3">
        <div className="flex flex-wrap gap-1">
          {result.themes.slice(0, 3).map(t => <ThemeTag key={t} theme={t} />)}
        </div>
        <button
          onClick={() => onPractice(result.story_id)}
          className="flex items-center gap-1 text-xs text-futuro-600 hover:text-futuro-700 hover:bg-futuro-50 px-2 py-1 rounded-lg transition-colors"
        >
          <MessageSquare size={12}/> Practice
        </button>
      </div>
    </div>
  );
}

export default function StoriesPage() {
  const router = useRouter();
  const [query,    setQuery]    = useState("");
  const [results,  setResults]  = useState<StorySearchResult[]>([]);
  const [rawMd,    setRawMd]    = useState("");
  const [loading,  setLoading]  = useState(false);
  const [rebuilt,  setRebuilt]  = useState<number | null>(null);
  const [rebuilding, setRebuilding] = useState(false);
  const [mode,     setMode]     = useState<"search" | "browse">("browse");

  useEffect(() => {
    storiesApi.raw().then(d => setRawMd(d.content));
  }, []);

  const doSearch = useCallback(async (q: string) => {
    if (!q.trim()) { setResults([]); setMode("browse"); return; }
    setLoading(true);
    setMode("search");
    try {
      const data = await storiesApi.search(q, 5);
      setResults(data.results);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const t = setTimeout(() => doSearch(query), 350);
    return () => clearTimeout(t);
  }, [query, doSearch]);

  async function rebuildIndex() {
    setRebuilding(true);
    try {
      const { stories_indexed } = await storiesApi.rebuildIndex();
      setRebuilt(stories_indexed);
    } finally {
      setRebuilding(false);
    }
  }

  function practiceStory(storyId: string) {
    router.push(`/chat?prefill=Let's practice ${storyId} for behavioral questions`);
  }

  // Count stories in raw markdown
  const storyCount = (rawMd.match(/^## STORY-/gm) ?? []).length;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-gray-200 bg-white">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <h1 className="font-semibold text-gray-900">Stories</h1>
            <span className="text-xs text-gray-400">{storyCount} stored</span>
          </div>
          <button
            onClick={rebuildIndex}
            disabled={rebuilding}
            title="Rebuild semantic search index"
            className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700 px-2 py-1.5 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <RefreshCw size={13} className={rebuilding ? "animate-spin" : ""} />
            {rebuilt !== null ? `${rebuilt} indexed` : "Rebuild index"}
          </button>
        </div>
        {/* Search */}
        <div className="relative">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search by question or theme — e.g. 'Tell me about a time you handled ambiguity'"
            className="w-full pl-9 pr-4 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-futuro-500 focus:border-transparent"
          />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-6">
        {mode === "search" ? (
          <div className="space-y-3">
            {loading && <p className="text-sm text-gray-400">Searching…</p>}
            {!loading && results.length === 0 && query && (
              <div className="text-center py-12">
                <p className="text-gray-500 text-sm">No stories matched your search.</p>
                <p className="text-gray-400 text-xs mt-1">Try rebuilding the index or add more stories via chat.</p>
              </div>
            )}
            {results.map(r => (
              <StoryResultCard key={r.story_id} result={r} onPractice={practiceStory} />
            ))}
          </div>
        ) : (
          /* Browse mode: render raw markdown as structured view */
          <div>
            {storyCount === 0 ? (
              <div className="text-center py-20">
                <p className="text-gray-500 text-sm font-medium">No stories yet.</p>
                <p className="text-gray-400 text-xs mt-1 max-w-xs mx-auto">
                  Go to Chat and say "Help me document a story about [project]" to add your first one.
                </p>
              </div>
            ) : (
              <pre className="text-sm text-gray-700 whitespace-pre-wrap font-sans leading-relaxed">
                {rawMd}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
