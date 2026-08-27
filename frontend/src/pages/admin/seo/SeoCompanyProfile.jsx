/**
 * SeoCompanyProfile — E-E-A-T company facts that feed Organization,
 * LocalBusiness and ContactPoint JSON-LD.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { Buildings, Certificate, MapPin, Phone } from '@phosphor-icons/react';
import { seoApi } from './seoApi';
import { Card, CardHeader, CardBody, Field, Input, Textarea, DirtyBar, Skeleton } from './_shared';

const FIELDS = [
  'legal_name', 'company_name', 'edrpou',
  'license_number', 'license_name', 'license_issued_at', 'license_issued_by', 'founding_date',
  'company_street', 'company_city', 'company_region', 'company_postal', 'company_country',
  'company_lat', 'company_lng',
  'company_phones', 'company_email', 'opening_hours', 'price_range',
  'same_as', 'company_description',
];

const SeoCompanyProfile = () => {
  const [data,    setData]    = useState(null);
  const [draft,   setDraft]   = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving,  setSaving]  = useState(false);

  const load = useCallback(async () => {
    try {
      const j = await seoApi.getCompany();
      setData(j);
      setDraft(j.company);
    } catch (e) { toast.error(`Завантаження: ${e.message}`); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const dirty = useMemo(
    () => draft && data && JSON.stringify(draft) !== JSON.stringify(data.company),
    [draft, data]
  );
  const set = (k, v) => setDraft(d => ({ ...d, [k]: v }));

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    try {
      const body = {};
      FIELDS.forEach(k => { body[k] = draft[k] || ''; });
      const j = await seoApi.putCompany(body);
      setData({ company: j.company });
      setDraft(j.company);
      toast.success('Компанія (E-E-A-T) збережена');
    } catch (e) { toast.error(e.message); }
    finally { setSaving(false); }
  };

  if (loading || !draft) return <Skeleton />;

  return (
    <div data-testid="seo-company-tab">
      <DirtyBar
        dirty={dirty} saving={saving}
        onSave={save} onDiscard={() => setDraft(data.company)}
      />

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader
            title="Юридична особа"
            subtitle="Формує Organization schema."
            icon={Buildings}
          />
          <CardBody className="grid grid-cols-2 gap-3">
            <Field label="Коротка/брендова назва">
              <Input value={draft.company_name || ''} onChange={e => set('company_name', e.target.value)} placeholder="ECO.NOVA" />
            </Field>
            <Field label="Юридична назва">
              <Input value={draft.legal_name || ''} onChange={e => set('legal_name', e.target.value)} placeholder="ТОВ «ЕКО-НОВА»" />
            </Field>
            <Field label="ЄДРПОУ">
              <Input value={draft.edrpou || ''} onChange={e => set('edrpou', e.target.value)} placeholder="12345678" data-testid="company-edrpou" />
            </Field>
            <Field label="Дата заснування" hint="YYYY, YYYY-MM або YYYY-MM-DD">
              <Input value={draft.founding_date || ''} onChange={e => set('founding_date', e.target.value)} placeholder="2010-01-15" />
            </Field>
            <Field className="col-span-2" label="Опис компанії" hint="До 600 символів. Використовується в Organization.description та фолбек-meta.">
              <Textarea value={draft.company_description || ''} onChange={e => set('company_description', e.target.value)} />
            </Field>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Ліцензія на поводження з відходами"
            subtitle="E-E-A-T-підтвердження: ліцензійний статус виводиться в футері та JSON-LD."
            icon={Certificate}
          />
          <CardBody className="grid grid-cols-2 gap-3">
            <Field label="№ ліцензії">
              <Input value={draft.license_number || ''} onChange={e => set('license_number', e.target.value)} data-testid="company-license" />
            </Field>
            <Field label="Назва ліцензії">
              <Input value={draft.license_name || ''} onChange={e => set('license_name', e.target.value)} placeholder="Ліцензія на поводження з небезп. відходами" />
            </Field>
            <Field label="Дата видачі" hint="YYYY-MM-DD">
              <Input value={draft.license_issued_at || ''} onChange={e => set('license_issued_at', e.target.value)} />
            </Field>
            <Field label="Ким видана">
              <Input value={draft.license_issued_by || ''} onChange={e => set('license_issued_by', e.target.value)} placeholder="Міндовкілля України" />
            </Field>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Адреса та геолокація"
            subtitle="Формує PostalAddress + GeoCoordinates."
            icon={MapPin}
          />
          <CardBody className="grid grid-cols-2 gap-3">
            <Field className="col-span-2" label="Вулиця, буд.">
              <Input value={draft.company_street || ''} onChange={e => set('company_street', e.target.value)} />
            </Field>
            <Field label="Місто">
              <Input value={draft.company_city || ''} onChange={e => set('company_city', e.target.value)} />
            </Field>
            <Field label="Область/регіон">
              <Input value={draft.company_region || ''} onChange={e => set('company_region', e.target.value)} />
            </Field>
            <Field label="Поштовий індекс">
              <Input value={draft.company_postal || ''} onChange={e => set('company_postal', e.target.value)} />
            </Field>
            <Field label="Країна (Код ISO)">
              <Input value={draft.company_country || 'UA'} onChange={e => set('company_country', e.target.value)} placeholder="UA" />
            </Field>
            <Field label="Latitude" hint="-90..90">
              <Input value={draft.company_lat || ''} onChange={e => set('company_lat', e.target.value)} placeholder="50.4501" />
            </Field>
            <Field label="Longitude" hint="-180..180">
              <Input value={draft.company_lng || ''} onChange={e => set('company_lng', e.target.value)} placeholder="30.5234" />
            </Field>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Контакти та соціальні мережі"
            subtitle="Формує ContactPoint + sameAs. Телефони через кому, sameAs — один URL на рядок."
            icon={Phone}
          />
          <CardBody className="grid grid-cols-2 gap-3">
            <Field className="col-span-2" label="Телефони">
              <Input value={draft.company_phones || ''} onChange={e => set('company_phones', e.target.value)} placeholder="+380 44 333 44 55, +380 67 111 22 33" />
            </Field>
            <Field label="Email">
              <Input value={draft.company_email || ''} onChange={e => set('company_email', e.target.value)} placeholder="info@example.ua" />
            </Field>
            <Field label="Графік роботи">
              <Input value={draft.opening_hours || ''} onChange={e => set('opening_hours', e.target.value)} placeholder="Mo-Fr 09:00-18:00" />
            </Field>
            <Field label="Ціновий діапазон" hint="№, €–€€€, №№№, – для LocalBusiness.">
              <Input value={draft.price_range || ''} onChange={e => set('price_range', e.target.value)} placeholder="₴₴–₴₴₴" />
            </Field>
            <Field className="col-span-2" label="sameAs (один URL на рядок)">
              <Textarea rows={4} value={draft.same_as || ''} onChange={e => set('same_as', e.target.value)} placeholder={'https://www.linkedin.com/company/eco-nova\nhttps://www.facebook.com/econova'} />
            </Field>
          </CardBody>
        </Card>
      </div>
    </div>
  );
};

export default SeoCompanyProfile;
