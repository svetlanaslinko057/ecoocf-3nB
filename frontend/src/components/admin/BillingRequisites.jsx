/**
 * BillingRequisites — Admin configuration of the company's legal entity +
 * bank accounts per currency (UAH primary; USD/EUR optional).
 *
 * Backed by:  GET/PUT /api/admin/billing/requisites  (CrmAPI.adminRequisitesGet/Save)
 * Rendered inside Settings → tab "Реквізити" (admin only).
 */
import React, { useEffect, useState, useCallback } from "react";
import { CrmAPI } from "@/lib/api";
import { toast } from "sonner";
import { Bank, ShieldCheck, FloppyDisk, Buildings } from "@phosphor-icons/react";

const CURRENCIES = ["UAH", "USD", "EUR"];

const LEGAL_FIELDS = [
  { key: "legal_name", label: "Юридична назва", ph: "ТОВ «ЕКО-НОВА»", req: true },
  { key: "edrpou", label: "ЄДРПОУ", ph: "44556677", req: true },
  { key: "ipn", label: "ІПН (податковий номер)", ph: "445566778899" },
  { key: "legal_address", label: "Юридична адреса", ph: "м. Київ, вул. Зелена, 1", wide: true },
  { key: "director_name", label: "Директор (ПІБ)", ph: "Іваненко І. І." },
  { key: "director_basis", label: "Діє на підставі", ph: "Статуту" },
  { key: "phone", label: "Телефон", ph: "+380 44 333 44 55" },
  { key: "email", label: "Email для рахунків", ph: "billing@eco.ua" },
];

const emptyAccount = (currency) => ({ currency, iban: "", bank_name: "", mfo: "", swift: "", enabled: false });

