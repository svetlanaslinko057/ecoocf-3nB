// Wave 5B: File Manager — список всіх завантажених/згенерованих файлів.
import React, { useEffect, useState, useCallback, useMemo } from "react";
import { FileStack, Search, Filter, Trash2, ExternalLink, Download, Image as ImageIcon, FileText, Sparkles } from "lucide-react";
import { FilesAPI, openStoredFile } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useSeo } from "@/lib/seo";
import { fmtDateTime } from "@/lib/portalMeta";
import { PageHeader, StatCard, EmptyState, TableSkeleton } from "@/components/portal/PortalUI";
import { FileUploader } from "@/components/portal/FileUploader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "@/components/ui/sonner";

function bytesFmt(n) {
  if (!n) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

const FILTERS = [
  { key: "all", label: "Усі" },
  { key: "pdf", label: "PDF" },
  { key: "doc", label: "Документи" },
  { key: "image", label: "Фото" },
  { key: "generated", label: "Згенеровані" },
];

export default function FilesManager() {
  useSeo("Файли · CRM", "Сховище документів і фото.");
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("all");
  const [q, setQ] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await FilesAPI.list({ limit: 500 });
      setFiles(r.items || []);
    } catch { /* empty */ } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = useMemo(() => {
    let r = files;
    if (tab === "pdf") r = r.filter((f) => (f.mime || "") === "application/pdf");
    else if (tab === "image") r = r.filter((f) => (f.mime || "").startsWith("image/"));
    else if (tab === "doc") r = r.filter((f) => /^application\/(msword|vnd\.|pdf)|^text\//.test(f.mime || ""));
    else if (tab === "generated") r = r.filter((f) => f.generated);
    if (q.trim()) {
      const ql = q.toLowerCase();
      r = r.filter((f) =>
        (f.title || "").toLowerCase().includes(ql) ||
        (f.filename || "").toLowerCase().includes(ql) ||
        (f.uploaded_by || "").toLowerCase().includes(ql) ||
        (f.purpose || "").toLowerCase().includes(ql)
      );
    }
    return r;
  }, [files, tab, q]);

  const stats = useMemo(() => {
    const total = files.length;
    const pdfs = files.filter((f) => (f.mime || "") === "application/pdf").length;
    const images = files.filter((f) => (f.mime || "").startsWith("image/")).length;
    const generated = files.filter((f) => f.generated).length;
    const totalSize = files.reduce((acc, f) => acc + (f.size || 0), 0);
    return { total, pdfs, images, generated, totalSize };
  }, [files]);

  const handleDelete = async (f) => {
    if (!window.confirm(`Видалити «${f.title || f.filename}»? Дію не можна відмінити.`)) return;
    try { await FilesAPI.delete(f.id); toast.success("Видалено"); setFiles((p) => p.filter((x) => x.id !== f.id)); }
    catch { toast.error("Не вдалося видалити"); }
  };

  return (
    <div data-testid="portal-files-manager">
      <PageHeader title="Файли" subtitle="Центральне сховище · документи, фото, згенеровані PDF" />

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard icon={FileStack} label="Усього файлів" value={stats.total} hint={bytesFmt(stats.totalSize)} testid="files-kpi-total" />
        <StatCard icon={FileText} label="PDF документів" value={stats.pdfs} testid="files-kpi-pdf" />
        <StatCard icon={ImageIcon} label="Фото" value={stats.images} testid="files-kpi-img" />
        <StatCard icon={Sparkles} label="Згенеровано" value={stats.generated} testid="files-kpi-gen" />
      </div>

      <div className="mb-6 grid gap-4 lg:grid-cols-[2fr_1fr]">
        <div>
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <Tabs value={tab} onValueChange={setTab}>
              <TabsList>{FILTERS.map((f) => <TabsTrigger key={f.key} value={f.key} data-testid={`files-filter-${f.key}`}>{f.label}</TabsTrigger>)}</TabsList>
            </Tabs>
            <div className="relative flex-1 max-w-md">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Пошук…" className="pl-9" data-testid="files-search" />
            </div>
          </div>
          <div className="rounded-2xl border border-[hsl(var(--border))] bg-white">
            {loading ? <div className="p-4"><TableSkeleton rows={6} /></div>
              : filtered.length === 0 ? <EmptyState icon={FileStack} title="Файлів немає" hint="Завантажте перший документ або згенеруйте PDF із картки операції." testid="files-empty" />
              : (
                <Table>
                  <TableHeader><TableRow><TableHead>Файл</TableHead><TableHead>Тип</TableHead><TableHead className="text-right">Розмір</TableHead><TableHead>Призначення</TableHead><TableHead>Завантажено</TableHead><TableHead className="w-28"></TableHead></TableRow></TableHeader>
                  <TableBody>{filtered.map((f) => {
                    const isImg = (f.mime || "").startsWith("image/");
                    const Icon = isImg ? ImageIcon : FileText;
                    return (
                      <TableRow key={f.id} data-testid="files-row">
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Icon className="h-4 w-4 shrink-0 text-[hsl(var(--primary))]" />
                            <div className="min-w-0"><div className="truncate font-medium text-slate-900" title={f.title || f.filename}>{f.title || f.filename}</div>
                              <div className="font-mono text-[10px] text-slate-400">{f.id.slice(0, 12)}{f.generated && <span className="ml-2 rounded-md border border-[#A7F3D0] bg-[#ECFDF5] px-1.5 py-0.5 text-[10px] font-medium text-[#065F46]">згенеровано</span>}</div>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell className="text-xs text-slate-500">{f.mime || "—"}</TableCell>
                        <TableCell className="text-right font-mono text-xs text-slate-600">{bytesFmt(f.size)}</TableCell>
                        <TableCell className="text-xs text-slate-500">{f.purpose || "—"}</TableCell>
                        <TableCell className="text-xs text-slate-500"><div>{f.uploaded_by || "—"}</div><div className="text-slate-400">{fmtDateTime(f.created_at)}</div></TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1">
                            <Button variant="ghost" size="icon" onClick={() => openStoredFile(f.id)} data-testid="files-view"><ExternalLink className="h-4 w-4" /></Button>
                            <Button variant="ghost" size="icon" onClick={() => openStoredFile(f.id, { download: true, filename: f.filename })} data-testid="files-download"><Download className="h-4 w-4" /></Button>
                            {isAdmin && <Button variant="ghost" size="icon" onClick={() => handleDelete(f)} data-testid="files-delete"><Trash2 className="h-4 w-4 text-[#991B1B]" /></Button>}
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}</TableBody>
                </Table>
              )}
          </div>
        </div>
        <div>
          <div className="rounded-2xl border border-[hsl(var(--border))] bg-white p-5">
            <div className="mb-3 text-sm font-semibold text-slate-900">Швидке завантаження</div>
            <FileUploader purpose="general" multiple onUploaded={(f) => setFiles((p) => [f, ...p])} testid="files-quick-upload" />
            <div className="mt-3 rounded-lg border border-dashed border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/40 p-3 text-xs text-slate-500">
              Для прив'язки до конкретного договору / вивозу / акта — використовуйте кнопку <b>Згенерувати PDF</b> або вкладку <b>Файли</b> у картці операції.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
