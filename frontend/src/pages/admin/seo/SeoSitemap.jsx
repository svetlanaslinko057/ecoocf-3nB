/**
 * SeoSitemap — preview, url count, included/excluded routes, regenerate.
 * Sitemap content itself is generated live by the engine; «regenerate»
 * simply invalidates cache + updates "last generated" timestamp.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import { MapTrifold, ArrowsClockwise, Eye, LinkSimple } from '@phosphor-icons/react';
import { seoApi } from './seoApi';
import { Card, CardHeader, CardBody, Button, Skeleton, CopyBtn } from './_shared';

const SeoSitemap = () => {
  const [state, setState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [regenerating, setRegenerating] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(null); // 'index' | 'pages' | ...
  const [previewXml, setPreviewXml] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const j = await seoApi.getSitemap();
      setState(j.sitemap);
    } catch (e) { toast.error(e.message); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const regen = async () => {
    setRegenerating(true);
    try {
      const j = await seoApi.regenerateSitemap();
      toast.success(`Кеш sitemap оновлено (${new Date(j.regenerated_at).toLocaleTimeString()})`);
      load();
    } catch (e) { toast.error(e.message); }
    finally { setRegenerating(false); }
  };

  const openPreview = async (kind) => {
    setPreviewOpen(kind);
    setPreviewXml('');
    setPreviewLoading(true);
    try {
      const t = await seoApi.previewSitemap(kind);
      setPreviewXml(t);
    } catch (e) { toast.error(e.message); }
    finally { setPreviewLoading(false); }
  };

  if (loading || !state) return <Skeleton />;

  return (
    <div data-testid="seo-sitemap-tab">
      <div className="grid gap-4 md:grid-cols-3">
        <Card className="md:col-span-2">
          <CardHeader
            title={`Sitemap Index (${state.url_count} URL в pages)`}
            subtitle="Каталог відходів та блог генеруються динамічно (коди відходів та опубліковані статті)."
            icon={MapTrifold}
            right={
              <Button variant="primary" onClick={regen} disabled={regenerating} data-testid="seo-sitemap-regen">
                <ArrowsClockwise size={13} weight="bold" className={regenerating ? 'animate-spin' : ''} />
                {regenerating ? 'Скидаю…' : 'Оновити кеш'}
              </Button>
            }
          />
          <CardBody className="space-y-3">
            <div className="flex items-center gap-2 text-[12.5px] text-[#3F3F46]">
              <LinkSimple size={13} className="text-[#71717A]" />
              <a href={state.sitemap_index_url} target="_blank" rel="noreferrer" className="underline hover:text-emerald-700 font-mono text-[12px]">{state.sitemap_index_url}</a>
              <CopyBtn value={state.sitemap_index_url} />
            </div>
            <div className="grid gap-2">
              {state.typed_sitemaps.map(s => (
                <div key={s.name} className="flex items-center gap-2 text-[12px]">
                  <span className="inline-block w-14 text-[11.5px] font-medium text-[#71717A]">{s.name}</span>
                  <a href={s.url} target="_blank" rel="noreferrer" className="font-mono text-[12px] text-[#3F3F46] hover:text-emerald-700 underline flex-1 truncate">{s.url}</a>
                  <Button size="sm" variant="secondary" onClick={() => openPreview(s.name)}><Eye size={11} /> Переглянути</Button>
                </div>
              ))}
              <div className="flex items-center gap-2 text-[12px] pt-1 border-t border-[#F4F4F5]">
                <span className="inline-block w-14 text-[11.5px] font-medium text-[#71717A]">index</span>
                <Button size="sm" variant="secondary" onClick={() => openPreview('index')}><Eye size={11} /> XML індексу</Button>
              </div>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title={`Включені (${(state.urls_included || []).length})`} icon={MapTrifold} />
          <div className="max-h-[400px] overflow-y-auto">
            <table className="w-full text-[12px]">
              <thead className="text-[#71717A] sticky top-0 bg-white">
                <tr className="text-left">
                  <th className="px-3 py-2">Path</th>
                  <th className="px-3 py-2">Freq</th>
                  <th className="px-3 py-2">Pri</th>
                </tr>
              </thead>
              <tbody>
                {(state.urls_included || []).map(r => (
                  <tr key={r.path} className="border-t border-[#F4F4F5]">
                    <td className="px-3 py-1.5 font-mono text-[11.5px]">{r.path}</td>
                    <td className="px-3 py-1.5 text-[#71717A]">{r.changefreq}</td>
                    <td className="px-3 py-1.5 text-[#71717A]">{r.priority}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        {(state.urls_excluded || []).length > 0 ? (
          <Card className="md:col-span-3">
            <CardHeader title={`Виключені з sitemap (${state.urls_excluded.length})`} icon={MapTrifold} />
            <CardBody className="flex flex-wrap gap-2">
              {state.urls_excluded.map(r => (
                <span key={r.path} className="font-mono text-[11.5px] text-rose-700 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded">{r.path}</span>
              ))}
            </CardBody>
          </Card>
        ) : null}
      </div>

      {previewOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" onClick={() => setPreviewOpen(null)}>
          <div className="w-full max-w-4xl bg-white rounded-2xl border border-[#E4E4E7] max-h-[85vh] overflow-hidden flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="px-5 py-3 border-b border-[#E4E4E7] flex items-center gap-3">
              <MapTrifold size={16} weight="bold" className="text-[#3F3F46]" />
              <div className="text-[14px] font-semibold text-[#18181B] flex-1">Preview: sitemap-{previewOpen}.xml</div>
              <button onClick={() => setPreviewOpen(null)} className="text-[13px] text-[#71717A] hover:text-[#18181B]">Закрити</button>
            </div>
            <div className="flex-1 overflow-auto p-5">
              {previewLoading ? <div className="text-[13px] text-[#71717A]">Завантаження…</div> : (
                <pre className="text-[11.5px] leading-relaxed text-[#18181B] font-mono whitespace-pre-wrap">{previewXml}</pre>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default SeoSitemap;
