"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { FolderOpen, Upload, FileText, Trash2, ExternalLink, Loader2, FolderTree } from "lucide-react";
import { portfolio } from "@/lib/api";
import type { PortfolioFile, PortfolioFolder } from "@/types";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(dateString: string): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(dateString));
}

export default function PortfolioPage() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const folderInputRef = useRef<HTMLInputElement | null>(null);
  const [files, setFiles] = useState<PortfolioFile[]>([]);
  const [folders, setFolders] = useState<PortfolioFolder[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [openingFile, setOpeningFile] = useState<string | null>(null);
  const [deletingEntry, setDeletingEntry] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadFiles(showLoading = true) {
    if (showLoading) setLoading(true);
    setError(null);
    try {
      const data = await portfolio.list();
      setFiles(data.files);
      setFolders(data.folders);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load portfolio files");
    } finally {
      if (showLoading) setLoading(false);
    }
  }

  useEffect(() => {
    loadFiles();
  }, []);

  useEffect(() => {
    if (!folderInputRef.current) return;
    folderInputRef.current.setAttribute("webkitdirectory", "");
    folderInputRef.current.setAttribute("directory", "");
  }, []);

  const acceptedTypes = useMemo(() => ".pdf,.doc,.docx", []);

  async function handleUpload(selected: FileList | null, preserveFolders = false) {
    if (!selected || selected.length === 0) return;
    setUploading(true);
    setError(null);
    try {
      const fileArray = Array.from(selected);
      const paths = preserveFolders
        ? fileArray.map((file) => (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name)
        : undefined;
      await portfolio.upload(fileArray, paths);
      await loadFiles(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
      if (folderInputRef.current) folderInputRef.current.value = "";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleOpen(filename: string) {
    setOpeningFile(filename);
    setError(null);
    try {
      await portfolio.open(filename);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not open file");
    } finally {
      setOpeningFile(null);
    }
  }

  async function handleDelete(entryPath: string) {
    setDeletingEntry(entryPath);
    setError(null);
    try {
      await portfolio.delete(entryPath);
      await loadFiles(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete file");
    } finally {
      setDeletingEntry(null);
    }
  }

  const groupedFiles = useMemo(() => {
    const groups = new Map<string, PortfolioFile[]>();
    for (const file of files) {
      const parts = file.relative_path.split("/");
      const groupKey = parts.length > 1 ? parts.slice(0, -1).join("/") : "";
      const current = groups.get(groupKey) ?? [];
      current.push(file);
      groups.set(groupKey, current);
    }
    return Array.from(groups.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [files]);

  return (
    <div className="h-full overflow-y-auto bg-gray-50">
      <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">Portfolio</h1>
            <p className="text-sm text-gray-500 mt-1">
              Keep your job-search documents in one place. Upload resumes, offer letters, cover letters, or interview materials as PDF or Word files.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="inline-flex items-center gap-2 rounded-xl bg-futuro-500 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-futuro-600 disabled:opacity-60"
            >
              {uploading ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
              {uploading ? "Uploading..." : "Upload files"}
            </button>
            <button
              onClick={() => folderInputRef.current?.click()}
              disabled={uploading}
              className="inline-flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:opacity-60"
            >
              <FolderTree size={16} />
              Upload folder
            </button>
          </div>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={acceptedTypes}
          className="hidden"
          onChange={(e) => handleUpload(e.target.files, false)}
        />
        <input
          ref={folderInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => handleUpload(e.target.files, true)}
        />

        <div className="grid gap-4 md:grid-cols-[1.1fr_0.9fr]">
          <section className="rounded-2xl border border-dashed border-futuro-200 bg-white p-6">
            <div className="flex items-start gap-3">
              <div className="rounded-2xl bg-futuro-50 p-3 text-futuro-600">
                <FolderOpen size={22} />
              </div>
              <div className="space-y-2">
                <h2 className="text-base font-semibold text-gray-900">Your document vault</h2>
                <p className="text-sm leading-6 text-gray-500">
                  Store materials you use across the whole search, like resume versions, case prep PDFs, role descriptions, offer docs, or recruiter follow-up notes.
                </p>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="inline-flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-700 transition-colors hover:bg-gray-50"
                >
                  <Upload size={15} />
                  Choose PDF / Word files
                </button>
                <button
                  onClick={() => folderInputRef.current?.click()}
                  className="ml-2 inline-flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-700 transition-colors hover:bg-gray-50"
                >
                  <FolderTree size={15} />
                  Choose a folder
                </button>
              </div>
            </div>
          </section>

          <section className="rounded-2xl border border-gray-200 bg-white p-6">
            <h2 className="text-base font-semibold text-gray-900">Supported now</h2>
            <ul className="mt-3 space-y-2 text-sm text-gray-500">
              <li>PDF resumes and offer documents</li>
              <li>Word files: `.doc` and `.docx`</li>
              <li>Folder upload keeps subfolder structure</li>
              <li>Open in browser or delete files or whole folders</li>
              <li>Stored locally under `backend/data/portfolio`</li>
            </ul>
          </section>
        </div>

        {folders.length > 0 && (
          <section className="rounded-2xl border border-gray-200 bg-white">
            <div className="border-b border-gray-100 px-6 py-4">
              <h2 className="text-base font-semibold text-gray-900">Folders</h2>
              <p className="mt-1 text-xs text-gray-400">{folders.length} saved folder{folders.length === 1 ? "" : "s"}</p>
            </div>
            <div className="grid gap-3 p-6 md:grid-cols-2 xl:grid-cols-3">
              {folders.map((folder) => (
                <div key={folder.path} className="rounded-xl border border-gray-200 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 text-gray-900">
                        <FolderOpen size={16} className="text-futuro-500" />
                        <p className="truncate text-sm font-medium">{folder.path}</p>
                      </div>
                      <p className="mt-1 text-xs text-gray-400">
                        {folder.file_count} file{folder.file_count === 1 ? "" : "s"} · updated {formatDate(folder.uploaded_at)}
                      </p>
                    </div>
                    <button
                      onClick={() => handleDelete(folder.path)}
                      disabled={deletingEntry === folder.path}
                      className="rounded-lg border border-red-200 p-2 text-red-600 transition-colors hover:bg-red-50 disabled:opacity-60"
                      title="Delete folder"
                    >
                      {deletingEntry === folder.path ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {error && (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <section className="rounded-2xl border border-gray-200 bg-white">
          <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
            <div>
              <h2 className="text-base font-semibold text-gray-900">Saved files</h2>
              <p className="text-xs text-gray-400 mt-1">{files.length} document{files.length === 1 ? "" : "s"}</p>
            </div>
            <button
              onClick={() => loadFiles()}
              className="text-sm text-gray-500 transition-colors hover:text-gray-700"
            >
              Refresh
            </button>
          </div>

          {loading ? (
            <div className="px-6 py-12 text-sm text-gray-500">Loading portfolio...</div>
          ) : files.length === 0 ? (
            <div className="px-6 py-12 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-gray-100 text-gray-400">
                <FileText size={22} />
              </div>
              <h3 className="mt-4 text-sm font-medium text-gray-900">No documents yet</h3>
              <p className="mt-1 text-sm text-gray-500">
                Upload your first resume, job description, or interview prep file to start building your portfolio.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {groupedFiles.map(([groupKey, groupFiles]) => (
                <div key={groupKey || "root"}>
                  <div className="px-6 py-3 text-xs font-medium uppercase tracking-wide text-gray-400">
                    {groupKey || "Loose files"}
                  </div>
                  <div className="divide-y divide-gray-100">
                    {groupFiles.map((file) => (
                      <div key={file.relative_path} className="flex items-center gap-4 px-6 py-4">
                        <div className="rounded-xl bg-gray-100 p-3 text-gray-500">
                          <FileText size={18} />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-gray-900">{file.filename}</p>
                          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-gray-400">
                            <span>{file.relative_path}</span>
                            <span>{formatBytes(file.size_bytes)}</span>
                            <span>{formatDate(file.uploaded_at)}</span>
                            <span>{file.content_type ?? "document"}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => handleOpen(file.relative_path)}
                            disabled={openingFile === file.relative_path}
                            className="inline-flex items-center gap-1 rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-600 transition-colors hover:bg-gray-50 disabled:opacity-60"
                          >
                            {openingFile === file.relative_path ? <Loader2 size={14} className="animate-spin" /> : <ExternalLink size={14} />}
                            Open
                          </button>
                          <button
                            onClick={() => handleDelete(file.relative_path)}
                            disabled={deletingEntry === file.relative_path}
                            className="inline-flex items-center gap-1 rounded-lg border border-red-200 px-3 py-2 text-sm text-red-600 transition-colors hover:bg-red-50 disabled:opacity-60"
                          >
                            {deletingEntry === file.relative_path ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                            Delete
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
