import React, { useEffect, useState, useCallback } from "react";
import { useParams } from "react-router-dom";
import { ContractSignAPI } from "@/lib/api";
import {
  Leaf, ShieldCheck, FileText, Building2, CalendarDays, Scale, Loader2,
  CheckCircle2, AlertTriangle, FileDown, PenLine, Fingerprint, Hash, Globe,
} from "lucide-react";

const fmtDate = (s) => {
  if (!s) return "—";
  try { return new Date(s).toLocaleDateString("uk-UA", { day: "2-digit", month: "long", year: "numeric" }); }
  catch { return s; }
};
const fmtDateTime = (s) => {
  if (!s) return "—";
  try { return new Date(s).toLocaleString("uk-UA", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }); }
  catch { return s; }
};
const money = (v, c) => (v == null ? "—" : `${Number(v).toLocaleString("uk-UA")} ${c || "UAH"}`);

function Shell({ children }) {
  return (
    <div className="min-h-screen bg-[#0B1A14] bg-[radial-gradient(120%_100%_at_50%_0%,#103a28_0%,#0B1A14_60%)] text-white">
      <div className="mx-auto flex max-w-3xl flex-col px-4 py-8 sm:py-12">
        <div className="mb-6 flex items-center gap-2">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#0E5E3A] text-[#5BC47A] ring-1 ring-white/10">
            <Leaf className="h-5 w-5" />
          </span>
          <div>
            <div className="text-lg font-bold tracking-tight">ECO<span className="text-[#5BC47A]">.</span><span className="opacity-55">NOVA</span></div>
            <div className="text-[11px] uppercase tracking-[0.2em] text-white/45">Електронний підпис</div>
          </div>
        </div>
        {children}
        <div className="mt-8 text-center text-[11px] text-white/35">
          Захищене посилання · Платформа утилізації відходів · Україна
        </div>
      </div>
    </div>
  );
}

