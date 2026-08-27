/**
 * ClientInvoices — B2B client cabinet: invoices & IBAN bank-transfer payment.
 *
 * Flow: client sees issued invoices → opens one → copies the company's IBAN
 * requisites + payment purpose → pays via their bank → uploads the payment
 * proof (mandatory) → presses "Я оплатив" → invoice goes to manager review.
 */
import React, { useEffect, useState, useCallback } from "react";
import { ClientAPI } from "@/lib/clientApi";
import { useClientCopy } from "./clientCopy";
import { toast } from "sonner";

const API_BASE = (process.env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "");
const money = (v, c = "UAH") => `${Number(v || 0).toLocaleString("uk-UA", { maximumFractionDigits: 2 })} ${c}`;
const absUrl = (u) => (!u ? "" : u.startsWith("http") ? u : `${API_BASE}${u}`);

const STATUS = {
  uk: {
    pending: { tone: "tone-grey", label: "Готується" },
    sent: { tone: "tone-amber", label: "До сплати" },
    overdue: { tone: "tone-amber", label: "Прострочено" },
    awaiting_confirmation: { tone: "tone-blue", label: "На перевірці" },
    paid: { tone: "tone-green", label: "Сплачено" },
    cancelled: { tone: "tone-grey", label: "Скасовано" },
  },
  en: {
    pending: { tone: "tone-grey", label: "Preparing" },
    sent: { tone: "tone-amber", label: "To pay" },
    overdue: { tone: "tone-amber", label: "Overdue" },
    awaiting_confirmation: { tone: "tone-blue", label: "Under review" },
    paid: { tone: "tone-green", label: "Paid" },
    cancelled: { tone: "tone-grey", label: "Cancelled" },
  },
};

function CopyRow({ label, value }) {
  if (!value) return null;
  const copy = () => {
    navigator.clipboard?.writeText(String(value)).then(
      () => toast.success("Скопійовано"),
      () => {}
    );
  };
  return (
    <div className="ci-req__row">
      <span className="ci-req__label">{label}</span>
      <span className="ci-req__value">{value}</span>
      <button type="button" className="ci-req__copy" onClick={copy} title="Копіювати">⧉</button>
    </div>
  );
}

function Requisites({ req, purpose, lang }) {
  if (!req) return null;
  return (
    <div className="ci-req" data-testid="client-invoice-requisites">
      <h4 className="ci-req__title">{lang === "en" ? "Payment details (bank transfer)" : "Реквізити для оплати (банківський переказ)"}</h4>
      <CopyRow label={lang === "en" ? "Recipient" : "Отримувач"} value={req.legal_name} />
      <CopyRow label="ЄДРПОУ" value={req.edrpou} />
      <CopyRow label="IBAN" value={req.iban} />
      <CopyRow label={lang === "en" ? "Bank" : "Банк"} value={req.bank_name} />
      <CopyRow label="МФО" value={req.mfo} />
      {req.swift && <CopyRow label="SWIFT/BIC" value={req.swift} />}
      <CopyRow label={lang === "en" ? "Purpose" : "Призначення"} value={purpose} />
    </div>
  );
}

