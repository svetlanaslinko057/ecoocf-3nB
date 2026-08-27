import React, { useEffect, useState, useCallback } from "react";
import { api, ContractFlowAPI } from "@/lib/api";
import "./contractflow.css";

const STATUS_BADGE = {
  draft: "gray", generated: "blue", sent_for_review: "blue", awaiting_profile: "amber",
  ready_for_acceptance: "blue", accepted: "blue", awaiting_payment: "amber",
  payment_confirmed: "blue", manager_approved: "green", active: "green",
  revision_pending_acceptance: "amber", closed: "gray", archived: "gray",
};
const FIELD_LABELS = {
  legal_name: "Юридична назва", edrpou: "ЄДРПОУ", legal_address: "Юридична адреса",
  phone: "Телефон", email: "Email", signer_full_name: "ПІБ підписанта", signer_position: "Посада підписанта",
  value: "Сума договору", currency: "Валюта", contract_type_id: "Тип договору", template_id: "Шаблон",
  service_name: "Послуга", title: "Назва", valid_from: "Діє з", valid_to: "Діє до", custom_vars: "Змінні",
  manual_regeneration: "Ручна регенерація", payment_terms: "Умови оплати", number: "Номер",
};
const labelFor = (k) => FIELD_LABELS[k] || k;
const PAY_BADGE = {
  not_invoiced: "gray", invoice_issued: "blue", awaiting_bank_transfer: "amber",
  proof_uploaded: "blue", payment_confirmed: "green", rejected: "red", needs_clarification: "amber",
};

