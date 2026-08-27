/**
 * SeoPrerender — Phase C admin panel for the bot-facing prerender pipeline.
 *
 * Shows: metrics (renders, cache hits, per-route hits, bot hits), route
 * allow-list, bot directory, and gives the admin two actions:
 *   • Warm cache  — pre-render every static route in UK+EN.
 *   • Purge cache — drop the Mongo cache (memory is dropped automatically
 *                   on the next admin SEO write).
 * Also provides a preview modal that renders the actual HTML a bot would
 * see for any static route.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import {
  Robot, ArrowsClockwise, Trash, Eye, ChartLineUp, MagnifyingGlass, Path,
} from '@phosphor-icons/react';
import { seoApi, BACKEND_URL } from './seoApi';
import { Card, CardHeader, CardBody, Button, Skeleton } from './_shared';

// Extend the existing api helper (kept local to this tab so we don't inflate
// the shared module for a Phase-C-only feature).
const preApi = {
  metrics: () => fetch(`${BACKEND_URL}/api/prerender/admin/metrics`, {
    headers: { Authorization: `Bearer ${localStorage.getItem('eco_token') || ''}` }
  }).then(r => r.json()),
  routes: () => fetch(`${BACKEND_URL}/api/prerender/admin/routes`, {
    headers: { Authorization: `Bearer ${localStorage.getItem('eco_token') || ''}` }
  }).then(r => r.json()),
  warm: () => fetch(`${BACKEND_URL}/api/prerender/admin/warm?langs=uk,en`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${localStorage.getItem('eco_token') || ''}` }
  }).then(r => r.json()),
  purge: () => fetch(`${BACKEND_URL}/api/prerender/admin/purge`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${localStorage.getItem('eco_token') || ''}` }
  }).then(r => r.json()),
  health: () => fetch(`${BACKEND_URL}/api/prerender/health`).then(r => r.json()),
  renderText: (path, lang) => fetch(`${BACKEND_URL}/api/prerender/render?path=${encodeURIComponent(path)}&lang=${lang}`, {
    headers: { 'User-Agent': 'Googlebot/2.1 (admin preview)' }
  }).then(r => r.text()),
};

const StatTile = ({ label, value, hint }) => (
  <div className="rounded-xl border border-[#E4E4E7] bg-white p-4">
    <div className="text-[11px] font-medium text-[#71717A] uppercase tracking-wider">{label}</div>
    <div className="text-[22px] font-semibold text-[#18181B] mt-1 tabular-nums">{value ?? '—'}</div>
    {hint ? <div className="text-[11px] text-[#71717A] mt-1 leading-snug">{hint}</div> : null}
  </div>
);

const SeoPrerender = () => {
  const [metrics, setMetrics]   = useState(null);
  const [routes, setRoutes]     = useState(null);
  const [loading, setLoading]   = useState(true);
  const [busy, setBusy]         = useState(false);
  const [preview, setPreview]   = useState(null);   // { path, lang, html }
  const [previewLoading, setPreviewLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [m, r] = await Promise.all([preApi.metrics(), preApi.routes()]);
      setMetrics(m);
      setRoutes(r);
    } catch (e) { toast.error(`Завантаження: ${e.message}`); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const warm = async () => {
    setBusy(true);
    try {
      const j = await preApi.warm();
      toast.success(`Прогріто ${j.warmed}/${j.total} маршрутів`);
      load();
    } catch (e) { toast.error(e.message); }
    finally { setBusy(false); }
  };

  const purge = async () => {
    if (!window.confirm('Скинути весь Mongo-кеш prerender? Наступні запити ботів перегенерують HTML.')) return;
    setBusy(true);
    try {
      const j = await preApi.purge();
      toast.success(`Видалено ${j.mongo_deleted} записів`);
      load();
    } catch (e) { toast.error(e.message); }
    finally { setBusy(false); }
  };

  const openPreview = async (path, lang = 'uk') => {
    setPreview({ path, lang, html: '' });
    setPreviewLoading(true);
    try {
      const html = await preApi.renderText(path, lang);
      setPreview({ path, lang, html });
    } catch (e) { toast.error(e.message); }
    finally { setPreviewLoading(false); }
  };

  if (loading) return <Skeleton />;

  const m = metrics?.metrics || {};
  const bots = metrics?.bots_directory || [];
  const perRoute = Object.entries(m.per_route || {}).sort((a, b) => (b[1]?.hits || 0) - (a[1]?.hits || 0));
  const botHits  = Object.entries(m.bot_hits || {}).sort((a, b) => b[1] - a[1]);

  return (
    <div data-testid="seo-prerender-tab" className="space-y-5">
      {/* Actions */}
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="primary" onClick={warm} disabled={busy} data-testid="prerender-warm">
          <ArrowsClockwise size={13} weight="bold" className={busy ? 'animate-spin' : ''} />
          {busy ? 'Обробка…' : 'Прогріти кеш (uk+en)'}
        </Button>
        <Button variant="danger" onClick={purge} disabled={busy}>
          <Trash size={13} /> Очистити Mongo-кеш
        </Button>
        <div className="ml-auto text-[11.5px] text-[#71717A]">
          Останній рендер: <b className="text-[#18181B]">{m.last_render_at ? new Date(m.last_render_at).toLocaleString() : '—'}</b>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <StatTile label="Рендерів" value={m.renders || 0} hint="Всього генерацій HTML" />
        <StatTile label="Кеш · memory" value={m.cache_hits_mem || 0} hint="Хіти in-process (TTL 5хв)" />
        <StatTile label="Кеш · Mongo" value={m.cache_hits_db || 0} hint="Хіти persistent (TTL 24г)" />
        <StatTile label="Проміси" value={m.cache_misses || 0} hint="Свіжі генерації" />
        <StatTile label="Записів в пам'яті" value={m.cache_entries_memory || 0} hint="Активний in-memory кеш" />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {/* Route allow-list */}
        <Card>
          <CardHeader
            title="Маршрути, що пререндеряться"
            subtitle="Тільки ці шляхи видадуть боту повний HTML. Все інше під /app, /admin, /client, /api — 403."
            icon={Path}
          />
          <CardBody className="space-y-3">
            <div>
              <div className="text-[11.5px] font-medium text-[#71717A] mb-1">Статичні</div>
              <div className="flex flex-wrap gap-1.5">
                {(routes?.static || []).map(p => (
                  <button
                    key={p}
                    onClick={() => openPreview(p, 'uk')}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md border border-[#E4E4E7] hover:bg-[#F4F4F5] font-mono text-[11.5px] text-[#18181B]"
                    data-testid={`prerender-preview-${p.replace(/\//g, '_') || 'root'}`}
                    title="Переглянути prerender для цього маршруту"
                  >
                    <Eye size={10} /> {p}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <div className="text-[11.5px] font-medium text-[#71717A] mb-1">Динамічні</div>
              <div className="flex flex-wrap gap-1.5">
                {(routes?.dynamic || []).map(d => (
                  <button
                    key={d.pattern}
                    onClick={() => openPreview(d.example, 'uk')}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md border border-[#E4E4E7] hover:bg-[#F4F4F5] font-mono text-[11.5px] text-[#18181B]"
                    title={`Приклад: ${d.example}`}
                  >
                    <Eye size={10} /> {d.pattern}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <div className="text-[11.5px] font-medium text-[#71717A] mb-1">Приватні префікси (403)</div>
              <div className="flex flex-wrap gap-1.5">
                {(routes?.private_prefixes || []).map(p => (
                  <span key={p} className="font-mono text-[11.5px] text-rose-700 bg-rose-50 border border-rose-200 px-1.5 py-0.5 rounded">{p}</span>
                ))}
              </div>
            </div>
          </CardBody>
        </Card>

        {/* Per-route hits */}
        <Card>
          <CardHeader title="Топ маршрутів за кількістю рендерів" icon={ChartLineUp} />
          <CardBody>
            {perRoute.length === 0 ? (
              <div className="text-[12px] text-[#71717A]">Поки що немає жодного рендеру.</div>
            ) : (
              <table className="w-full text-[12px]">
                <thead className="text-[#71717A]"><tr>
                  <th className="text-left py-1.5 font-medium">Path</th>
                  <th className="text-right py-1.5 font-medium">Hits</th>
                  <th className="text-right py-1.5 font-medium">Останній</th>
                </tr></thead>
                <tbody>
                  {perRoute.slice(0, 20).map(([path, r]) => (
                    <tr key={path} className="border-t border-[#F4F4F5]">
                      <td className="py-1.5 font-mono text-[11.5px]">{path}</td>
                      <td className="py-1.5 text-right tabular-nums">{r.hits}</td>
                      <td className="py-1.5 text-right text-[11px] text-[#71717A]">{r.last ? new Date(r.last).toLocaleTimeString() : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardBody>
        </Card>

        {/* Bot hits + directory */}
        <Card>
          <CardHeader title="Активні боти (за хітами)" icon={Robot} />
          <CardBody>
            {botHits.length === 0 ? (
              <div className="text-[12px] text-[#71717A]">Поки що не було візитів ботів через /api/prerender/render.</div>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {botHits.map(([name, hits]) => (
                  <span key={name} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-50 border border-emerald-200 text-emerald-800 text-[11.5px]">
                    {name}: <b className="tabular-nums">{hits}</b>
                  </span>
                ))}
              </div>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title={`Довідник ботів (${bots.length})`}
            subtitle="Whitelist для is_bot() — застосовується як serving-hint. Спуфінг UA не небезпечний (бот отримує ту саму сторінку, що й людина)."
            icon={MagnifyingGlass}
          />
          <CardBody>
            <div className="max-h-64 overflow-y-auto">
              <table className="w-full text-[11.5px]">
                <thead className="text-[#71717A] sticky top-0 bg-white"><tr>
                  <th className="text-left py-1 font-medium">Name</th>
                  <th className="text-left py-1 font-medium">Category</th>
                </tr></thead>
                <tbody>
                  {bots.map(b => (
                    <tr key={b.name} className="border-t border-[#F4F4F5]">
                      <td className="py-1 font-medium">{b.name}</td>
                      <td className="py-1 text-[#71717A]">{b.category}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardBody>
        </Card>
      </div>

      {/* Preview modal */}
      {preview ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" onClick={() => setPreview(null)}>
          <div className="w-full max-w-5xl bg-white rounded-2xl border border-[#E4E4E7] max-h-[90vh] overflow-hidden flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="px-5 py-3 border-b border-[#E4E4E7] flex items-center gap-3">
              <Robot size={16} weight="bold" className="text-[#3F3F46]" />
              <div className="text-[14px] font-semibold text-[#18181B] flex-1 font-mono">
                {preview.path} · {preview.lang}
              </div>
              <select value={preview.lang} onChange={e => openPreview(preview.path, e.target.value)} className="h-8 px-2 rounded-lg border border-[#E4E4E7] text-[12px]">
                <option value="uk">uk</option>
                <option value="en">en</option>
              </select>
              <button onClick={() => setPreview(null)} className="text-[13px] text-[#71717A] hover:text-[#18181B] px-2">Закрити</button>
            </div>
            <div className="flex-1 overflow-auto p-5 bg-[#FAFAFA]">
              {previewLoading ? <div className="text-[13px] text-[#71717A]">Рендер…</div> : (
                <pre className="text-[11px] leading-relaxed text-[#18181B] font-mono whitespace-pre-wrap">{preview.html || '(порожньо)'}</pre>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default SeoPrerender;
