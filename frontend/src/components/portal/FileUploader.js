// Wave 5B: drag-drop file uploader + attachment chips.
import React, { useRef, useState, useCallback } from "react";
import { Upload, X, Loader2, ExternalLink, Download, Image as ImageIcon, FileText, Trash2 } from "lucide-react";
import { FilesAPI, openStoredFile } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/sonner";

const MAX_MB = 50;

function bytesFmt(n) {
  if (!n) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

export function FileUploader({ onUploaded, links = {}, purpose = "general", accept = "*", multiple = false, label = "Перетягніть файл або натисніть, щоб обрати", testid = "file-uploader" }) {
  const ref = useRef(null);
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);

  const upload = useCallback(async (files) => {
    if (!files || !files.length) return;
    setBusy(true);
    try {
      for (const file of files) {
        if (file.size > MAX_MB * 1024 * 1024) { toast.error(`${file.name}: > ${MAX_MB} MB`); continue; }
        const fd = new FormData();
        fd.append("file", file);
        fd.append("purpose", purpose);
        for (const [k, v] of Object.entries(links || {})) if (v) fd.append(k, v);
        const r = await FilesAPI.upload(fd);
        onUploaded && onUploaded(r.file);
      }
      toast.success(`Завантажено ${files.length}`);
    } catch (e) { toast.error(e?.response?.data?.detail || "Не вдалося завантажити"); }
    finally { setBusy(false); if (ref.current) ref.current.value = ""; }
  }, [onUploaded, links, purpose]);

  const onPick = (e) => upload(Array.from(e.target.files || []));
  const onDrop = (e) => { e.preventDefault(); setDrag(false); upload(Array.from(e.dataTransfer.files || [])); };

  return (
    <div className={`relative rounded-xl border-2 border-dashed p-4 transition ${drag ? "border-[hsl(var(--primary))] bg-[hsl(var(--accent))]" : "border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/40"}`}
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={onDrop}
      onClick={() => !busy && ref.current?.click()}
      data-testid={testid}>
      <input ref={ref} type="file" accept={accept} multiple={multiple} onChange={onPick} className="hidden" data-testid={`${testid}-input`} />
      <div className="flex flex-col items-center gap-2 text-center text-sm">
        {busy ? <Loader2 className="h-6 w-6 animate-spin text-[hsl(var(--primary))]" /> : <Upload className="h-6 w-6 text-[hsl(var(--primary))]" />}
        <div className="font-medium text-slate-800">{busy ? "Завантаження…" : label}</div>
        <div className="text-xs text-slate-500">До {MAX_MB} MB · PDF, Word, Excel, JPG, PNG, WebP</div>
      </div>
    </div>
  );
}

export function AttachmentChip({ file, onRemove, testid }) {
  const isImage = (file.mime || "").startsWith("image/");
  const Icon = isImage ? ImageIcon : FileText;
  return (
    <div className="group inline-flex max-w-full items-center gap-2 rounded-lg border border-[hsl(var(--border))] bg-white px-2.5 py-1.5 text-sm" data-testid={testid}>
      <Icon className="h-4 w-4 shrink-0 text-[hsl(var(--primary))]" />
      <span className="min-w-0 truncate text-slate-700" title={file.title || file.filename}>{file.title || file.filename}</span>
      <span className="hidden text-xs text-slate-400 sm:inline">{bytesFmt(file.size)}</span>
      <Button variant="ghost" size="icon" className="h-6 w-6 shrink-0" onClick={(e) => { e.stopPropagation(); openStoredFile(file.id); }} title="Відкрити"><ExternalLink className="h-3.5 w-3.5" /></Button>
      <Button variant="ghost" size="icon" className="h-6 w-6 shrink-0" onClick={(e) => { e.stopPropagation(); openStoredFile(file.id, { download: true, filename: file.filename }); }} title="Завантажити"><Download className="h-3.5 w-3.5" /></Button>
      {onRemove && <Button variant="ghost" size="icon" className="h-6 w-6 shrink-0 opacity-0 group-hover:opacity-100" onClick={(e) => { e.stopPropagation(); onRemove(file); }} title="Видалити"><Trash2 className="h-3.5 w-3.5 text-[#991B1B]" /></Button>}
    </div>
  );
}

export function PhotoPreview({ file, onRemove, testid }) {
  return (
    <div className="group relative overflow-hidden rounded-lg border border-[hsl(var(--border))] bg-slate-100" data-testid={testid}>
      <img
        src=""
        alt={file.filename}
        loading="lazy"
        onLoad={(e) => { /* will be replaced by blob */ }}
        ref={async (el) => {
          if (!el || el.dataset.loaded === "1") return;
          el.dataset.loaded = "1";
          try {
            const blob = await FilesAPI.view(file.id);
            el.src = URL.createObjectURL(blob);
          } catch {/* empty */}
        }}
        className="h-32 w-full object-cover"
      />
      <div className="flex items-center justify-between gap-1 border-t border-[hsl(var(--border))] bg-white px-2 py-1 text-xs text-slate-600">
        <span className="truncate">{file.title || file.filename}</span>
        <div className="flex shrink-0 gap-0.5">
          <button onClick={() => openStoredFile(file.id)} className="text-slate-400 hover:text-[hsl(var(--primary))]" title="Відкрити"><ExternalLink className="h-3.5 w-3.5" /></button>
          {onRemove && <button onClick={() => onRemove(file)} className="text-slate-400 hover:text-[#991B1B]" title="Видалити"><X className="h-3.5 w-3.5" /></button>}
        </div>
      </div>
    </div>
  );
}

export function AttachmentsPanel({ links, files, onUploaded, onRemove, purpose = "attachment", title = "Файли", emptyHint, accept, testid = "attach-panel" }) {
  return (
    <div className="rounded-xl border border-[hsl(var(--border))] bg-white p-4" data-testid={testid}>
      <div className="mb-3 flex items-center justify-between">
        <div className="text-sm font-semibold text-slate-900">{title} <span className="ml-1 text-xs font-normal text-slate-400">({(files || []).length})</span></div>
      </div>
      {(files || []).length === 0 ? (
        <div className="mb-3 rounded-lg border border-dashed border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/50 px-3 py-3 text-center text-xs text-slate-500">{emptyHint || "Файлів ще не додано"}</div>
      ) : (
        <div className="mb-3 flex flex-wrap gap-2">{files.map((f) => <AttachmentChip key={f.id} file={f} onRemove={onRemove} testid={`${testid}-chip`} />)}</div>
      )}
      <FileUploader onUploaded={onUploaded} links={links} purpose={purpose} accept={accept} multiple label="Додати файл" testid={`${testid}-uploader`} />
    </div>
  );
}
