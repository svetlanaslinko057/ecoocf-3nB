import React, { useEffect, useState, useCallback } from "react";
import { ContractFlowAPI } from "@/lib/api";
import "./contractflow.css";

const INVOICE_SCOPES = [
  { v: "final", l: "Фінальний" },
  { v: "per_period", l: "За період" },
  { v: "per_act", l: "За кожним актом" },
];

export default function ContractTypesPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);
  const [flash, setFlash] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await ContractFlowAPI.types();
      setItems(d.items || []);
    } catch (e) { setFlash("Помилка завантаження"); }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);
  const toast = (m) => { setFlash(m); setTimeout(() => setFlash(""), 2500); };

  const save = async (form) => {
    try {
      if (form.id) await ContractFlowAPI.updateType(form.id, form);
      else await ContractFlowAPI.createType(form);
      setEditing(null); toast("Збережено"); load();
    } catch (e) { toast(e?.response?.data?.detail || "Помилка збереження"); }
  };
  const remove = async (id) => {
    if (!window.confirm("Видалити тип договору?")) return;
    await ContractFlowAPI.deleteType(id); toast("Видалено"); load();
  };

  return (
    <div className="cf-wrap">
      <div className="cf-head">
        <div>
          <div className="cf-title">Типи договорів</div>
          <div className="cf-sub">Універсальні типи договорів. Кожен тип має набір обов'язкових реквізитів, шаблон за замовчуванням та політику оплати.</div>
        </div>
        <button className="cf-btn" data-testid="cf-add-type" onClick={() => setEditing({ name: "", code: "", description: "", invoice_scope: "final", active: true })}>+ Новий тип</button>
      </div>

      <div className="cf-card">
        {loading ? <div className="cf-empty">Завантаження…</div> : items.length === 0 ? (
          <div className="cf-empty">Ще немає типів договорів</div>
        ) : (
          <table className="cf-table">
            <thead><tr><th>Назва</th><th>Код</th><th>Оплата</th><th>Статус</th><th></th></tr></thead>
            <tbody>
              {items.map((t) => (
                <tr key={t.id} data-testid="cf-type-row">
                  <td><b>{t.name}</b><div className="cf-muted">{t.description}</div></td>
                  <td><span className="cf-badge gray">{t.code || "—"}</span></td>
                  <td>{(INVOICE_SCOPES.find((s) => s.v === t.invoice_scope) || {}).l || t.invoice_scope}</td>
                  <td>{t.active ? <span className="cf-badge green">Активний</span> : <span className="cf-badge gray">Вимкнено</span>}</td>
                  <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                    <button className="cf-btn ghost sm" onClick={() => setEditing(t)}>Редагувати</button>{" "}
                    <button className="cf-btn warn sm" onClick={() => remove(t.id)}>Видалити</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {editing && <TypeModal initial={editing} onClose={() => setEditing(null)} onSave={save} />}
      {flash && <div className="cf-flash">{flash}</div>}
    </div>
  );
}

function TypeModal({ initial, onClose, onSave }) {
  const [f, setF] = useState({ ...initial });
  const upd = (k, v) => setF((p) => ({ ...p, [k]: v }));
  return (
    <div className="cf-modal-bg" onClick={onClose}>
      <div className="cf-modal" onClick={(e) => e.stopPropagation()}>
        <div className="cf-title" style={{ fontSize: 18, marginBottom: 16 }}>{f.id ? "Редагувати тип" : "Новий тип договору"}</div>
        <div className="cf-field"><label className="cf-label">Назва *</label>
          <input className="cf-input" data-testid="cf-type-name" value={f.name || ""} onChange={(e) => upd("name", e.target.value)} /></div>
        <div className="cf-row2">
          <div className="cf-field"><label className="cf-label">Код</label>
            <input className="cf-input" value={f.code || ""} onChange={(e) => upd("code", e.target.value)} /></div>
          <div className="cf-field"><label className="cf-label">Політика оплати</label>
            <select className="cf-select" value={f.invoice_scope || "final"} onChange={(e) => upd("invoice_scope", e.target.value)}>
              {INVOICE_SCOPES.map((s) => <option key={s.v} value={s.v}>{s.l}</option>)}
            </select></div>
        </div>
        <div className="cf-field"><label className="cf-label">Опис</label>
          <textarea className="cf-textarea" rows={2} value={f.description || ""} onChange={(e) => upd("description", e.target.value)} /></div>
        <div className="cf-field"><label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
          <input type="checkbox" checked={!!f.active} onChange={(e) => upd("active", e.target.checked)} /> Активний</label></div>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 8 }}>
          <button className="cf-btn ghost" onClick={onClose}>Скасувати</button>
          <button className="cf-btn" data-testid="cf-type-save" disabled={!f.name} onClick={() => onSave(f)}>Зберегти</button>
        </div>
      </div>
    </div>
  );
}
