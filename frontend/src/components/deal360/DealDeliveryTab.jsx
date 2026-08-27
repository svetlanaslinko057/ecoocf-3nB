/**
 * Wave 13 — Deal360 Delivery tab
 *
 * Vertical timeline + carrier card + ETA editor + documents.
 * Pulls the full bundle from `GET /api/delivery/{deal_id}` so we get the
 * canonical 9-stage timeline regardless of how many milestones are stored.
 *
 * If no shipment exists for the deal yet, shows a single "Create shipment"
 * call-to-action that POSTs to `/api/delivery/shipments`.
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Truck, Calendar, Plus, ShieldWarning } from '@phosphor-icons/react';

import { API_URL } from '../../App';
import DeliveryHealthBadge from '../delivery360/DeliveryHealthBadge';
import ShipmentTimeline    from '../delivery360/ShipmentTimeline';
import CarrierAssign       from '../delivery360/CarrierAssign';
import DeliveryDocuments   from '../delivery360/DeliveryDocuments';

const toDateInput = (iso) => {
  if (!iso) return '';
  try { return new Date(iso).toISOString().slice(0, 10); } catch { return ''; }
};

const DealDeliveryTab = ({ dealId, shipments = [], onChanged }) => {
  const [bundle,  setBundle]  = useState(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [etaExpected, setEtaExpected] = useState('');
  const [etaActual,   setEtaActual]   = useState('');
  const [savingEta,   setSavingEta]   = useState(false);

  const primary = shipments?.[0];

  const fetchBundle = useCallback(async () => {
    if (!primary?.id && !dealId) {
      setBundle(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const ref = primary?.id || dealId;
      const r = await axios.get(`${API_URL}/api/delivery/${ref}`);
      const data = r.data?.data || null;
      setBundle(data);
      const del = data?.shipment?.delivery || {};
      setEtaExpected(toDateInput(del.eta_expected));
      setEtaActual(toDateInput(del.eta_actual));
    } catch (err) {
      // 404 → no shipment yet, that's fine
      if (err.response?.status !== 404) {
        toast.error(err.response?.data?.detail || 'Failed to load delivery bundle');
      }
      setBundle(null);
    } finally { setLoading(false); }
  }, [primary, dealId]);

  useEffect(() => { fetchBundle(); }, [fetchBundle]);

  const createShipment = async () => {
    if (!dealId) return;
    setCreating(true);
    try {
      await axios.post(`${API_URL}/api/delivery/shipments`, {
        deal_id: dealId,
        current_milestone: 'auction_won',
      });
      toast.success('Shipment created');
      await fetchBundle();
      onChanged?.();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to create shipment');
    } finally { setCreating(false); }
  };

  const saveEta = async () => {
    if (!bundle?.shipment?.id) return;
    setSavingEta(true);
    try {
      const payload = {};
      if (etaExpected) payload.eta_expected = new Date(etaExpected).toISOString();
      if (etaActual)   payload.eta_actual   = new Date(etaActual).toISOString();
      if (!Object.keys(payload).length) return;
      await axios.post(`${API_URL}/api/delivery/${bundle.shipment.id}/eta`, payload);
      toast.success('ETA updated');
      await fetchBundle();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save ETA');
    } finally { setSavingEta(false); }
  };

  if (loading) {
    return (
      <div className="py-16 flex justify-center" data-testid="delivery-tab-loading">
        <div className="w-7 h-7 border-2 border-[#18181B] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!bundle) {
    return (
      <div className="py-12 text-center" data-testid="delivery-tab-empty">
        <Truck size={36} className="mx-auto text-[#A1A1AA]" weight="duotone" />
        <div className="text-sm text-[#71717A] mt-2">No shipment yet for this deal.</div>
        <button
          onClick={createShipment}
          disabled={creating}
          className="mt-3 inline-flex items-center gap-1.5 text-[12px] font-semibold rounded-full bg-[#18181B] text-white px-4 py-1.5 hover:bg-[#27272A] disabled:opacity-60"
          data-testid="delivery-create-shipment"
        >
          <Plus size={12} weight="bold" /> {creating ? 'Creating…' : 'Create shipment'}
        </button>
      </div>
    );
  }

  const health    = bundle.delivery_health || {};
  const shipment  = bundle.shipment || {};
  const delivery  = shipment.delivery || {};
  const timeline  = bundle.timeline || [];
  const documents = bundle.documents || [];
  const missing   = health.metrics?.missing_documents || [];
  const reasons   = health.reasons || [];

  return (
    <div className="space-y-4" data-testid="delivery-tab">
      {/* Health summary banner */}
      <div className="bg-[#FAFAFA] border border-[#E4E4E7] rounded-2xl p-4 flex items-center gap-4 flex-wrap" data-testid="delivery-health-banner">
        <DeliveryHealthBadge health={health} size="lg" />
        <div className="flex-1 min-w-[180px]">
          <div className="text-[11px] uppercase tracking-wider font-bold text-[#71717A]">Current stage</div>
          <div className="text-[14px] font-semibold text-[#18181B]">
            {(health.metrics?.current_milestone || '').replace(/_/g, ' ') || '—'}
          </div>
        </div>
        <div className="min-w-[120px]">
          <div className="text-[11px] uppercase tracking-wider font-bold text-[#71717A]">Progress</div>
          <div className="text-[14px] font-semibold text-[#18181B] tabular-nums">
            {health.metrics?.milestones_done || 0} / {health.metrics?.milestones_total || 9}
          </div>
        </div>
        <div className="min-w-[120px]">
          <div className="text-[11px] uppercase tracking-wider font-bold text-[#71717A]">ETA variance</div>
          {typeof health.metrics?.eta_variance_days === 'number' ? (
            <div className={`text-[14px] font-semibold tabular-nums ${health.metrics.eta_variance_days > 0 ? 'text-red-700' : 'text-emerald-700'}`}>
              {health.metrics.eta_variance_days > 0 ? '+' : ''}{health.metrics.eta_variance_days}d
            </div>
          ) : <div className="text-[14px] text-[#71717A]">—</div>}
        </div>
        {reasons.length > 0 && reasons[0] !== 'On track' ? (
          <div className="basis-full mt-2 pt-2 border-t border-[#E4E4E7] flex flex-wrap items-center gap-1.5 text-[12px]">
            <ShieldWarning size={12} className="text-amber-700" weight="bold" />
            <span className="font-semibold text-[#52525B]">Reasons:</span>
            {reasons.map((r, i) => <span key={i} className="inline-flex items-center rounded-full bg-amber-50 text-amber-800 border border-amber-200 px-2 py-0.5 text-[11px]">{r}</span>)}
          </div>
        ) : null}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="md:col-span-2">
          <ShipmentTimeline
            shipmentId={shipment.id}
            timeline={timeline}
            onChanged={() => { fetchBundle(); onChanged?.(); }}
          />
        </div>

        <aside className="space-y-3">
          <CarrierAssign
            shipmentId={shipment.id}
            currentCarrierId={delivery.carrier_id}
            currentCarrierName={delivery.carrier_name}
            onChanged={() => { fetchBundle(); onChanged?.(); }}
          />

          <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4" data-testid="eta-editor">
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider font-bold text-[#71717A] mb-2">
              <Calendar size={14} weight="bold" /> ETA engine
            </div>
            <label className="block text-[11px] text-[#71717A] mb-1">Expected</label>
            <input
              type="date" value={etaExpected} onChange={(e) => setEtaExpected(e.target.value)}
              className="w-full px-2 py-1.5 border border-[#E4E4E7] rounded-lg text-sm bg-white mb-2"
              data-testid="eta-expected"
            />
            <label className="block text-[11px] text-[#71717A] mb-1">Actual</label>
            <input
              type="date" value={etaActual} onChange={(e) => setEtaActual(e.target.value)}
              className="w-full px-2 py-1.5 border border-[#E4E4E7] rounded-lg text-sm bg-white mb-2"
              data-testid="eta-actual"
            />
            <button
              onClick={saveEta}
              disabled={savingEta || (!etaExpected && !etaActual)}
              className="w-full inline-flex items-center justify-center gap-1 text-[12px] font-semibold rounded-full bg-[#18181B] text-white px-3 py-1.5 hover:bg-[#27272A] disabled:opacity-50"
              data-testid="eta-save"
            >
              {savingEta ? 'Saving…' : 'Save ETA'}
            </button>
          </div>
        </aside>
      </div>

      <DeliveryDocuments
        shipmentId={shipment.id}
        documents={documents}
        missing={missing}
        onChanged={() => { fetchBundle(); onChanged?.(); }}
      />
    </div>
  );
};

export default DealDeliveryTab;