export default function WasteContractSign() {
  const { token } = useParams();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [data, setData] = useState(null);
  const [fullName, setFullName] = useState("");
  const [terms, setTerms] = useState(false);
  const [signing, setSigning] = useState(false);
  const [signedNow, setSignedNow] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const res = await ContractSignAPI.view(token);
      setData(res);
      document.title = `Підпис договору ${res?.contract?.number || ""} · ECO.NOVA`;
    } catch (e) {
      setError(e?.response?.data?.detail || "Договір не знайдено або посилання недоступне.");
    } finally { setLoading(false); }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const sign = async () => {
    if (!fullName.trim() || fullName.trim().length < 4) { setError("Введіть повне ім'я підписанта."); return; }
    if (!terms) { setError("Потрібно прийняти умови договору."); return; }
    setSigning(true); setError("");
    try {
      const res = await ContractSignAPI.sign(token, { full_name: fullName.trim(), terms_accepted: true });
      setData((d) => ({ ...d, contract: { ...(d?.contract || {}), ...res.contract } }));
      setSignedNow(true);
    } catch (e) {
      setError(e?.response?.data?.detail || "Не вдалося підписати договір.");
    } finally { setSigning(false); }
  };

  if (loading) {
    return <Shell><div className="flex items-center justify-center rounded-2xl border border-white/10 bg-white/5 py-20 text-white/60"><Loader2 className="mr-2 h-5 w-5 animate-spin" /> Завантаження договору…</div></Shell>;
  }

  if (error && !data) {
    return (
      <Shell>
        <div className="rounded-2xl border border-red-400/20 bg-red-500/10 p-8 text-center">
          <AlertTriangle className="mx-auto h-10 w-10 text-red-300" />
          <div className="mt-3 text-lg font-semibold">Посилання недоступне</div>
          <p className="mt-1 text-sm text-white/60">{error}</p>
        </div>
      </Shell>
    );
  }

  const c = data?.contract || {};
  const company = data?.company || {};
  const operator = data?.operator || {};
  const isSigned = c.status === "signed" || c.esign_status === "signed";

  return (
    <Shell>
      {/* Contract card */}
      <div className="overflow-hidden rounded-2xl border border-white/10 bg-white text-slate-800 shadow-2xl">
        <div className="flex items-center justify-between gap-3 border-b border-slate-100 bg-[#F2F8F3] px-5 py-4">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#0E5E3A]/10 text-[#0E5E3A]"><FileText className="h-5 w-5" /></span>
            <div>
              <div className="text-sm text-slate-500">{c.title || "Договір на утилізацію відходів"}</div>
              <div className="font-mono text-base font-semibold text-slate-900">{c.number || "—"}</div>
            </div>
          </div>
          {isSigned
            ? <span className="flex items-center gap-1.5 rounded-full bg-[#0E5E3A] px-3 py-1 text-xs font-semibold text-white"><CheckCircle2 className="h-3.5 w-3.5" /> Підписано</span>
            : <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-700">Очікує підпису</span>}
        </div>

        <div className="grid gap-4 px-5 py-5 sm:grid-cols-2">
          <div className="flex items-start gap-2">
            <Building2 className="mt-0.5 h-4 w-4 text-slate-400" />
            <div><div className="text-xs text-slate-500">Замовник</div><div className="text-sm font-medium text-slate-900">{company.name || "—"}</div>{company.edrpou && <div className="text-xs text-slate-500">ЄДРПОУ {company.edrpou}</div>}</div>
          </div>
          <div className="flex items-start gap-2">
            <ShieldCheck className="mt-0.5 h-4 w-4 text-slate-400" />
            <div><div className="text-xs text-slate-500">Виконавець</div><div className="text-sm font-medium text-slate-900">{operator.name || "ECO.NOVA Utilization Operator"}</div>{operator.edrpou && <div className="text-xs text-slate-500">ЄДРПОУ {operator.edrpou}</div>}</div>
          </div>
          <div className="flex items-start gap-2">
            <Scale className="mt-0.5 h-4 w-4 text-slate-400" />
            <div><div className="text-xs text-slate-500">Сума договору</div><div className="text-sm font-semibold text-slate-900">{money(c.amount, c.currency)}</div></div>
          </div>
          <div className="flex items-start gap-2">
            <CalendarDays className="mt-0.5 h-4 w-4 text-slate-400" />
            <div><div className="text-xs text-slate-500">Термін дії</div><div className="text-sm font-medium text-slate-900">{fmtDate(c.valid_from)} — {fmtDate(c.valid_to)}</div></div>
          </div>
        </div>

        {(c.items || []).length > 0 && (
          <div className="border-t border-slate-100 px-5 py-4">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Перелік відходів</div>
            <div className="rounded-xl border border-slate-100">
              {(c.items || []).map((it, i) => (
                <div key={i} className="flex items-center justify-between border-b border-slate-100 px-3 py-2 text-sm last:border-b-0">
                  <div className="flex items-center gap-2"><span className="font-mono text-slate-900">{it.waste_code}</span><span className="max-w-[14rem] truncate text-slate-500">{it.name || ""}</span></div>
                  <div className="text-slate-600">{it.qty != null ? `${it.qty} ${it.unit || "kg"}` : ""}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {c.has_pdf && (
          <div className="border-t border-slate-100 px-5 py-3">
            <a href={c.pdf_url ? `${(process.env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "")}${c.pdf_url}` : ContractSignAPI.pdfUrl(token)} target="_blank" rel="noreferrer"
               className="inline-flex items-center gap-2 text-sm font-medium text-[#0E5E3A] hover:underline" data-testid="esign-pdf-link">
              <FileDown className="h-4 w-4" /> Переглянути повний текст договору (PDF)
            </a>
          </div>
        )}
      </div>

      {/* Sign / signed block */}
      {isSigned ? (
        <div className="mt-5 space-y-4" data-testid="esign-success">
          <div className="rounded-2xl border border-[#5BC47A]/30 bg-[#0E5E3A]/20 p-6 text-center">
            <CheckCircle2 className="mx-auto h-12 w-12 text-[#5BC47A]" />
            <div className="mt-3 text-lg font-semibold text-white">{signedNow ? "Дякуємо! Договір підписано" : "Договір вже підписано"}</div>
            <p className="mt-1 text-sm text-white/65">
              Підписант: <span className="font-medium text-white">{c.signed_by || c.signed_full_name || "—"}</span><br />
              {c.signed_at && <>Дата та час підпису: {fmtDateTime(c.signed_at)}</>}
            </p>
          </div>

          {/* Electronic signature certificate — tamper-evident audit trail */}
          {c.signature && (
            <div className="rounded-2xl border border-white/10 bg-white p-5 text-slate-800" data-testid="esign-certificate">
              <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#0E5E3A]/10 text-[#0E5E3A]"><Fingerprint className="h-5 w-5" /></span>
                <div>
                  <div className="text-sm font-semibold text-slate-900">Сертифікат електронного підпису</div>
                  <div className="text-[11px] text-slate-500">Простий електронний підпис (ПЕП)</div>
                </div>
              </div>
              <dl className="mt-3 space-y-2.5 text-sm">
                <div className="flex flex-col gap-0.5 sm:flex-row sm:justify-between sm:gap-3">
                  <dt className="text-slate-500">Серійний номер</dt>
                  <dd className="break-all font-mono text-slate-900" data-testid="esign-serial">{c.signature.signature_id}</dd>
                </div>
                <div className="flex flex-col gap-0.5 sm:flex-row sm:justify-between sm:gap-3">
                  <dt className="text-slate-500">Підписант</dt>
                  <dd className="font-medium text-slate-900">{c.signature.signer_name}</dd>
                </div>
                <div className="flex flex-col gap-0.5 sm:flex-row sm:justify-between sm:gap-3">
                  <dt className="text-slate-500">Дата та час (UTC)</dt>
                  <dd className="text-slate-900">{fmtDateTime(c.signature.signed_at)}</dd>
                </div>
                {c.signature.ip && (
                  <div className="flex flex-col gap-0.5 sm:flex-row sm:justify-between sm:gap-3">
                    <dt className="flex items-center gap-1 text-slate-500"><Globe className="h-3.5 w-3.5" /> IP-адреса</dt>
                    <dd className="font-mono text-slate-900">{c.signature.ip}</dd>
                  </div>
                )}
                <div className="flex flex-col gap-1 border-t border-slate-100 pt-2.5">
                  <dt className="flex items-center gap-1 text-slate-500"><Hash className="h-3.5 w-3.5" /> Хеш документа ({c.signature.hash_algorithm || "SHA-256"})</dt>
                  <dd className="break-all rounded-lg bg-slate-50 px-2.5 py-1.5 font-mono text-[11px] leading-relaxed text-slate-700" data-testid="esign-hash">{c.signature.document_hash}</dd>
                </div>
              </dl>
              <p className="mt-3 rounded-lg bg-[#F2F8F3] px-3 py-2 text-[11px] leading-relaxed text-slate-500">
                {c.signature.standard ? `Правова основа: ${c.signature.standard}. ` : ""}
                Підпис прив'язано до незмінного хешу умов договору: будь-яка зміна тексту після підписання змінить хеш і зробить підробку очевидною.
              </p>
            </div>
          )}
          <p className="text-center text-xs text-white/45">Копію договору та аудит підпису збережено в системі оператора. Дякуємо за співпрацю!</p>
        </div>
      ) : (
        <div className="mt-5 rounded-2xl border border-white/10 bg-white/5 p-6">
          <div className="flex items-center gap-2 text-white"><PenLine className="h-5 w-5 text-[#5BC47A]" /><span className="font-semibold">Підписання договору</span></div>
          <p className="mt-1 text-sm text-white/55">Введіть ваше повне ім'я (П.І.Б.) та підтвердьте згоду з умовами для електронного підпису.</p>

          <div className="mt-4 space-y-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-white/60">Прізвище, ім'я, по батькові</label>
              <input
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Напр.: Петренко Іван Васильович"
                className="w-full rounded-xl border border-white/15 bg-[#0B1A14] px-3 py-2.5 text-sm text-white placeholder:text-white/30 outline-none focus:border-[#5BC47A]"
                data-testid="esign-fullname"
              />
            </div>
            <label className="flex cursor-pointer items-start gap-2.5 text-sm text-white/70">
              <input type="checkbox" checked={terms} onChange={(e) => setTerms(e.target.checked)} className="mt-0.5 h-4 w-4 accent-[#5BC47A]" data-testid="esign-terms" />
              <span>Я ознайомлений(-а) з умовами договору, маю повноваження підписувати його від імені замовника та надаю згоду на підписання в електронній формі.</span>
            </label>
            {error && <div className="rounded-lg border border-red-400/20 bg-red-500/10 px-3 py-2 text-sm text-red-200">{error}</div>}
            <button
              onClick={sign}
              disabled={signing || !fullName.trim() || !terms}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#5BC47A] px-4 py-3 text-sm font-semibold text-[#0B1A14] transition hover:bg-[#6fd28d] disabled:cursor-not-allowed disabled:opacity-50"
              data-testid="esign-submit"
            >
              {signing ? <><Loader2 className="h-4 w-4 animate-spin" /> Підписання…</> : <><ShieldCheck className="h-4 w-4" /> Підписати договір</>}
            </button>
            <p className="text-center text-[11px] text-white/35">Дата, час, IP-адреса та пристрій підписання фіксуються для юридичної значущості.</p>
          </div>
        </div>
      )}
    </Shell>
  );
}