function InvoiceCard({ inv, lang, onChanged }) {
  const st = (STATUS[lang] || STATUS.uk)[inv.status] || { tone: "tone-grey", label: inv.status };
  const amount = inv.amount ?? inv.total ?? 0;
  const cur = inv.currency || "UAH";
  const payable = ["sent", "overdue"].includes(inv.status);
  const [open, setOpen] = useState(payable);
  const [file, setFile] = useState(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const claim = inv.payment_claim || {};

  const submit = async () => {
    if (!file) return toast.error(lang === "en" ? "Attach the payment proof file" : "Прикріпіть файл-підтвердження оплати");
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const up = await ClientAPI.uploadInvoiceProof(inv.id, fd);
      await ClientAPI.confirmInvoicePayment(inv.id, { proof_url: up.url, note });
      toast.success(lang === "en" ? "Sent for manager review" : "Надіслано менеджеру на перевірку");
      onChanged && onChanged();
    } catch (e) {
      toast.error(e?.response?.data?.detail || (lang === "en" ? "Failed" : "Не вдалося"));
    } finally { setBusy(false); }
  };

  return (
    <div className="cl-card ci-card" data-testid={`client-invoice-${inv.id}`}>
      <div className="ci-card__head" onClick={() => setOpen((v) => !v)} role="button">
        <div>
          <div className="ci-card__num">{lang === "en" ? "Invoice" : "Рахунок"} № {inv.number || inv.id?.slice(-8)}</div>
          <div className="cl-td-sub">{inv.description || (inv.items?.[0]?.name) || "—"}</div>
        </div>
        <div className="ci-card__right">
          <span className={`cl-badge ${st.tone}`}>{st.label}</span>
          <div className="ci-card__amount">{money(amount, cur)}</div>
        </div>
      </div>

      {open && (
        <div className="ci-card__body">
          {inv.status === "paid" && (
            <div className="ci-note ci-note--ok">{lang === "en" ? "Payment confirmed. Thank you!" : "Оплату підтверджено. Дякуємо! Замовлення прийнято в роботу."}</div>
          )}
          {inv.status === "awaiting_confirmation" && (
            <div className="ci-note ci-note--info">
              {lang === "en" ? "We received your payment notice and are verifying it." : "Ми отримали ваше повідомлення про оплату — перевіряємо надходження коштів."}
              {claim.proof_url && <> · <a href={absUrl(claim.proof_url)} target="_blank" rel="noreferrer">{lang === "en" ? "View proof" : "Переглянути підтвердження"}</a></>}
            </div>
          )}
          {claim.rejection_reason && inv.status !== "awaiting_confirmation" && (
            <div className="ci-note ci-note--warn">{lang === "en" ? "Previous payment was not confirmed:" : "Попередню оплату не підтверджено:"} {claim.rejection_reason}</div>
          )}

          {(payable || inv.status === "awaiting_confirmation" || inv.status === "paid") && (
            <Requisites req={inv.requisites} purpose={inv.payment_purpose} lang={lang} />
          )}

          {payable && (
            <div className="ci-pay" data-testid="client-invoice-pay">
              <h4 className="ci-req__title">{lang === "en" ? "I have paid" : "Я сплатив(ла)"}</h4>
              <p className="cl-td-sub" style={{ marginBottom: 10 }}>{lang === "en" ? "Upload the payment receipt / payment order (PDF or image) — required." : "Завантажте квитанцію / платіжне доручення (PDF або зображення) — обов'язково."}</p>
              <input type="file" accept=".pdf,.png,.jpg,.jpeg,.webp" onChange={(e) => setFile(e.target.files?.[0] || null)} className="ci-file" data-testid="client-proof-input" />
              <textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder={lang === "en" ? "Comment (optional): payer, date…" : "Коментар (необов'язково): платник, дата…"} rows={2} className="ci-textarea" />
              <button className="cl-btn cl-btn--primary" onClick={submit} disabled={busy} data-testid="client-confirm-payment">
                {busy ? (lang === "en" ? "Sending…" : "Надсилання…") : (lang === "en" ? "Confirm payment" : "Підтвердити оплату")}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ClientInvoices() {
  const { L, lang } = useClientCopy();
  const [items, setItems] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const r = await ClientAPI.invoices();
      setItems(r.items || []);
      setSummary(r.summary || null);
    } catch (e) {
      toast.error(lang === "en" ? "Failed to load invoices" : "Не вдалося завантажити рахунки");
    } finally { setLoading(false); }
  }, [lang]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="cl-skel">{L.loading}</div>;

  return (
    <div data-testid="client-invoices">
      <div className="cl-head">
        <div>
          <p className="cl-eyebrow">{lang === "en" ? "Billing" : "Оплати"}</p>
          <h1 className="cl-h1">{lang === "en" ? "Invoices" : "Рахунки"}</h1>
        </div>
      </div>

      {summary && (
        <div className="cl-kpis" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 14, marginBottom: 18 }}>
          <div className="cl-kpi"><span className="cl-td-sub">{lang === "en" ? "To pay" : "До сплати"}</span><b style={{ fontSize: 22 }}>{summary.to_pay || 0}</b></div>
          <div className="cl-kpi"><span className="cl-td-sub">{lang === "en" ? "Under review" : "На перевірці"}</span><b style={{ fontSize: 22 }}>{summary.awaiting || 0}</b></div>
          <div className="cl-kpi"><span className="cl-td-sub">{lang === "en" ? "Paid" : "Сплачено"}</span><b style={{ fontSize: 22 }}>{summary.paid || 0}</b></div>
          <div className="cl-kpi"><span className="cl-td-sub">{lang === "en" ? "Outstanding" : "Заборгованість"}</span><b style={{ fontSize: 18 }}>{money(summary.outstanding_amount, summary.currency || "UAH")}</b></div>
        </div>
      )}

      {items.length === 0 ? (
        <div className="cl-card"><div className="cl-empty"><p>{lang === "en" ? "No invoices yet. They will appear here once a manager issues one." : "Рахунків поки немає. Вони з'являться тут, коли менеджер виставить рахунок до оплати."}</p></div></div>
      ) : (
        <div className="ci-list">
          {items.map((inv) => (
            <InvoiceCard key={inv.id} inv={inv} lang={lang} onChanged={load} />
          ))}
        </div>
      )}
    </div>
  );
}