export default function ContractsFlowPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [creating, setCreating] = useState(false);
  const [flash, setFlash] = useState("");
  const toast = (m) => { setFlash(m); setTimeout(() => setFlash(""), 2800); };

  const load = useCallback(async () => {
    setLoading(true);
    try { const d = await ContractFlowAPI.contracts(); setItems(d.items || []); }
    catch { toast("Помилка завантаження"); }
    setLoading(false);
  }, []);
  useEffect(() => { load(); }, [load]);

  const open = async (id) => {
    try { setSelected(await ContractFlowAPI.contract(id)); }
    catch { toast("Не вдалося відкрити договір"); }
  };

  if (selected) {
    return <ContractDetail contract={selected} onBack={() => { setSelected(null); load(); }} onReload={async () => setSelected(await ContractFlowAPI.contract(selected.id))} toast={toast} flash={flash} />;
  }

  return (
    <div className="cf-wrap">
      <div className="cf-head">
        <div>
          <div className="cf-title">Універсальні договори</div>
          <div className="cf-sub">Створення, генерація, ознайомлення, оплата (IBAN) та активація договорів під будь-який шаблон.</div>
        </div>
        <button className="cf-btn" data-testid="cf-create-contract" onClick={() => setCreating(true)}>+ Новий договір</button>
      </div>

      <div className="cf-card">
        {loading ? <div className="cf-empty">Завантаження…</div> : items.length === 0 ? (
          <div className="cf-empty">Ще немає договорів. Створіть перший.</div>
        ) : (
          <table className="cf-table">
            <thead><tr><th>№</th><th>Клієнт</th><th>Сума</th><th>Статус</th><th>Оплата</th><th></th></tr></thead>
            <tbody>
              {items.map((c) => (
                <tr key={c.id} data-testid="cf-contract-row">
                  <td><b>{c.number}</b><div className="cf-muted">{c.title}</div></td>
                  <td>{c.customer_name || c.customer_id}</td>
                  <td>{c.value ? `${c.value} ${c.currency || "UAH"}` : "—"}</td>
                  <td><span className={`cf-badge ${STATUS_BADGE[c.status] || "gray"}`}>{c.status_label || c.status}</span></td>
                  <td><span className={`cf-badge ${PAY_BADGE[(c.payment || {}).status] || "gray"}`}>{c.payment_status_label || "—"}</span></td>
                  <td style={{ textAlign: "right" }}><button className="cf-btn ghost sm" onClick={() => open(c.id)}>Відкрити</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {creating && <CreateModal onClose={() => setCreating(false)} onCreated={(c) => { setCreating(false); toast("Договір створено"); setSelected(c); }} toast={toast} />}
      {flash && <div className="cf-flash">{flash}</div>}
    </div>
  );
}

function CreateModal({ onClose, onCreated, toast }) {
  const [customers, setCustomers] = useState([]);
  const [types, setTypes] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [f, setF] = useState({ customer_id: "", contract_type_id: "", template_id: "", title: "Договір", value: "", valid_from: "", valid_to: "" });
  const [busy, setBusy] = useState(false);
  const upd = (k, v) => setF((p) => ({ ...p, [k]: v }));

  useEffect(() => {
    (async () => {
      try {
        const [cr, ty, tp] = await Promise.all([
          api.get("/customers", { params: { limit: 200 } }).then((r) => r.data).catch(() => []),
          ContractFlowAPI.types({ active: true }),
          ContractFlowAPI.templates({ status: "active" }),
        ]);
        const list = Array.isArray(cr) ? cr : (cr.items || cr.customers || cr.data || []);
        setCustomers(list);
        setTypes(ty.items || []); setTemplates(tp.items || []);
      } catch { toast("Помилка завантаження довідників"); }
    })();
  }, [toast]);

  const submit = async () => {
    if (!f.customer_id) return toast("Оберіть клієнта");
    setBusy(true);
    try {
      const body = { ...f, value: f.value ? Number(f.value) : null };
      const c = await ContractFlowAPI.createContract(body);
      onCreated(c);
    } catch (e) { toast(e?.response?.data?.detail || "Помилка створення"); }
    setBusy(false);
  };

  const typeTemplates = templates.filter((t) => !f.contract_type_id || t.contract_type_id === f.contract_type_id || !t.contract_type_id);

  return (
    <div className="cf-modal-bg" onClick={onClose}>
      <div className="cf-modal" onClick={(e) => e.stopPropagation()}>
        <div className="cf-title" style={{ fontSize: 18, marginBottom: 6 }}>Новий договір</div>
        <div className="cf-sub" style={{ marginBottom: 16 }}>Договір можна створити навіть з неповними реквізитами клієнта — підписати можна лише після їх заповнення.</div>
        <div className="cf-field"><label className="cf-label">Клієнт *</label>
          <select className="cf-select" data-testid="cf-create-customer" value={f.customer_id} onChange={(e) => upd("customer_id", e.target.value)}>
            <option value="">— оберіть клієнта —</option>
            {customers.map((c) => <option key={c.id || c.customerId} value={c.id || c.customerId}>{c.name || c.company_name || c.email} ({c.email})</option>)}
          </select></div>
        <div className="cf-row2">
          <div className="cf-field"><label className="cf-label">Тип договору</label>
            <select className="cf-select" data-testid="cf-create-type" value={f.contract_type_id} onChange={(e) => upd("contract_type_id", e.target.value)}>
              <option value="">— авто —</option>
              {types.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select></div>
          <div className="cf-field"><label className="cf-label">Шаблон</label>
            <select className="cf-select" value={f.template_id} onChange={(e) => upd("template_id", e.target.value)}>
              <option value="">— за замовчуванням типу —</option>
              {typeTemplates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select></div>
        </div>
        <div className="cf-row2">
          <div className="cf-field"><label className="cf-label">Назва</label>
            <input className="cf-input" value={f.title} onChange={(e) => upd("title", e.target.value)} /></div>
          <div className="cf-field"><label className="cf-label">Сума (грн)</label>
            <input className="cf-input" type="number" value={f.value} onChange={(e) => upd("value", e.target.value)} /></div>
        </div>
        <div className="cf-row2">
          <div className="cf-field"><label className="cf-label">Діє з</label>
            <input className="cf-input" type="date" value={f.valid_from} onChange={(e) => upd("valid_from", e.target.value)} /></div>
          <div className="cf-field"><label className="cf-label">Діє до</label>
            <input className="cf-input" type="date" value={f.valid_to} onChange={(e) => upd("valid_to", e.target.value)} /></div>
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 8 }}>
          <button className="cf-btn ghost" onClick={onClose}>Скасувати</button>
          <button className="cf-btn" data-testid="cf-create-submit" disabled={busy || !f.customer_id} onClick={submit}>{busy ? "Створення…" : "Створити"}</button>
        </div>
      </div>
    </div>
  );
}

function ContractDetail({ contract, onBack, onReload, toast, flash }) {
  const [busy, setBusy] = useState("");
  const [editProfile, setEditProfile] = useState(false);
  const cur = contract.current || (contract.versions || []).slice(-1)[0] || {};
  const validation = cur.validation || {};
  const pay = contract.payment || {};
  const rev = contract.revision;
  const revDoc = contract.revision_document || {};
  const act = (name, fn) => async () => {
    setBusy(name);
    try { await fn(); await onReload(); toast("Готово"); }
    catch (e) {
      const d = e?.response?.data?.detail;
      toast(typeof d === "string" ? d : (d?.error ? "Дію заблоковано: бракує реквізитів" : "Помилка"));
    }
    setBusy("");
  };

  return (
    <div className="cf-wrap">
      <div className="cf-head">
        <div>
          <button className="cf-btn ghost sm" onClick={onBack}>← Назад</button>
          <div className="cf-title" style={{ marginTop: 10 }}>Договір {contract.number}</div>
          <div style={{ marginTop: 6, display: "flex", gap: 8, flexWrap: "wrap" }}>
            <span className={`cf-badge ${STATUS_BADGE[contract.status] || "gray"}`}>{contract.status_label || contract.status}</span>
            <span className={`cf-badge ${PAY_BADGE[pay.status] || "gray"}`}>{contract.payment_status_label || pay.status}</span>
            <span className="cf-badge gray">чинна версія v{contract.active_version || cur.version}</span>
            {contract.acceptance ? <span className="cf-badge green">Прийнято клієнтом</span> : null}
            {rev ? <span className="cf-badge amber" data-testid="cf-revision-badge">Нова редакція v{rev.version} · {rev.status_label}</span> : null}
          </div>
        </div>
        <a className="cf-btn ghost" href={ContractFlowAPI.pdfUrl(contract.id)} target="_blank" rel="noreferrer">PDF</a>
      </div>

      <div className="cf-detail-grid">
        <div>
          {rev && (
            <div className="cf-card" data-testid="cf-revision-panel" style={{ marginBottom: 16, borderLeft: "4px solid #d97706" }}>
              <div className="cf-label" style={{ marginBottom: 8 }}>Нова редакція очікує погодження (v{rev.version})</div>
              <div className="cf-alert warn" style={{ marginBottom: 10 }}>
                Активна (чинна) редакція: <b>v{contract.active_version}</b>. Нова редакція стане чинною лише після повторного погодження клієнтом
                {rev.payment_required ? " та коригувальної оплати" : ""} і затвердження менеджером.
              </div>
              <div className="cf-kv"><b>Що змінилося</b><span>{(rev.changed_fields || []).map((k) => labelFor(k)).join(", ") || "—"}</span></div>
              <div className="cf-kv"><b>Автор зміни</b><span>{rev.created_by} · {rev.created_at ? new Date(rev.created_at).toLocaleString("uk-UA") : ""}</span></div>
              <div className="cf-kv"><b>Причина</b><span>{rev.change_reason}</span></div>
              <div className="cf-kv"><b>Повторне погодження</b><span>{rev.acceptance ? `так · ${new Date(rev.acceptance.accepted_at).toLocaleString("uk-UA")}` : "очікується"}</span></div>
              <div className="cf-kv"><b>Вплив на оплату</b><span>{rev.payment_required ? `так · ${rev.payment_status_label || (rev.payment||{}).status || "—"}` : "ні"}</span></div>
              <div style={{ marginTop: 10 }}>
                <button className="cf-btn ghost" data-testid="cf-resend-revision" disabled={busy} onClick={act("resend", () => ContractFlowAPI.send(contract.id))}>Надіслати повторно</button>
              </div>
              <div className="cf-label" style={{ margin: "14px 0 8px" }}>Документ нової редакції (v{rev.version})</div>
              <iframe title="revision-preview" className="cf-preview" srcDoc={revDoc.html || "<p>—</p>"} sandbox="" />
            </div>
          )}
          <div className="cf-card" style={{ marginBottom: 16 }}>
            <div className="cf-label" style={{ marginBottom: 8 }}>{rev ? `Чинна редакція (v${contract.active_version})` : `Попередній перегляд документа (v${cur.version})`}</div>
            <iframe title="preview" className="cf-preview" srcDoc={cur.html || "<p>Немає версії</p>"} sandbox="" />
          </div>

          <div className="cf-card">
            <div className="cf-label" style={{ marginBottom: 10 }}>Дії менеджера</div>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <button className="cf-btn ghost" data-testid="cf-regenerate" disabled={busy} onClick={act("regen", () => ContractFlowAPI.regenerate(contract.id))}>Регенерувати</button>
              <button className="cf-btn blue" data-testid="cf-send" disabled={busy} onClick={act("send", () => ContractFlowAPI.send(contract.id))}>Надіслати на ознайомлення</button>
              <button className="cf-btn ghost" data-testid="cf-issue-invoice" disabled={busy} onClick={act("inv", () => ContractFlowAPI.issueInvoice(contract.id))}>Виставити рахунок (IBAN)</button>
              <button className="cf-btn" data-testid="cf-confirm-payment" disabled={busy} onClick={act("cp", () => ContractFlowAPI.confirmPayment(contract.id, { reference: "manual" }))}>Підтвердити оплату</button>
              <button className="cf-btn warn" disabled={busy} onClick={act("rp", () => ContractFlowAPI.rejectPayment(contract.id, { notes: "Потрібно уточнити" }))}>Відхилити оплату</button>
              <button className="cf-btn" data-testid="cf-approve" disabled={busy} onClick={act("ap", () => ContractFlowAPI.approve(contract.id))} style={{ background: "#7c3aed" }}>Approve → Активувати</button>
            </div>
            <div className="cf-muted" style={{ marginTop: 10 }}>Порядок: Надіслати → (клієнт приймає) → рахунок → клієнт вантажить підтвердження → Підтвердити оплату → Approve.</div>
          </div>
        </div>

        <div>
          <div className="cf-card" style={{ marginBottom: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div className="cf-label">Юридичні реквізити клієнта</div>
              <button className="cf-btn ghost sm" data-testid="cf-edit-profile" onClick={() => setEditProfile(true)}>Доповнити</button>
            </div>
            <div className="cf-progress"><span style={{ width: `${validation.completion_percent || 0}%` }} /></div>
            <div className="cf-muted" style={{ marginBottom: 8 }}>Заповнено: {validation.completion_percent || 0}%</div>
            {validation.complete ? (
              <div className="cf-alert ok">Реквізити повні — договір можна прийняти й оплатити.</div>
            ) : (
              <div className="cf-alert warn">
                Не вистачає для прийняття:
                <div style={{ marginTop: 6 }}>
                  {(cur.blocking_reasons || []).map((r, i) => <span className="cf-chip" key={i}>{r}</span>)}
                </div>
              </div>
            )}
          </div>

          <div className="cf-card" style={{ marginBottom: 16 }}>
            <div className="cf-label" style={{ marginBottom: 8 }}>Оплата (тільки IBAN)</div>
            <div className="cf-kv"><b>Статус</b><span>{contract.payment_status_label || pay.status}</span></div>
            {pay.iban && <div className="cf-kv"><b>IBAN</b><span>{pay.iban}</span></div>}
            {pay.amount_due != null && <div className="cf-kv"><b>Сума</b><span>{pay.amount_due} {pay.currency || "UAH"}</span></div>}
            {pay.recipient_name && <div className="cf-kv"><b>Отримувач</b><span>{pay.recipient_name}</span></div>}
            {pay.payment_purpose && <div className="cf-kv"><b>Призначення</b><span>{pay.payment_purpose}</span></div>}
            {pay.proof_file_id && <div className="cf-kv"><b>Підтвердження</b>
              <a href={ContractFlowAPI.fileUrl(pay.proof_file_id)} target="_blank" rel="noreferrer">{pay.proof_filename || "переглянути"}</a></div>}
            {pay.payment_reference && <div className="cf-kv"><b>Референс</b><span>{pay.payment_reference}</span></div>}
          </div>

          <div className="cf-card">
            <div className="cf-label" style={{ marginBottom: 8 }}>Історія</div>
            <ul className="cf-timeline">
              {(contract.events || []).slice().reverse().map((e, i) => (
                <li key={i}><b>{e.note}</b><div className="cf-muted">{e.actor} · {new Date(e.at).toLocaleString("uk-UA")}</div></li>
              ))}
              {(!contract.events || contract.events.length === 0) && <li className="cf-muted">Подій ще немає</li>}
            </ul>
          </div>
        </div>
      </div>

      {editProfile && <ProfileEditor customerId={contract.customer_id} onClose={() => setEditProfile(false)} onSaved={async () => { setEditProfile(false); await onReload(); toast("Реквізити оновлено"); }} toast={toast} />}
      {flash && <div className="cf-flash">{flash}</div>}
    </div>
  );
}

const REQ = [
  ["legal_name", "Юридична назва"], ["edrpou", "ЄДРПОУ"], ["legal_address", "Юридична адреса"],
  ["phone", "Телефон"], ["email", "Email"], ["signer_full_name", "ПІБ підписанта"], ["signer_position", "Посада підписанта"],
];
const OPT = [["iban", "IBAN"], ["bank_name", "Банк"], ["vat_number", "ІПН / ПДВ"], ["postal_address", "Поштова адреса"]];

function ProfileEditor({ customerId, onClose, onSaved, toast }) {
  const [f, setF] = useState({});
  const [busy, setBusy] = useState(false);
  useEffect(() => { (async () => {
    try { const d = await ContractFlowAPI.legalProfile(customerId); setF(d.profile || {}); } catch { toast("Помилка"); }
  })(); }, [customerId, toast]);
  const upd = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const save = async () => {
    setBusy(true);
    try { await ContractFlowAPI.saveLegalProfile(customerId, f); onSaved(); }
    catch { toast("Помилка збереження"); } setBusy(false);
  };
  return (
    <div className="cf-modal-bg" onClick={onClose}>
      <div className="cf-modal" onClick={(e) => e.stopPropagation()}>
        <div className="cf-title" style={{ fontSize: 18, marginBottom: 14 }}>Юридичні реквізити клієнта</div>
        <div className="cf-row2">
          {REQ.map(([k, l]) => (
            <div className="cf-field" key={k}><label className="cf-label">{l} *</label>
              <input className="cf-input" data-testid={`cf-prof-${k}`} value={f[k] || ""} onChange={(e) => upd(k, e.target.value)} /></div>
          ))}
          {OPT.map(([k, l]) => (
            <div className="cf-field" key={k}><label className="cf-label">{l}</label>
              <input className="cf-input" value={f[k] || ""} onChange={(e) => upd(k, e.target.value)} /></div>
          ))}
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
          <button className="cf-btn ghost" onClick={onClose}>Скасувати</button>
          <button className="cf-btn" data-testid="cf-prof-save" disabled={busy} onClick={save}>Зберегти</button>
        </div>
      </div>
    </div>
  );
}
