/**
 * Wave 6 — Legal Policy Settings (/admin/settings/legal-policy)
 *
 * Small, focused admin configuration page (5 fields):
 *   - default_fx_usd_to_eur
 *   - min_deposit_eur
 *   - deposit_percent_of_max_bid
 *   - refund_deadline_days
 *   - invoice_template_id
 *
 * This page is SEPARATE from the operational /admin/legal page. It is config,
 * not workflow. Read: any staff role. Write: admin only.
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { API_URL } from '../../App';
import { toast } from 'sonner';
import { FloppyDisk, ArrowsClockwise, Scales } from '@phosphor-icons/react';

const DEFAULTS = {
  default_fx_usd_to_eur: 0.92,
  min_deposit_eur: 1000,
  deposit_percent_of_max_bid: 10,
  refund_deadline_days: 30,
  invoice_template_id: 'default',
};

function Field({ label, hint, children }) {
  return (
    <label className="block">
      <div className="text-sm font-semibold mb-1" style={{ color: '#0F172A' }}>{label}</div>
      {children}
      {hint && <div className="text-xs mt-1" style={{ color: '#9CA3AF' }}>{hint}</div>}
    </label>
  );
}

export default function LegalPolicySettingsPage() {
  const [value, setValue] = useState(DEFAULTS);
  const [meta, setMeta] = useState({ updated_at: null, updated_by: null });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await axios.get(`${API_URL}/api/admin/settings/legal-policy`);
      const d = r.data.data || {};
      setValue({
        default_fx_usd_to_eur: d.default_fx_usd_to_eur ?? DEFAULTS.default_fx_usd_to_eur,
        min_deposit_eur: d.min_deposit_eur ?? DEFAULTS.min_deposit_eur,
        deposit_percent_of_max_bid: d.deposit_percent_of_max_bid ?? DEFAULTS.deposit_percent_of_max_bid,
        refund_deadline_days: d.refund_deadline_days ?? DEFAULTS.refund_deadline_days,
        invoice_template_id: d.invoice_template_id ?? DEFAULTS.invoice_template_id,
      });
      setMeta({ updated_at: d.updated_at, updated_by: d.updated_by });
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to load policy');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const save = async () => {
    setSaving(true);
    try {
      const payload = {
        default_fx_usd_to_eur: Number(value.default_fx_usd_to_eur),
        min_deposit_eur: Number(value.min_deposit_eur),
        deposit_percent_of_max_bid: Number(value.deposit_percent_of_max_bid),
        refund_deadline_days: parseInt(value.refund_deadline_days, 10),
        invoice_template_id: String(value.invoice_template_id || '').trim(),
      };
      const r = await axios.put(`${API_URL}/api/admin/settings/legal-policy`, payload);
      const d = r.data.data || {};
      setMeta({ updated_at: d.updated_at, updated_by: d.updated_by });
      toast.success('Legal policy saved');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const reset = () => setValue(DEFAULTS);

  return (
    <div className="p-6 max-w-3xl mx-auto" data-testid="legal-policy-page">
      <div className="flex items-center gap-2 mb-2">
        <Scales size={22} weight="bold" style={{ color: '#FFA800' }} />
        <h1 className="text-2xl font-bold" style={{ color: '#0F172A' }}>Legal Policy</h1>
      </div>
      <p className="text-sm mb-6" style={{ color: '#6B7280' }}>
        Small, focused defaults used across deposit, contracts and invoicing.
        Operational workflow lives separately under <strong>/admin/legal</strong>.
      </p>

      {error && (
        <div className="rounded-md border p-3 mb-4 text-sm" style={{ background: '#FEF2F2', borderColor: '#FECACA', color: '#7F1D1D' }}>
          {error}
        </div>
      )}

      <div className="rounded-xl border bg-white p-6 space-y-4" style={{ borderColor: '#E5E7EB' }}>
        <Field label="Default FX (USD → EUR)" hint="Used when a deposit is calculated without an explicit FX override.">
          <input
            type="number" step="0.001" min="0.1" max="5"
            value={value.default_fx_usd_to_eur}
            onChange={(e) => setValue({ ...value, default_fx_usd_to_eur: e.target.value })}
            className="w-full border rounded-md px-3 py-2 text-sm"
            style={{ borderColor: '#D1D5DB' }}
            data-testid="lp-fx"
            disabled={loading}
          />
        </Field>

        <Field label="Minimum deposit (EUR)" hint="Floor for the auto-calculated required deposit.">
          <input
            type="number" step="50" min="0"
            value={value.min_deposit_eur}
            onChange={(e) => setValue({ ...value, min_deposit_eur: e.target.value })}
            className="w-full border rounded-md px-3 py-2 text-sm"
            style={{ borderColor: '#D1D5DB' }}
            data-testid="lp-min-deposit"
            disabled={loading}
          />
        </Field>

        <Field label="Deposit % of max bid" hint="Percentage applied to max_bid_usd × FX to derive the required deposit (subject to minimum above).">
          <input
            type="number" step="0.5" min="0" max="100"
            value={value.deposit_percent_of_max_bid}
            onChange={(e) => setValue({ ...value, deposit_percent_of_max_bid: e.target.value })}
            className="w-full border rounded-md px-3 py-2 text-sm"
            style={{ borderColor: '#D1D5DB' }}
            data-testid="lp-deposit-pct"
            disabled={loading}
          />
        </Field>

        <Field label="Refund deadline (days)" hint="After this many days without a car, deposit becomes refund-eligible automatically.">
          <input
            type="number" step="1" min="0" max="3650"
            value={value.refund_deadline_days}
            onChange={(e) => setValue({ ...value, refund_deadline_days: e.target.value })}
            className="w-full border rounded-md px-3 py-2 text-sm"
            style={{ borderColor: '#D1D5DB' }}
            data-testid="lp-refund-days"
            disabled={loading}
          />
        </Field>

        <Field label="Invoice template id" hint="Default template used for generated invoices.">
          <input
            type="text"
            value={value.invoice_template_id}
            onChange={(e) => setValue({ ...value, invoice_template_id: e.target.value })}
            className="w-full border rounded-md px-3 py-2 text-sm"
            style={{ borderColor: '#D1D5DB' }}
            data-testid="lp-tpl"
            disabled={loading}
          />
        </Field>

        <div className="flex items-center justify-between pt-4 border-t" style={{ borderColor: '#F3F4F6' }}>
          <div className="text-xs" style={{ color: '#9CA3AF' }}>
            {meta.updated_at ? (
              <>Last saved {new Date(meta.updated_at).toLocaleString()} by {meta.updated_by || 'admin'}</>
            ) : 'Not saved yet'}
          </div>
          <div className="flex gap-2">
            <button
              onClick={reset}
              className="px-3 py-2 rounded-md text-sm font-semibold border"
              style={{ borderColor: '#E5E7EB', color: '#6B7280', background: '#FFFFFF' }}
              disabled={loading || saving}
              data-testid="lp-reset"
            >
              <ArrowsClockwise size={14} className="inline mr-1" /> Reset to defaults
            </button>
            <button
              onClick={save}
              className="px-4 py-2 rounded-md text-sm font-semibold"
              style={{ background: '#FFA800', color: '#111' }}
              disabled={loading || saving}
              data-testid="lp-save"
            >
              <FloppyDisk size={14} className="inline mr-1" /> {saving ? 'Saving…' : 'Save policy'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
