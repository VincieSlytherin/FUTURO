"use client";

import { useEffect, useMemo, useState } from "react";
import { CheckSquare, Plus, RefreshCw, Trash2, GraduationCap, ListTodo, Pencil, X, Save } from "lucide-react";
import { memory as memoryApi } from "@/lib/api";

type PlannerItem = {
  id: string;
  text: string;
  checked: boolean;
};

const PLACEHOLDER_ITEMS = new Set([
  "No daily tasks yet.",
  "No learning items yet.",
]);

function escapeRegex(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function parseSection(content: string, section: string): PlannerItem[] {
  const pattern = new RegExp(`(?:^|\\n)## ${escapeRegex(section)}\\n\\n?([\\s\\S]*?)(?=\\n## |$)`);
  const match = content.match(pattern);
  if (!match) return [];

  return match[1]
    .split("\n")
    .map((line, index) => {
      const trimmed = line.trim();
      if (trimmed.startsWith("- [ ] ")) {
        return { id: `${section}-${index}`, text: trimmed.slice(6).trim(), checked: false };
      }
      if (trimmed.startsWith("- [x] ") || trimmed.startsWith("- [X] ")) {
        return { id: `${section}-${index}`, text: trimmed.slice(6).trim(), checked: true };
      }
      return null;
    })
    .filter((item): item is PlannerItem => Boolean(item && item.text && !PLACEHOLDER_ITEMS.has(item.text)));
}

function serializeItems(items: PlannerItem[]): string {
  if (items.length === 0) return "";
  return items.map((item) => `- [${item.checked ? "x" : " "}] ${item.text}`).join("\n");
}

function slugify(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "") || "item";
}

