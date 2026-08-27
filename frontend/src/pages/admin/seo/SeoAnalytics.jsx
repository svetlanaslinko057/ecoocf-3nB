/**
 * SeoAnalytics — GA4, GTM, Google Ads, Facebook Pixel, LinkedIn Insight,
 * search-console verifications and IndexNow key. Every field takes effect on
 * the next page load (frontend reads /api/seo/runtime-config).
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { ChartLineUp, Funnel, ShieldCheck, LinkSimple } from '@phosphor-icons/react';
import { seoApi } from './seoApi';
import { Card, CardHeader, CardBody, Field, Input, DirtyBar, Skeleton } from './_shared';

const normLabels = (labels = {}) => ({
  lead_submit:     labels.lead_submit     || '',
  calc_used:       labels.calc_used       || '',
  contract_signed: labels.contract_signed || '',
});

const SeoAnalytics = () => {
  const [data,    setData]    = useState(null);
  const [draft,   setDraft]   = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving,  setSaving]  = useState(false);

  const load = useCallback(async () => {
    try {
      const j = await seoApi.getAnalytics();
      const a = { ...j.analytics, google_ads_conversion_labels: normLabels(j.analytics?.google_ads_conversion_labels) };
      setData({ analytics: a });
      setDraft(a);
    } catch (e) { toast.error(`Завантаження: ${e.message}`); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const dirty = useMemo(
    () => draft && data && JSON.stringify(draft) !== JSON.stringify(data.analytics),
    [draft, data]
  );
  const set = (k, v) => setDraft(d => ({ ...d, [k]: v }));
  const setLabel = (k, v) => setDraft(d => ({ ...d, google_ads_conversion_labels: { ...(d.google_ads_conversion_labels || {}), [k]: v } }));

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    try {
      const j = await seoApi.putAnalytics(draft);
      const a = { ...j.analytics, google_ads_conversion_labels: normLabels(j.analytics?.google_ads_conversion_labels) };
      setData({ analytics: a });
      setDraft(a);
      toast.success('Аналітика збережена — без редеплою');
    } catch (e) { toast.error(e.message); }
    finally { setSaving(false); }
  };

  if (loading || !draft) return <Skeleton />;

  return (
    <div data-testid="seo-analytics-tab">
      <DirtyBar dirty={dirty} saving={saving} onSave={save} onDiscard={() => setDraft(data.analytics)} />

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader
            title="Google Analytics та Tag Manager"
            subtitle="Майже завжди вводте ОДИН з них: GA4 або GTM — котрий веде облік."
            icon={ChartLineUp}
          />
          <CardBody className="space-y-4">
            <Field label="GA4 Measurement ID" hint="G-XXXXXXXXXX — в Analytics: Admin → Data Streams.">
              <Input value={draft.ga4_measurement_id || ''} onChange={e => set('ga4_measurement_id', e.target.value)} placeholder="G-XXXXXXXXXX" data-testid="seo-input-ga4" />
            </Field>
            <Field label="GTM Container ID" hint="GTM-XXXXXXX. Прибирайте GA4, якщо GA4 вже є у GTM.">
              <Input value={draft.gtm_container_id || ''} onChange={e => set('gtm_container_id', e.target.value)} placeholder="GTM-XXXXXXX" data-testid="seo-input-gtm" />
            </Field>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Google Ads — конверсії"
            subtitle="AW‑ID + label’и по ключових діях. Порожнє поле — подія не надсилається."
            icon={Funnel}
          />
          <CardBody className="space-y-3">
            <Field label="Google Ads Conversion ID" hint="AW-XXXXXXXXX (9–10 цифр).">
              <Input value={draft.google_ads_conversion_id || ''} onChange={e => set('google_ads_conversion_id', e.target.value)} placeholder="AW-XXXXXXXXX" />
            </Field>
            <Field label="Label — lead_submit">
              <Input value={draft.google_ads_conversion_labels?.lead_submit || ''} onChange={e => setLabel('lead_submit', e.target.value)} placeholder="AbCd_EfGhIj-1234" />
            </Field>
            <Field label="Label — calc_used">
              <Input value={draft.google_ads_conversion_labels?.calc_used || ''} onChange={e => setLabel('calc_used', e.target.value)} />
            </Field>
            <Field label="Label — contract_signed">
              <Input value={draft.google_ads_conversion_labels?.contract_signed || ''} onChange={e => setLabel('contract_signed', e.target.value)} />
            </Field>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Соціальні пікселі"
            subtitle="Залиште порожнім, якщо не використовуєте цей канал."
            icon={LinkSimple}
          />
          <CardBody className="space-y-3">
            <Field label="Meta / Facebook Pixel ID" hint="8–20 цифр.">
              <Input value={draft.facebook_pixel_id || ''} onChange={e => set('facebook_pixel_id', e.target.value)} />
            </Field>
            <Field label="LinkedIn Insight Tag ID" hint="4–15 цифр.">
              <Input value={draft.linkedin_insight_id || ''} onChange={e => set('linkedin_insight_id', e.target.value)} />
            </Field>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Верифікації пошуковиків та IndexNow"
            subtitle="Можна вставляти чистий токен або цілий <meta content=…> — автовитягнемо content."
            icon={ShieldCheck}
          />
          <CardBody className="space-y-3">
            <Field label="Google Search Console verification">
              <Input value={draft.google_site_verification || ''} onChange={e => set('google_site_verification', e.target.value)} placeholder="AbCd…" data-testid="seo-input-gsc" />
            </Field>
            <Field label="Bing Webmaster verification">
              <Input value={draft.bing_site_verification || ''} onChange={e => set('bing_site_verification', e.target.value)} />
            </Field>
            <Field label="Yandex verification">
              <Input value={draft.yandex_site_verification || ''} onChange={e => set('yandex_site_verification', e.target.value)} />
            </Field>
            <Field label="IndexNow key" hint="Авто-пінг в IndexNow після оновлення контенту.">
              <Input value={draft.indexnow_key || ''} onChange={e => set('indexnow_key', e.target.value)} />
            </Field>
          </CardBody>
        </Card>
      </div>
    </div>
  );
};

export default SeoAnalytics;
