import React, { useEffect, useState, useCallback } from "react";
import { ClientAPI } from "@/lib/clientApi";
import "../contractflow/contractflow.css";

const STATUS_BADGE = {
  draft: "gray", generated: "blue", sent_for_review: "blue", awaiting_profile: "amber",
  ready_for_acceptance: "blue", accepted: "blue", awaiting_payment: "amber",
  payment_confirmed: "blue", manager_approved: "green", active: "green", revision_pending_acceptance: "amber", closed: "gray", archived: "gray",
};

export default function ClientContractFlow() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [flash, setFlash] = useState("");
  const toast = (m) => { setFlash(m); setTimeout(() => setFlash(""), 3000); };

  const load = useCallback(async () => {
    setLoading(true);
    try { const d = await ClientAPI.cfContracts(); setItems(d.items || []); }
    catch { toast("Помилка завантаження"); }
    setLoading(false);
  }, []);
  useEffect(() => { load(); }, [load]);

  const open = async (id) => {
    try { const c = await ClientAPI.cfContract(id); await ClientAPI.cfOpen(id); setSelected(await ClientAPI.cfContract(id)); }
    catch { toast("Не вдалося відкрити"); }
  };

  if (selected) return <ClientDetail contract={selected} onBack={() => { setSelected(null); load(); }}
    onReload={async () => setSelected(await ClientAPI.cfContract(selected.id))} toast={toast} flash={flash} />;

  return (
    <div className="cf-wrap" style={{ padding: "12px 0" }}>
      <div className="cf-head">
        <div><div className="cf-title">Договори на підпис</div>
          <div className="cf-sub">Ознайомтесь, доповніть реквізити, прийміть умови та оплатіть банківським переказом.</div></div>
      </div>
      <div className="cf-card">
        {loading ? <div className="cf-empty">Завантаження…</div> : items.length === 0 ? (
          <div className="cf-empty">Договорів на підпис поки немає</div>
        ) : (
          <table className="cf-table">
            <thead><tr><th>№</th><th>Назва</th><th>Сума</th><th>Статус</th><th></th></tr></thead>
            <tbody>
              {items.map((c) => (
                <tr key={c.id} data-testid="client-cf-row">
                  <td><b>{c.number}</b></td>
                  <td>{c.title}</td>
                  <td>{c.value ? `${c.value} ${c.currency || "UAH"}` : "—"}</td>
                  <td><span className={`cf-badge ${STATUS_BADGE[c.status] || "gray"}`}>{c.status_label || c.status}</span></td>
                  <td style={{ textAlign: "right" }}><button className="cf-btn ghost sm" data-testid="client-cf-open" onClick={() => open(c.id)}>Відкрити</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {flash && <div className="cf-flash">{flash}</div>}
    </div>
  );
}

const FIELD_LABELS = {
  legal_name: "Юридична назва", edrpou: "ЄДРПОУ", legal_address: "Юридична адреса",
  phone: "Телефон", email: "Email", signer_full_name: "ПІБ підписанта", signer_position: "Посада підписанта",
  value: "Сума договору", currency: "Валюта", contract_type_id: "Тип договору", template_id: "Шаблон",
  service_name: "Послуга", title: "Назва", valid_from: "Діє з", valid_to: "Діє до", custom_vars: "Змінні",
  manual_regeneration: "Ручна регенерація", payment_terms: "Умови оплати",
};
const labelFor = (k) => FIELD_LABELS[k] || k;

function ClientDetail({ contract, onBack, onReload, toast, flash }) {
  const [read, setRead] = useState(false);
  const [busy, setBusy] = useState(false);
  const [editProfile, setEditProfile] = useState(false);

  // A pending revision drives the acceptance/payment UI instead of the in-force edition.
  const rev = contract.revision;
  const inRevision = !!rev;
  const inForce = contract.current || (contract.versions || []).slice(-1)[0] || {};
  const doc4view = inRevision ? (contract.revision_document || inForce) : inForce;
  const validation = doc4view.validation || {};
  const complete = validation.complete;
  const pay = inRevision ? (rev.payment || {}) : (contract.payment || {});
  const paymentRequired = inRevision ? !!rev.payment_required : true;
  const accepted = inRevision ? (rev.status !== "pending_acceptance") : !!contract.acceptance;
  const canAccept = complete && doc4view.can_accept && !accepted;
  const payDone = pay.status === "payment_confirmed";
  const awaitingApprove = inRevision && (rev.status === "accepted" || rev.status === "payment_confirmed");

  const accept = async () => {
    setBusy(true);
    try { await ClientAPI.cfAccept(contract.id, { read_confirmed: true }); await onReload(); toast(inRevision ? "Нову редакцію погоджено" : "Умови прийнято"); }
    catch (e) {
      const d = e?.response?.data?.detail;
      toast(typeof d === "object" ? "Не вистачає реквізитів для прийняття" : (d || "Помилка"));
    }
    setBusy(false);
  };
  const uploadProof = async (file) => {
    setBusy(true);
    const fd = new FormData(); fd.append("file", file);
    try { await ClientAPI.cfUploadProof(contract.id, fd); await onReload(); toast("Підтвердження завантажено"); }
    catch { toast("Помилка завантаження"); } setBusy(false);
  };

  return (
    <div className="cf-wrap" style={{ padding: "12px 0" }}>
      <div className="cf-head">
        <div>
          <button className="cf-btn ghost sm" onClick={onBack}>← Назад</button>
          <div className="cf-title" style={{ marginTop: 10 }}>Договір {contract.number}</div>
          <div style={{ marginTop: 6 }}><span className={`cf-badge ${STATUS_BADGE[contract.status] || "gray"}`}>{contract.status_label || contract.status}</span></div>
        </div>
        <a className="cf-btn ghost" href={ClientAPI.cfPdfUrl(contract.id)} target="_blank" rel="noreferrer">Завантажити PDF</a>
      </div>

      {inRevision && (
        <div className="cf-card" data-testid="client-revision-banner" style={{ marginBottom: 16, borderLeft: "4px solid #d97706" }}>
          <div className="cf-alert warn" style={{ marginBottom: 8 }}>
            <b>Підготовлено нову редакцію договору (v{rev.version}).</b> Чинною залишається попередня редакція (v{contract.active_version}), доки ви не погодите нову.
          </div>
          <div className="cf-muted" style={{ marginBottom: 6 }}>Що змінилося:</div>
          <div>{(rev.changed_fields || []).map((f, i) => <span className="cf-chip" key={i}>{labelFor(f)}</span>)}</div>
          {paymentRequired && <div className="cf-muted" style={{ marginTop: 8 }}>Зміна впливає на суму — після погодження буде виставлено коригувальний рахунок.</div>}
        </div>
      )}

      <div className="cf-detail-grid">
        <div className="cf-card">
          <div className="cf-label" style={{ marginBottom: 8 }}>{inRevision ? `Нова редакція (v${rev.version})` : "Текст договору"}</div>
          <iframe title="doc" className="cf-preview" srcDoc={doc4view.html || ""} sandbox="" />
        </div>

        <div>
          {!complete && (
            <div className="cf-card" style={{ marginBottom: 16 }}>
              <div className="cf-alert warn">
                Для прийняття договору не вистачає:
                <div style={{ marginTop: 6 }}>{(cur.blocking_reasons || []).map((r, i) => <span className="cf-chip" key={i}>{r}</span>)}</div>
              </div>
              <button className="cf-btn" data-testid="client-fill-profile" onClick={() => setEditProfile(true)}>Заповнити реквізити</button>
            </div>
          )}

          {!accepted ? (
            <div className="cf-card" style={{ marginBottom: 16 }}>
              <div className="cf-label" style={{ marginBottom: 8 }}>Прийняття умов</div>
              <label style={{ display: "flex", gap: 10, alignItems: "flex-start", cursor: canAccept ? "pointer" : "not-allowed", opacity: canAccept ? 1 : 0.55 }}>
                <input type="checkbox" data-testid="client-accept-checkbox" disabled={!canAccept} checked={read} onChange={(e) => setRead(e.target.checked)} />
                <span>Я прочитав(ла) договір і погоджуюсь з його умовами</span>
              </label>
              <button className="cf-btn" data-testid="client-accept-btn" style={{ marginTop: 12 }} disabled={!canAccept || !read || busy} onClick={accept}>Прийняти умови</button>
              {!complete && <div className="cf-muted" style={{ marginTop: 8 }}>Чекбокс стане активним після заповнення реквізитів.</div>}
            </div>
          ) : (
            <div className="cf-card" style={{ marginBottom: 16 }}>
              <div className="cf-alert ok">{inRevision
                ? `Ви погодили нову редакцію ${rev.acceptance?.accepted_at ? new Date(rev.acceptance.accepted_at).toLocaleString("uk-UA") : ""}.`
                : `Ви прийняли умови ${contract.acceptance?.accepted_at ? new Date(contract.acceptance.accepted_at).toLocaleString("uk-UA") : ""}.`}</div>

              {awaitingApprove && !paymentRequired && (
                <div className="cf-alert" style={{ marginTop: 10 }}>Нову редакцію погоджено. Очікуйте затвердження менеджером.</div>
              )}

              {paymentRequired && (<>
              <div className="cf-label" style={{ marginBottom: 8, marginTop: 10 }}>{inRevision ? "Коригувальна оплата (IBAN)" : "Оплата банківським переказом (IBAN)"}</div>
              {pay.iban ? (<>
                <div className="cf-kv"><b>Отримувач</b><span>{pay.recipient_name}</span></div>
                <div className="cf-kv"><b>ЄДРПОУ</b><span>{pay.recipient_edrpou}</span></div>
                <div className="cf-kv"><b>IBAN</b><span style={{ userSelect: "all" }}>{pay.iban}
                  <button className="cf-btn ghost sm" style={{ marginLeft: 8 }} onClick={() => { navigator.clipboard?.writeText(pay.iban); toast("IBAN скопійовано"); }}>копіювати</button></span></div>
                <div className="cf-kv"><b>Банк</b><span>{pay.bank_name}</span></div>
                <div className="cf-kv"><b>Сума</b><span>{pay.amount_due} {pay.currency || "UAH"}</span></div>
                <div className="cf-kv"><b>Призначення</b><span>{pay.payment_purpose}
                  <button className="cf-btn ghost sm" style={{ marginLeft: 8 }} onClick={() => { navigator.clipboard?.writeText(pay.payment_purpose || ""); toast("Скопійовано"); }}>копіювати</button></span></div>
                {pay.terms && <div className="cf-muted" style={{ marginTop: 8 }}>{pay.terms}</div>}

                <div style={{ marginTop: 14 }}>
                  <div className="cf-badge blue" style={{ marginBottom: 8 }}>Статус: {inRevision ? (rev.payment_status_label || pay.status) : contract.payment_status_label}</div>
                  {pay.status !== "payment_confirmed" ? (
                    <label className="cf-btn" style={{ cursor: "pointer", display: "inline-flex" }}>
                      {pay.proof_file_id ? "Замінити підтвердження" : "Завантажити платіжне підтвердження"}
                      <input type="file" hidden data-testid="client-upload-proof" disabled={busy} onChange={(e) => e.target.files[0] && uploadProof(e.target.files[0])} />
                    </label>
                  ) : <div className="cf-alert ok">Оплату підтверджено. Очікуйте активації договору.</div>}
                  {pay.proof_filename && <div className="cf-muted" style={{ marginTop: 8 }}>Завантажено: {pay.proof_filename}</div>}
                </div>
              </>) : <div className="cf-muted">Рахунок формується…</div>}
              </>)}
            </div>
          )}

          <div className="cf-card">
            <div className="cf-label" style={{ marginBottom: 8 }}>Статус реквізитів</div>
            <div className="cf-progress"><span style={{ width: `${validation.completion_percent || 0}%` }} /></div>
            <div className="cf-muted">{complete ? "Реквізити заповнені" : `Заповнено ${validation.completion_percent || 0}%`}</div>
            <button className="cf-btn ghost sm" style={{ marginTop: 10 }} onClick={() => setEditProfile(true)}>Редагувати реквізити</button>
          </div>
        </div>
      </div>

      {editProfile && <ClientProfileEditor onClose={() => setEditProfile(false)} onSaved={async () => { setEditProfile(false); await onReload(); toast("Реквізити оновлено"); }} toast={toast} />}
      {flash && <div className="cf-flash">{flash}</div>}
    </div>
  );
}

const REQ = [["legal_name", "Юридична назва"], ["edrpou", "ЄДРПОУ"], ["legal_address", "Юридична адреса"],
  ["phone", "Телефон"], ["email", "Email"], ["signer_full_name", "ПІБ підписанта"], ["signer_position", "Посада підписанта"]];
const OPT = [["iban", "IBAN"], ["bank_name", "Банк"], ["vat_number", "ІПН / ПДВ"]];

function ClientProfileEditor({ onClose, onSaved, toast }) {
  const [f, setF] = useState({});
  const [busy, setBusy] = useState(false);
  useEffect(() => { (async () => { try { const d = await ClientAPI.cfLegalProfile(); setF(d.profile || {}); } catch { toast("Помилка"); } })(); }, [toast]);
  const upd = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const save = async () => { setBusy(true); try { await ClientAPI.cfSaveLegalProfile(f); onSaved(); } catch { toast("Помилка збереження"); } setBusy(false); };
  return (
    <div className="cf-modal-bg" onClick={onClose}>
      <div className="cf-modal" onClick={(e) => e.stopPropagation()}>
        <div className="cf-title" style={{ fontSize: 18, marginBottom: 14 }}>Мої юридичні реквізити</div>
        <div className="cf-row2">
          {REQ.map(([k, l]) => (
            <div className="cf-field" key={k}><label className="cf-label">{l} *</label>
              <input className="cf-input" data-testid={`client-prof-${k}`} value={f[k] || ""} onChange={(e) => upd(k, e.target.value)} /></div>
          ))}
          {OPT.map(([k, l]) => (
            <div className="cf-field" key={k}><label className="cf-label">{l}</label>
              <input className="cf-input" value={f[k] || ""} onChange={(e) => upd(k, e.target.value)} /></div>
          ))}
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
          <button className="cf-btn ghost" onClick={onClose}>Скасувати</button>
          <button className="cf-btn" data-testid="client-prof-save" disabled={busy} onClick={save}>Зберегти</button>
        </div>
      </div>
    </div>
  );
}
