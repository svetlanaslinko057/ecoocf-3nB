import React, { useEffect, useState, useCallback } from "react";
import { FileText, Truck, BadgeCheck, X, Save, Calendar, MapPin, User, Phone, Car, Scale, FileSignature, Tag, History as HistoryIcon, ExternalLink, Hash, FileDown, Sparkles, Send, Copy, Eye, CheckCircle2, ShieldCheck, RotateCcw } from "lucide-react";
import { PortalAPI, FilesAPI, openStoredFile, ContractSignAPI } from "@/lib/api";
import {
  CONTRACT_ORDER, CONTRACT_LABELS, PICKUP_ORDER, PICKUP_LABELS,
  ACT_ORDER, ACT_LABELS, fmtDate, fmtDateTime, labelFor,
} from "@/lib/portalMeta";
import { StatusBadge } from "@/components/portal/PortalUI";
import { FileUploader, AttachmentChip, PhotoPreview, AttachmentsPanel } from "@/components/portal/FileUploader";
import DocumentTimeline from "@/components/portal/DocumentTimeline";
import PickupPhotoChecklist from "@/components/portal/PickupPhotoChecklist";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { toast } from "@/components/ui/sonner";

const KIND_META = {
  contract: {
    icon: FileText, label: "Договір",
    order: CONTRACT_ORDER, labels: CONTRACT_LABELS,
    fetch: PortalAPI.contract, update: PortalAPI.updateContract,
    status: PortalAPI.setContractStatus, generate: FilesAPI.generateContract,
    linkKey: "contract_id", pdfButton: "Згенерувати PDF договору",
  },
  pickup: {
    icon: Truck, label: "Вивіз",
    order: PICKUP_ORDER, labels: PICKUP_LABELS,
    fetch: PortalAPI.pickup, update: PortalAPI.updatePickup,
    status: PortalAPI.setPickupStatus, generate: FilesAPI.generatePickup,
    linkKey: "pickup_id", pdfButton: "Згенерувати накладну",
  },
  act: {
    icon: BadgeCheck, label: "Акт утилізації",
    order: ACT_ORDER, labels: ACT_LABELS,
    fetch: PortalAPI.act, update: PortalAPI.updateAct,
    status: PortalAPI.setActStatus, generate: FilesAPI.generateAct,
    linkKey: "act_id", pdfButton: "Згенерувати PDF акта",
  },
};

function unwrap(data, kind) {
  return data?.[kind] || data?.item || data;
}

function num(v) { return v === "" || v === null || v === undefined ? null : Number(v); }

