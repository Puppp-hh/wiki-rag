import { useEffect, useRef, useState, useCallback } from "react";
import "../styles/Library.css";

type FileItem = {
  name: string;
  kind: LibraryKind;
  wikiName?: string;
  editable: boolean;
  chunks: number | null;
  indexed: boolean;
  updatedAt: string;
};

type Preview = {
  name: string;
  kind: LibraryKind;
  editable: boolean;
  previewUrl?: string;
  content: string;
  updatedAt: string;
};

type LibraryKind = "md" | "text" | "code" | "pdf" | "word" | "image" | "other";
type NewFileType = "md" | "txt" | "py" | "java";

const CODE_EXTS =
  "java|py|js|jsx|ts|tsx|vue|html|css|scss|json|xml|ya?ml|sql|sh|go|c|cpp|h|hpp|cs|php|rb|rs|kt|swift|properties|gradle";
const SUPPORTED_UPLOAD_RE = new RegExp(
  `\\.(md|txt|pdf|docx|png|jpe?g|webp|${CODE_EXTS})$`,
  "i"
);
const EDITABLE_RE = new RegExp(`\\.(md|txt|${CODE_EXTS})$`, "i");
const SUPPORTED_ACCEPT =
  ".md,.txt,.pdf,.docx,.png,.jpg,.jpeg,.webp,.java,.py,.js,.jsx,.ts,.tsx,.vue,.html,.css,.scss,.json,.xml,.yml,.yaml,.sql,.sh,.go,.c,.cpp,.h,.hpp,.cs,.php,.rb,.rs,.kt,.swift,.properties,.gradle,text/markdown,text/plain,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,image/*";

type RebuildTask = {
  task_id?: string;
  ok?: boolean;
  status: "queued" | "running" | "done" | "error" | "missing";
  stage?: string;
  message?: string;
  percent?: number;
  current_file?: string;
  file_index?: number;
  file_total?: number;
  chunk_index?: number;
  chunk_total?: number;
  chunk_count?: number;
  synced?: number;
  reused?: number;
  rebuilt?: number;
  error?: string;
};