export default function BillingRequisites() {
  const [form, setForm] = useState({
    legal_name: "", edrpou: "", ipn: "", vat_payer: false, legal_address: "",
    director_name: "", director_basis: "Статуту", phone: "", email: "",
    payment_purpose_template: "Оплата за рахунком {number} від {date}", notes: "",
  });
  const [accounts, setAccounts] = useState(CURRENCIES.map((c) => emptyAccount(c)));
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [meta, setMeta] = useState({ configured: false, updated_at: null, updated_by: null });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await CrmAPI.adminRequisitesGet();
      const req = r.requisites || {};
      setForm((p) => ({
        ...p,
        legal_name: req.legal_name || "", edrpou: req.edrpou || "", ipn: req.ipn || "",
        vat_payer: !!req.vat_payer, legal_address: req.legal_address || "",
        director_name: req.director_name || "", director_basis: req.director_basis || "Статуту",
        phone: req.phone || "", email: req.email || "",
        payment_purpose_template: req.payment_purpose_template || "Оплата за рахунком {number} від {date}",
        notes: req.notes || "",
      }));
      const byCur = {};
      (req.accounts || []).forEach((a) => { byCur[a.currency] = a; });
      setAccounts(CURRENCIES.map((c) => byCur[c] ? { ...emptyAccount(c), ...byCur[c] } : emptyAccount(c)));
      setMeta({ configured: !!req.configured, updated_at: req.updated_at, updated_by: req.updated_by });
    } catch (e) {
      toast.error("Не вдалося завантажити реквізити");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const setField = (k, v) => setForm((p) => ({ ...p, [k]: v }));
  const setAcc = (idx, k, v) => setAccounts((p) => p.map((a, i) => (i === idx ? { ...a, [k]: v } : a)));

  const save = async () => {
    if (!form.legal_name.trim() || !form.edrpou.trim()) {
      return toast.error("Заповніть юридичну назву та ЄДРПОУ");
    }
    const enabledAccs = accounts.filter((a) => a.enabled);
    if (enabledAccs.length === 0) {
      return toast.error("Увімкніть та заповніть щонайменше один рахунок (IBAN)");
    }
    for (const a of enabledAccs) {
      if (!a.iban.trim()) return toast.error(`Вкажіть IBAN для ${a.currency}`);
    }
    setSaving(true);
    try {
      await CrmAPI.adminRequisitesSave({ ...form, accounts });
      toast.success("Реквізити збережено");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Не вдалося зберегти");
    } finally { setSaving(false); }
  };

  if (loading) {
    return <div className="section-card"><div className="animate-pulse text-sm text-[#71717A]">Завантаження реквізитів…</div></div>;
  }

  return (
    <div className="space-y-6" data-testid="billing-requisites">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          {meta.configured ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 text-emerald-700 px-3 py-1 text-xs font-semibold"><ShieldCheck size={14} weight="fill" /> Налаштовано</span>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 text-amber-700 px-3 py-1 text-xs font-semibold">Не налаштовано</span>
          )}
          {meta.updated_at && <span className="text-xs text-[#A1A1AA]">Оновлено {String(meta.updated_at).slice(0, 10)}{meta.updated_by ? ` · ${meta.updated_by}` : ""}</span>}
        </div>
        <button onClick={save} disabled={saving} className="inline-flex items-center gap-2 rounded-lg bg-[#2f5d3d] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#244c31] transition-colors disabled:opacity-60" data-testid="requisites-save">
          <FloppyDisk size={16} weight="bold" /> {saving ? "Збереження…" : "Зберегти реквізити"}
        </button>
      </div>

      {/* Legal entity */}
      <div className="section-card">
        <div className="flex items-center gap-2 mb-4">
          <Buildings size={20} weight="duotone" className="text-[#2f5d3d]" />
          <h3 className="text-base font-semibold text-[#18181B]">Юридична особа</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {LEGAL_FIELDS.map((f) => (
            <div key={f.key} className={f.wide ? "md:col-span-2" : ""}>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{f.label}{f.req && <span className="text-red-500"> *</span>}</label>
              <input type="text" value={form[f.key] || ""} onChange={(e) => setField(f.key, e.target.value)} placeholder={f.ph} className="input w-full" data-testid={`requisites-${f.key}`} />
            </div>
          ))}
          <div className="md:col-span-2 flex items-center gap-3 pt-1">
            <input id="vat_payer" type="checkbox" checked={form.vat_payer} onChange={(e) => setField("vat_payer", e.target.checked)} className="h-4 w-4 rounded border-zinc-300 text-[#2f5d3d] focus:ring-[#2f5d3d]" data-testid="requisites-vat" />
            <label htmlFor="vat_payer" className="text-sm text-[#3f3f46]">Платник ПДВ</label>
          </div>
        </div>
      </div>

      {/* Bank accounts per currency */}
      <div className="section-card">
        <div className="flex items-center gap-2 mb-4">
          <Bank size={20} weight="duotone" className="text-[#2f5d3d]" />
          <h3 className="text-base font-semibold text-[#18181B]">Банківські рахунки за валютою</h3>
        </div>
        <p className="text-sm text-[#71717A] mb-4">Увімкніть валюти, у яких приймаєте оплату. Гривневий рахунок (UAH) — основний. При виставленні рахунку підтягуються реквізити відповідної валюти.</p>
        <div className="space-y-4">
          {accounts.map((a, idx) => (
            <div key={a.currency} className={`rounded-xl border p-4 transition-colors ${a.enabled ? "border-[#2f5d3d]/40 bg-[#f6f8f2]" : "border-zinc-200 bg-white"}`} data-testid={`account-${a.currency}`}>
              <div className="flex items-center justify-between mb-3">
                <span className="inline-flex items-center gap-2 font-bold text-[#18181B]"><span className="rounded-md bg-[#2f5d3d] text-white text-xs px-2 py-1">{a.currency}</span>{a.currency === "UAH" ? "Гривня" : a.currency === "USD" ? "Долар США" : "Євро"}</span>
                <label className="inline-flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={a.enabled} onChange={(e) => setAcc(idx, "enabled", e.target.checked)} className="h-4 w-4 rounded border-zinc-300 text-[#2f5d3d] focus:ring-[#2f5d3d]" data-testid={`account-toggle-${a.currency}`} />
                  <span className="text-sm text-[#3f3f46]">{a.enabled ? "Увімкнено" : "Вимкнено"}</span>
                </label>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="md:col-span-2">
                  <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-1.5">IBAN</label>
                  <input type="text" value={a.iban} onChange={(e) => setAcc(idx, "iban", e.target.value)} placeholder="UA21 3223 1300 0002 6007 2335 6600 1" className="input w-full font-mono" disabled={!a.enabled} data-testid={`account-iban-${a.currency}`} />
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-1.5">Банк</label>
                  <input type="text" value={a.bank_name} onChange={(e) => setAcc(idx, "bank_name", e.target.value)} placeholder="АТ «ПриватБанк»" className="input w-full" disabled={!a.enabled} />
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-1.5">МФО</label>
                  <input type="text" value={a.mfo} onChange={(e) => setAcc(idx, "mfo", e.target.value)} placeholder="305299" className="input w-full" disabled={!a.enabled} />
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-1.5">SWIFT/BIC (для USD/EUR)</label>
                  <input type="text" value={a.swift} onChange={(e) => setAcc(idx, "swift", e.target.value)} placeholder="PBANUA2X" className="input w-full" disabled={!a.enabled} />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Payment purpose */}
      <div className="section-card">
        <h3 className="text-base font-semibold text-[#18181B] mb-3">Призначення платежу</h3>
        <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">Шаблон (доступні плейсхолдери: {"{number}"}, {"{date}"})</label>
        <input type="text" value={form.payment_purpose_template} onChange={(e) => setField("payment_purpose_template", e.target.value)} className="input w-full" data-testid="requisites-purpose" />
        <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2 mt-4">Примітки (внутрішні)</label>
        <textarea value={form.notes} onChange={(e) => setField("notes", e.target.value)} rows={2} className="input w-full" />
      </div>
    </div>
  );
}
