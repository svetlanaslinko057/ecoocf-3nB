/**
 * Journey UI - Funnel Visualization Page
 *
 * Mobile-first redesign:
 *   • Single AdminPageHeader (no card-in-card).
 *   • Period select uses a stable min-width so it never gets squished
 *     into a vertical "30 days" ribbon on narrow screens.
 *   • KPI tiles use AdminStat (consistent typography + Mazzard).
 *   • Funnel rows stack their drop-off chip BELOW the bar on mobile, so
 *     long stage names like "Awaiting Payment" don't crash into the bar.
 *   • Bottleneck items use `<AdminSection>`-style inside the card — no
 *     more bordered tile inside a bordered card.
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useLang } from '../../i18n';
import {
  TrendingDown,
  TrendingUp,
  Clock,
  Users,
  Target,
  AlertTriangle,
  RefreshCw,
  ArrowDown,
  ChevronRight,
  BarChart3,
} from 'lucide-react';
import WhiteSelect from '../../components/ui/WhiteSelect';
import RefreshButton from '../../components/ui/RefreshButton';
import {
  AdminPageHeader,
  AdminCard,
  AdminStat,
} from '../../components/ui/AdminPagePrimitives';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Stage config with colors and icons
const STAGE_CONFIG = {
  NEW_LEAD:        { label: 'New lead',         labelEn: 'New Lead',         color: '#3B82F6' },
  CONTACT_ATTEMPT: { label: 'Contact',          labelEn: 'Contact',          color: '#8B5CF6' },
  QUALIFIED:       { label: 'Qualified',        labelEn: 'Qualified',        color: '#6366F1' },
  CAR_SELECTED:    { label: 'Car Selected',     labelEn: 'Car Selected',     color: '#14B8A6' },
  NEGOTIATION:     { label: 'Negotiations',     labelEn: 'Negotiation',      color: '#F59E0B' },
  CONTRACT_SENT:   { label: 'Contract',         labelEn: 'Contract Sent',    color: '#EAB308' },
  CONTRACT_SIGNED: { label: 'Signed',           labelEn: 'Signed',           color: '#5BC47A' },
  PAYMENT_PENDING: { label: 'Awaiting Payment', labelEn: 'Payment Pending',  color: '#F97316' },
  PAYMENT_DONE:    { label: 'Paid',             labelEn: 'Paid',             color: '#22C55E' },
  SHIPPING:        { label: 'Delivery',         labelEn: 'Shipping',         color: '#06B6D4' },
  DELIVERED:       { label: 'Delivered',        labelEn: 'Delivered',        color: '#10B981' },
};

const STAGE_ORDER = Object.keys(STAGE_CONFIG);

const JourneyPage = () => {
  const { t, lang } = useLang();
  const [loading, setLoading] = useState(true);
  const [funnelData, setFunnelData] = useState(null);
  const [bottlenecks, setBottlenecks] = useState([]);
  const [durations, setDurations] = useState(null);
  const [period, setPeriod] = useState(30);
  const [error, setError] = useState(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem('token');
      const headers = { Authorization: `Bearer ${token}` };
      const [funnelRes, bottlenecksRes, durationsRes] = await Promise.all([
        axios.get(`${API_URL}/api/journey/funnel?days=${period}`, { headers }),
        axios.get(`${API_URL}/api/journey/bottlenecks?days=${period}`, { headers }),
        axios.get(`${API_URL}/api/journey/durations?days=${period}`, { headers }),
      ]);
      setFunnelData(funnelRes.data);
      setBottlenecks(bottlenecksRes.data);
      setDurations(durationsRes.data);
    } catch (err) {
      console.error('Failed to fetch journey data:', err);
      setError(t('adm2_e0eb0ef25b'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [period]);

  const maxFunnelValue = funnelData
    ? Math.max(...STAGE_ORDER.map((stage) => funnelData.funnel[stage] || 0), 1)
    : 1;

  const daysWord = lang === 'uk' ? t('adm2_e85d4cee49') : 'days';

  return (
    <div className="space-y-4 sm:space-y-5" data-testid="journey-page">
      <AdminPageHeader
        icon={BarChart3}
        title={t('journeyFunnelTitle') || t('adm2_a1eb607b82') || 'Journey · Funnel'}
        subtitle={t('journeyFunnelSubtitle') || t('adm2_9ea75dad82')}
        testId="journey-header"
        actions={(
          <>
            <div className="w-[140px] shrink-0">
              <WhiteSelect
                value={period}
                onChange={(e) => setPeriod(Number(e.target.value))}
                data-testid="period-selector"
              >
                <option value={7}>7 {daysWord}</option>
                <option value={30}>30 {daysWord}</option>
                <option value={90}>90 {daysWord}</option>
              </WhiteSelect>
            </div>
            <RefreshButton
              onClick={fetchData}
              loading={loading}
              ariaLabel={lang === 'uk' ? t('adm2_b6bf91f845') : 'Refresh'}
              testId="refresh-btn"
            />
          </>
        )}
      />

      {error && (
        <div className="bg-rose-50 border border-rose-200 text-rose-700 rounded-2xl p-4 text-[13px]">
          {error}
        </div>
      )}

      {/* KPI tiles — 2-up on mobile, 4-up on md+. */}
      {funnelData && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5 sm:gap-3">
          <AdminStat
            label={lang === 'uk' ? t('adm2_84996f1637') : 'Total deals'}
            value={funnelData.totalDeals}
            icon={Users}
          />
          <AdminStat
            label={lang === 'uk' ? t('adm2_f5cce37a63') : 'Delivered'}
            value={funnelData.delivered}
            icon={Target}
            tone="positive"
          />
          <AdminStat
            label={lang === 'uk' ? t('adm2_b7e8aa2f85') : 'Conversion'}
            value={`${funnelData.conversionRate}%`}
            icon={TrendingUp}
          />
          <AdminStat
            label={lang === 'uk' ? t('adm2_417bbb12ec') : 'Period'}
            value={`${period}d`}
            icon={Clock}
          />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-5">
        {/* ── Main funnel ── */}
        <AdminCard className="lg:col-span-2">
          <h2 className="text-[14.5px] font-semibold text-[#18181B] mb-4">
            {lang === 'uk' ? t('adm2_a1eb607b82') : 'Sales Funnel'}
          </h2>

          {loading ? (
            <div className="flex items-center justify-center h-72">
              <RefreshCw className="w-6 h-6 text-[#18181B] animate-spin" />
            </div>
          ) : funnelData ? (
            <div className="space-y-2.5" data-testid="funnel-visualization">
              {STAGE_ORDER.map((stage, idx) => {
                const config = STAGE_CONFIG[stage];
                const value = funnelData.funnel[stage] || 0;
                const percentage = (value / maxFunnelValue) * 100;
                const dropOff = funnelData.dropOff?.find((d) => d.from === stage);

                return (
                  <div key={stage} className="relative">
                    {/* Label row */}
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <span className="text-[12px] text-[#3F3F46] font-medium truncate">
                        {lang === 'uk' ? config.label : config.labelEn}
                      </span>
                      {dropOff && dropOff.rate > 0 && (
                        <span className="inline-flex items-center gap-1 text-[11px] text-rose-600 shrink-0">
                          <TrendingDown className="w-3 h-3" />
                          {dropOff.rate}%
                        </span>
                      )}
                    </div>
                    {/* Bar */}
                    <div className="h-9 bg-[#F4F4F5] rounded-lg overflow-hidden relative">
                      <div
                        className="h-full rounded-lg transition-all duration-500 flex items-center justify-end pr-2.5"
                        style={{
                          width: `${Math.max(percentage, 5)}%`,
                          backgroundColor: config.color,
                        }}
                      >
                        <span className="text-white font-semibold text-[12.5px] tabular-nums">{value}</span>
                      </div>
                    </div>
                    {idx < STAGE_ORDER.length - 1 && (
                      <div className="flex justify-center my-0.5">
                        <ArrowDown className="w-3 h-3 text-[#D4D4D8]" />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-center text-[#71717A] py-12 text-[13px]">
              {lang === 'uk' ? t('adm2_ab301504ad') : 'No data available'}
            </div>
          )}
        </AdminCard>

        {/* ── Right column ── */}
        <div className="space-y-4 sm:space-y-5">
          {/* Bottlenecks */}
          <AdminCard>
            <h3 className="text-[14.5px] font-semibold text-[#18181B] mb-3 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-500" />
              {lang === 'uk' ? t('adm2_b7a51b5fa5') : 'Bottlenecks'}
            </h3>

            {bottlenecks.length > 0 ? (
              <div className="space-y-2" data-testid="bottlenecks-list">
                {bottlenecks.map((bottleneck, idx) => (
                  <div
                    key={idx}
                    className="bg-amber-50/70 rounded-xl p-3 border-l-[3px] border-amber-500"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5 text-[12px] min-w-0 flex-wrap">
                        <span className="text-[#3F3F46] truncate">
                          {lang === 'uk'
                            ? STAGE_CONFIG[bottleneck.from]?.label || bottleneck.from
                            : STAGE_CONFIG[bottleneck.from]?.labelEn || bottleneck.from}
                        </span>
                        <ChevronRight className="w-3.5 h-3.5 text-[#A1A1AA] shrink-0" />
                        <span className="text-[#3F3F46] truncate">
                          {lang === 'uk'
                            ? STAGE_CONFIG[bottleneck.to]?.label || bottleneck.to
                            : STAGE_CONFIG[bottleneck.to]?.labelEn || bottleneck.to}
                        </span>
                      </div>
                      <span className="text-amber-600 font-bold text-[13px] shrink-0 tabular-nums">
                        {bottleneck.rate}%
                      </span>
                    </div>
                    <p className="text-[#71717A] text-[11px] mt-1">
                      {bottleneck.count} {lang === 'uk' ? t('adm2_16ff386eac') : 'dropped'}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[#71717A] text-[12.5px]">
                {lang === 'uk' ? t('adm2_ca211dffd9') : 'No bottlenecks detected'}
              </p>
            )}
          </AdminCard>

          {/* Durations */}
          <AdminCard>
            <h3 className="text-[14.5px] font-semibold text-[#18181B] mb-3 flex items-center gap-2">
              <Clock className="w-4 h-4 text-[#3B82F6]" />
              {lang === 'uk' ? t('adm2_7f869d6855') : 'Average durations'}
            </h3>

            {durations?.averages ? (
              <div className="space-y-1.5" data-testid="durations-list">
                {Object.entries(durations.averages)
                  .filter(([key]) => key !== 'totalJourneyDays')
                  .map(([key, value]) => {
                    const labels = {
                      daysToContact:  { uk: t('adm2_ab3d02bdd5'), en: 'To Contact' },
                      daysToDeal:     { uk: t('adm2_4ef7753310'), en: 'To Deal' },
                      daysToContract: { uk: t('adm2_fd62458163'), en: 'To Contract' },
                      daysToPayment:  { uk: t('adm2_bb331725a4'), en: 'To Payment' },
                      daysToDelivery: { uk: t('adm2_5fb668924c'), en: 'To Delivery' },
                    };
                    const label = labels[key]?.[lang === 'uk' ? 'uk' : 'en'] || key;
                    return (
                      <div
                        key={key}
                        className="flex items-center justify-between py-1.5 border-b border-[#F4F4F5]"
                      >
                        <span className="text-[12px] text-[#52525B]">{label}</span>
                        <span className="text-[12.5px] text-[#18181B] font-medium tabular-nums">
                          {value} {daysWord}
                        </span>
                      </div>
                    );
                  })}
                <div className="flex items-center justify-between pt-3 mt-2 border-t border-[#E4E4E7]">
                  <span className="text-[12.5px] text-[#18181B] font-semibold">
                    {lang === 'uk' ? t('adm2_1169cb90da') : 'Total journey'}
                  </span>
                  <span className="text-[14px] text-[#18181B] font-bold tabular-nums">
                    {durations.averages.totalJourneyDays} {daysWord}
                  </span>
                </div>
                <p className="text-[#A1A1AA] text-[11px] mt-2">
                  {lang === 'uk' ? t('adm2_ed4ce0d0aa') : 'Based on'}{' '}
                  {durations.count} {lang === 'uk' ? t('adm2_619f8896d0') : 'completed deals'}
                </p>
              </div>
            ) : (
              <p className="text-[#71717A] text-[12.5px]">
                {lang === 'uk' ? t('adm2_e776bd6252') : 'Not enough data'}
              </p>
            )}
          </AdminCard>
        </div>
      </div>
    </div>
  );
};

export default JourneyPage;