export function LibraryPage() {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [draftName, setDraftName] = useState("");
  const [draftContent, setDraftContent] = useState("");
  const [newFileType, setNewFileType] = useState<NewFileType>("md");
  const [isNew, setIsNew] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [rebuildTask, setRebuildTask] = useState<RebuildTask | null>(null);
  const uploadInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const progressTimerRef = useRef<number | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/library");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setFiles(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    return () => {
      if (progressTimerRef.current != null) {
        window.clearTimeout(progressTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    folderInputRef.current?.setAttribute("webkitdirectory", "");
    folderInputRef.current?.setAttribute("directory", "");
  }, []);

  async function rebuild() {
    setBusy(true);
    setError(null);
    setNotice(null);
    clearProgressTimer();
    setRebuildTask({
      status: "queued",
      stage: "queued",
      message: "等待重建索引",
      percent: 0,
    });
    try {
      const res = await fetch("/api/library/rebuild", { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!data.ok || !data.task_id) {
        throw new Error(data.error ?? "启动重建失败");
      }
      await pollRebuild(data.task_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function pollRebuild(taskId: string) {
    for (;;) {
      await delay(450);
      const res = await fetch(
        `/api/library/rebuild/${encodeURIComponent(taskId)}`
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as RebuildTask;
      setRebuildTask(data);
      if (!data.ok && data.status !== "running" && data.status !== "queued") {
        throw new Error(data.error ?? "重建失败");
      }
      if (data.status === "done") {
        await refresh();
        hideProgressLater();
        return;
      }
      if (data.status === "error" || data.status === "missing") {
        throw new Error(data.error ?? "重建失败");
      }
    }
  }

  async function uploadLibraryFiles(
    files: FileList | null,
    preserveRelativePath = false
  ) {
    const allFiles = Array.from(files ?? []);
    if (allFiles.length === 0) return;

    const uploadEntries = allFiles
      .map((file) => ({ file, name: getUploadName(file, preserveRelativePath) }))
      .filter((entry) => isSupportedUpload(entry.name));
    const skipped = allFiles.length - uploadEntries.length;
    if (uploadEntries.length === 0) {
      setError("没有找到支持的文件类型");
      return;
    }

    setBusy(true);
    setError(null);
    setNotice(skipped > 0 ? `已跳过 ${skipped} 个暂不支持的文件` : null);
    clearProgressTimer();
    setRebuildTask({
      status: "running",
      stage: "upload",
      message: "准备上传文件",
      percent: 1,
      file_index: 0,
      file_total: uploadEntries.length,
    });
    try {
      const payloadFiles: { name: string; data: string }[] = [];
      for (let i = 0; i < uploadEntries.length; i += 1) {
        const { file, name } = uploadEntries[i];
        setRebuildTask({
          status: "running",
          stage: "upload",
          message: `读取 ${name}`,
          percent: Math.round((i / uploadEntries.length) * 30) + 5,
          current_file: name,
          file_index: i + 1,
          file_total: uploadEntries.length,
        });
        const data = await readFileAsDataUrl(file);
        payloadFiles.push({ name, data });
      }

      setRebuildTask({
        status: "running",
        stage: "upload",
        message: `上传 ${uploadEntries.length} 个文件`,
        percent: 40,
        file_index: uploadEntries.length,
        file_total: uploadEntries.length,
      });

      const res = await fetch("/api/library/upload", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ files: payloadFiles }),
      });
      if (!res.ok) throw new Error(`上传失败: HTTP ${res.status}`);
      const data = await res.json();
      if (!data.ok || !data.task_id) {
        throw new Error(data.error ?? "上传失败");
      }

      setRebuildTask({
        status: "queued",
        stage: "queued",
        message: "上传完成，等待重建索引",
        percent: 45,
        file_index: uploadEntries.length,
        file_total: uploadEntries.length,
      });
      await pollRebuild(data.task_id);
      await refresh();
      setNotice(
        `已上传并索引 ${uploadEntries.length} 个文件` +
          (skipped > 0 ? `，跳过 ${skipped} 个不支持的文件` : "")
      );
      const firstName = payloadFiles[0]?.name;
      if (firstName) {
        await openPreview(firstName);
      }
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      setError(message);
      setRebuildTask((task) => ({
        status: "error",
        stage: "error",
        message: "上传失败",
        percent: 100,
        error: message,
        file_index: task?.file_index,
        file_total: task?.file_total,
      }));
    } finally {
      setBusy(false);
      if (uploadInputRef.current) uploadInputRef.current.value = "";
      if (folderInputRef.current) folderInputRef.current.value = "";
    }
  }

  async function openPreview(name: string) {
    setSelected(name);
    setPreviewLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/library/file/${encodeLibraryPath(name)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!data.ok) throw new Error(data.error ?? "读取失败");
      setPreview({
        name: data.name,
        kind: data.kind ?? "other",
        editable: Boolean(data.editable),
        previewUrl: data.previewUrl
          ? `/api/library/blob/${encodeLibraryPath(data.name)}`
          : undefined,
        content: data.content,
        updatedAt: data.updatedAt,
      });
      setDraftName(data.name);
      setDraftContent(data.content);
      setIsNew(false);
      setDirty(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setPreview(null);
    } finally {
      setPreviewLoading(false);
    }
  }

  function newNote() {
    const base =
      newFileType === "md"
        ? "new_note"
        : newFileType === "txt"
        ? "new_text"
        : newFileType === "py"
        ? "new_script"
        : "NewClass";
    let name = `${base}.${newFileType}`;
    let i = 1;
    const names = new Set(files.map((f) => f.name));
    while (names.has(name)) {
      name = `${base}_${i}.${newFileType}`;
      i += 1;
    }
    const template =
      newFileType === "md"
        ? "# 新笔记\n\n在这里写入内容。\n"
        : newFileType === "txt"
        ? "在这里写入文本内容。\n"
        : newFileType === "py"
        ? "def main():\n    pass\n\n\nif __name__ == \"__main__\":\n    main()\n"
        : "public class NewClass {\n    public static void main(String[] args) {\n    }\n}\n";
    setSelected(name);
    setPreview({
      name,
      kind:
        newFileType === "md"
          ? "md"
          : newFileType === "txt"
          ? "text"
          : "code",
      editable: true,
      content: template,
      updatedAt: "未保存",
    });
    setDraftName(name);
    setDraftContent(template);
    setIsNew(true);
    setDirty(true);
    setError(null);
    setNotice(null);
  }

  async function saveNote() {
    const name = normalizeEditableName(draftName, newFileType);
    if (!name) {
      setError("文件名不能为空");
      return;
    }
    setDraftName(name);
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const res = await fetch(`/api/library/file/${encodeLibraryPath(name)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: draftContent }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!data.ok) throw new Error(data.error ?? "保存失败");
      await refresh();
      await openPreview(data.name);
      setNotice(`已保存并索引 ${data.name}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function deleteNote() {
    const name = normalizeExistingName(draftName);
    if (!name) return;
    if (!window.confirm(`确定删除 ${name} 吗？`)) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const res = await fetch(`/api/library/file/${encodeLibraryPath(name)}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!data.ok) throw new Error(data.error ?? "删除失败");
      setSelected(null);
      setPreview(null);
      setDraftName("");
      setDraftContent("");
      setDirty(false);
      setIsNew(false);
      await refresh();
      setNotice(`已删除 ${name}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const filtered = files.filter((f) =>
    f.name.toLowerCase().includes(query.toLowerCase())
  );
  const indexed = files.filter((f) => f.indexed).length;
  const rebuildPercent = Math.max(
    0,
    Math.min(100, Math.round(rebuildTask?.percent ?? 0))
  );
  const rebuildRunning =
    rebuildTask?.status === "queued" || rebuildTask?.status === "running";
  const rebuildFileInfo =
    rebuildTask?.file_total && rebuildTask.file_total > 0
      ? `文件 ${rebuildTask.file_index ?? 0}/${rebuildTask.file_total}`
      : "";
  const rebuildChunkInfo =
    rebuildTask?.chunk_total && rebuildTask.chunk_total > 0
      ? `段 ${rebuildTask.chunk_index ?? 0}/${rebuildTask.chunk_total}`
      : "";
  const rebuildCurrentFile = rebuildRunning ? rebuildTask?.current_file : "";

  function clearProgressTimer() {
    if (progressTimerRef.current != null) {
      window.clearTimeout(progressTimerRef.current);
      progressTimerRef.current = null;
    }
  }

  function hideProgressLater() {
    clearProgressTimer();
    progressTimerRef.current = window.setTimeout(() => {
      setRebuildTask(null);
      progressTimerRef.current = null;
    }, 1200);
  }

  return (
    <div className="page library">
      <header className="library__header">
        <div>
          <h1 className="section-title">Library</h1>
          <p className="section-stats">
            全部 {files.length} · 支持 md/txt/代码/pdf/docx/图片 · 已索引 {indexed} · 未索引{" "}
            {files.length - indexed}
          </p>
        </div>
        <button
          className="btn-primary"
          onClick={rebuild}
          disabled={busy || loading}
        >
          {rebuildRunning ? `Rebuilding ${rebuildPercent}%` : "Rebuild Index"}
        </button>
      </header>

      <div className="library__toolbar">
        <input
          className="input library__search"
          placeholder="搜索文件名…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className="library__new-group" aria-label="新建文件">
          <button className="btn-pill library__new-button" onClick={newNote} disabled={busy}>
            New File
          </button>
          <select
            className="library__type-select"
            value={newFileType}
            onChange={(e) => setNewFileType(e.target.value as NewFileType)}
            disabled={busy}
            title="选择新建文件类型"
          >
            <option value="md">Markdown</option>
            <option value="txt">Text</option>
            <option value="py">Python</option>
            <option value="java">Java</option>
          </select>
        </div>
        <input
          ref={uploadInputRef}
          className="library__upload-input"
          type="file"
          accept={SUPPORTED_ACCEPT}
          multiple
          onChange={(e) => uploadLibraryFiles(e.currentTarget.files)}
        />
        <input
          ref={folderInputRef}
          className="library__upload-input"
          type="file"
          multiple
          onChange={(e) => uploadLibraryFiles(e.currentTarget.files, true)}
        />
        <button
          className="btn-pill"
          onClick={() => uploadInputRef.current?.click()}
          disabled={busy}
        >
          Upload Files
        </button>
        <button
          className="btn-pill"
          onClick={() => folderInputRef.current?.click()}
          disabled={busy}
        >
          Upload Folder
        </button>
      </div>

      {rebuildTask && (
        <div
          className={
            "library__progress" +
            (rebuildTask.status === "error" ? " library__progress--error" : "")
          }
        >
          <div className="library__progress-row">
            <div>
              <strong>{rebuildTask.message ?? "重建索引中"}</strong>
              <span>
                {[
                  rebuildTask.stage ? `阶段 ${rebuildTask.stage}` : "",
                  rebuildFileInfo,
                  rebuildChunkInfo,
                  rebuildCurrentFile,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </span>
            </div>
            <b>{rebuildPercent}%</b>
          </div>
          <div className="library__progress-bar" aria-hidden="true">
            <div
              className="library__progress-fill"
              style={{ width: `${rebuildPercent}%` }}
            />
          </div>
          <div className="library__progress-meta">
            <span>同步 {rebuildTask.synced ?? 0}</span>
            <span>复用 {rebuildTask.reused ?? 0}</span>
            <span>重建 {rebuildTask.rebuilt ?? 0}</span>
            <span>索引段数 {rebuildTask.chunk_count ?? 0}</span>
          </div>
          {rebuildTask.error && (
            <div className="library__progress-error">{rebuildTask.error}</div>
          )}
        </div>
      )}

      {error && <div className="library__error">{error}</div>}
      {notice && <div className="library__notice">{notice}</div>}

      <div className="library__workspace">
        <div className="library__list-wrap">
          <ul className="library__list">
            <li className="library__row library__row--head">
              <span />
              <span>文件名</span>
              <span>段数</span>
              <span>状态</span>
              <span>更新时间</span>
            </li>
            {loading && filtered.length === 0 && (
              <li className="library__row library__row--empty">加载中…</li>
            )}
            {!loading && filtered.length === 0 && (
              <li className="library__row library__row--empty">没有文件</li>
            )}
            {filtered.map((f) => (
              <li
                className={
                  "library__row" + (selected === f.name ? " is-selected" : "")
                }
                key={f.name}
                onClick={() => openPreview(f.name)}
              >
                <span className="library__icon">{kindIcon(f.kind)}</span>
                <span className="library__name">{f.name}</span>
                <span className="library__chunks">
                  {f.chunks != null ? `${f.chunks} 段` : "—"}
                </span>
                <span
                  className={
                    "library__status " +
                    (f.indexed
                      ? "library__status--ok"
                      : "library__status--off")
                  }
                >
                  {f.indexed ? "已索引" : "未索引"}
                </span>
                <span className="library__time">{f.updatedAt}</span>
              </li>
            ))}
          </ul>
        </div>

        <aside className="library__preview">
          {!selected && (
            <div className="library__preview-empty">
              选择左侧文件查看内容
            </div>
          )}
          {selected && previewLoading && (
            <div className="library__preview-empty">读取中…</div>
          )}
          {preview && !previewLoading && (
            <>
              <div className="library__preview-head">
                <div>
                  <input
                    className="library__preview-name"
                    value={draftName}
                    onChange={(e) => {
                      setDraftName(e.target.value);
                      setDirty(true);
                    }}
                    disabled={!isNew && selected === preview.name}
                  />
                  <p>
                    {kindLabel(preview.kind)} · {preview.updatedAt}
                  </p>
                </div>
                <div className="library__preview-actions">
                  <button
                    className="btn-pill"
                    onClick={saveNote}
                    disabled={busy || !preview.editable || (!dirty && !isNew)}
                  >
                    保存并索引
                  </button>
                  <button
                    className="btn-pill library__danger"
                    onClick={deleteNote}
                    disabled={busy || isNew}
                  >
                    删除
                  </button>
                </div>
              </div>
              {preview.kind === "image" && preview.previewUrl && (
                <div className="library__image-preview">
                  <img src={preview.previewUrl} alt={preview.name} />
                </div>
              )}
              <textarea
                className="library__preview-editor"
                value={draftContent}
                onChange={(e) => {
                  setDraftContent(e.target.value);
                  setDirty(true);
                }}
                disabled={!preview.editable}
                spellCheck={false}
              />
            </>
          )}
        </aside>
      </div>
    </div>
  );
}

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function normalizeEditableName(value: string, fallbackExt: NewFileType = "md") {
  const trimmed = value.trim();
  if (!trimmed) return "";
  if (isEditableName(trimmed)) return trimmed;
  return `${trimmed}.${fallbackExt}`;
}

function normalizeExistingName(value: string) {
  return value.trim();
}

function isSupportedUpload(name: string) {
  return SUPPORTED_UPLOAD_RE.test(name);
}

function isEditableName(name: string) {
  return EDITABLE_RE.test(name);
}

function getUploadName(file: File, preserveRelativePath: boolean) {
  const withRelativePath = file as File & { webkitRelativePath?: string };
  return preserveRelativePath && withRelativePath.webkitRelativePath
    ? withRelativePath.webkitRelativePath
    : file.name;
}

function encodeLibraryPath(name: string) {
  return name.split("/").map(encodeURIComponent).join("/");
}

function readFileAsDataUrl(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error(`读取文件失败：${file.name}`));
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.readAsDataURL(file);
  });
}

function kindLabel(kind: LibraryKind) {
  const labels: Record<LibraryKind, string> = {
    md: "Markdown",
    text: "Text",
    code: "Code",
    pdf: "PDF",
    word: "Word",
    image: "Image",
    other: "File",
  };
  return labels[kind] ?? "File";
}

function kindIcon(kind: LibraryKind) {
  const icons: Record<LibraryKind, string> = {
    md: "MD",
    text: "TXT",
    code: "CODE",
    pdf: "PDF",
    word: "DOC",
    image: "IMG",
    other: "FILE",
  };
  return icons[kind] ?? "FILE";
}