// ── Electronic signature panel (contracts only) ──────────────────────────────
function EsignPanel({ doc, id, onChanged }) {
  const [busy, setBusy] = useState(false);
  const [shareUrl, setShareUrl] = useState(
    doc.view_token ? `${window.location.origin}/contract/${doc.view_token}` : ""
  );
  const signed = doc.status === "signed" || doc.esign_status === "signed";
  const revoked = doc.esign_revoked || doc.esign_status === "revoked";
  const sent = !!doc.view_token && !revoked && !signed;

  const send = async () => {
    setBusy(true);
    try {
      const res = await PortalAPI.sendContractEsign(id);
      const url = res.share_url?.startsWith("http")
        ? res.share_url
        : `${window.location.origin}/contract/${res.view_token}`;
      setShareUrl(url);
      toast.success("Посилання на підписання створено");
      onChanged && onChanged(res.contract);
    } catch (e) { toast.error(e?.response?.data?.detail || "Не вдалося надіслати"); }
    finally { setBusy(false); }
  };

  const revoke = async () => {
    if (!window.confirm("Відкликати посилання? Клієнт більше не зможе підписати договір за ним.")) return;
    setBusy(true);
    try {
      const res = await PortalAPI.revokeContractEsign(id);
      setShareUrl("");
      toast.success("Посилання відкликано");
      onChanged && onChanged(res.contract);
    } catch (e) { toast.error(e?.response?.data?.detail || "Не вдалося відкликати"); }
    finally { setBusy(false); }
  };

  const copy = async () => {
    try { await navigator.clipboard.writeText(shareUrl); toast.success("Скопійовано"); }
    catch { toast.error("Не вдалося скопіювати"); }
  };

  const Step = ({ active, done, icon: Ic, label, at }) => (
    <div className="flex flex-1 flex-col items-center gap-1.5 text-center">
      <div className={
        "flex h-9 w-9 items-center justify-center rounded-full border " +
        (done ? "border-[#0E5E3A] bg-[#0E5E3A] text-white"
              : active ? "border-[#5BC47A] bg-[#5BC47A]/15 text-[#0E5E3A]"
              : "border-[hsl(var(--border))] bg-white text-slate-300")
      }>
        <Ic className="h-4 w-4" />
      </div>
      <div className={"text-[11px] font-medium " + (done || active ? "text-slate-700" : "text-slate-400")}>{label}</div>
      {at && <div className="text-[10px] text-slate-400">{fmtDateTime(at)}</div>}
    </div>
  );

  return (
    <div className="space-y-4">
      {/* Progress */}
      <div className="rounded-xl border border-[hsl(var(--border))] bg-white p-4">
        <div className="flex items-start gap-1">
          <Step done icon={FileText} label="Чернетка" at={doc.created_at} />
          <div className="mt-4 h-px flex-1 bg-[hsl(var(--border))]" />
          <Step done={sent || signed} active={sent && !signed} icon={Send} label="Надіслано" at={doc.esign_sent_at} />
          <div className="mt-4 h-px flex-1 bg-[hsl(var(--border))]" />
          <Step done={signed || !!doc.esign_viewed_at} active={!!doc.esign_viewed_at && !signed} icon={Eye} label="Переглянуто" at={doc.esign_viewed_at} />
          <div className="mt-4 h-px flex-1 bg-[hsl(var(--border))]" />
          <Step done={signed} active={false} icon={CheckCircle2} label="Підписано" at={doc.signed_at} />
        </div>
      </div>

      {signed ? (
        <div className="rounded-xl border border-[#0E5E3A]/30 bg-[#0E5E3A]/5 p-4" data-testid="opd-esign-signed-card">
          <div className="flex items-center gap-2 text-[#0E5E3A]">
            <ShieldCheck className="h-5 w-5" />
            <span className="font-semibold">Договір підписано електронно</span>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
            <div><div className="text-xs text-slate-500">Підписант</div><div className="font-medium text-slate-900">{doc.signed_by || "—"}</div></div>
            <div><div className="text-xs text-slate-500">Дата/час</div><div className="font-medium text-slate-900">{doc.signed_at ? fmtDateTime(doc.signed_at) : "—"}</div></div>
            <div><div className="text-xs text-slate-500">IP-адреса</div><div className="font-mono text-slate-700">{doc.signed_ip || "—"}</div></div>
            <div className="truncate"><div className="text-xs text-slate-500">Пристрій</div><div className="truncate text-xs text-slate-600" title={doc.signed_user_agent}>{doc.signed_user_agent || "—"}</div></div>
          </div>
        </div>
      ) : (
        <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/40 p-4">
          <div className="flex items-center gap-2">
            <FileSignature className="h-5 w-5 text-[hsl(var(--primary))]" />
            <div>
              <div className="text-sm font-semibold text-slate-900">Електронний підпис договору</div>
              <div className="text-xs text-slate-500">Згенеруйте захищене посилання й надішліть клієнту для підписання.</div>
            </div>
          </div>

          {sent && shareUrl ? (
            <div className="mt-3 space-y-2">
              <Label className="text-xs">Посилання для клієнта</Label>
              <div className="flex items-center gap-2">
                <Input readOnly value={shareUrl} className="font-mono text-xs" data-testid="opd-esign-link" onFocus={(e) => e.target.select()} />
                <Button variant="secondary" size="icon" onClick={copy} title="Копіювати"><Copy className="h-4 w-4" /></Button>
                <Button variant="secondary" size="icon" onClick={() => window.open(shareUrl, "_blank")} title="Відкрити"><ExternalLink className="h-4 w-4" /></Button>
              </div>
              <div className="flex items-center justify-between pt-1">
                <span className="text-xs text-slate-500">
                  {doc.esign_viewed_at ? `Клієнт переглянув ${fmtDateTime(doc.esign_viewed_at)}` : "Очікує на перегляд клієнтом"}
                </span>
                <div className="flex gap-2">
                  <Button variant="ghost" size="sm" onClick={send} disabled={busy} className="gap-1.5"><RotateCcw className="h-3.5 w-3.5" /> Перевідправити</Button>
                  <Button variant="ghost" size="sm" onClick={revoke} disabled={busy} className="gap-1.5 text-red-600 hover:text-red-700"><X className="h-3.5 w-3.5" /> Відкликати</Button>
                </div>
              </div>
            </div>
          ) : (
            <div className="mt-3">
              <Button onClick={send} disabled={busy} className="gap-2" data-testid="opd-esign-send">
                <Send className="h-4 w-4" /> {busy ? "Генерація…" : "Надіслати на підписання"}
              </Button>
              {revoked && <span className="ml-3 text-xs text-slate-500">Попереднє посилання було відкликано.</span>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ContractForm({ doc, onChange }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div className="grid gap-1.5 sm:col-span-2"><Label>Назва</Label>
        <Input value={doc.title || ""} onChange={(e) => onChange({ title: e.target.value })} data-testid="opd-contract-title" />
      </div>
      <div className="grid gap-1.5"><Label>Сума</Label><Input type="number" value={doc.amount ?? ""} onChange={(e) => onChange({ amount: num(e.target.value) })} data-testid="opd-contract-amount" /></div>
      <div className="grid gap-1.5"><Label>Валюта</Label>
        <Select value={doc.currency || "UAH"} onValueChange={(v) => onChange({ currency: v })}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="UAH">UAH</SelectItem><SelectItem value="EUR">EUR</SelectItem><SelectItem value="USD">USD</SelectItem></SelectContent>
        </Select>
      </div>
      <div className="grid gap-1.5"><Label>Діє з</Label><Input type="date" value={(doc.valid_from || "").slice(0,10)} onChange={(e) => onChange({ valid_from: e.target.value ? new Date(e.target.value).toISOString() : null })} data-testid="opd-contract-from" /></div>
      <div className="grid gap-1.5"><Label>Діє до</Label><Input type="date" value={(doc.valid_to || "").slice(0,10)} onChange={(e) => onChange({ valid_to: e.target.value ? new Date(e.target.value).toISOString() : null })} data-testid="opd-contract-to" /></div>
      <div className="grid gap-1.5 sm:col-span-2"><Label>Посилання на PDF</Label>
        <div className="flex gap-2"><Input value={doc.file_id || ""} onChange={(e) => onChange({ file_id: e.target.value })} placeholder="URL або ID файлу" data-testid="opd-contract-file" />
          {doc.file_id && /\/api\/storage\/files\/|^https?:/i.test(doc.file_id) && <Button variant="secondary" size="icon" onClick={() => openStoredFile(doc.file_id)}><ExternalLink className="h-4 w-4" /></Button>}
        </div>
      </div>
      <div className="grid gap-1.5"><Label>Підписант (є-підпис)</Label><Input value={doc.signed_by || ""} onChange={(e) => onChange({ signed_by: e.target.value })} placeholder="П.І.Б. або email" /></div>
      <div className="grid gap-1.5"><Label>Підписано</Label><div className="flex h-10 items-center rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] px-3 text-sm text-slate-700"><FileSignature className="mr-2 h-4 w-4 text-[hsl(var(--primary))]" />{doc.signed_at ? fmtDateTime(doc.signed_at) : "—"}</div></div>
    </div>
  );
}

function PickupForm({ doc, onChange }) {
  const driver = doc.driver || {};
  const setDriver = (patch) => onChange({ driver: { ...driver, ...patch } });
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div className="grid gap-1.5"><Label>Запланований час</Label><Input type="datetime-local" value={(doc.scheduled_at || "").slice(0,16)} onChange={(e) => onChange({ scheduled_at: e.target.value ? new Date(e.target.value).toISOString() : null })} data-testid="opd-pickup-sched" /></div>
      <div className="grid gap-1.5"><Label>Тип транспорту</Label>
        <Select value={doc.transport_type || ""} onValueChange={(v) => onChange({ transport_type: v })}>
          <SelectTrigger data-testid="opd-pickup-transport"><SelectValue placeholder="—" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="van">Спец-фургон</SelectItem>
            <SelectItem value="truck">Вантажівка</SelectItem>
            <SelectItem value="adr">ADR відповідний</SelectItem>
            <SelectItem value="vacuum">Асенізаційна</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="grid gap-1.5"><Label>Тип тари</Label>
        <Select value={doc.container_type || ""} onValueChange={(v) => onChange({ container_type: v })}>
          <SelectTrigger><SelectValue placeholder="—" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="client">Тара клієнта</SelectItem>
            <SelectItem value="provided">Наша тара</SelectItem>
            <SelectItem value="ibc">IBC 1000 л</SelectItem>
            <SelectItem value="drum">Бочка 200 л</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="grid gap-1.5"><Label>Фактична вага, кг</Label><Input type="number" value={doc.weight_kg ?? ""} onChange={(e) => onChange({ weight_kg: num(e.target.value) })} data-testid="opd-pickup-weight" /></div>
      <div className="grid gap-1.5 sm:col-span-2"><Label>Маршрут / Адреси</Label><Textarea rows={2} value={doc.route || ""} onChange={(e) => onChange({ route: e.target.value })} placeholder="Київ, вул. Шевченка 1 → Київ, вул. Сома завод 5" data-testid="opd-pickup-route" /></div>
      <div className="rounded-xl border border-dashed border-[hsl(var(--border))] p-3 sm:col-span-2">
        <div className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Водій / Авто</div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-1.5"><Label className="text-xs flex items-center gap-1.5"><User className="h-3.5 w-3.5" /> П.І.Б.</Label><Input value={driver.name || ""} onChange={(e) => setDriver({ name: e.target.value })} data-testid="opd-pickup-driver-name" /></div>
          <div className="grid gap-1.5"><Label className="text-xs flex items-center gap-1.5"><Phone className="h-3.5 w-3.5" /> Телефон</Label><Input value={driver.phone || ""} onChange={(e) => setDriver({ phone: e.target.value })} placeholder="+380…" /></div>
          <div className="grid gap-1.5"><Label className="text-xs flex items-center gap-1.5"><Car className="h-3.5 w-3.5" /> Авто</Label><Input value={driver.vehicle || ""} onChange={(e) => setDriver({ vehicle: e.target.value })} placeholder="Mercedes Sprinter, АА 0000 ББ" data-testid="opd-pickup-vehicle" /></div>
          <div className="grid gap-1.5"><Label className="text-xs flex items-center gap-1.5"><MapPin className="h-3.5 w-3.5" /> GPS / Посилання</Label><Input value={driver.gps || ""} onChange={(e) => setDriver({ gps: e.target.value })} placeholder="50.45, 30.52 або https://…" /></div>
        </div>
      </div>
      <div className="grid gap-1.5 sm:col-span-2"><Label>Фото (URL)</Label><Input value={doc.photo_url || ""} onChange={(e) => onChange({ photo_url: e.target.value })} placeholder="https://…" data-testid="opd-pickup-photo" /></div>
      {doc.photo_url && /^https?:/i.test(doc.photo_url) && (
        <div className="sm:col-span-2 overflow-hidden rounded-xl border border-[hsl(var(--border))]"><img src={doc.photo_url} alt="pickup" className="max-h-56 w-full object-cover" /></div>
      )}
      <div className="grid gap-1.5"><Label>Забрано</Label><div className="flex h-10 items-center rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] px-3 text-sm text-slate-700">{doc.picked_up_at ? fmtDateTime(doc.picked_up_at) : "—"}</div></div>
      <div className="grid gap-1.5"><Label>Доставлено</Label><div className="flex h-10 items-center rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] px-3 text-sm text-slate-700">{doc.delivered_at ? fmtDateTime(doc.delivered_at) : "—"}</div></div>
    </div>
  );
}

function ActForm({ doc, onChange }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div className="grid gap-1.5"><Label>Дата утилізації</Label><Input type="date" value={(doc.act_date || "").slice(0,10)} onChange={(e) => onChange({ act_date: e.target.value ? new Date(e.target.value).toISOString() : null })} data-testid="opd-act-date" /></div>
      <div className="grid gap-1.5"><Label>Фактична вага, кг</Label><Input type="number" value={doc.total_weight_kg ?? ""} onChange={(e) => onChange({ total_weight_kg: num(e.target.value) })} data-testid="opd-act-weight" /></div>
      <div className="grid gap-1.5 sm:col-span-2"><Label>Метод утилізації</Label>
        <Select value={doc.utilization_method || ""} onValueChange={(v) => onChange({ utilization_method: v })}>
          <SelectTrigger data-testid="opd-act-method"><SelectValue placeholder="—" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="incineration">Спалювання</SelectItem>
            <SelectItem value="neutralization">Хім.нейтралізація</SelectItem>
            <SelectItem value="recycling">Переробка</SelectItem>
            <SelectItem value="sorting">Сортування / розріб</SelectItem>
            <SelectItem value="burial">Захоронення</SelectItem>
            <SelectItem value="composting">Компостування</SelectItem>
            <SelectItem value="sterilization">Стерилізація автоклавом</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="grid gap-1.5 sm:col-span-2"><Label>Посилання на акт (PDF)</Label>
        <div className="flex gap-2"><Input value={doc.file_id || ""} onChange={(e) => onChange({ file_id: e.target.value })} placeholder="URL або ID файлу" data-testid="opd-act-file" />
          {doc.file_id && /\/api\/storage\/files\/|^https?:/i.test(doc.file_id) && <Button variant="secondary" size="icon" onClick={() => openStoredFile(doc.file_id)}><ExternalLink className="h-4 w-4" /></Button>}
        </div>
      </div>
      <div className="grid gap-1.5"><Label>Підписант</Label><Input value={doc.signed_by || ""} onChange={(e) => onChange({ signed_by: e.target.value })} /></div>
      <div className="grid gap-1.5"><Label>Підписано</Label><div className="flex h-10 items-center rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] px-3 text-sm text-slate-700">{doc.signed_at ? fmtDateTime(doc.signed_at) : "—"}</div></div>
    </div>
  );
}

export function OperationDetailDrawer({ open, onOpenChange, kind, id, onSaved }) {
  const meta = KIND_META[kind] || KIND_META.contract;
  const [doc, setDoc] = useState(null);
  const [original, setOriginal] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [statusBusy, setStatusBusy] = useState(false);
  const [pdfBusy, setPdfBusy] = useState(false);
  const [files, setFiles] = useState([]);
  const Icon = meta.icon;

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const data = await meta.fetch(id);
      const d = unwrap(data, kind);
      setDoc(d); setOriginal(d);
      const params = { [meta.linkKey]: id };
      const r = await FilesAPI.list(params).catch(() => ({ items: [] }));
      setFiles(r.items || []);
    } catch (e) { toast.error("Не вдалося завантажити деталі"); }
    finally { setLoading(false); }
  }, [id, kind, meta]);

  useEffect(() => { if (open) load(); }, [open, load]);

  const dirty = doc && original && JSON.stringify(doc) !== JSON.stringify(original);
  const patch = (p) => setDoc((d) => ({ ...d, ...p }));

  const save = async () => {
    if (!doc) return;
    setSaving(true);
    try {
      // Send only operational fields (avoid id/status_history/etc.)
      const fields = (() => {
        if (kind === "contract") return ["title","amount","currency","valid_from","valid_to","file_id","signed_by","notes"];
        if (kind === "pickup") return ["scheduled_at","transport_type","container_type","weight_kg","route","driver","photo_url","notes","contract_id"];
        if (kind === "act") return ["act_date","total_weight_kg","utilization_method","file_id","signed_by","notes","contract_id","pickup_id"];
        return [];
      })();
      const payload = {};
      for (const k of fields) payload[k] = doc[k];
      const res = await meta.update(id, payload);
      const fresh = unwrap(res, kind);
      setDoc(fresh); setOriginal(fresh);
      toast.success("Збережено");
      onSaved && onSaved(fresh);
    } catch (e) { toast.error(e?.response?.data?.detail || "Не вдалося зберегти"); }
    finally { setSaving(false); }
  };

  const setStatus = async (status) => {
    setStatusBusy(true);
    try {
      const res = await meta.status(id, status);
      const fresh = unwrap(res, kind);
      setDoc(fresh); setOriginal(fresh);
      toast.success(`Статус → ${meta.labels[status]}`);
      onSaved && onSaved(fresh);
    } catch { toast.error("Не вдалося змінити статус"); }
    finally { setStatusBusy(false); }
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-2xl overflow-y-auto" data-testid={`opd-${kind}-drawer`}>
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2"><Icon className="h-5 w-5 text-[hsl(var(--primary))]" /> {meta.label} {doc?.number && <span className="font-mono text-base text-slate-500">· {doc.number}</span>}</SheetTitle>
          <SheetDescription>Повноцінна операційна картка з повною історією виконання</SheetDescription>
        </SheetHeader>

        {loading || !doc ? (
          <div className="mt-6 space-y-3">
            <div className="h-8 animate-pulse rounded bg-[hsl(var(--secondary))]" />
            <div className="h-32 animate-pulse rounded bg-[hsl(var(--secondary))]" />
            <div className="h-32 animate-pulse rounded bg-[hsl(var(--secondary))]" />
          </div>
        ) : (
          <div className="mt-6">
            <div className="mb-4 flex flex-wrap items-center gap-3 rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] p-3">
              <div className="flex items-center gap-2"><Tag className="h-4 w-4 text-slate-400" /><span className="text-xs text-slate-500">Статус:</span> <StatusBadge status={doc.status} /></div>
              <Select value={doc.status} onValueChange={setStatus} disabled={statusBusy}>
                <SelectTrigger className="h-8 w-[200px]" data-testid={`opd-${kind}-status`}><SelectValue /></SelectTrigger>
                <SelectContent>{meta.order.map((s) => <SelectItem key={s} value={s}>{meta.labels[s]}</SelectItem>)}</SelectContent>
              </Select>
              <div className="ml-auto flex items-center gap-3 text-xs text-slate-500">
                <span className="flex items-center gap-1"><Calendar className="h-3.5 w-3.5" />{fmtDate(doc.created_at)}</span>
                {doc.created_by && <span className="flex items-center gap-1"><User className="h-3.5 w-3.5" />{doc.created_by}</span>}
              </div>
            </div>

            <Tabs defaultValue="details">
              <TabsList>
                <TabsTrigger value="details" data-testid={`opd-${kind}-tab-details`}>Деталі</TabsTrigger>
                <TabsTrigger value="items" data-testid={`opd-${kind}-tab-items`}>Відходи ({(doc.items || []).length})</TabsTrigger>
                {kind === "contract" && <TabsTrigger value="esign" data-testid="opd-contract-tab-esign">Е-підпис</TabsTrigger>}
                <TabsTrigger value="files" data-testid={`opd-${kind}-tab-files`}>Файли ({files.length})</TabsTrigger>
                <TabsTrigger value="history" data-testid={`opd-${kind}-tab-history`}>Історія</TabsTrigger>
              </TabsList>

              <TabsContent value="details" className="mt-4">
                {kind === "contract" && <ContractForm doc={doc} onChange={patch} />}
                {kind === "pickup" && <PickupForm doc={doc} onChange={patch} />}
                {kind === "act" && <ActForm doc={doc} onChange={patch} />}
                <div className="mt-4 grid gap-1.5"><Label>Нотатки</Label><Textarea rows={2} value={doc.notes || ""} onChange={(e) => patch({ notes: e.target.value })} data-testid={`opd-${kind}-notes`} /></div>
                <div className="mt-4 flex items-center justify-end gap-2">
                  <Button variant="secondary" onClick={() => setDoc(original)} disabled={!dirty || saving}>Скинути</Button>
                  <Button onClick={save} disabled={!dirty || saving} className="gap-2" data-testid={`opd-${kind}-save`}><Save className="h-4 w-4" /> {saving ? "Збереження…" : "Зберегти"}</Button>
                </div>
              </TabsContent>

              <TabsContent value="items" className="mt-4">
                {(doc.items || []).length === 0
                  ? <div className="rounded-xl border border-dashed border-[hsl(var(--border))] p-6 text-center text-sm text-slate-500">Відходи не вказані</div>
                  : <div className="rounded-xl border border-[hsl(var(--border))]">
                      {(doc.items || []).map((it, i) => (
                        <div key={i} className="flex items-center justify-between gap-3 border-b border-[hsl(var(--border))] px-3 py-2 last:border-b-0">
                          <div>
                            <div className="font-mono text-sm text-slate-900">{it.waste_code}</div>
                            <div className="mt-0.5 text-xs text-slate-500 max-w-xs truncate">{it.name || "—"}</div>
                          </div>
                          <div className="flex items-center gap-3 text-xs text-slate-600">
                            {it.qty != null && <span className="flex items-center gap-1"><Scale className="h-3.5 w-3.5" />{it.qty} {it.unit || "kg"}</span>}
                            {it.packaging && <span className="rounded-md border border-[hsl(var(--border))] px-1.5 py-0.5">{it.packaging}</span>}
                            {it.hazardous && <span className="rounded-md border border-[#FDE68A] bg-[#FFFBEB] px-1.5 py-0.5 text-[#92400E]">небезп.</span>}
                            {it.accepted === false && <span className="rounded-md border border-[#FECACA] bg-[#FEF2F2] px-1.5 py-0.5 text-[#991B1B]">не прийм.</span>}
                          </div>
                        </div>
                      ))}
                    </div>}
              </TabsContent>

              {kind === "contract" && (
                <TabsContent value="esign" className="mt-4">
                  <EsignPanel doc={doc} id={id} onChanged={(fresh) => { if (fresh) { setDoc(fresh); setOriginal(fresh); onSaved && onSaved(fresh); } else { load(); } }} />
                </TabsContent>
              )}

              <TabsContent value="files" className="mt-4 space-y-3">
                <DocumentTimeline entityType={kind} entityId={id} onChanged={() => load()} />
                {kind === "pickup" && (
                  <PickupPhotoChecklist
                    pickupId={id}
                    companyId={doc.company_id}
                    onUploaded={(f) => setFiles((p) => [f, ...p])}
                  />
                )}
                <div className="flex items-center justify-between rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/40 p-3">
                  <div>
                    <div className="text-sm font-semibold text-slate-900">{meta.pdfButton}</div>
                    <div className="text-xs text-slate-500">Брендований PDF буде додано до файлів цього {meta.label.toLowerCase()}.</div>
                  </div>
                  <Button size="sm" onClick={async () => {
                    setPdfBusy(true);
                    try { const r = await meta.generate(id); toast.success("PDF згенеровано"); setFiles((p) => [r.file, ...p]); load(); }
                    catch { toast.error("Не вдалося згенерувати"); } finally { setPdfBusy(false); }
                  }} disabled={pdfBusy} className="gap-2" data-testid={`opd-${kind}-generate-pdf`}>
                    {pdfBusy ? <FileDown className="h-4 w-4 animate-pulse" /> : <Sparkles className="h-4 w-4" />} {pdfBusy ? "Генерація…" : "Згенерувати"}
                  </Button>
                </div>
                <AttachmentsPanel
                  links={{ [meta.linkKey]: id, company_id: doc.company_id }}
                  files={files}
                  purpose={kind === "pickup" ? "photo" : "doc"}
                  title={kind === "pickup" ? "Документи й фото" : "Документи"}
                  emptyHint={kind === "pickup" ? "Додайте фото вивозу (до/після) та ТТН." : "Завантажте PDF, скани або інші файли."}
                  onUploaded={(f) => setFiles((p) => [f, ...p])}
                  onRemove={async (f) => {
                    if (!window.confirm(`Видалити «${f.title || f.filename}»?`)) return;
                    try { await FilesAPI.delete(f.id); setFiles((p) => p.filter((x) => x.id !== f.id)); toast.success("Видалено"); }
                    catch { toast.error("Не вдалося видалити"); }
                  }}
                  testid={`opd-${kind}-files`}
                />
              </TabsContent>

              <TabsContent value="history" className="mt-4">
                {(doc.status_history || []).length === 0
                  ? <div className="rounded-xl border border-dashed border-[hsl(var(--border))] p-6 text-center text-sm text-slate-500">Подій немає</div>
                  : <ol className="relative ml-3 border-l border-[hsl(var(--border))]" data-testid={`opd-${kind}-history-list`}>
                      {(doc.status_history || []).slice().reverse().map((h, i) => (
                        <li key={i} className="ml-4 py-3">
                          <span className="absolute -left-[6px] mt-1.5 h-3 w-3 rounded-full border-2 border-white bg-[hsl(var(--primary))]" />
                          <div className="flex items-center gap-2 text-sm text-slate-800"><HistoryIcon className="h-4 w-4 text-slate-400" /> {meta.labels[h.status] || labelFor(h.status)}</div>
                          <div className="mt-0.5 text-xs text-slate-400">{fmtDateTime(h.at)} · {h.by || "система"}{h.note ? ` · ${h.note}` : ""}</div>
                        </li>
                      ))}
                    </ol>}
              </TabsContent>
            </Tabs>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
