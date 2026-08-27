/**
 * Customer360Indicators — small status badge ribbon shown at the top
 * of the Customer 360 page (UAT Enhancement #4 spec).
 *
 * Surfaces the binary signals that managers use to triage a customer
 * at a glance without opening the card. Driven by
 *   GET /api/customers/{cid}/roadmap-indicators
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import {
  AlertTriangle, CalendarCheck2, ClipboardList, Clock, FileSignature,
  ShoppingBag, Wallet, Activity,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const Pill = ({ active, label, icon: Icon, tone = 'zinc', testId, extra }) => {
  const toneMap = {
    zinc:    { on: 'bg-zinc-900 text-white border-zinc-900',           off: 'bg-zinc-50 text-zinc-400 border-zinc-200' },
    blue:    { on: 'bg-blue-600 text-white border-blue-600',           off: 'bg-zinc-50 text-zinc-400 border-zinc-200' },
    amber:   { on: 'bg-amber-500 text-white border-amber-500',         off: 'bg-zinc-50 text-zinc-400 border-zinc-200' },
    rose:    { on: 'bg-rose-600 text-white border-rose-600',           off: 'bg-zinc-50 text-zinc-400 border-zinc-200' },
    emerald: { on: 'bg-emerald-600 text-white border-emerald-600',     off: 'bg-zinc-50 text-zinc-400 border-zinc-200' },
    violet:  { on: 'bg-violet-600 text-white border-violet-600',       off: 'bg-zinc-50 text-zinc-400 border-zinc-200' },
  };
  const cls = active ? toneMap[tone].on : toneMap[tone].off;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold border transition ${cls}`}
      data-testid={testId}
      title={label}
    >
      <Icon className="w-3.5 h-3.5" />
      {label}
      {extra ? <span className="font-bold">· {extra}</span> : null}
    </span>
  );
};

const Customer360Indicators = ({ customerId, lang = 'uk' }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!customerId) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API_URL}/api/customers/${customerId}/roadmap-indicators`);
        if (!cancelled) setData(r.data?.indicators || null);
      } catch { /* RBAC 403 silently → hide ribbon */ }
      finally { if (!cancelled) setLoading(false); }
    })();
    return () => { cancelled = true; };
  }, [customerId]);

  if (loading || !data) return null;

  const L = {
    uk: { task: 'Активна задача', overdue: 'Прострочено', meeting: 'Зустріч', deposit: 'Депозит', sale: 'Продаж', contract: 'Договір', risk: 'Ризики', progress: 'Прогрес' },
    en: { task: 'Open task', overdue: 'Overdue', meeting: 'Meeting', deposit: 'Deposit', sale: 'Sale', contract: 'Contract', risk: 'Risks', progress: 'Progress' },
    bg: { task: 'Отворена задача', overdue: 'Просрочена', meeting: 'Среща', deposit: 'Депозит', sale: 'Продажба', contract: 'Договор', risk: 'Рискове', progress: 'Прогрес' },
  };
  const l = L[lang] || L.uk;

  return (
    <div
      className="flex items-center gap-1.5 flex-wrap"
      data-testid="customer360-indicators"
    >
      <Pill testId="ind-task" active={data.has_open_task} label={l.task} icon={ClipboardList} tone="blue" />
      <Pill testId="ind-overdue" active={data.has_overdue_task} label={l.overdue} icon={Clock} tone="rose" />
      <Pill testId="ind-meeting" active={data.had_meeting} label={l.meeting} icon={CalendarCheck2} tone="violet" />
      <Pill testId="ind-deposit" active={data.has_deposit} label={l.deposit} icon={Wallet} tone="emerald" />
      <Pill testId="ind-sale" active={data.has_sale} label={l.sale} icon={ShoppingBag} tone="emerald" />
      <Pill testId="ind-contract" active={data.has_contract} label={l.contract} icon={FileSignature} tone="zinc" />
      {data.risk_count > 0 && (
        <Pill
          testId="ind-risks"
          active={true}
          label={l.risk}
          icon={AlertTriangle}
          tone="amber"
          extra={data.risk_count}
        />
      )}
      {data.roadmap_progress_pct > 0 && (
        <Pill
          testId="ind-progress"
          active={true}
          label={l.progress}
          icon={Activity}
          tone="zinc"
          extra={`${data.roadmap_progress_pct}%`}
        />
      )}
    </div>
  );
};

export default Customer360Indicators;
