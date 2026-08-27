/**
 * BlogArticlesEditor — bilingual CMS for the /blog page.
 *
 * Embedded inside AdminInfoPage under the “Content → Blog Articles” tab.
 *
 * Capabilities
 * ────────────
 *  • List all articles (filter by category, search by title).
 *  • Create / edit articles with:
 *      – category (1 of 6 predefined slugs)
 *      – cover image upload (saved to /api/static/blog/…)
 *      – bilingual title + excerpt + body (UA + EN language tabs)
 *      – full rich text editor (react-quill-new) for body
 *        with bold / italic / underline / lists / links / images
 *        / blockquote / code / headings / colors / alignment
 *      – up to 5 recommendation (related) articles (multi-select)
 *      – publish toggle (drafts vs live)
 *  • Read time is auto-computed on the backend (200 words / minute).
 *  • Delete with confirmation.
 *
 * All endpoints under /api/admin/blog/* require admin or master_admin role.
 */
import React, { useEffect, useMemo, useState, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import RichTextEditor from '../../components/admin/blog/RichTextEditor';
import WhiteDatePicker from '../../components/ui/WhiteDatePicker';
import { useLang } from '../../i18n';
import {
  Plus, Trash, FloppyDisk, ArrowsClockwise, PencilSimple, UploadSimple,
  Eye, EyeSlash, CheckCircle, MagnifyingGlass, X, Globe, Image as ImageIcon,
  Tag as TagIcon, Calendar,
} from '@phosphor-icons/react';
import WhiteSelect from '../../components/ui/WhiteSelect';
import RefreshButton from '../../components/ui/RefreshButton';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const CATEGORIES = [
  { value: 'news',       label: 'Новини'              },
  { value: 'regulation', label: 'Регулювання'         },
  { value: 'guides',     label: 'Гайди / інструкції'  },
  { value: 'cases',      label: 'Кейси'               },
  { value: 'ecology',    label: 'Екологія'            },
  { value: 'industry',   label: 'Галузь'              },
];

const LANGS = [
  { code: 'uk', label: 'Українська (основна)' },
  { code: 'en', label: 'English (alternate)' },
];

// Auth headers
function authHeaders() {
  const token = localStorage.getItem('eco_token')
    || localStorage.getItem('token')
    || localStorage.getItem('access_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// Empty article scaffold
function emptyArticle() {
  return {
    id: '',
    slug: '',
    category: 'news',
    cover_image_url: '',
    title:   { uk: '', en: '' },
    excerpt: { uk: '', en: '' },
    body:    { uk: '', en: '' },
    tags: [],
    related_ids: [],
    read_time_minutes: 1,
    published: false,
    published_at: '',
  };
}

const inputCls =
  'w-full bg-white border border-[#E4E4E7] rounded-md px-3 py-2 text-sm ' +
  'text-[#18181B] placeholder-[#A1A1AA] focus:outline-none focus:border-amber-500';

const labelCls = 'text-xs uppercase tracking-wide text-[#71717A] mb-1 block';

// ─────────────────────────────────────────────────────────────────────────
//  Main component
// ─────────────────────────────────────────────────────────────────────────
export default function BlogArticlesEditor() {
  const { t } = useLang();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState({ category: 'all', q: '' });
  const [editing, setEditing] = useState(null); // article in edit modal
  const [deleting, setDeleting] = useState(null); // article in delete confirm

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (filter.category !== 'all') params.category = filter.category;
      if (filter.q.trim()) params.q = filter.q.trim();
      const { data } = await axios.get(`${API_URL}/api/admin/blog/articles`, {
        params,
        headers: authHeaders(),
      });
      setItems(data.items || []);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to load articles');
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => setEditing(emptyArticle());
  const openEdit = (a) => setEditing({ ...emptyArticle(), ...a });
  const closeEditor = () => setEditing(null);

  const remove = async () => {
    if (!deleting?.id) return;
    try {
      await axios.delete(`${API_URL}/api/admin/blog/articles/${deleting.id}`, {
        headers: authHeaders(),
      });
      toast.success(t('adm_article_deleted'));
      setDeleting(null);
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to delete');
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-3">
          <div className="min-w-0">
            <h2 className="text-lg font-semibold text-[#18181B]">Blog Articles (CMS)</h2>
            <p className="text-sm text-[#71717A] mt-1 break-words">
              Create bilingual (UA + EN) articles for the public&nbsp;
              <code className="text-[#18181B] bg-[#FAFAFA] px-1 py-0.5 rounded">/blog</code> page. Read time is calculated
              automatically (200 words&nbsp;/&nbsp;minute).
            </p>
          </div>
          <button
            onClick={openCreate}
            data-testid="blog-new-btn"
            className="inline-flex items-center justify-center gap-2 px-4 h-10 rounded-xl bg-[#18181B] text-white text-sm font-semibold hover:bg-[#27272A] active:bg-black transition focus:outline-none focus-visible:ring-4 focus-visible:ring-black/15 whitespace-nowrap"
          >
            <Plus size={16} weight="bold" />{t('newArticleAction')}</button>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-end gap-3 pt-3 border-t border-[#E4E4E7]">
          <div className="min-w-[160px]">
            <label className={labelCls}>{t('category')}</label>
            <WhiteSelect
              value={filter.category}
              onChange={(e) => setFilter((f) => ({ ...f, category: e.target.value }))}
              data-testid="blog-filter-category"
            >
              <option value="all">{t('allCategories')}</option>
              {CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </WhiteSelect>
          </div>
          <div className="flex-1 min-w-[200px]">
            <label className={labelCls}>{t('search')}</label>
            <div className="relative">
              <MagnifyingGlass size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#A1A1AA]" />
              <input
                value={filter.q}
                onChange={(e) => setFilter((f) => ({ ...f, q: e.target.value }))}
                placeholder={t('adm_search_by_title')}
                className={`${inputCls} pl-9`}
                data-testid="blog-filter-search"
              />
            </div>
          </div>
          <RefreshButton
            onClick={load}
            loading={loading}
            ariaLabel={t('reloadAction')}
            testId="blog-reload-btn"
            title={t('reloadAction')}
          />
        </div>
      </div>

      {/* Articles list */}
      <div className="bg-white border border-[#E4E4E7] rounded-2xl overflow-hidden">
        {loading ? (
          <div className="py-12 text-center text-[#A1A1AA] text-sm">{t('adm_loading')}</div>
        ) : items.length === 0 ? (
          <div className="py-12 text-center text-[#A1A1AA] text-sm">
            No articles yet. Click&nbsp;<span className="text-[#18181B] font-medium">{t('newArticleAction')}</span>&nbsp;to start.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-[#FAFAFA] border-b border-[#E4E4E7] text-[#71717A] uppercase text-xs tracking-wide">
              <tr>
                <th className="text-left px-4 py-3 font-medium">{t('taskTitle')}</th>
                <th className="text-left px-4 py-3 font-medium">{t('category')}</th>
                <th className="text-left px-4 py-3 font-medium">{t('readFilter')}</th>
                <th className="text-left px-4 py-3 font-medium">{t('publishedStatus')}</th>
                <th className="text-left px-4 py-3 font-medium">{t('createdOn')}</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {items.map((a) => (
                <tr key={a.id} className="border-b border-[#E4E4E7] last:border-0 hover:bg-[#FAFAFA]">
                  <td className="px-4 py-3">
                    <div className="text-[#18181B] font-medium">{a.title?.uk || a.title?.en || '(untitled)'}</div>
                    {a.title?.uk && a.title?.en && (
                      <div className="text-xs text-[#A1A1AA] mt-0.5">{a.title.en}</div>
                    )}
                    <div className="text-xs text-[#A1A1AA] mt-0.5">/{a.slug}</div>
                  </td>
                  <td className="px-4 py-3 text-[#52525B]">
                    {CATEGORIES.find((c) => c.value === a.category)?.label || a.category}
                  </td>
                  <td className="px-4 py-3 text-[#71717A]">{a.read_time_minutes} min</td>
                  <td className="px-4 py-3">
                    {a.published ? (
                      <span className="inline-flex items-center gap-1 text-emerald-600 text-xs">
                        <CheckCircle size={14} weight="fill" /> {t('adm_live')}
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-[#A1A1AA] text-xs">
                        <EyeSlash size={14} /> {t('adm_draft')}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-[#A1A1AA] text-xs">
                    {a.created_at ? new Date(a.created_at).toLocaleDateString() : ''}
                  </td>
                  <td className="px-4 py-3 text-right whitespace-nowrap">
                    <button
                      onClick={() => openEdit(a)}
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md bg-[#FAFAFA] hover:bg-[#FAFAFA] text-[#18181B] text-xs mr-2"
                      data-testid={`blog-edit-${a.id}`}
                    >
                      <PencilSimple size={12} /> {t('adm_edit')}
                    </button>
                    <button
                      onClick={() => setDeleting(a)}
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-xs"
                      data-testid={`blog-delete-${a.id}`}
                    >
                      <Trash size={12} /> {t('adm_delete')}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Editor modal */}
      {editing && (
        <ArticleEditorModal
          initial={editing}
          allItems={items}
          onClose={closeEditor}
          onSaved={() => { closeEditor(); load(); }}
        />
      )}

      {/* Delete confirm */}
      {deleting && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
          <div className="bg-white border border-[#E4E4E7] rounded-lg p-6 max-w-sm w-full">
            <h3 className="text-lg font-semibold text-[#18181B] mb-2">{t('deleteArticleQuestion')}</h3>
            <p className="text-sm text-[#71717A] mb-5">
              «{deleting.title?.en || deleting.title?.uk || deleting.slug}» — this action cannot be undone.
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setDeleting(null)} className="px-4 py-2 rounded-md bg-[#FAFAFA] hover:bg-[#FAFAFA] text-[#18181B] text-sm">
                {t('cancelAction')}
              </button>
              <button onClick={remove} className="px-4 py-2 rounded-md bg-rose-600 hover:bg-rose-500 text-white text-sm font-semibold" data-testid="blog-delete-confirm">
                {t('deleteAction')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
//  Editor modal (create / edit)
// ─────────────────────────────────────────────────────────────────────────
function ArticleEditorModal({ initial, allItems, onClose, onSaved }) {
  const { t } = useLang();
  const [form, setForm] = useState(initial);
  const [activeLang, setActiveLang] = useState('uk');
  const [saving, setSaving] = useState(false);
  const [uploadingImg, setUploadingImg] = useState(false);

  const isNew = !form.id;

  const set = (path, value) => {
    setForm((f) => {
      const next = { ...f };
      if (Array.isArray(path)) {
        let ref = next;
        for (let i = 0; i < path.length - 1; i++) {
          ref[path[i]] = { ...(ref[path[i]] || {}) };
          ref = ref[path[i]];
        }
        ref[path[path.length - 1]] = value;
      } else {
        next[path] = value;
      }
      return next;
    });
  };

  const uploadCover = async (file) => {
    if (!file) return;
    setUploadingImg(true);
    try {
      const fd = new FormData();
      fd.append('image', file);
      const { data } = await axios.post(`${API_URL}/api/admin/blog/upload-image`, fd, {
        headers: { ...authHeaders(), 'Content-Type': 'multipart/form-data' },
      });
      set('cover_image_url', data.url);
      toast.success(t('adm_image_uploaded'));
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Image upload failed');
    } finally {
      setUploadingImg(false);
    }
  };

  const save = async (publish = null) => {
    setSaving(true);
    try {
      const payload = {
        category: form.category,
        cover_image_url: form.cover_image_url || '',
        title: form.title,
        excerpt: form.excerpt,
        body: form.body,
        tags: form.tags || [],
        related_ids: form.related_ids || [],
        published: publish === null ? form.published : publish,
      };
      if (form.slug) payload.slug = form.slug;
      if (form.published_at) payload.published_at = form.published_at;

      let saved;
      if (isNew) {
        const r = await axios.post(`${API_URL}/api/admin/blog/articles`, payload, { headers: authHeaders() });
        saved = r.data;
        toast.success(t('adm_article_created'));
      } else {
        const r = await axios.put(`${API_URL}/api/admin/blog/articles/${form.id}`, payload, { headers: authHeaders() });
        saved = r.data;
        toast.success(t('adm_article_saved'));
      }
      onSaved(saved);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const relatedOptions = useMemo(() => {
    return (allItems || []).filter((a) => a.id !== form.id);
  }, [allItems, form.id]);

  const toggleRelated = (id) => {
    set('related_ids', (form.related_ids || []).includes(id)
      ? (form.related_ids || []).filter((x) => x !== id)
      : [...(form.related_ids || []), id].slice(0, 5));
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-stretch justify-center overflow-y-auto py-6">
      <div className="bg-white border border-[#E4E4E7] rounded-lg max-w-5xl w-full mx-4 flex flex-col">
        {/* header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#E4E4E7]">
          <h2 className="text-lg font-semibold text-[#18181B]">
            {isNew ? 'New article' : 'Edit article'}
          </h2>
          <button onClick={onClose} className="text-[#71717A] hover:text-[#18181B]" data-testid="blog-modal-close">
            <X size={22} />
          </button>
        </div>

        {/* body */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          {/* Meta row */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className={labelCls}>{t('category')}</label>
              <WhiteSelect
                value={form.category}
                onChange={(e) => set('category', e.target.value)}
                data-testid="blog-form-category"
              >
                {CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </WhiteSelect>
            </div>
            <div>
              <label className={labelCls}>Slug (URL)</label>
              <input
                value={form.slug || ''}
                onChange={(e) => set('slug', e.target.value)}
                placeholder="auto-from-title-en"
                className={inputCls}
                data-testid="blog-form-slug"
              />
            </div>
            <div>
              <label className={labelCls}>{t('readTime')}</label>
              <div className="px-3 py-2 text-sm text-[#52525B] bg-white border border-[#E4E4E7] rounded-md">
                {form.read_time_minutes || 1} min&nbsp;<span className="text-[#A1A1AA]">(auto)</span>
              </div>
            </div>
          </div>

          {/* Cover image */}
          <div>
            <label className={labelCls}>Cover image (recommended 513×424 or any 16:13)</label>
            <div className="flex items-start gap-4">
              <div className="w-48 h-40 rounded-md border border-[#E4E4E7] bg-[#FAFAFA] overflow-hidden flex items-center justify-center text-[#A1A1AA]">
                {form.cover_image_url ? (
                  <img src={`${API_URL}${form.cover_image_url}`} alt="" className="w-full h-full object-cover" />
                ) : (
                  <ImageIcon size={32} />
                )}
              </div>
              <div className="flex-1 space-y-2">
                <label className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-[#E4E4E7] bg-white hover:bg-[#FAFAFA] text-[#18181B] text-sm cursor-pointer transition-colors" data-testid="blog-form-upload-label">
                  <UploadSimple size={14} />
                  {uploadingImg ? 'Uploading…' : 'Upload image'}
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp,image/gif"
                    className="hidden"
                    onChange={(e) => uploadCover(e.target.files?.[0])}
                    data-testid="blog-form-upload-input"
                  />
                </label>
                {form.cover_image_url && (
                  <button
                    onClick={() => set('cover_image_url', '')}
                    className="ml-2 inline-flex items-center gap-1 px-3 py-2 rounded-md bg-rose-50 hover:bg-rose-100 text-rose-700 text-xs border border-rose-200"
                  >
                    <Trash size={12} /> {t('adm_remove')}
                  </button>
                )}
                <p className="text-xs text-[#A1A1AA]">{t('adm_jpg_png_webp_or_gif_max_8_mb')}</p>
              </div>
            </div>
          </div>

          {/* Language tabs */}
          <div>
            <div className="flex items-center gap-2 border-b border-[#E4E4E7] mb-3">
              {LANGS.map((l) => (
                <button
                  key={l.code}
                  onClick={() => setActiveLang(l.code)}
                  className={
                    'px-4 py-2 text-sm font-medium border-b-2 -mb-px transition ' +
                    (activeLang === l.code
                      ? 'border-amber-500 text-amber-500'
                      : 'border-transparent text-[#71717A] hover:text-[#18181B]')
                  }
                  data-testid={`blog-lang-${l.code}`}
                >
                  <Globe size={14} className="inline mr-1.5" />
                  {l.label}
                </button>
              ))}
            </div>

            <div className="space-y-4">
              <div>
                <label className={labelCls}>Title ({activeLang.toUpperCase()})</label>
                <input
                  value={form.title?.[activeLang] || ''}
                  onChange={(e) => set(['title', activeLang], e.target.value)}
                  placeholder={activeLang === 'uk' ? 'Напр.: «Новий закон про відходи 2026»…' : 'e.g. "EU Waste Directive 2026"…'}
                  className={inputCls}
                  data-testid={`blog-form-title-${activeLang}`}
                />
              </div>
              <div>
                <label className={labelCls}>Short excerpt ({activeLang.toUpperCase()}) — shown on the blog list</label>
                <textarea
                  rows={3}
                  value={form.excerpt?.[activeLang] || ''}
                  onChange={(e) => set(['excerpt', activeLang], e.target.value)}
                  placeholder={t('adm_a_12_sentence_preview_shown_on_the_public_blog_lis')}
                  className={inputCls}
                  data-testid={`blog-form-excerpt-${activeLang}`}
                />
              </div>
              <div>
                <label className={labelCls}>Full body ({activeLang.toUpperCase()}) — rich text</label>
                <div data-testid={`blog-form-body-${activeLang}`}>
                  <RichTextEditor
                    value={form.body?.[activeLang] || ''}
                    onChange={(v) => set(['body', activeLang], v)}
                    placeholder={
                      activeLang === 'uk'
                        ? 'Напишіть статтю українською…'
                        : 'Write the article in English…'
                    }
                    testId={`blog-form-rte-${activeLang}`}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Tags + Publish date */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className={labelCls}>
                <TagIcon size={12} className="inline mr-1" />
                Tags (Enter to add, max 12)
              </label>
              <TagsInput
                value={form.tags || []}
                onChange={(v) => set('tags', v)}
              />
            </div>
            <div>
              <label className={labelCls}>
                <Calendar size={12} className="inline mr-1" />
                Publish date (overrides auto)
              </label>
              <WhiteDatePicker
                value={(form.published_at || '').slice(0, 10)}
                onChange={(e) => set('published_at', e.target.value)}
                data-testid="blog-form-published-at"
              />
            </div>
          </div>

          {/* Related articles */}
          <div>
            <label className={labelCls}>Related articles (up to 5)</label>
            {relatedOptions.length === 0 ? (
              <p className="text-xs text-[#A1A1AA]">{t('noOtherArticles')}</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-44 overflow-y-auto pr-2">
                {relatedOptions.map((r) => {
                  const sel = (form.related_ids || []).includes(r.id);
                  return (
                    <label key={r.id} className={
                      'flex items-center gap-2 px-3 py-2 rounded-md cursor-pointer border text-sm ' +
                      (sel
                        ? 'bg-amber-50 border-amber-400 text-amber-700'
                        : 'bg-white border-[#E4E4E7] text-[#52525B] hover:border-[#E4E4E7]')
                    }>
                      <input
                        type="checkbox"
                        checked={sel}
                        onChange={() => toggleRelated(r.id)}
                        className="accent-amber-500"
                      />
                      <span className="truncate">{r.title?.en || r.title?.uk || r.slug}</span>
                    </label>
                  );
                })}
              </div>
            )}
          </div>

          {/* Publish toggle */}
          <div className="flex items-center gap-3 pt-3 border-t border-[#E4E4E7]">
            <button
              onClick={() => set('published', !form.published)}
              className={
                'inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm font-semibold transition ' +
                (form.published
                  ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
                  : 'bg-[#FAFAFA] hover:bg-[#FAFAFA] text-[#18181B]')
              }
              data-testid="blog-form-publish-toggle"
            >
              {form.published ? <Eye size={14} /> : <EyeSlash size={14} />}
              {form.published ? 'Published (live)' : 'Draft (hidden)'}
            </button>
            <span className="text-xs text-[#A1A1AA]">
              {t('adm_drafts_are_not_visible_on_the_public_blog_page')}
            </span>
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 px-6 py-4 border-t border-[#E4E4E7] bg-white">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-md bg-[#FAFAFA] hover:bg-[#FAFAFA] text-[#18181B] text-sm"
            disabled={saving}
          >
            {t('cancelAction')}
          </button>
          <button
            onClick={() => save()}
            disabled={saving}
            className="inline-flex items-center gap-2 px-5 py-2 rounded-md bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-black text-sm font-semibold"
            data-testid="blog-form-save"
          >
            <FloppyDisk size={14} />
            {saving ? 'Saving…' : (isNew ? 'Create article' : 'Save changes')}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
//  Tags input — chip-style, free-form (max 12, dedup case-insensitive)
// ─────────────────────────────────────────────────────────────────────────
function TagsInput({ value, onChange }) {
  const { t } = useLang();
  const [input, setInput] = useState('');
  const tags = Array.isArray(value) ? value : [];

  const addTag = (raw) => {
    const t = (raw || '').trim().slice(0, 40);
    if (!t) return;
    const lower = t.toLowerCase();
    if (tags.some((x) => x.toLowerCase() === lower)) return;
    if (tags.length >= 12) return;
    onChange([...tags, t]);
  };
  const removeTag = (idx) => {
    onChange(tags.filter((_, i) => i !== idx));
  };

  const onKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addTag(input);
      setInput('');
    } else if (e.key === 'Backspace' && input === '' && tags.length > 0) {
      removeTag(tags.length - 1);
    }
  };
  const onPaste = (e) => {
    const txt = e.clipboardData?.getData('text');
    if (txt && /[,\n]/.test(txt)) {
      e.preventDefault();
      txt.split(/[,\n]/).map((x) => x.trim()).filter(Boolean).forEach(addTag);
      setInput('');
    }
  };

  return (
    <div
      className="flex flex-wrap items-center gap-2 bg-white border border-[#E4E4E7] rounded-lg px-2 py-2 min-h-[40px] focus-within:border-[#18181B] focus-within:ring-2 focus-within:ring-[#18181B]/10 transition-all"
      data-testid="blog-form-tags"
    >
      {tags.map((t, i) => (
        <span
          key={`${t}-${i}`}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-50 border border-amber-300 text-amber-700 text-xs"
          data-testid={`blog-form-tag-chip-${i}`}
        >
          {t}
          <button
            type="button"
            onClick={() => removeTag(i)}
            className="text-amber-600 hover:text-amber-800"
            aria-label={`Remove ${t}`}
          >
            <X size={10} weight="bold" />
          </button>
        </span>
      ))}
      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={onKeyDown}
        onPaste={onPaste}
        onBlur={() => { if (input) { addTag(input); setInput(''); } }}
        placeholder={tags.length === 0 ? 'утилізація, небезпечні відходи, ліцензія…' : ''}
        className="flex-1 min-w-[120px] bg-transparent outline-none border-0 px-1 py-0 text-sm text-[#18181B] placeholder-[#A1A1AA]"
        data-testid="blog-form-tag-input"
      />
    </div>
  );
}
