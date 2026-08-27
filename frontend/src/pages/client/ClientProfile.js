import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ClientAPI } from "@/lib/clientApi";
import { useClientAuth } from "@/context/ClientAuthContext";
import { useClientCopy } from "./clientCopy";

export default function ClientProfile() {
  const { customer, refresh, logout } = useClientAuth();
  const { L } = useClientCopy();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", phone: "", company_name: "", position: "" });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (customer) {
      setForm({
        name: customer.name || "",
        phone: customer.phone || "",
        company_name: customer.company_name || "",
        position: customer.position || "",
      });
    }
  }, [customer]);

  const set = (k) => (e) => { setForm((f) => ({ ...f, [k]: e.target.value })); setSaved(false); };

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await ClientAPI.updateMe(form);
      await refresh();
      setSaved(true);
    } finally {
      setSaving(false);
    }
  };

  const doLogout = () => { logout(); navigate("/", { replace: true }); };

  return (
    <div data-testid="client-profile">
      <div className="cl-head">
        <div>
          <p className="cl-eyebrow">{L.profEyebrow}</p>
          <h1 className="cl-h1">{L.profileH}</h1>
        </div>
      </div>

      <div className="cl-card cl-card--narrow">
        <form onSubmit={save} className="cl-form">
          <label className="cl-field">
            <span>{L.fEmail}</span>
            <input value={customer?.email || ""} disabled />
          </label>
          <label className="cl-field">
            <span>{L.fName}</span>
            <input value={form.name} onChange={set("name")} data-testid="profile-name" />
          </label>
          <label className="cl-field">
            <span>{L.fPhone}</span>
            <input value={form.phone} onChange={set("phone")} data-testid="profile-phone" placeholder="+380\u2026" />
          </label>
          <label className="cl-field">
            <span>{L.fCompany}</span>
            <input value={form.company_name} onChange={set("company_name")} data-testid="profile-company" />
          </label>
          <label className="cl-field">
            <span>{L.fPosition}</span>
            <input value={form.position} onChange={set("position")} data-testid="profile-position" />
          </label>
          <div className="cl-form__foot">
            <button type="submit" className="cl-btn cl-btn--primary" disabled={saving} data-testid="profile-save">
              {saving ? L.saving : L.save}
            </button>
            {saved && <span className="cl-saved">{L.saved}</span>}
            <button type="button" className="cl-btn cl-btn--ghost" onClick={doLogout}>{L.signOut}</button>
          </div>
        </form>
      </div>
    </div>
  );
}
