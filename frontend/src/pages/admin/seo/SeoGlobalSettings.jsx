/**
 * SeoGlobalSettings — domain, environment, canonical, indexing master switch,
 * default title/desc/OG, AI-crawler block.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { Globe, Robot, ShieldCheck, Image as ImageIcon } from '@phosphor-icons/react';
import { seoApi } from './seoApi';
import { Card, CardHeader, CardBody, Field, Input, Textarea, Select, Toggle, DirtyBar, Skeleton } from './_shared';

const SeoGlobalSettings = () => {
  const [data,    setData]    = useState(null);
  const [draft,   setDraft]   = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving,  setSaving]  = useState(false);

  const load = useCallback(async () => {
    try {
      const j = await seoApi.getSettings();
      setData(j);
      setDraft(j.settings);
    } catch (e) { toast.error(`Завантаження: ${e.message}`); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const dirty = useMemo(
    () => draft && data && JSON.stringify(draft) !== JSON.stringify(data.settings),
    [draft, data]
  );
  const set = (k, v) => setDraft(d => ({ ...d, [k]: v }));

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    try {
      // Only send the fields this tab owns.
      const body = {
        public_origin:                 draft.public_origin || '',
        seo_environment:               draft.seo_environment || 'auto',
        allow_indexing_in_production:  !!draft.allow_indexing_in_production,
        canonical_strategy:            draft.canonical_strategy || 'origin',
        default_language:              draft.default_language || 'uk',
        enabled_languages:             draft.enabled_languages || 'uk,en',
        site_name:                     draft.site_name || '',
        default_title:                 draft.default_title || '',
        default_description:           draft.default_description || '',
        default_keywords:              draft.default_keywords || '',
        default_og_image:              draft.default_og_image || '',
        block_ai_crawlers:             !!draft.block_ai_crawlers,
      };
      const j = await seoApi.patchSettings(body);
      setData({ ...data, settings: j.settings });
      setDraft(j.settings);
      toast.success('Глобальні SEO-налаштування збережено');
    } catch (e) { toast.error(e.message); }
    finally { setSaving(false); }
  };

  if (loading || !draft) return <Skeleton />;

  return (
    <div data-testid="seo-settings-tab">
      <DirtyBar
        dirty={dirty} saving={saving}
        onSave={save} onDiscard={() => setDraft(data.settings)}
        savedAt={data?.settings?.updated_at} updatedBy={data?.settings?.updated_by}
      />

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader
            title="Домен та середовище"
            subtitle="Керує canonical, sitemap, robots і origin в базах JSON-LD."
            icon={Globe}
          />
          <CardBody className="space-y-4">
            <Field
              label="Публічний origin"
              hint="Повний URL production-домену (напр. https://eco-nova.ua). Порожнє → використовується env або Host запиту."
            >
              <Input
                value={draft.public_origin || ''}
                onChange={(e) => set('public_origin', e.target.value)}
                placeholder="https://example.com"
                data-testid="seo-input-origin"
              />
            </Field>
            <Field label="Середовище" hint="auto — визначається автоматично по host'у. Інше — свідома примусова мітка.">
              <Select
                value={draft.seo_environment || 'auto'}
                onChange={(e) => set('seo_environment', e.target.value)}
                data-testid="seo-input-env"
              >
                <option value="auto">auto (авто-визначення)</option>
                <option value="production">production</option>
                <option value="preview">preview</option>
                <option value="stage">stage</option>
                <option value="test">test</option>
                <option value="dev">dev</option>
              </Select>
            </Field>
            <Field label="Canonical стратегія" hint="origin — завжди адмін-домен; request — з запиту; admin_override — лише вручну в per-page.">
              <Select
                value={draft.canonical_strategy || 'origin'}
                onChange={(e) => set('canonical_strategy', e.target.value)}
              >
                <option value="origin">origin (рекомендовано)</option>
                <option value="request">request host</option>
                <option value="admin_override">admin_override</option>
              </Select>
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Мова за замовчування">
                <Select
                  value={draft.default_language || 'uk'}
                  onChange={(e) => set('default_language', e.target.value)}
                >
                  <option value="uk">Українська (uk)</option>
                  <option value="en">English (en)</option>
                </Select>
              </Field>
              <Field label="Мови (через кому)">
                <Input
                  value={draft.enabled_languages || 'uk,en'}
                  onChange={(e) => set('enabled_languages', e.target.value)}
                  placeholder="uk,en"
                />
              </Field>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Індексація"
            subtitle="Майстер-вимикач: без цього Google не займе production‑домен в індекс."
            icon={ShieldCheck}
          />
          <CardBody className="space-y-4">
            <Toggle
              checked={!!draft.allow_indexing_in_production}
              onChange={(v) => set('allow_indexing_in_production', v)}
              label="Дозволити індексацію в production"
              hint="Поки вимкнено, robots.txt віддає Disallow: / для всіх ботів, навіть на production‑домені."
              dataTestid="seo-toggle-indexing"
            />
            <Toggle
              checked={!!draft.block_ai_crawlers}
              onChange={(v) => set('block_ai_crawlers', v)}
              label="Блокувати AI-кравлери"
              hint="Додає Disallow: / для GPTBot, ClaudeBot, CCBot, Google-Extended, Perplexity, Bytespider та інших."
              dataTestid="seo-toggle-ai"
            />
          </CardBody>
        </Card>

        <Card className="md:col-span-2">
          <CardHeader
            title="Сайт-ідентичність"
            subtitle="Фолбек-теги для сторінок без власних override’ів."
            icon={ImageIcon}
          />
          <CardBody className="grid gap-4 md:grid-cols-2">
            <Field label="Назва сайту">
              <Input
                value={draft.site_name || ''}
                onChange={(e) => set('site_name', e.target.value)}
                placeholder="ECO.NOVA"
              />
            </Field>
            <Field label="OG image за замовчування" hint="Повний URL або шлях від /. Рекомендовано 1200×630 PNG/JPG.">
              <Input
                value={draft.default_og_image || ''}
                onChange={(e) => set('default_og_image', e.target.value)}
                placeholder="/og-image.png"
              />
            </Field>
            <Field className="md:col-span-2" label="Шаблон Title" hint="Відображається як fallback, коли per-page не вказано.">
              <Input
                value={draft.default_title || ''}
                onChange={(e) => set('default_title', e.target.value)}
                placeholder="ECO.NOVA — Утилізація небезпечних відходів"
              />
            </Field>
            <Field className="md:col-span-2" label="Description за замовчування">
              <Textarea
                value={draft.default_description || ''}
                onChange={(e) => set('default_description', e.target.value)}
                placeholder="Стислий опис для соціальних мереж…"
              />
            </Field>
            <Field className="md:col-span-2" label="Keywords" hint="Через кому. Пошуковики ігнорують meta keywords, але це залишається для внутрішніх класифікаторів.">
              <Input
                value={draft.default_keywords || ''}
                onChange={(e) => set('default_keywords', e.target.value)}
                placeholder="..."
              />
            </Field>
          </CardBody>
        </Card>
      </div>
    </div>
  );
};

export default SeoGlobalSettings;
