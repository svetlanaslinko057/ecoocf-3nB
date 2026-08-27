import React, { useState } from "react";
import { ClientAPI } from "@/lib/clientApi";
import { useClientCopy } from "./clientCopy";

// In-cabinet self-serve order: search licensed codes, add quantities, submit.
export default function NewRequestModal({ onClose, onCreated }) {
  const { L } = useClientCopy();
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [items, setItems] = useState([]); // {waste_code, name, qty}
  const [comment, setComment] = useState("");
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);

  const search = async (val) => {
    setQ(val);
    if (val.trim().length < 2) {
      setResults([]);
      return;
    }
    setSearching(true);
    try {
      const d = await ClientAPI.searchCodes(val.trim());
      setResults(d.items || d.codes || d.results || []);
    } catch (e) {
      setResults([]);
    } finally {
      setSearching(false);
    }
  };

  const addItem = (code) => {
    const c = code.code || code.waste_code;
    if (!c || items.find((i) => i.waste_code === c)) return;
    setItems((arr) => [...arr, { waste_code: c, name: code.name || "", qty: 100 }]);
    setQ("");
    setResults([]);
  };

  const setQty = (idx, v) => setItems((arr) => arr.map((it, i) => (i === idx ? { ...it, qty: v } : it)));
  const removeItem = (idx) => setItems((arr) => arr.filter((_, i) => i !== idx));

  const submit = async () => {
    setErr("");
    if (items.length === 0) {
      setErr(L.nrErrEmpty);
      return;
    }
    setSaving(true);
    try {
      const payload = {
        items: items.map((i) => ({ waste_code: i.waste_code, qty: Number(i.qty) || 0, unit: "kg", name: i.name })),
        comment,
      };
      const d = await ClientAPI.createRequest(payload);
      onCreated && onCreated(d.request_id);
    } catch (e) {
      const msg = e?.response?.data?.detail || L.nrErrCreate;
      setErr(typeof msg === "string" ? msg : L.nrErrCreate);
      setSaving(false);
    }
  };

  return (
    <div className="inq-overlay" role="dialog" aria-modal="true" data-testid="new-request-modal">
      <div className="inq-backdrop" onClick={onClose} />
      <div className="inq-card inq-card--wide">
        <button className="inq-close" onClick={onClose} aria-label={L.close}>×</button>
        <p className="inq-eyebrow">{L.nrEyebrow}</p>
        <h3 className="inq-title">{L.nrTitle}</h3>
        <p className="inq-sub">{L.nrSub}</p>

        <div className="nr-search">
          <input
            value={q}
            onChange={(e) => search(e.target.value)}
            placeholder={L.nrSearchPh}
            data-testid="nr-search-input"
          />
          {searching && <span className="nr-search__hint">{L.nrSearching}</span>}
          {results.length > 0 && (
            <ul className="nr-results" data-testid="nr-results">
              {results.slice(0, 8).map((c) => (
                <li key={c.code || c.waste_code} onClick={() => addItem(c)}>
                  <b>{c.code || c.waste_code}</b> <span>{c.name}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {items.length > 0 && (
          <div className="nr-items">
            {items.map((it, idx) => (
              <div className="nr-item" key={it.waste_code}>
                <div className="nr-item__code">
                  <b>{it.waste_code}</b>
                  <span>{it.name}</span>
                </div>
                <div className="nr-item__qty">
                  <input
                    type="number"
                    min="1"
                    value={it.qty}
                    onChange={(e) => setQty(idx, e.target.value)}
                    data-testid={`nr-qty-${idx}`}
                  />
                  <span>{L.kg}</span>
                </div>
                <button className="nr-item__rm" onClick={() => removeItem(idx)} aria-label={L.remove}>×</button>
              </div>
            ))}
          </div>
        )}

        <label className="inq-field inq-field--full">
          <span>{L.nrComment}</span>
          <textarea rows={2} value={comment} onChange={(e) => setComment(e.target.value)} data-testid="nr-comment" />
        </label>

        {err && <p className="inq-err">{err}</p>}
        <button className="inq-submit" onClick={submit} disabled={saving} data-testid="nr-submit">
          {saving ? L.nrCreating : L.nrCreate}
        </button>
      </div>
    </div>
  );
}
