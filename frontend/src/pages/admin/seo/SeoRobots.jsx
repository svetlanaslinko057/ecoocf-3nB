/**
 * SeoRobots — manage indexing mode, disallow/allow paths, sitemap URL,
 * custom lines. Live preview of the robots.txt that would be served.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { Robot, Eye } from '@phosphor-icons/react';
import { seoApi } from './seoApi';
import { Card, CardHeader, CardBody, Field, Input, Textarea, Select, DirtyBar, Skeleton } from './_shared';

const asLines = (val) => Array.isArray(val) ? val.join('\n') : (val || '');

const SeoRobots = () => {
  const [data,    setData]    = useState(null);
  const [draft,   setDraft]   = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving,  setSaving]  = useState(false);
  const [preview, setPreview] = useState('');
  const [pvLoading, setPvLoading] = useState(false);

  const load = useCallback(async () => {
    try {
      const j = await seoApi.getRobots();
      const r = {
        ...j.robots,
        disallow: asLines(j.robots?.disallow),
        allow:    asLines(j.robots?.allow),
      };
      setData({ robots: r, context: j.context });
      setDraft(r);
    } catch (e) { toast.error(`Завантаження: ${e.message}`); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const dirty = useMemo(() => draft && data && JSON.stringify(draft) !== JSON.stringify(data.robots), [draft, data]);
  const set = (k, v) => setDraft(d => ({ ...d, [k]: v }));

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    try {
      const body = {
        mode: draft.mode || 'auto',
        disallow: (draft.disallow || '').split(/[\n,]/).map(s => s.trim()).filter(Boolean),
        allow:    (draft.allow    || '').split(/[\n,]/).map(s => s.trim()).filter(Boolean),
        sitemap_url:  draft.sitemap_url || '',
        custom_lines: draft.custom_lines || '',
      };
      const j = await seoApi.putRobots(body);
      const r = {
        ...j.robots,
        disallow: asLines(j.robots?.disallow),
        allow:    asLines(j.robots?.allow),
      };
      setData(d => ({ ...d, robots: r }));
      setDraft(r);
      toast.success('Robots збережено');
    } catch (e) { toast.error(e.message); }
    finally { setSaving(false); }
  };

  const doPreview = async () => {
    setPvLoading(true);
    try {
      const t = await seoApi.previewRobots();
      setPreview(t);
    } catch (e) { toast.error(e.message); }
    finally { setPvLoading(false); }
  };
  useEffect(() => { if (data) doPreview(); }, [data]); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading || !draft) return <Skeleton />;

  const env = data?.context?.environment || 'auto';
  const indexingAllowed = !!data?.context?.indexing_enabled;
  const origin = data?.context?.public_origin || '';

  return (
    <div data-testid="seo-robots-tab">
      <DirtyBar dirty={dirty} saving={saving} onSave={save} onDiscard={() => setDraft(data.robots)} />

      {/* Status banner */}
      <div className={`mb-4 rounded-xl border px-4 py-3 text-[12.5px] ${indexingAllowed && env === 'production' ? 'border-emerald-200 bg-emerald-50 text-emerald-900' : 'border-amber-200 bg-amber-50 text-amber-900'}`}>
        <b>Поточний стан:</b> середовище <code>{env}</code>{origin ? <> · origin <code>{origin}</code></> : null} · індексація <b>{indexingAllowed ? 'дозволена' : 'вимкнена'}</b>.
        {' '}Майстер-вимикач «Дозволити індексацію в production» — в глобальних налаштуваннях.
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader title="Режим robots.txt" subtitle="Повний контроль над тим, що отримують боти." icon={Robot} />
          <CardBody className="space-y-3">
            <Field label="Режим" hint="auto — за середовищем + майстер-вимикачем. index/noindex — примусово.">
              <Select value={draft.mode || 'auto'} onChange={e => set('mode', e.target.value)} data-testid="seo-robots-mode">
                <option value="auto">auto</option>
                <option value="index">index (примусово дозволити)</option>
                <option value="noindex">noindex (примусово Disallow: /)</option>
              </Select>
            </Field>
            <Field label="Sitemap URL" hint="Порожнє = origin+/sitemap.xml. Повний URL або /shared/path.">
              <Input value={draft.sitemap_url || ''} onChange={e => set('sitemap_url', e.target.value)} placeholder="https://example.com/sitemap.xml" />
            </Field>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Кастомні рядки (додати вкінці)" icon={Robot} />
          <CardBody>
            <Textarea rows={5} value={draft.custom_lines || ''} onChange={e => set('custom_lines', e.target.value)} placeholder={'# Extra rules\nUser-agent: SomeBot\nDisallow: /private'} />
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Disallow (один шлях на рядок)" icon={Robot} />
          <CardBody>
            <Textarea rows={8} value={draft.disallow || ''} onChange={e => set('disallow', e.target.value)} placeholder={'/app\n/admin\n/client\n/api/\n/contract/'} />
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Allow (один шлях на рядок)" icon={Robot} />
          <CardBody>
            <Textarea rows={8} value={draft.allow || ''} onChange={e => set('allow', e.target.value)} placeholder={'/$\n/waste\n/calculator\n/contacts\n/blog'} />
          </CardBody>
        </Card>

        <Card className="md:col-span-2">
          <CardHeader
            title="Live-прев'ю robots.txt"
            subtitle="Станом на останнє збереження. Натисніть Переглянути, щоб оновити."
            icon={Eye}
            right={<button type="button" onClick={doPreview} className="text-[12px] text-emerald-700 hover:text-emerald-800 inline-flex items-center gap-1"><Eye size={11} weight="bold" /> Переглянути</button>}
          />
          <CardBody>
            {pvLoading ? <div className="text-[12px] text-[#71717A]">Завантаження…</div> : (
              <pre className="text-[11.5px] leading-relaxed text-[#18181B] font-mono whitespace-pre-wrap bg-[#FAFAFA] rounded-lg p-3 border border-[#E4E4E7] max-h-[420px] overflow-auto">{preview || '# (no preview yet)'}</pre>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
};

export default SeoRobots;