function PlannerSection({
  title,
  subtitle,
  icon,
  items,
  saving,
  onToggle,
  onEdit,
  onDelete,
  onAdd,
}: {
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  items: PlannerItem[];
  saving: boolean;
  onToggle: (id: string) => void;
  onEdit: (id: string, text: string) => void;
  onDelete: (id: string) => void;
  onAdd: (text: string) => void;
}) {
  const [draft, setDraft] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingText, setEditingText] = useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!draft.trim()) return;
    onAdd(draft.trim());
    setDraft("");
  }

  function startEditing(item: PlannerItem) {
    setEditingId(item.id);
    setEditingText(item.text);
  }

  function cancelEditing() {
    setEditingId(null);
    setEditingText("");
  }

  function saveEditing() {
    if (!editingId || !editingText.trim()) return;
    onEdit(editingId, editingText.trim());
    cancelEditing();
  }

  const openCount = items.filter((item) => !item.checked).length;

  return (
    <section className="rounded-2xl border border-gray-200 bg-white">
      <div className="border-b border-gray-100 px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-futuro-50 p-2 text-futuro-600">{icon}</div>
          <div>
            <h2 className="text-base font-semibold text-gray-900">{title}</h2>
            <p className="mt-1 text-sm text-gray-500">{subtitle}</p>
          </div>
          <div className="ml-auto text-right">
            <div className="text-sm font-semibold text-gray-900">{openCount}</div>
            <div className="text-xs text-gray-400">open</div>
          </div>
        </div>
      </div>

      <div className="space-y-3 p-6">
        <form onSubmit={submit} className="flex gap-2">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={`Add a ${title.toLowerCase().slice(0, -1)}...`}
            className="flex-1 rounded-xl border border-gray-200 px-3 py-2.5 text-sm text-gray-800 outline-none transition focus:border-futuro-400 focus:ring-2 focus:ring-futuro-100"
          />
          <button
            type="submit"
            disabled={!draft.trim() || saving}
            className="inline-flex items-center gap-2 rounded-xl bg-futuro-500 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-futuro-600 disabled:opacity-50"
          >
            <Plus size={14} />
            Add
          </button>
        </form>

        {items.length === 0 ? (
          <div className="rounded-xl border border-dashed border-gray-200 px-4 py-8 text-center text-sm text-gray-400">
            Nothing here yet.
          </div>
        ) : (
          <div className="space-y-2">
            {items.map((item) => (
              <div key={item.id} className="flex items-start gap-3 rounded-xl border border-gray-100 px-4 py-3">
                <input
                  type="checkbox"
                  checked={item.checked}
                  disabled={saving}
                  onChange={() => onToggle(item.id)}
                  className="mt-0.5 h-4 w-4 rounded border-gray-300 text-futuro-500 focus:ring-futuro-400"
                />
                <div className="min-w-0 flex-1">
                  {editingId === item.id ? (
                    <div className="space-y-2">
                      <input
                        value={editingText}
                        onChange={(e) => setEditingText(e.target.value)}
                        className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm text-gray-800 outline-none transition focus:border-futuro-400 focus:ring-2 focus:ring-futuro-100"
                        autoFocus
                      />
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={saveEditing}
                          disabled={!editingText.trim() || saving}
                          className="inline-flex items-center gap-1 rounded-lg bg-futuro-500 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-futuro-600 disabled:opacity-50"
                        >
                          <Save size={12} />
                          Save
                        </button>
                        <button
                          type="button"
                          onClick={cancelEditing}
                          disabled={saving}
                          className="inline-flex items-center gap-1 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 transition hover:bg-gray-50 disabled:opacity-50"
                        >
                          <X size={12} />
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <p className={`text-sm ${item.checked ? "text-gray-400 line-through" : "text-gray-800"}`}>
                      {item.text}
                    </p>
                  )}
                </div>
                {editingId !== item.id && (
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => startEditing(item)}
                      disabled={saving}
                      className="rounded-lg p-2 text-gray-400 transition hover:bg-futuro-50 hover:text-futuro-600 disabled:opacity-50"
                      title="Edit item"
                    >
                      <Pencil size={14} />
                    </button>
                    <button
                      type="button"
                      onClick={() => onDelete(item.id)}
                      disabled={saving}
                      className="rounded-lg p-2 text-gray-400 transition hover:bg-red-50 hover:text-red-500 disabled:opacity-50"
                      title="Delete item"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

export default function PlannerPage() {
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  async function loadPlanner() {
    setLoading(true);
    setError(null);
    try {
      const data = await memoryApi.get("planner.md");
      setContent(data.content);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load planner");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadPlanner();
  }, []);

  const dailyTasks = useMemo(() => parseSection(content, "Daily tasks"), [content]);
  const learningBacklog = useMemo(() => parseSection(content, "Learning backlog"), [content]);

  async function saveSection(section: "Daily tasks" | "Learning backlog", items: PlannerItem[]) {
    setSaving(true);
    setError(null);
    setNote(null);
    try {
      const nextContent = serializeItems(items);
      await memoryApi.applyUpdate("planner.md", {
        section,
        action: "replace",
        content: nextContent,
        reason: `Updated ${section.toLowerCase()} from planner`,
      });
      const fresh = await memoryApi.get("planner.md");
      setContent(fresh.content);
      setNote("Saved to planner memory.");
      window.setTimeout(() => setNote(null), 1800);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save planner");
    } finally {
      setSaving(false);
    }
  }

  function updateItems(
    section: "Daily tasks" | "Learning backlog",
    items: PlannerItem[],
    updater: (current: PlannerItem[]) => PlannerItem[],
  ) {
    const updated = updater(items);
    void saveSection(section, updated);
  }

  return (
    <div className="h-full overflow-y-auto bg-gray-50">
      <div className="mx-auto max-w-6xl px-6 py-8 space-y-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">Planner</h1>
            <p className="mt-1 text-sm text-gray-500">
              Keep your weekly priorities, daily tasks, and learning backlog in one memory-backed checklist that Futuro can reference in chat and in the weekly digest.
            </p>
          </div>
          <button
            onClick={loadPlanner}
            disabled={loading || saving}
            className="inline-flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 transition hover:bg-gray-50 disabled:opacity-50"
          >
            <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>

        {(error || note) && (
          <div className={`rounded-xl border px-4 py-3 text-sm ${error ? "border-red-200 bg-red-50 text-red-700" : "border-green-200 bg-green-50 text-green-700"}`}>
            {error ?? note}
          </div>
        )}

        {loading ? (
          <div className="rounded-2xl border border-gray-200 bg-white px-6 py-12 text-sm text-gray-500">
            Loading planner...
          </div>
        ) : (
          <div className="grid gap-6 lg:grid-cols-2">
            <PlannerSection
              title="Daily tasks"
              subtitle="Concrete things to finish today or this week."
              icon={<CheckSquare size={18} />}
              items={dailyTasks}
              saving={saving}
              onToggle={(id) =>
                updateItems("Daily tasks", dailyTasks, (current) =>
                  current.map((item) => (item.id === id ? { ...item, checked: !item.checked } : item))
                )
              }
              onEdit={(id, text) =>
                updateItems("Daily tasks", dailyTasks, (current) =>
                  current.map((item) => (item.id === id ? { ...item, text } : item))
                )
              }
              onDelete={(id) =>
                updateItems("Daily tasks", dailyTasks, (current) => current.filter((item) => item.id !== id))
              }
              onAdd={(text) =>
                updateItems("Daily tasks", dailyTasks, (current) => [
                  ...current,
                  { id: `daily-${slugify(text)}-${Date.now()}`, text, checked: false },
                ])
              }
            />
            <PlannerSection
              title="Learning backlog"
              subtitle="Things you want to study, practice, or revisit next."
              icon={<GraduationCap size={18} />}
              items={learningBacklog}
              saving={saving}
              onToggle={(id) =>
                updateItems("Learning backlog", learningBacklog, (current) =>
                  current.map((item) => (item.id === id ? { ...item, checked: !item.checked } : item))
                )
              }
              onEdit={(id, text) =>
                updateItems("Learning backlog", learningBacklog, (current) =>
                  current.map((item) => (item.id === id ? { ...item, text } : item))
                )
              }
              onDelete={(id) =>
                updateItems("Learning backlog", learningBacklog, (current) => current.filter((item) => item.id !== id))
              }
              onAdd={(text) =>
                updateItems("Learning backlog", learningBacklog, (current) => [
                  ...current,
                  { id: `learn-${slugify(text)}-${Date.now()}`, text, checked: false },
                ])
              }
            />
          </div>
        )}

        <section className="rounded-2xl border border-gray-200 bg-white p-6">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-futuro-50 p-2 text-futuro-600">
              <ListTodo size={18} />
            </div>
            <div>
              <h2 className="text-base font-semibold text-gray-900">How chat uses this</h2>
              <p className="mt-1 text-sm text-gray-500">
                Futuro reads `planner.md` automatically, so your planner becomes part of the conversation context without getting mixed into campaign notes. You can ask things like “help me reorder today’s tasks” or “what should I learn first this week?” and it will use this checklist.
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
