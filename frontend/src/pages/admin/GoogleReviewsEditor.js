/**
 * GoogleReviewsEditor — Admin panel for the Google Reviews integration.
 *
 * Hosts:
 *   1. Config form: API key (masked), Place ID, min rating filter,
 *      max reviews to show, fallback rating/count/url, enable toggle,
 *      "Sync now" button.
 *   2. Reviews moderation table: lists all cached reviews (Google +
 *      manually-added), with controls to hide/show, pin/unpin, delete.
 *   3. "Add manual review" form for curated quotes.
 *
 * Wires to:
 *   GET    /api/admin/google-reviews/config
 *   PUT    /api/admin/google-reviews/config
 *   POST   /api/admin/google-reviews/sync
 *   GET    /api/admin/google-reviews
 *   POST   /api/admin/google-reviews/manual
 *   PATCH  /api/admin/google-reviews/{id}
 *   DELETE /api/admin/google-reviews/{id}
 *
 * Uses the existing AdminInfoPage UI primitives (Block, Field) for
 * visual consistency.
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Star,
  ArrowsClockwise,
  CheckCircle,
  EyeSlash,
  Eye,
  Trash,
  Plus,
  PushPin,
  PushPinSimpleSlash,
  Key,
} from '@phosphor-icons/react';
import WhiteSelect from '../../components/ui/WhiteSelect';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// ── Reusable visual primitives — kept here so this file is self-contained
function Block({ title, description, children, footer }) {
  return (
    <div className="bg-white border border-[#E4E4E7] rounded-2xl">
      {(title || description) && (
        <div className="px-5 pt-5 pb-4">
          {title && <h2 className="font-semibold text-[#18181B] text-[15px]">{title}</h2>}
          {description && <p className="text-[12.5px] text-[#71717A] mt-1 leading-relaxed">{description}</p>}
        </div>
      )}
      <div className="px-5 pb-5">{children}</div>
      {footer && (
        <div className="px-5 py-3 border-t border-[#F4F4F5] bg-[#FAFAFA] rounded-b-2xl text-[12px] text-[#71717A]">
          {footer}
        </div>
      )}
    </div>
  );
}

function Field({ label, hint, children }) {
  return (
    <label className="block">
      <div className="text-[12.5px] font-medium text-[#3F3F46] mb-1">{label}</div>
      {children}
      {hint && <div className="text-[11.5px] text-[#A1A1AA] mt-1">{hint}</div>}
    </label>
  );
}

function inputCls() {
  return 'w-full bg-white border border-[#E4E4E7] rounded-lg px-3 py-2 text-[13.5px] text-[#18181B] focus:outline-none focus:ring-2 focus:ring-[#FEAE00]/40';
}

const STAR_ROW = ({ count }) => {
  const n = Math.max(0, Math.min(5, parseInt(count, 10) || 0));
  return (
    <div className="inline-flex items-center gap-0.5 text-[#FEAE00]" data-testid={`stars-${n}`}>
      {Array.from({ length: 5 }).map((_, i) => (
        <Star key={i} size={13} weight={i < n ? 'fill' : 'regular'} />
      ))}
    </div>
  );
};

function getAuthHeaders() {
  // Match the convention used by every other admin page in this repo:
  // the admin auth token is stored under `localStorage.token`. We accept
  // a couple of aliases for forward-compat.
  const t =
    localStorage.getItem('token') ||
    localStorage.getItem('admin_token') ||
    localStorage.getItem('access_token');
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export default function GoogleReviewsEditor() {
  const [config, setConfig] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [savingCfg, setSavingCfg] = useState(false);

  // Manual review form state
  const [manualForm, setManualForm] = useState({
    author_name: '',
    rating: 5,
    text: '',
    text_uk: '',
    language: 'en',
  });

  // ── Load ──
  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [cfgRes, listRes] = await Promise.all([
        axios.get(`${API_URL}/api/admin/google-reviews/config`, { headers: getAuthHeaders() }),
        axios.get(`${API_URL}/api/admin/google-reviews`, { headers: getAuthHeaders() }),
      ]);
      setConfig(cfgRes.data || {});
      setReviews(Array.isArray(listRes.data?.items) ? listRes.data.items : []);
    } catch (e) {
      toast.error('Failed to load Google Reviews data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // ── Config helpers ──
  const updateCfg = (field, value) => {
    setConfig((c) => ({ ...(c || {}), [field]: value }));
  };

  const saveConfig = async (patch = null) => {
    setSavingCfg(true);
    try {
      // Normalise place IDs — accept newline OR comma separated input in the
      // textarea. Trim, drop blanks, dedupe while preserving order.
      const rawIds = Array.isArray(config?.place_ids)
        ? config.place_ids
        : String(config?.place_ids || '').split(/[\n,]/);
      const placeIds = [];
      const seen = new Set();
      for (const raw of rawIds) {
        const p = String(raw || '').trim();
        if (p && !seen.has(p)) { seen.add(p); placeIds.push(p); }
      }
      const body = patch || {
        enabled: !!config?.enabled,
        place_ids: placeIds,
        // Send empty `place_id` to clear the legacy single-place field once
        // multi-place is in use; service tolerates both keys.
        place_id: placeIds.length ? '' : (config?.place_id || ''),
        min_rating_filter: parseInt(config?.min_rating_filter, 10) || 4,
        max_reviews_to_show: parseInt(config?.max_reviews_to_show, 10) || 6,
        auto_sync_enabled: !!config?.auto_sync_enabled,
        sync_interval_hours: parseInt(config?.sync_interval_hours, 10) || 24,
        fallback_rating: parseFloat(config?.fallback_rating) || 0,
        fallback_count: parseInt(config?.fallback_count, 10) || 0,
        fallback_url: config?.fallback_url || '',
      };
      const r = await axios.put(`${API_URL}/api/admin/google-reviews/config`, body, {
        headers: getAuthHeaders(),
      });
      setConfig(r.data || {});
      toast.success('Google Reviews config saved');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to save config');
    } finally {
      setSavingCfg(false);
    }
  };

  const rotateApiKey = async (newKey) => {
    if (!newKey || newKey.length < 8) {
      toast.error('API key looks too short');
      return;
    }
    setSavingCfg(true);
    try {
      const r = await axios.put(
        `${API_URL}/api/admin/google-reviews/config`,
        { api_key: newKey },
        { headers: getAuthHeaders() },
      );
      setConfig(r.data || {});
      toast.success('API key updated');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to save API key');
    } finally {
      setSavingCfg(false);
    }
  };

  // ── Sync ──
  const syncNow = async () => {
    setSyncing(true);
    try {
      const r = await axios.post(`${API_URL}/api/admin/google-reviews/sync`, {}, {
        headers: getAuthHeaders(),
      });
      const d = r.data || {};
      toast.success(
        `Synced — ${d.created || 0} new, ${d.updated || 0} updated (Google rating ${d.google_rating?.toFixed?.(1) || '—'}, count ${d.google_count || 0})`,
      );
      await loadAll();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Sync failed — check API key & Place ID');
    } finally {
      setSyncing(false);
    }
  };

  // ── Per-review mutations ──
  const toggleHidden = async (review) => {
    try {
      const r = await axios.patch(
        `${API_URL}/api/admin/google-reviews/${review.id}`,
        { hidden: !review.hidden },
        { headers: getAuthHeaders() },
      );
      setReviews((rs) => rs.map((x) => (x.id === review.id ? r.data : x)));
    } catch (e) {
      toast.error('Failed to update review');
    }
  };

  const togglePinned = async (review) => {
    try {
      const r = await axios.patch(
        `${API_URL}/api/admin/google-reviews/${review.id}`,
        { pinned: !review.pinned },
        { headers: getAuthHeaders() },
      );
      setReviews((rs) => rs.map((x) => (x.id === review.id ? r.data : x)));
    } catch (e) {
      toast.error('Failed to update review');
    }
  };

  const deleteReview = async (review) => {
    if (!window.confirm(`Delete review by "${review.author_name}"?`)) return;
    try {
      await axios.delete(`${API_URL}/api/admin/google-reviews/${review.id}`, {
        headers: getAuthHeaders(),
      });
      setReviews((rs) => rs.filter((x) => x.id !== review.id));
      toast.success('Review deleted');
    } catch (e) {
      toast.error('Failed to delete');
    }
  };

  const addManual = async () => {
    if (!manualForm.author_name.trim() || !manualForm.text.trim()) {
      toast.error('Name and review text are required');
      return;
    }
    try {
      const r = await axios.post(
        `${API_URL}/api/admin/google-reviews/manual`,
        manualForm,
        { headers: getAuthHeaders() },
      );
      setReviews((rs) => [r.data, ...rs]);
      setManualForm({ author_name: '', rating: 5, text: '', text_uk: '', language: 'en' });
      toast.success('Manual review added');
    } catch (e) {
      toast.error('Failed to add manual review');
    }
  };

  // ── Aggregates (preview what the public block sees) ──
  const visibleForPublic = reviews.filter(
    (r) => !r.hidden && (parseInt(r.rating, 10) || 0) >= (parseInt(config?.min_rating_filter, 10) || 4),
  );
  const allRatings = reviews.filter((r) => !r.hidden && r.rating).map((r) => parseInt(r.rating, 10) || 0);
  const avgRating = allRatings.length
    ? +(allRatings.reduce((a, b) => a + b, 0) / allRatings.length).toFixed(1)
    : (config?.fallback_rating || 0);

  if (loading) {
    return (
      <Block title="Google Reviews">
        <p className="text-[13px] text-[#71717A]">Loading…</p>
      </Block>
    );
  }

  return (
    <div className="space-y-6" data-testid="google-reviews-editor">
      {/* ── Config block ── */}
      <Block
        title="Google Reviews — Configuration"
        description="Enter your Google Places API key and Place ID to pull real reviews. The badge rating and review count are computed from synced reviews so admin moderation is reflected truthfully."
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field
            label="Google Places API Key"
            hint={
              config?.has_api_key
                ? `Saved (preview: ${config.api_key_preview || '—'}). Type a new key + click "Update key" to rotate.`
                : 'Not configured. Create a key at https://console.cloud.google.com → APIs → Places API (New).'
            }
          >
            <div className="flex gap-2">
              <input
                type="password"
                className={inputCls()}
                placeholder={config?.has_api_key ? '••••••• (leave blank to keep current)' : 'AIza…'}
                data-testid="grev-api-key-input"
                onChange={(e) => updateCfg('_pending_api_key', e.target.value)}
              />
              <button
                type="button"
                className="px-3 py-2 bg-[#18181B] text-white rounded-lg text-[12.5px] font-semibold hover:bg-[#3F3F46] disabled:opacity-50 inline-flex items-center gap-1.5"
                onClick={() => {
                  const key = config?._pending_api_key || '';
                  if (key) {
                    rotateApiKey(key);
                    updateCfg('_pending_api_key', '');
                  } else {
                    toast.info('Enter a key first');
                  }
                }}
                disabled={savingCfg}
                data-testid="grev-api-key-save"
              >
                <Key size={14} /> Update key
              </button>
            </div>
          </Field>

          <Field
            label="Place IDs"
            hint='One Place ID per line. Add multiple if your business has more than one location on Google Maps. Find IDs at https://developers.google.com/maps/documentation/places/web-service/place-id'
          >
            <textarea
              className={inputCls() + ' min-h-[88px] py-2 leading-relaxed'}
              value={
                Array.isArray(config?.place_ids)
                  ? config.place_ids.join('\n')
                  : (config?.place_ids || config?.place_id || '')
              }
              onChange={(e) => updateCfg('place_ids', e.target.value.split(/\n+/))}
              placeholder={'ChIJB-guEIiFqkAR8GNK_oYqkVQ\nChIJJcLGTmKDqkARGJsv5IyZEvI'}
              data-testid="grev-place-ids"
              rows={3}
            />
          </Field>

          <Field label="Min rating to display" hint="Reviews with rating below this value are hidden on the public site.">
            <WhiteSelect
              value={config?.min_rating_filter || 4}
              onChange={(e) => updateCfg('min_rating_filter', parseInt(e.target.value, 10))}
              data-testid="grev-min-rating"
            >
              {[1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>{n}+ stars</option>
              ))}
            </WhiteSelect>
          </Field>

          <Field label="Max reviews to show on homepage">
            <input
              type="number"
              min={1}
              max={20}
              className={inputCls()}
              value={config?.max_reviews_to_show || 6}
              onChange={(e) => updateCfg('max_reviews_to_show', parseInt(e.target.value, 10) || 6)}
              data-testid="grev-max-show"
            />
          </Field>

          <Field label="Fallback rating" hint="Used when no reviews are cached yet (bootstrap phase).">
            <input
              type="number"
              min={0}
              max={5}
              step={0.1}
              className={inputCls()}
              value={config?.fallback_rating ?? 4.9}
              onChange={(e) => updateCfg('fallback_rating', parseFloat(e.target.value) || 0)}
              data-testid="grev-fallback-rating"
            />
          </Field>

          <Field label="Fallback total review count">
            <input
              type="number"
              min={0}
              className={inputCls()}
              value={config?.fallback_count ?? 31}
              onChange={(e) => updateCfg('fallback_count', parseInt(e.target.value, 10) || 0)}
              data-testid="grev-fallback-count"
            />
          </Field>

          <Field label='"X Google reviews" link URL' hint="The link that opens when the badge is clicked.">
            <input
              type="url"
              className={inputCls()}
              value={config?.fallback_url || ''}
              onChange={(e) => updateCfg('fallback_url', e.target.value)}
              placeholder="https://www.google.com/maps/place/…"
              data-testid="grev-fallback-url"
            />
          </Field>

          <Field label="Block enabled">
            <WhiteSelect
              value={config?.enabled ? 'true' : 'false'}
              onChange={(e) => updateCfg('enabled', e.target.value === 'true')}
              data-testid="grev-enabled"
            >
              <option value="true">Enabled — show on homepage</option>
              <option value="false">Disabled — hide block</option>
            </WhiteSelect>
          </Field>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => saveConfig()}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-[#FEAE00] text-black rounded-lg text-[13px] font-semibold hover:brightness-95 disabled:opacity-50"
            disabled={savingCfg}
            data-testid="grev-save-config"
          >
            <CheckCircle size={14} /> Save config
          </button>

          <button
            type="button"
            onClick={syncNow}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-[#18181B] text-white rounded-lg text-[13px] font-semibold hover:bg-[#3F3F46] disabled:opacity-50"
            disabled={syncing || !config?.has_api_key || !(config?.place_ids?.length || config?.place_id)}
            data-testid="grev-sync-now"
            title={!config?.has_api_key || !(config?.place_ids?.length || config?.place_id) ? 'API key and at least one Place ID required first' : 'Pull latest reviews from Google'}
          >
            <ArrowsClockwise size={14} className={syncing ? 'animate-spin' : ''} /> Sync now
          </button>

          {config?.last_synced_at && (
            <span className="text-[12px] text-[#71717A]">
              Last sync: {new Date(config.last_synced_at).toLocaleString()}
            </span>
          )}
          {config?.last_sync_error && (
            <span className="text-[12px] text-[#DC2626]" data-testid="grev-last-error">
              ⚠ {config.last_sync_error.slice(0, 120)}
            </span>
          )}
        </div>

        {/* Live aggregate preview */}
        <div className="mt-6 p-4 rounded-lg bg-[#FAFAFA] border border-[#E4E4E7]">
          <div className="text-[12px] uppercase tracking-wider text-[#71717A] mb-2">Public block preview</div>
          <div className="flex items-center gap-4">
            <span className="text-[24px] font-bold text-[#18181B]" data-testid="grev-preview-rating">{avgRating}</span>
            <STAR_ROW count={Math.round(avgRating)} />
            <span className="text-[13px] text-[#3F3F46]" data-testid="grev-preview-count">
              {reviews.filter((r) => !r.hidden).length || config?.fallback_count || 0} Google reviews
            </span>
            <span className="ml-auto text-[12px] text-[#71717A]">
              {visibleForPublic.length} review{visibleForPublic.length === 1 ? '' : 's'} visible on homepage
              (filter: ≥ {config?.min_rating_filter || 4}★)
            </span>
          </div>
        </div>
      </Block>

      {/* ── Add manual review ── */}
      <Block
        title="Add a manual review"
        description="For curated quotes from offline customers. Marked as source=manual and shown alongside Google-synced reviews."
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="Author name">
            <input
              type="text"
              className={inputCls()}
              value={manualForm.author_name}
              onChange={(e) => setManualForm((f) => ({ ...f, author_name: e.target.value }))}
              placeholder="Georgi"
              data-testid="grev-manual-name"
            />
          </Field>
          <Field label="Rating">
            <WhiteSelect
              value={manualForm.rating}
              onChange={(e) => setManualForm((f) => ({ ...f, rating: parseInt(e.target.value, 10) }))}
              data-testid="grev-manual-rating"
            >
              {[5, 4, 3, 2, 1].map((n) => (
                <option key={n} value={n}>{n} stars</option>
              ))}
            </WhiteSelect>
          </Field>
          <Field label="Review text (English)">
            <textarea
              className={inputCls()}
              rows={3}
              value={manualForm.text}
              onChange={(e) => setManualForm((f) => ({ ...f, text: e.target.value }))}
              data-testid="grev-manual-text"
            />
          </Field>
          <Field label="Review text (Ukrainian)">
            <textarea
              className={inputCls()}
              rows={3}
              value={manualForm.text_uk}
              onChange={(e) => setManualForm((f) => ({ ...f, text_uk: e.target.value }))}
              data-testid="grev-manual-text-bg"
            />
          </Field>
        </div>
        <button
          type="button"
          onClick={addManual}
          className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 bg-[#18181B] text-white rounded-lg text-[13px] font-semibold hover:bg-[#3F3F46]"
          data-testid="grev-manual-add"
        >
          <Plus size={14} /> Add review
        </button>
      </Block>

      {/* ── Moderation table ── */}
      <Block
        title={`Reviews moderation (${reviews.length})`}
        description="Hide / show, pin to top, or delete individual reviews. Pinned reviews appear first."
      >
        {reviews.length === 0 ? (
          <p className="text-[13px] text-[#71717A]">
            No reviews yet. Set up the API key & Place ID above, then click "Sync now" — or add a manual review.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="text-left text-[11.5px] uppercase tracking-wider text-[#71717A] border-b border-[#E4E4E7]">
                  <th className="py-2 pr-3">Author</th>
                  <th className="py-2 pr-3">Rating</th>
                  <th className="py-2 pr-3">Source</th>
                  <th className="py-2 pr-3">Text</th>
                  <th className="py-2 pr-3">Date</th>
                  <th className="py-2 pr-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {reviews.map((r) => {
                  const isFiltered =
                    !r.hidden &&
                    (parseInt(r.rating, 10) || 0) < (parseInt(config?.min_rating_filter, 10) || 4);
                  return (
                    <tr
                      key={r.id}
                      className={`border-b border-[#F4F4F5] ${r.hidden ? 'opacity-50' : ''}`}
                      data-testid={`grev-row-${r.id}`}
                    >
                      <td className="py-2 pr-3 font-medium text-[#18181B]">
                        {r.pinned ? <PushPin size={12} className="inline mr-1 text-[#FEAE00]" weight="fill" /> : null}
                        {r.author_name || '—'}
                      </td>
                      <td className="py-2 pr-3"><STAR_ROW count={r.rating} /></td>
                      <td className="py-2 pr-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[11px] font-medium ${
                            r.source === 'manual'
                              ? 'bg-[#FEF3C7] text-[#92400E]'
                              : 'bg-[#DBEAFE] text-[#1E40AF]'
                          }`}
                        >
                          {r.source || 'google'}
                        </span>
                      </td>
                      <td className="py-2 pr-3 max-w-md">
                        <p className="text-[#3F3F46] truncate" title={r.text}>{r.text || '—'}</p>
                        {isFiltered && (
                          <p className="text-[11px] text-[#DC2626]">Below display filter (won't show on homepage)</p>
                        )}
                      </td>
                      <td className="py-2 pr-3 text-[#71717A] whitespace-nowrap">
                        {r.time ? new Date(r.time).toLocaleDateString() : '—'}
                      </td>
                      <td className="py-2 pr-3 text-right whitespace-nowrap">
                        <div className="inline-flex items-center gap-1">
                          <button
                            type="button"
                            onClick={() => togglePinned(r)}
                            className="p-1.5 rounded hover:bg-[#F4F4F5] text-[#71717A]"
                            title={r.pinned ? 'Unpin' : 'Pin to top'}
                            data-testid={`grev-pin-${r.id}`}
                          >
                            {r.pinned ? <PushPinSimpleSlash size={14} /> : <PushPin size={14} />}
                          </button>
                          <button
                            type="button"
                            onClick={() => toggleHidden(r)}
                            className="p-1.5 rounded hover:bg-[#F4F4F5] text-[#71717A]"
                            title={r.hidden ? 'Show' : 'Hide'}
                            data-testid={`grev-toggle-${r.id}`}
                          >
                            {r.hidden ? <Eye size={14} /> : <EyeSlash size={14} />}
                          </button>
                          <button
                            type="button"
                            onClick={() => deleteReview(r)}
                            className="p-1.5 rounded hover:bg-[#FEE2E2] text-[#DC2626]"
                            title="Delete"
                            data-testid={`grev-delete-${r.id}`}
                          >
                            <Trash size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Block>
    </div>
  );
}
