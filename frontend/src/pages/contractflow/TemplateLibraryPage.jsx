import React, { useEffect, useState, useCallback } from "react";
import { ContractFlowAPI } from "@/lib/api";
import "./contractflow.css";

const STATUS_BADGE = { active: "green", draft: "amber", archived: "gray" };

export default function TemplateLibraryPage() {
  const [items, setItems] = useState([]);
  const [types, setTypes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);
  const [flash, setFlash] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [t, ty] = await Promise.all([ContractFlowAPI.templates(), ContractFlowAPI.types()]);
      setItems(t.items || []);
      setTypes(ty.items || []);
    } catch (e) { setFlash("Помилка завантаження"); }
    setLoading(false);
  }, []);
  useEffect(() => { load(); }, [load]);
  const toast = (m) => { setFlash(m); setTimeout(() => setFlash(""), 2600); };

  const openNew = () => setEditing({
    name: "", language: "uk", format: "html", status: "draft", contract_type_id: "",
    html: "<html><body style='font-family:DejaVu Sans,Arial;padding:24px'>\n<h1>Договір №{{contract.number}}</h1>\n<p>ЗАМОВНИК: {{company.legal_name}}, ЄДРПОУ {{company.edrpou}}</p>\n<p>Підписант: {{signer.full_name}} ({{signer.position}})</p>\n<p>Оплата на IBAN: {{payment.iban}}</p>\n</body></html>",
  });

  const openEdit = async (id) => {
    try { const full = await ContractFlowAPI.template(id); setEditing(full); }
    catch { toast("Не вдалося відкрити шаблон"); }
  };

  const save = async (form) => {
    try {
      if (form.id && !form._legacy) await ContractFlowAPI.updateTemplate(form.id, form);
      else await ContractFlowAPI.createTemplate(form);
      setEditing(null); toast("Збережено"); load();
    } catch (e) { toast(e?.response?.data?.detail || "Помилка збереження"); }
  };
  const remove = async (id) => {
    if (!window.confirm("Видалити шаблон?")) return;
    await ContractFlowAPI.deleteTemplate(id); toast("Видалено"); load();
  };

  const upload = async (file) => {
    const fd = new FormData(); fd.append("file", file);
    try { await ContractFlowAPI.uploadTemplate(fd, { name: file.name }); toast("Завантажено (чернетка)"); load(); }
    catch (e) { toast("Помилка завантаження файлу"); }
  };

  return (
    <div className="cf-wrap">
      <div className="cf-head">
        <div>
          <div className="cf-title">Бібліотека шаблонів</div>
          <div className="cf-sub">HTML / DOCX / PDF. Використовуйте універсальні змінні {"{{...}}"}. Один тип договору може мати кілька шаблонів.</div>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <label className="cf-btn ghost" style={{ cursor: "pointer" }}>
            Завантажити файл
            <input type="file" hidden accept=".html,.htm,.docx,.pdf" onChange={(e) => e.target.files[0] && upload(e.target.files[0])} />
          </label>
          <button className="cf-btn" data-testid="cf-add-template" onClick={openNew}>+ Новий шаблон</button>
        </div>
      </div>

      <div className="cf-card">
        {loading ? <div className="cf-empty">Завантаження…</div> : items.length === 0 ? (
          <div className="cf-empty">Ще немає шаблонів</div>
        ) : (
          <table className="cf-table">
            <thead><tr><th>Назва</th><th>Формат</th><th>Мова</th><th>Тип</th><th>Статус</th><th></th></tr></thead>
            <tbody>
              {items.map((t) => (
                <tr key={t.id} data-testid="cf-template-row">
                  <td><b>{t.name}</b><div className="cf-muted">v{t.version} · {(t.checksum || "").slice(0, 10)}</div></td>
                  <td><span className="cf-badge blue">{(t.format || "html").toUpperCase()}</span></td>
                  <td>{(t.language || "uk").toUpperCase()}</td>
                  <td className="cf-muted">{(types.find((x) => x.id === t.contract_type_id) || {}).name || "—"}</td>
                  <td><span className={`cf-badge ${STATUS_BADGE[t.status] || "gray"}`}>{t.status}</span></td>
                  <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                    <button className="cf-btn ghost sm" onClick={() => openEdit(t.id)}>Редагувати</button>{" "}
                    <button className="cf-btn warn sm" onClick={() => remove(t.id)}>Видалити</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {editing && <TemplateModal initial={editing} types={types} onClose={() => setEditing(null)} onSave={save} />}
      {flash && <div className="cf-flash">{flash}</div>}
    </div>
  );
}

function TemplateModal({ initial, types, onClose, onSave }) {
  const [f, setF] = useState({ ...initial });
  const upd = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const isStatic = f.format && f.format !== "html";
  return (
    <div className="cf-modal-bg" onClick={onClose}>
      <div className="cf-modal lg" onClick={(e) => e.stopPropagation()}>
        <div className="cf-title" style={{ fontSize: 18, marginBottom: 16 }}>{f.id ? "Редагувати шаблон" : "Новий шаблон"}</div>
        <div className="cf-row2">
          <div className="cf-field"><label className="cf-label">Назва *</label>
            <input className="cf-input" data-testid="cf-template-name" value={f.name || ""} onChange={(e) => upd("name", e.target.value)} /></div>
          <div className="cf-field"><label className="cf-label">Тип договору</label>
            <select className="cf-select" value={f.contract_type_id || ""} onChange={(e) => upd("contract_type_id", e.target.value)}>
              <option value="">— не привʼязано —</option>
              {types.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select></div>
        </div>
        <div className="cf-row2">
          <div className="cf-field"><label className="cf-label">Мова</label>
            <select className="cf-select" value={f.language || "uk"} onChange={(e) => upd("language", e.target.value)}>
              <option value="uk">UA</option><option value="en">EN</option><option value="ru">RU</option>
            </select></div>
          <div className="cf-field"><label className="cf-label">Статус</label>
            <select className="cf-select" data-testid="cf-template-status" value={f.status || "draft"} onChange={(e) => upd("status", e.target.value)}>
              <option value="draft">Чернетка</option><option value="active">Активний</option><option value="archived">Архів</option>
            </select></div>
        </div>
        {isStatic ? (
          <div className="cf-alert info">Формат {f.format.toUpperCase()} — статичний шаблон. Підстановка змінних недоступна, зберігається як джерело.</div>
        ) : (
          <div className="cf-field"><label className="cf-label">HTML шаблон (змінні: {"{{company.legal_name}}, {{signer.full_name}}, {{payment.iban}}, {{contract.number}}"} …)</label>
            <textarea className="cf-textarea" data-testid="cf-template-html" style={{ fontFamily: "monospace", minHeight: 240 }} value={f.html || ""} onChange={(e) => upd("html", e.target.value)} /></div>
        )}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 8 }}>
          <button className="cf-btn ghost" onClick={onClose}>Скасувати</button>
          <button className="cf-btn" data-testid="cf-template-save" disabled={!f.name} onClick={() => onSave(f)}>Зберегти</button>
        </div>
      </div>
    </div>
  );
}
