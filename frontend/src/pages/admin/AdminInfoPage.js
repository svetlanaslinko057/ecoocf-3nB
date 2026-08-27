/**
 * AdminInfoPage — site-wide info / legal / content editor (grouped layout).
 *
 * Структура (sidebar з групами замість пласких табів):
 *   ┌─ Legal & Privacy ──────┐
 *   │  • Privacy Policy      │  ← rich text UA+EN (same logic for all 4)
 *   │  • Terms of Use        │
 *   │  • Cookie Policy       │
 *   │  • Conditions          │
 *   │  • Cookie Banner       │  (consent banner copy + toggle)
 *   ├─ Content ──────────────┤
 *   │  • FAQ                 │  Q&A accordion editor
 *   │  • Reviews             │  ← NEW: testimonials with image upload
 *   ├─ Layout ───────────────┤
 *   │  • Header              │  phones + CTA
 *   │  • Footer              │  contacts, socials, Viber community
 *   └────────────────────────┘
 *
 * API:
 *   GET  /api/site-info                              public
 *   PUT  /api/admin/site-info                        admin/master_admin
 *   POST /api/admin/site-info/upload-review-image    admin/master_admin
 */
import React, { useEffect, useState, useMemo, useRef, useCallback } from 'react';
import axios from 'axios';
import { useParams, useLocation } from 'react-router-dom';
import { toast } from 'sonner';
import ReactQuill from 'react-quill-new';
import 'react-quill-new/dist/quill.snow.css';
import GoogleReviewsEditor from './GoogleReviewsEditor';
import RefreshButton from '../../components/ui/RefreshButton';
import { useLang } from '../../i18n';
import {
  ShieldCheck,
  FileText,
  Cookie,
  ListChecks,
  PhoneCall,
  Globe,
  FloppyDisk,
  ArrowsClockwise,
  CheckCircle,
  Question,
  Plus,
  Trash,
  ArrowUp,
  ArrowDown,
  EyeSlash,
  Eye,
  Star,
  ChatCircle,
  Image as ImageIcon,
  UploadSimple,
  User,
  Megaphone,
  Newspaper,
  PencilSimple,
  CaretDown,
  Check,
  Handshake,
  LinkSimple,
  Certificate,
} from '@phosphor-icons/react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// ─────────────────────────────────────────────────────────────────────────
//  Sidebar configuration — groups of related pages
// ─────────────────────────────────────────────────────────────────────────
const NAV_GROUPS = [
  {
    id: 'legal',
    label: 'Legal & Privacy',
    items: [
      { id: 'privacy',       label: 'Privacy Policy', icon: ShieldCheck },
      { id: 'terms',         label: 'Terms of Use',   icon: FileText },
      { id: 'cookies',       label: 'Cookie Policy',  icon: Cookie },
      { id: 'conditions',    label: 'Conditions',     icon: ListChecks },
      { id: 'cookie_banner', label: 'Cookie Banner',  icon: Megaphone },
    ],
  },
  {
    id: 'content',
    label: 'Content',
    items: [
      { id: 'faq',            label: 'FAQ',            icon: Question },
      { id: 'reviews',        label: 'Reviews',        icon: ChatCircle },
      { id: 'google_reviews', label: 'Google Reviews', icon: Star },
      { id: 'before_after',   label: 'Before / After', icon: ImageIcon },
      { id: 'partners',       label: 'Partners',       icon: Handshake },
      { id: 'certificates',   label: 'Certificates',   icon: Certificate },
    ],
  },
  {
    id: 'layout',
    label: 'Layout',
    items: [
      { id: 'hero',   label: 'Hero Banner', icon: ImageIcon },
      { id: 'header', label: 'Header', icon: PhoneCall },
      { id: 'footer', label: 'Footer', icon: PhoneCall },
    ],
  },
];

const POLICY_KEYS = ['privacy', 'terms', 'cookies', 'conditions'];

const LANGS = [
  { code: 'uk', label: 'Українська' },
  { code: 'en', label: 'English' },
];

const SOCIALS = [
  { key: 'instagram', label: 'Instagram', placeholder: 'https://instagram.com/your-page' },
  { key: 'facebook',  label: 'Facebook',  placeholder: 'https://facebook.com/your-page' },
  { key: 'telegram',  label: 'Telegram',  placeholder: 'https://t.me/your-channel' },
  { key: 'tiktok',    label: 'TikTok',    placeholder: 'https://tiktok.com/@your-page' },
  { key: 'whatsapp',  label: 'WhatsApp',  placeholder: 'https://wa.me/359XXXXXXXXX' },
  { key: 'viber',     label: 'Viber',     placeholder: 'viber://chat?number=%2B359XXXXXXXXX' },
];

const quillModules = {
  toolbar: [
    [{ header: [1, 2, 3, false] }],
    ['bold', 'italic', 'underline', 'strike'],
    [{ list: 'ordered' }, { list: 'bullet' }],
    ['link', 'blockquote'],
    [{ align: [] }],
    ['clean'],
  ],
};

// ─────────────────────────────────────────────────────────────────────────
//  Re-usable UI primitives
// ─────────────────────────────────────────────────────────────────────────
function Block({ title, description, children, footer }) {
  const { t } = useLang();
  return (
    <div className="bg-white border border-[#E4E4E7] rounded-2xl">
      {(title || description) && (
        <div className="px-5 pt-5 pb-4">
          {title && <h2 className="font-semibold text-[#18181B] text-[15px]">{title}</h2>}
          {description && <p className="text-[12.5px] text-[#71717A] mt-1 leading-relaxed">{description}</p>}
        </div>
      )}
      <div className="px-5 pb-5">{children}</div>
      {footer && <div className="px-5 py-3 border-t border-[#F4F4F5] bg-[#FAFAFA] rounded-b-2xl text-[12px] text-[#71717A]">{footer}</div>}
    </div>
  );
}

function Field({ label, hint, children }) {
  const { t } = useLang();
  return (
    <label className="block">
      <span className="block text-[12px] font-semibold text-[#52525B] mb-1.5 uppercase tracking-wider">{label}</span>
      {children}
      {hint && <span className="block text-[11.5px] text-[#A1A1AA] mt-1">{hint}</span>}
    </label>
  );
}

const inputCls =
  'w-full bg-white border border-[#E4E4E7] rounded-lg px-3.5 h-10 text-[14px] text-[#18181B] placeholder:text-[#A1A1AA] focus:outline-none focus:border-[#18181B] focus:ring-2 focus:ring-[#18181B]/10 transition-all';

const textareaCls =
  'w-full bg-white border border-[#E4E4E7] rounded-lg px-3.5 py-2.5 text-[14px] text-[#18181B] placeholder:text-[#A1A1AA] focus:outline-none focus:border-[#18181B] focus:ring-2 focus:ring-[#18181B]/10 transition-all resize-y';

// ─────────────────────────────────────────────────────────────────────────
//  GroupDropdown — compact section picker (replaces the tall vertical sidebar).
//  Renders ONE button per nav-group. Clicking opens a popover listing that
//  group's items. The active group (the one containing the current tab) is
//  visually emphasised (filled black). The active item is shown right below
//  the button row as a breadcrumb-style label.
// ─────────────────────────────────────────────────────────────────────────
function GroupDropdown({ group, activeId, onPick }) {
  const [open, setOpen] = React.useState(false);
  const containerRef = React.useRef(null);
  const ownsActive = group.items.some((it) => it.id === activeId);
  const activeItem = group.items.find((it) => it.id === activeId);

  React.useEffect(() => {
    if (!open) return undefined;
    const handler = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    const onEsc = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', handler);
    document.addEventListener('keydown', onEsc);
    return () => {
      document.removeEventListener('mousedown', handler);
      document.removeEventListener('keydown', onEsc);
    };
  }, [open]);

  return (
    <div className="relative min-w-0 flex-1 sm:flex-none sm:w-[200px]" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        data-testid={`info-group-${group.id}`}
        className={`w-full flex items-center justify-between gap-2 px-3.5 h-10 rounded-xl text-[13px] font-semibold transition-all border ${
          ownsActive
            ? 'bg-[#18181B] text-white border-[#18181B]'
            : 'bg-white text-[#52525B] border-[#E4E4E7] hover:bg-[#FAFAFA] hover:border-[#D4D4D8]'
        }`}
      >
        <span className="flex items-center gap-2 min-w-0">
          <span className="truncate uppercase tracking-[0.04em] text-[11.5px]">{group.label}</span>
          {ownsActive && activeItem && (
            <span className="text-[11.5px] font-normal opacity-80 truncate hidden md:inline">
              · {activeItem.label}
            </span>
          )}
        </span>
        <CaretDown size={14} weight="bold" className={`flex-shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div
          role="listbox"
          className="absolute z-30 mt-1.5 left-0 right-0 sm:right-auto sm:min-w-[240px] bg-white border border-[#E4E4E7] rounded-xl shadow-xl overflow-hidden"
        >
          <div className="py-1.5">
            {group.items.map((it) => {
              const Icon = it.icon;
              const isActive = it.id === activeId;
              return (
                <button
                  key={it.id}
                  type="button"
                  role="option"
                  aria-selected={isActive}
                  onClick={() => { onPick(it.id); setOpen(false); }}
                  data-testid={`info-tab-${it.id}`}
                  className={`w-full flex items-center gap-2.5 px-3.5 py-2.5 text-[13.5px] font-medium text-left transition-colors ${
                    isActive
                      ? 'bg-[#F4F4F5] text-[#18181B]'
                      : 'text-[#52525B] hover:bg-[#FAFAFA] hover:text-[#18181B]'
                  }`}
                >
                  <Icon size={16} weight={isActive ? 'fill' : 'regular'} className="flex-shrink-0" />
                  <span className="flex-1 truncate">{it.label}</span>
                  {isActive && <Check size={14} weight="bold" className="text-[#18181B] flex-shrink-0" />}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
export default function AdminInfoPage() {
  const { t } = useLang();
  const params = useParams();
  const location = useLocation();
  const initialTab = useMemo(() => {
    if (params.tab) return params.tab;
    return 'privacy';
  }, [params.tab, location.pathname]);
  const [tab, setTab] = useState(initialTab);
  useEffect(() => { setTab(initialTab); }, [initialTab]);
  const [activeLang, setActiveLang] = useState('uk');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [savedAt, setSavedAt] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API_URL}/api/site-info`);
      setData(r.data);
      setDirty(false);
    } catch {
      toast.error(t('adm_failed_to_load_site_settings'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  // ── Policy helpers ──────────────────────────────────────────────────────
  const updatePolicy = (key, lang, field, value) => {
    setData((prev) => ({
      ...prev,
      policies: {
        ...(prev?.policies || {}),
        [key]: {
          ...(prev?.policies?.[key] || {}),
          [lang]: {
            ...(prev?.policies?.[key]?.[lang] || {}),
            [field]: value,
          },
        },
      },
    }));
    setDirty(true);
  };

  // ── Footer helpers ──────────────────────────────────────────────────────
  const updateFooter = (path, value) => {
    setData((prev) => {
      const next = { ...(prev || {}) };
      next.footer = { ...(prev?.footer || {}) };
      const segments = path.split('.');
      let cur = next.footer;
      for (let i = 0; i < segments.length - 1; i++) {
        const seg = segments[i];
        cur[seg] = { ...(cur[seg] || {}) };
        cur = cur[seg];
      }
      cur[segments[segments.length - 1]] = value;
      return next;
    });
    setDirty(true);
  };

  const updateBanner = (field, value) => {
    setData((prev) => ({
      ...prev,
      cookie_banner: { ...(prev?.cookie_banner || {}), [field]: value },
    }));
    setDirty(true);
  };

  const updateHeader = (field, value) => {
    setData((prev) => ({
      ...prev,
      header: { ...(prev?.header || {}), [field]: value },
    }));
    setDirty(true);
  };

  // ── FAQ helpers ─────────────────────────────────────────────────────────
  const updateFaq = (field, value) => {
    setData((prev) => ({
      ...prev,
      faq: { ...(prev?.faq || {}), [field]: value },
    }));
    setDirty(true);
  };

  const updateFaqItem = (idx, patch) => {
    setData((prev) => {
      const items = [...((prev?.faq?.items) || [])];
      if (idx < 0 || idx >= items.length) return prev;
      items[idx] = { ...items[idx], ...patch };
      return { ...prev, faq: { ...(prev?.faq || {}), items } };
    });
    setDirty(true);
  };

  const addFaqItem = () => {
    setData((prev) => {
      const items = [...((prev?.faq?.items) || [])];
      items.push({
        id: `faq-${Date.now()}`,
        enabled: true,
        question_en: '',
        question_uk: '',
        answer_en: '',
        answer_uk: '',
      });
      return { ...prev, faq: { ...(prev?.faq || { enabled: true }), items } };
    });
    setDirty(true);
  };

  const removeFaqItem = (idx) => {
    setData((prev) => {
      const items = [...((prev?.faq?.items) || [])];
      if (idx < 0 || idx >= items.length) return prev;
      items.splice(idx, 1);
      return { ...prev, faq: { ...(prev?.faq || {}), items } };
    });
    setDirty(true);
  };

  const moveFaqItem = (idx, dir) => {
    setData((prev) => {
      const items = [...((prev?.faq?.items) || [])];
      const target = idx + dir;
      if (target < 0 || target >= items.length) return prev;
      const tmp = items[idx];
      items[idx] = items[target];
      items[target] = tmp;
      return { ...prev, faq: { ...(prev?.faq || {}), items } };
    });
    setDirty(true);
  };

  // ── Reviews helpers ─────────────────────────────────────────────────────
  const updateReviews = (field, value) => {
    setData((prev) => ({
      ...prev,
      reviews: { ...(prev?.reviews || {}), [field]: value },
    }));
    setDirty(true);
  };

  const updateReviewItem = (idx, patch) => {
    setData((prev) => {
      const items = [...((prev?.reviews?.items) || [])];
      if (idx < 0 || idx >= items.length) return prev;
      items[idx] = { ...items[idx], ...patch };
      return { ...prev, reviews: { ...(prev?.reviews || {}), items } };
    });
    setDirty(true);
  };

  const addReviewItem = () => {
    setData((prev) => {
      const items = [...((prev?.reviews?.items) || [])];
      items.push({
        id: `rev-${Date.now()}`,
        enabled: true,
        name: '',
        name_uk: '',
        role_en: '',
        role_uk: '',
        image_url: '',
        rating: 5,
        text_en: '',
        text_uk: '',
      });
      return {
        ...prev,
        reviews: { ...(prev?.reviews || { enabled: true }), items },
      };
    });
    setDirty(true);
  };

  const removeReviewItem = (idx) => {
    setData((prev) => {
      const items = [...((prev?.reviews?.items) || [])];
      if (idx < 0 || idx >= items.length) return prev;
      items.splice(idx, 1);
      return { ...prev, reviews: { ...(prev?.reviews || {}), items } };
    });
    setDirty(true);
  };

  const moveReviewItem = (idx, dir) => {
    setData((prev) => {
      const items = [...((prev?.reviews?.items) || [])];
      const target = idx + dir;
      if (target < 0 || target >= items.length) return prev;
      const tmp = items[idx];
      items[idx] = items[target];
      items[target] = tmp;
      return { ...prev, reviews: { ...(prev?.reviews || {}), items } };
    });
    setDirty(true);
  };

  const uploadReviewImage = useCallback(async (idx, file) => {
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      toast.error('Image too large (max 5MB)');
      return;
    }
    const fd = new FormData();
    fd.append('image', file);
    try {
      const token = localStorage.getItem('eco_token') || localStorage.getItem('token');
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const r = await axios.post(
        `${API_URL}/api/admin/site-info/upload-review-image`,
        fd,
        { headers: { ...headers, 'Content-Type': 'multipart/form-data' } },
      );
      const url = r?.data?.url;
      if (url) {
        updateReviewItem(idx, { image_url: url });
        toast.success(t('adm_image_uploaded'));
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Upload failed');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Partners helpers ────────────────────────────────────────────────────
  const updatePartners = (field, value) => {
    setData((prev) => ({
      ...prev,
      partners: { ...(prev?.partners || {}), [field]: value },
    }));
    setDirty(true);
  };

  const updatePartnerItem = (idx, patch) => {
    setData((prev) => {
      const items = [...((prev?.partners?.items) || [])];
      if (idx < 0 || idx >= items.length) return prev;
      items[idx] = { ...items[idx], ...patch };
      return { ...prev, partners: { ...(prev?.partners || {}), items } };
    });
    setDirty(true);
  };

  const addPartnerItem = () => {
    setData((prev) => {
      const items = [...((prev?.partners?.items) || [])];
      items.push({
        id: `partner-${Date.now()}`,
        enabled: true,
        name_uk: '',
        name_en: '',
        desc_uk: '',
        desc_en: '',
        image_url: '',
        logo_url: '',
        link: '',
      });
      return {
        ...prev,
        partners: { ...(prev?.partners || { enabled: true }), items },
      };
    });
    setDirty(true);
  };

  const removePartnerItem = (idx) => {
    setData((prev) => {
      const items = [...((prev?.partners?.items) || [])];
      if (idx < 0 || idx >= items.length) return prev;
      items.splice(idx, 1);
      return { ...prev, partners: { ...(prev?.partners || {}), items } };
    });
    setDirty(true);
  };

  const movePartnerItem = (idx, dir) => {
    setData((prev) => {
      const items = [...((prev?.partners?.items) || [])];
      const target = idx + dir;
      if (target < 0 || target >= items.length) return prev;
      const tmp = items[idx];
      items[idx] = items[target];
      items[target] = tmp;
      return { ...prev, partners: { ...(prev?.partners || {}), items } };
    });
    setDirty(true);
  };

  const uploadPartnerAsset = useCallback(async (idx, field, file) => {
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      toast.error('Image too large (max 5MB)');
      return;
    }
    const fd = new FormData();
    fd.append('image', file);
    try {
      const token = localStorage.getItem('eco_token') || localStorage.getItem('token');
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const r = await axios.post(
        `${API_URL}/api/admin/site-info/upload-partner-logo`,
        fd,
        { headers: { ...headers, 'Content-Type': 'multipart/form-data' } },
      );
      const url = r?.data?.url;
      if (url) {
        setData((prev) => {
          const items = [...((prev?.partners?.items) || [])];
          if (idx < 0 || idx >= items.length) return prev;
          items[idx] = { ...items[idx], [field]: url };
          return { ...prev, partners: { ...(prev?.partners || {}), items } };
        });
        setDirty(true);
        toast.success(t('adm_image_uploaded'));
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Upload failed');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);


  // ── Certificates / licenses helpers ──────────────────────────────────────
  const updateCertificates = (field, value) => {
    setData((prev) => ({
      ...prev,
      certificates: { ...(prev?.certificates || {}), [field]: value },
    }));
    setDirty(true);
  };

  const updateCertificateItem = (idx, patch) => {
    setData((prev) => {
      const items = [...((prev?.certificates?.items) || [])];
      if (idx < 0 || idx >= items.length) return prev;
      items[idx] = { ...items[idx], ...patch };
      return { ...prev, certificates: { ...(prev?.certificates || {}), items } };
    });
    setDirty(true);
  };

  const addCertificateItem = () => {
    setData((prev) => {
      const items = [...((prev?.certificates?.items) || [])];
      items.push({
        id: `cert-${Date.now()}`,
        no: String(items.length + 1).padStart(2, '0'),
        category: 'certificate',
        enabled: true,
        title_uk: '',
        title_en: '',
        desc_uk: '',
        desc_en: '',
        issuer_uk: '',
        issuer_en: '',
        number: '',
        issued: '',
        valid_until: '',
        image_url: '',
        file_url: '',
      });
      return {
        ...prev,
        certificates: { ...(prev?.certificates || { enabled: true }), items },
      };
    });
    setDirty(true);
  };

  const removeCertificateItem = (idx) => {
    setData((prev) => {
      const items = [...((prev?.certificates?.items) || [])];
      if (idx < 0 || idx >= items.length) return prev;
      items.splice(idx, 1);
      return { ...prev, certificates: { ...(prev?.certificates || {}), items } };
    });
    setDirty(true);
  };

  const moveCertificateItem = (idx, dir) => {
    setData((prev) => {
      const items = [...((prev?.certificates?.items) || [])];
      const target = idx + dir;
      if (target < 0 || target >= items.length) return prev;
      const tmp = items[idx];
      items[idx] = items[target];
      items[target] = tmp;
      return { ...prev, certificates: { ...(prev?.certificates || {}), items } };
    });
    setDirty(true);
  };

  const uploadCertificateAsset = useCallback(async (idx, field, file) => {
    if (!file) return;
    const isPdf = field === 'file_url';
    const maxMb = isPdf ? 25 : 8;
    if (file.size > maxMb * 1024 * 1024) {
      toast.error(`File too large (max ${maxMb}MB)`);
      return;
    }
    const fd = new FormData();
    fd.append(isPdf ? 'file' : 'image', file);
    const endpoint = isPdf
      ? '/api/admin/site-info/upload-certificate-file'
      : '/api/admin/site-info/upload-certificate-image';
    try {
      const token = localStorage.getItem('eco_token') || localStorage.getItem('token');
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const r = await axios.post(`${API_URL}${endpoint}`, fd, {
        headers: { ...headers, 'Content-Type': 'multipart/form-data' },
      });
      const url = r?.data?.url;
      if (url) {
        setData((prev) => {
          const items = [...((prev?.certificates?.items) || [])];
          if (idx < 0 || idx >= items.length) return prev;
          items[idx] = { ...items[idx], [field]: url };
          return { ...prev, certificates: { ...(prev?.certificates || {}), items } };
        });
        setDirty(true);
        toast.success(isPdf ? 'Document uploaded' : t('adm_image_uploaded'));
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Upload failed');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);


  // ── Before/After helpers ────────────────────────────────────────────────
  const updateBeforeAfter = (field, value) => {
    setData((prev) => ({
      ...prev,
      before_after: { ...(prev?.before_after || {}), [field]: value },
    }));
    setDirty(true);
  };

  const updateBeforeAfterItem = (idx, patch) => {
    setData((prev) => {
      const items = [...((prev?.before_after?.items) || [])];
      if (idx < 0 || idx >= items.length) return prev;
      items[idx] = { ...items[idx], ...patch };
      return { ...prev, before_after: { ...(prev?.before_after || {}), items } };
    });
    setDirty(true);
  };

  const addBeforeAfterItem = () => {
    setData((prev) => {
      const items = [...((prev?.before_after?.items) || [])];
      items.push({
        id: `ba-${Date.now()}`,
        enabled: true,
        model: '',
        order_date: '',
        finished_date: '',
        price: '',
        before_image_url: '',
        after_image_url: '',
      });
      return {
        ...prev,
        before_after: { ...(prev?.before_after || { enabled: true }), items },
      };
    });
    setDirty(true);
  };

  const removeBeforeAfterItem = (idx) => {
    setData((prev) => {
      const items = [...((prev?.before_after?.items) || [])];
      if (idx < 0 || idx >= items.length) return prev;
      items.splice(idx, 1);
      return { ...prev, before_after: { ...(prev?.before_after || {}), items } };
    });
    setDirty(true);
  };

  const moveBeforeAfterItem = (idx, dir) => {
    setData((prev) => {
      const items = [...((prev?.before_after?.items) || [])];
      const target = idx + dir;
      if (target < 0 || target >= items.length) return prev;
      const tmp = items[idx];
      items[idx] = items[target];
      items[target] = tmp;
      return { ...prev, before_after: { ...(prev?.before_after || {}), items } };
    });
    setDirty(true);
  };

  const uploadBeforeAfterImage = useCallback(async (idx, side, file) => {
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) {
      toast.error('Image too large (max 10MB)');
      return;
    }
    const fd = new FormData();
    fd.append('image', file);
    try {
      const token = localStorage.getItem('eco_token') || localStorage.getItem('token');
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const r = await axios.post(
        `${API_URL}/api/admin/site-info/upload-before-after-image`,
        fd,
        { headers: { ...headers, 'Content-Type': 'multipart/form-data' } },
      );
      const url = r?.data?.url;
      if (url) {
        updateBeforeAfterItem(idx, { [`${side}_image_url`]: url });
        toast.success(t('adm_image_uploaded'));
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Upload failed');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Hero (homepage banner) helpers ──────────────────────────────────────
  const updateHero = (field, value) => {
    setData((prev) => ({
      ...prev,
      hero: { ...(prev?.hero || {}), [field]: value },
    }));
    setDirty(true);
  };

  const uploadHeroImage = useCallback(async (file, variant = 'web') => {
    if (!file) return;
    const allowedTypes = ['image/jpeg', 'image/png', 'image/webp'];
    if (!allowedTypes.includes(file.type)) {
      toast.error(t('adm_unsupported_format_use_jpg_png_or_webp'));
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      toast.error('Image too large (max 5 MB)');
      return;
    }
    const ALLOWED = { web: 'image_url', mobile: 'image_url_mobile', scene2: 'scene2_image', scene3: 'scene3_image' };
    const v = ALLOWED[variant] ? variant : 'web';
    const targetField = ALLOWED[v];
    const fd = new FormData();
    fd.append('image', file);
    try {
      const token = localStorage.getItem('eco_token') || localStorage.getItem('token');
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const r = await axios.post(
        `${API_URL}/api/admin/site-info/upload-hero-image?variant=${v}`,
        fd,
        { headers: { ...headers, 'Content-Type': 'multipart/form-data' } },
      );
      const url = r?.data?.url;
      if (url) {
        setData((prev) => ({
          ...prev,
          hero: { ...(prev?.hero || {}), [targetField]: url },
        }));
        setDirty(true);
        toast.success(t('adm_hero_image_uploaded'));
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Upload failed');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Socials ─────────────────────────────────────────────────────────────
  const readSocial = (key) => {
    const v = data?.footer?.socials?.[key];
    if (!v) return { enabled: false, url: '' };
    if (typeof v === 'string') return { enabled: !!v, url: v };
    return { enabled: !!v.enabled, url: v.url || '' };
  };

  const updateSocial = (key, patch) => {
    const cur = readSocial(key);
    const next = { ...cur, ...patch };
    updateFooter(`socials.${key}`, next);
  };

  // ── Save ────────────────────────────────────────────────────────────────
  const save = async () => {
    setSaving(true);
    try {
      const token = localStorage.getItem('eco_token') || localStorage.getItem('token');
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const r = await axios.put(
        `${API_URL}/api/admin/site-info`,
        {
          policies: data?.policies || {},
          header: data?.header || {},
          footer: data?.footer || {},
          cookie_banner: data?.cookie_banner || {},
          faq: data?.faq || {},
          reviews: data?.reviews || {},
          before_after: data?.before_after || {},
          hero: data?.hero || {},
          partners: data?.partners || {},
          certificates: data?.certificates || {},
        },
        { headers },
      );
      setData(r.data);
      setDirty(false);
      setSavedAt(new Date());
      toast.success(t('adm_saved'));
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const policy = useMemo(
    () => data?.policies?.[tab]?.[activeLang] || { title: '', content: '' },
    [data, tab, activeLang],
  );

  const isPolicy = POLICY_KEYS.includes(tab);

  const activeItem = useMemo(() => {
    for (const grp of NAV_GROUPS) {
      const found = grp.items.find((i) => i.id === tab);
      if (found) return { group: grp.label, item: found };
    }
    return null;
  }, [tab]);

  if (loading) {
    return (
      <div>
        <div className="text-center text-[#71717A] py-10 flex items-center justify-center gap-2">
          <ArrowsClockwise size={18} className="animate-spin" />
          {t('adm_loading')}
        </div>
      </div>
    );
  }

  return (
    <div data-testid="admin-info-page">
      {/* Page header */}
      {/*
        ── Info — Site content header (June 2026) ────────────────────────
        Mobile (< md):
          ┌──────────────────────────────────────────────┐
          │ Info — Site content              [Refresh]   │  Row 1
          │ Legal documents, FAQ, reviews…               │
          ├──────────────────────────────────────────────┤
          │ [ 💾 Save changes ]      ✓ Saved 11:15…      │  Row 2
          └──────────────────────────────────────────────┘
        Desktop (≥ md):
          [ title block ]   ✓Saved [Save changes] [Refresh]

        Refresh is the standard black square icon (no "Reload" text, no
        white background) — matches Payments / Services / Email / etc.
      */}
      <div className="mb-6">
        {/* Row 1: title + Refresh pinned top-RIGHT (always). On desktop we
            also dock the "Save changes" CTA and the "Saved at …" status
            into this same row to the LEFT of Refresh — keeps the primary
            save action close to the page-level controls. */}
        <div className="flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl font-bold text-[#18181B] leading-tight break-words">{t('adm_info_site_content')}</h1>
            <p className="text-sm text-[#71717A] mt-1 break-words">
              {t('adm_legal_documents_faq_reviews_header_footer_and_cook')}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {/* Desktop-only: Save status + Save button live inline with Refresh. */}
            {savedAt && !dirty && (
              <span className="hidden md:inline-flex items-center gap-1.5 text-[12px] text-[#16A34A]">
                <CheckCircle size={14} weight="fill" /> Saved {savedAt.toLocaleTimeString()}
              </span>
            )}
            <button
              onClick={save}
              disabled={!dirty || saving}
              className="hidden md:inline-flex items-center gap-2 px-4 h-10 rounded-lg bg-[#18181B] hover:bg-black text-white text-[13px] font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              data-testid="info-save-desktop"
            >
              <FloppyDisk size={15} weight="fill" /> {saving ? 'Saving…' : dirty ? 'Save changes' : 'Saved'}
            </button>
            <RefreshButton
              onClick={load}
              disabled={saving}
              loading={false}
              ariaLabel={t('adm_reload')}
              testId="info-reload"
              title={t('adm_reload')}
            />
          </div>
        </div>

        {/* Row 2 (mobile-only): Save changes as primary action, full-width.
            Status badge ("Saved 11:15:23") sits to its right. */}
        <div className="mt-4 md:hidden flex items-center gap-3">
          <button
            onClick={save}
            disabled={!dirty || saving}
            className="inline-flex items-center justify-center gap-2 h-11 px-5 rounded-lg bg-[#18181B] hover:bg-black text-white text-[13px] font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            data-testid="info-save"
          >
            <FloppyDisk size={15} weight="fill" /> {saving ? 'Saving…' : dirty ? 'Save changes' : 'Saved'}
          </button>
          {savedAt && !dirty && (
            <span className="inline-flex items-center gap-1.5 text-[12px] text-[#16A34A]">
              <CheckCircle size={14} weight="fill" /> Saved {savedAt.toLocaleTimeString()}
            </span>
          )}
        </div>
      </div>

      {/* Section picker — 3 compact dropdowns (Legal & Privacy / Content / Layout) */}
      <div className="bg-white border border-[#E4E4E7] rounded-2xl p-3 sm:p-4 mb-5">
        <div className="flex flex-col sm:flex-row sm:flex-wrap gap-2 sm:gap-3">
          {NAV_GROUPS.map((grp) => (
            <GroupDropdown
              key={grp.id}
              group={grp}
              activeId={tab}
              onPick={setTab}
            />
          ))}
        </div>
        {/* Inline breadcrumb on small screens — desktop already shows it in the trigger */}
        {activeItem && (
          <div className="mt-3 sm:hidden flex items-center gap-2 text-[12.5px] text-[#71717A]">
            <span>{activeItem.group}</span>
            <span className="text-[#D4D4D8]">/</span>
            <span className="text-[#18181B] font-semibold">{activeItem.item.label}</span>
          </div>
        )}
      </div>

      {/* Main content area — full width now that the sidebar is gone */}
      <div className="min-w-0 space-y-5">
          {/* Breadcrumb */}
          {activeItem && (
            <div className="flex items-center gap-2 text-[12.5px] text-[#71717A]">
              <span>{activeItem.group}</span>
              <span className="text-[#D4D4D8]">/</span>
              <span className="text-[#18181B] font-semibold">{activeItem.item.label}</span>
            </div>
          )}

          {/* Policy editor (privacy / terms / cookies / conditions) */}
          {isPolicy && (
            <Block
              title={activeItem?.item?.label || 'Policy'}
              description={t('adm_edit_title_and_richtext_body_for_both_languages_bo')}
            >
              {/* Lang selector */}
              <div className="inline-flex items-center gap-1 rounded-lg p-0.5 bg-[#F4F4F5] border border-[#E4E4E7] mb-5">
                {LANGS.map((l) => (
                  <button
                    key={l.code}
                    onClick={() => setActiveLang(l.code)}
                    className={`px-3 py-1.5 text-[12px] font-semibold uppercase tracking-wider rounded-md transition-all flex items-center gap-1.5 ${
                      activeLang === l.code
                        ? 'bg-white text-[#18181B] shadow-sm border border-[#E4E4E7]'
                        : 'text-[#71717A] hover:text-[#18181B]'
                    }`}
                    data-testid={`info-lang-${l.code}`}
                  >
                    <Globe size={12} />
                    {l.label}
                  </button>
                ))}
              </div>

              <div className="grid grid-cols-1 gap-4">
                <Field label={t('taskTitle')}>
                  <input
                    type="text"
                    value={policy.title || ''}
                    onChange={(e) => updatePolicy(tab, activeLang, 'title', e.target.value)}
                    className={inputCls}
                    placeholder={t('adm_eg_privacy_policy')}
                    data-testid="info-policy-title"
                  />
                </Field>

                <div>
                  <span className="block text-[12px] font-semibold text-[#52525B] mb-1.5 uppercase tracking-wider">{t('contentLabel')}</span>
                  <div className="bibi-admin-quill">
                    <ReactQuill
                      theme="snow"
                      value={policy.content || ''}
                      onChange={(v) => updatePolicy(tab, activeLang, 'content', v)}
                      modules={quillModules}
                    />
                  </div>
                </div>
              </div>
            </Block>
          )}

          {/* Cookie banner — grouped under Legal */}
          {tab === 'cookie_banner' && (
            <Block
              title={t('cookieConsentBanner')}
              description={t('adm_bilingual_copy_shown_at_the_bottom_of_the_public_s')}
            >
              <label className="flex items-center gap-3 text-[14px] text-[#18181B] mb-5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={!!data?.cookie_banner?.enabled}
                  onChange={(e) => updateBanner('enabled', e.target.checked)}
                  className="w-4 h-4 accent-[#18181B] cursor-pointer"
                  data-testid="info-banner-enabled"
                />
                <span className="font-medium">{t('showCookieBanner')}</span>
              </label>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Field label="Title (EN)">
                  <input
                    type="text"
                    value={data?.cookie_banner?.title_en || ''}
                    onChange={(e) => updateBanner('title_en', e.target.value)}
                    className={inputCls}
                  />
                </Field>
                <Field label="Title (UA)">
                  <input
                    type="text"
                    value={data?.cookie_banner?.title_uk || ''}
                    onChange={(e) => updateBanner('title_uk', e.target.value)}
                    className={inputCls}
                  />
                </Field>
                <Field label="Body (EN)">
                  <textarea
                    rows={4}
                    value={data?.cookie_banner?.body_en || ''}
                    onChange={(e) => updateBanner('body_en', e.target.value)}
                    className={textareaCls}
                  />
                </Field>
                <Field label="Body (UA)">
                  <textarea
                    rows={4}
                    value={data?.cookie_banner?.body_uk || ''}
                    onChange={(e) => updateBanner('body_uk', e.target.value)}
                    className={textareaCls}
                  />
                </Field>
              </div>
            </Block>
          )}

          {/* FAQ editor */}
          {tab === 'faq' && (
            <FAQEditor
              data={data}
              updateFaq={updateFaq}
              updateFaqItem={updateFaqItem}
              addFaqItem={addFaqItem}
              removeFaqItem={removeFaqItem}
              moveFaqItem={moveFaqItem}
            />
          )}

          {/* Reviews editor — NEW */}
          {tab === 'reviews' && (
            <ReviewsEditor
              data={data}
              updateReviews={updateReviews}
              updateReviewItem={updateReviewItem}
              addReviewItem={addReviewItem}
              removeReviewItem={removeReviewItem}
              moveReviewItem={moveReviewItem}
              uploadReviewImage={uploadReviewImage}
            />
          )}

          {/* Before / After editor — NEW */}
          {tab === 'before_after' && (
            <BeforeAfterEditor
              data={data}
              updateBeforeAfter={updateBeforeAfter}
              updateBeforeAfterItem={updateBeforeAfterItem}
              addBeforeAfterItem={addBeforeAfterItem}
              removeBeforeAfterItem={removeBeforeAfterItem}
              moveBeforeAfterItem={moveBeforeAfterItem}
              uploadBeforeAfterImage={uploadBeforeAfterImage}
            />
          )}

          {/* Google Reviews integration — config + moderation table */}
          {tab === 'google_reviews' && <GoogleReviewsEditor />}

          {/* Partners editor — NEW */}
          {tab === 'partners' && (
            <PartnersEditor
              data={data}
              updatePartners={updatePartners}
              updatePartnerItem={updatePartnerItem}
              addPartnerItem={addPartnerItem}
              removePartnerItem={removePartnerItem}
              movePartnerItem={movePartnerItem}
              uploadPartnerAsset={uploadPartnerAsset}
            />
          )}

          {tab === 'certificates' && (
            <CertificatesEditor
              data={data}
              updateCertificates={updateCertificates}
              updateCertificateItem={updateCertificateItem}
              addCertificateItem={addCertificateItem}
              removeCertificateItem={removeCertificateItem}
              moveCertificateItem={moveCertificateItem}
              uploadCertificateAsset={uploadCertificateAsset}
            />
          )}

          {/* Hero Banner editor — homepage */}
          {tab === 'hero' && (
            <HeroEditor
              data={data}
              updateHero={updateHero}
              uploadHeroImage={uploadHeroImage}
            />
          )}

          {/* Header settings */}
          {tab === 'header' && (
            <Block
              title={t('publicHeader')}
              description={t('adm_phone_numbers_shown_in_the_public_site_header_one')}
            >
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Field label={t('phonesLabel')} hint={t('adm_one_number_per_line_eg_359_875_313_158')}>
                  <textarea
                    rows={3}
                    value={(data?.header?.phones || []).join('\n')}
                    onChange={(e) =>
                      updateHeader(
                        'phones',
                        e.target.value.split('\n').map((s) => s.trim()).filter(Boolean),
                      )
                    }
                    className={textareaCls}
                    placeholder={'+380 44 333 44 55\n+380 50 123 45 67'}
                    data-testid="info-header-phones"
                  />
                </Field>
                <div className="space-y-4">
                  <Field label="CTA button label (EN)" hint={t('adm_yellow_button_on_the_right_of_the_header')}>
                    <input
                      type="text"
                      value={data?.header?.cta_label_en || ''}
                      onChange={(e) => updateHeader('cta_label_en', e.target.value)}
                      className={inputCls}
                      placeholder={t('contactUs')}
                      data-testid="info-header-cta-en"
                    />
                  </Field>
                  <Field label="CTA button label (UA)">
                    <input
                      type="text"
                      value={data?.header?.cta_label_uk || ''}
                      onChange={(e) => updateHeader('cta_label_uk', e.target.value)}
                      className={inputCls}
                      placeholder={t('adm_contact_us')}
                      data-testid="info-header-cta-uk"
                    />
                  </Field>
                </div>
              </div>
            </Block>
          )}

          {/* Footer settings */}
          {tab === 'footer' && (
            <div className="space-y-5">
              <Block title={t('navContacts')} description={t('adm_phones_email_addresses_and_working_hours_displayed')}>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Field label={t('phonesLabel')} hint={t('adm_one_number_per_line')}>
                    <textarea
                      rows={3}
                      value={(data?.footer?.contacts?.phones || []).join('\n')}
                      onChange={(e) =>
                        updateFooter(
                          'contacts.phones',
                          e.target.value.split('\n').map((s) => s.trim()).filter(Boolean),
                        )
                      }
                      className={textareaCls}
                      placeholder="+380 44 333 44 55"
                      data-testid="info-footer-phones"
                    />
                  </Field>
                  <div className="space-y-4">
                    <Field label={t('emailLabel')}>
                      <input
                        type="email"
                        value={data?.footer?.contacts?.email || ''}
                        onChange={(e) => updateFooter('contacts.email', e.target.value)}
                        className={inputCls}
                        placeholder="info@eco-utyl.ua"
                        data-testid="info-footer-email"
                      />
                    </Field>
                  </div>

                  {/* Working hours — paired EN / UA */}
                  <Field label="Working hours (English)">
                    <input
                      type="text"
                      value={data?.footer?.contacts?.working_hours || ''}
                      onChange={(e) => updateFooter('contacts.working_hours', e.target.value)}
                      className={inputCls}
                      placeholder={t('adm_mon_fri_1000_1900')}
                      data-testid="info-footer-hours"
                    />
                  </Field>
                  <Field label={t('adm3_9aafd2e0a0')} hint={'Українська версія'}>
                    <input
                      type="text"
                      value={data?.footer?.contacts?.working_hours_uk || ''}
                      onChange={(e) => updateFooter('contacts.working_hours_uk', e.target.value)}
                      className={inputCls}
                      placeholder={t('adm_mon_fri_1000_1900_2')}
                      data-testid="info-footer-hours-uk"
                    />
                  </Field>

                  {/* Addresses — paired EN / UA */}
                  <Field label="Addresses (English)" hint={t('adm_one_address_per_line')}>
                    <textarea
                      rows={3}
                      value={(data?.footer?.contacts?.addresses || []).join('\n')}
                      onChange={(e) =>
                        updateFooter(
                          'contacts.addresses',
                          e.target.value.split('\n').map((s) => s.trim()).filter(Boolean),
                        )
                      }
                      className={textareaCls}
                      placeholder="Україна, м. Київ, вул. Хрещатик, 1"
                      data-testid="info-footer-addresses"
                    />
                  </Field>
                  <Field label={t('adm3_df848915fc')} hint={t('adm_one_address_per_line_falls_back_to_canonical_trans')}>
                    <textarea
                      rows={3}
                      value={(data?.footer?.contacts?.addresses_uk || []).join('\n')}
                      onChange={(e) =>
                        updateFooter(
                          'contacts.addresses_uk',
                          e.target.value.split('\n').map((s) => s.trim()).filter(Boolean),
                        )
                      }
                      className={textareaCls}
                      placeholder="Україна, м. Київ, вул. Хрещатик, 1"
                      data-testid="info-footer-addresses-uk"
                    />
                  </Field>

                  {/* Registration address — paired EN / UA (new) */}
                  <Field label="Registration address (English)">
                    <input
                      type="text"
                      value={data?.footer?.contacts?.registration_address || ''}
                      onChange={(e) => updateFooter('contacts.registration_address', e.target.value)}
                      className={inputCls}
                      placeholder="Україна, 01001, м. Київ, вул. Хрещатик, 1"
                      data-testid="info-footer-reg-address"
                    />
                  </Field>
                  <Field label={t('adm3_d4d76851ee')}>
                    <input
                      type="text"
                      value={data?.footer?.contacts?.registration_address_uk || ''}
                      onChange={(e) => updateFooter('contacts.registration_address_uk', e.target.value)}
                      className={inputCls}
                      placeholder="Україна, 01001, м. Київ, вул. Хрещатик, 1"
                      data-testid="info-footer-reg-address-uk"
                    />
                  </Field>
                </div>
              </Block>

              <Block title={t('socialMediaLinks')} description={t('adm_public_social_channels_toggle_a_channel_to_showhid')}>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {SOCIALS.map((s) => {
                    const cur = readSocial(s.key);
                    return (
                      <div key={s.key} className="flex items-start gap-3 p-3 bg-[#FAFAFA] border border-[#E4E4E7] rounded-lg">
                        <label className="flex items-center mt-7 cursor-pointer shrink-0" title={cur.enabled ? 'Enabled' : 'Disabled'}>
                          <input
                            type="checkbox"
                            checked={cur.enabled}
                            onChange={(e) => updateSocial(s.key, { enabled: e.target.checked })}
                            className="w-4 h-4 accent-[#18181B] cursor-pointer"
                            data-testid={`info-social-enabled-${s.key}`}
                          />
                        </label>
                        <div className="flex-1 min-w-0">
                          <Field label={s.label} hint={cur.enabled ? 'Visible in footer' : 'Hidden from footer'}>
                            <input
                              type="text"
                              value={cur.url}
                              onChange={(e) => updateSocial(s.key, { url: e.target.value })}
                              className={inputCls}
                              placeholder={s.placeholder}
                              data-testid={`info-social-${s.key}`}
                              disabled={!cur.enabled}
                            />
                          </Field>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </Block>

              <Block title={t('viberCommunityBlock')} description="Separate &lsquo;Join our group&rsquo; block in the footer (not a regular social icon).">
                <label className="flex items-center gap-3 text-[14px] text-[#18181B] mb-4 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={!!data?.footer?.viber_community?.enabled}
                    onChange={(e) => updateFooter('viber_community.enabled', e.target.checked)}
                    className="w-4 h-4 accent-[#18181B] cursor-pointer"
                    data-testid="info-viber-enabled"
                  />
                  <span className="font-medium">{t('showViberBlock')}</span>
                </label>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Field label={t('viberLink')}>
                    <input
                      type="text"
                      value={data?.footer?.viber_community?.url || ''}
                      onChange={(e) => updateFooter('viber_community.url', e.target.value)}
                      className={inputCls}
                      placeholder="viber://chat?number=..."
                      data-testid="info-viber-url"
                    />
                  </Field>
                  <Field label="Label (EN)">
                    <input
                      type="text"
                      value={data?.footer?.viber_community?.label_en || ''}
                      onChange={(e) => updateFooter('viber_community.label_en', e.target.value)}
                      className={inputCls}
                      placeholder={t('mobileFooterJoinGroup')}
                    />
                  </Field>
                  <Field label="Label (UA)">
                    <input
                      type="text"
                      value={data?.footer?.viber_community?.label_uk || ''}
                      onChange={(e) => updateFooter('viber_community.label_uk', e.target.value)}
                      className={inputCls}
                      placeholder={t('adm_join_our_group')}
                    />
                  </Field>
                </div>
              </Block>
            </div>
          )}
        </div>

      {/* Light-theme Quill styling */}
      <style>{`
        .bibi-admin-quill .ql-toolbar {
          background: #FAFAFA;
          border: 1px solid #E4E4E7 !important;
          border-bottom: 0 !important;
          border-top-left-radius: 8px;
          border-top-right-radius: 8px;
          padding: 8px 10px;
        }
        .bibi-admin-quill .ql-toolbar .ql-stroke { stroke: #52525B; }
        .bibi-admin-quill .ql-toolbar .ql-fill   { fill:   #52525B; }
        .bibi-admin-quill .ql-toolbar .ql-picker-label { color: #52525B; }
        .bibi-admin-quill .ql-toolbar button:hover .ql-stroke,
        .bibi-admin-quill .ql-toolbar .ql-active .ql-stroke { stroke: #18181B; }
        .bibi-admin-quill .ql-toolbar button:hover .ql-fill,
        .bibi-admin-quill .ql-toolbar .ql-active .ql-fill   { fill:   #18181B; }
        .bibi-admin-quill .ql-toolbar button:hover,
        .bibi-admin-quill .ql-toolbar .ql-active { background: #F4F4F5; border-radius: 4px; }
        .bibi-admin-quill .ql-toolbar .ql-picker-options {
          background: #FFF;
          color: #18181B;
          border: 1px solid #E4E4E7;
          border-radius: 6px;
          box-shadow: 0 6px 20px rgba(0,0,0,0.08);
        }
        .bibi-admin-quill .ql-container {
          background: #FFF;
          border: 1px solid #E4E4E7 !important;
          color: #18181B;
          font-size: 14px;
          min-height: 280px;
          border-bottom-left-radius: 8px;
          border-bottom-right-radius: 8px;
        }
        .bibi-admin-quill .ql-editor {
          min-height: 280px;
          font-family: inherit;
        }
        .bibi-admin-quill .ql-editor.ql-blank::before {
          color: #A1A1AA;
          font-style: normal;
        }
        .bibi-admin-quill .ql-editor a { color: #2563EB; text-decoration: underline; }
        .bibi-admin-quill .ql-editor h1,
        .bibi-admin-quill .ql-editor h2,
        .bibi-admin-quill .ql-editor h3 { color: #18181B; font-weight: 700; }
        .bibi-admin-quill .ql-editor blockquote {
          border-left: 3px solid #E4E4E7;
          padding-left: 12px;
          color: #52525B;
        }
      `}</style>
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────────────
//  Hero Variant Card — reusable upload + preview block for one form-factor.
//  Used twice inside HeroEditor: once for the desktop 16:9 banner and once
//  for the mobile 361:326 banner. Keeps the two flows visually identical
//  while letting each card own its own file-input ref and aspect.
// ─────────────────────────────────────────────────────────────────────────
function HeroVariantCard({
  variant,
  aspectClass,
  label,
  ratioHint,
  previewUrl,
  currentUrl,
  eyebrow,
  onUpload,
  onClear,
  onUrlChange,
  urlPlaceholder,
  previewTestId,
  uploadTestId,
  removeTestId,
  fileInputTestId,
  urlInputTestId,
  tipsText,
  mirrorOverlay = true,
  disabled = false,
  disabledHint,
  t,
}) {
  const fileRef = useRef(null);
  return (
    <div
      className={`rounded-2xl border border-[#E4E4E7] bg-white p-3 sm:p-4 space-y-3 transition-opacity ${
        disabled ? 'opacity-60' : ''
      }`}
      data-variant={variant}
    >
      <div className="flex items-center justify-between gap-2">
        <p className="text-[12px] font-bold uppercase tracking-wider text-[#18181B]">
          {label}
        </p>
        <span className="text-[10.5px] text-[#71717A] tabular-nums">
          {ratioHint}
        </span>
      </div>

      {/* Preview */}
      <div
        className={`relative w-full ${aspectClass} bg-[#0e0e0e] border border-[#E4E4E7] rounded-xl overflow-hidden`}
      >
        {previewUrl ? (
          <img
            src={previewUrl}
            alt={t('heroPreview')}
            className="absolute inset-0 w-full h-full object-cover"
            data-testid={previewTestId}
          />
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-[#A1A1AA] text-sm gap-2 px-4 text-center">
            <ImageIcon size={36} weight="thin" />
            <span>{t('adm_no_custom_image_using_builtin_default_photo')}</span>
          </div>
        )}
        {/* Mock overlay matches public-site rendering. Mobile hero is full-bleed
            and has no left-side dim, so we hide the overlay there. */}
        {mirrorOverlay && (
          <div
            className="absolute inset-0 pointer-events-none"
            style={{
              background:
                'linear-gradient(90deg, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.55) 35%, rgba(0,0,0,0.05) 65%, rgba(0,0,0,0) 100%)',
            }}
          />
        )}
        <div className="absolute left-4 top-3 text-white/80 text-[10px] tracking-[0.18em] uppercase">
          {eyebrow}
        </div>
      </div>

      {/* Controls */}
      <div className="space-y-2.5">
        <input
          ref={fileRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f && !disabled) onUpload(f);
            e.target.value = '';
          }}
          data-testid={fileInputTestId}
          disabled={disabled}
        />
        <button
          type="button"
          onClick={() => !disabled && fileRef.current?.click()}
          disabled={disabled}
          className="w-full inline-flex items-center justify-center gap-2 px-4 h-11 rounded-lg bg-[#18181B] hover:bg-black text-white text-[13px] font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          data-testid={uploadTestId}
        >
          <UploadSimple size={16} weight="bold" />
          {previewUrl ? 'Replace image' : 'Upload image'}
        </button>
        {previewUrl && currentUrl && (
          <button
            type="button"
            onClick={onClear}
            disabled={disabled}
            className="w-full inline-flex items-center justify-center gap-2 px-4 h-10 rounded-lg border border-[#E4E4E7] bg-white hover:bg-[#FAFAFA] text-[#52525B] hover:text-[#18181B] text-[13px] font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            data-testid={removeTestId}
          >
            <Trash size={14} />
            {t('useDefaultPhoto')}
          </button>
        )}
        <Field
          label={t('orPasteImageUrl')}
          hint={t('adm_external_url_or_relative_path_leave_empty_to_use_t')}
        >
          <input
            type="text"
            value={currentUrl}
            onChange={(e) => onUrlChange(e.target.value)}
            className={inputCls}
            placeholder={urlPlaceholder}
            data-testid={urlInputTestId}
            disabled={disabled}
          />
        </Field>
        {disabledHint ? (
          <p className="text-[11.5px] text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-snug">
            {disabledHint}
          </p>
        ) : (
          <div className="text-[11.5px] text-[#71717A] leading-relaxed">
            <strong>{t('tipsColon')}</strong> {tipsText}
          </div>
        )}
      </div>
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────────────
//  Hero Banner Editor — homepage banner (left text block + right photo)
// ─────────────────────────────────────────────────────────────────────────
function HeroEditor({ data, updateHero, uploadHeroImage }) {
  const { t } = useLang();
  const hero = data?.hero || {};
  const enabled = hero.enabled !== false;

  // Build absolute URL for previews when image_url is a relative path
  const apiBase = process.env.REACT_APP_BACKEND_URL || '';
  const toAbs = (u) =>
    !u ? '' : u.startsWith('http') ? u : `${apiBase}${u}`;
  const previewUrlWeb = toAbs(hero.image_url);
  // When sync is on, the mobile card mirrors the web image for accurate preview.
  const previewUrlMobile = hero.sync_mobile_with_web
    ? toAbs(hero.image_url)
    : toAbs(hero.image_url_mobile);

  return (
    <div className="space-y-5">
      <Block
        title={t('adm_hero_banner_homepage')}
        description="Top section of the public homepage. Edit eyebrow, the big 3-line title, the three KPI lines and the background photo. All texts are bilingual (UA + EN)."
      >
        <label className="flex items-center gap-3 text-[14px] text-[#18181B] mb-5 cursor-pointer">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => updateHero('enabled', e.target.checked)}
            className="w-4 h-4 accent-[#18181B] cursor-pointer"
            data-testid="info-hero-enabled"
          />
          <span className="font-medium">{t('showHeroBanner')}</span>
        </label>

        {/* Eyebrow */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-5">
          <Field label="Eyebrow (EN)" hint={t('adm_shown_above_the_big_title_eg_america_korea')}>
            <input
              type="text"
              value={hero.eyebrow_en || ''}
              onChange={(e) => updateHero('eyebrow_en', e.target.value)}
              className={inputCls}
              placeholder={t('adm_america_korea')}
              data-testid="info-hero-eyebrow-en"
            />
          </Field>
          <Field label="Eyebrow (UA)">
            <input
              type="text"
              value={hero.eyebrow_uk || ''}
              onChange={(e) => updateHero('eyebrow_uk', e.target.value)}
              className={inputCls}
              placeholder={t('adm_america_korea_2')}
              data-testid="info-hero-eyebrow-uk"
            />
          </Field>
        </div>

        {/* Title — three lines, line 2 is the yellow accent */}
        <div className="bg-[#FAFAFA] border border-[#E4E4E7] rounded-xl p-4 mb-5">
          <div className="text-[12px] font-semibold text-[#52525B] uppercase tracking-wider mb-3">
            Big title — three lines (line 2 renders in amber)
          </div>
          {[1, 2, 3].map((n) => (
            <div key={n} className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-3 last:mb-0">
              <Field label={`Line ${n} (EN)${n === 2 ? '  •  amber accent' : ''}`}>
                <input
                  type="text"
                  value={hero[`title_line${n}_en`] || ''}
                  onChange={(e) => updateHero(`title_line${n}_en`, e.target.value)}
                  className={inputCls}
                  placeholder={['From auction', 'to keys', 'in your hands'][n - 1]}
                  data-testid={`info-hero-title${n}-en`}
                />
              </Field>
              <Field label={`Line ${n} (UA)`}>
                <input
                  type="text"
                  value={hero[`title_line${n}_uk`] || ''}
                  onChange={(e) => updateHero(`title_line${n}_uk`, e.target.value)}
                  className={inputCls}
                  placeholder={[t('adm3_546405c33b'), t('adm3_ccb59cc168'), t('adm3_b679087e59')][n - 1]}
                  data-testid={`info-hero-title${n}-bg`}
                />
              </Field>
            </div>
          ))}
        </div>

        {/* KPI strip */}
        <div className="bg-[#FAFAFA] border border-[#E4E4E7] rounded-xl p-4 mb-5">
          <div className="text-[12px] font-semibold text-[#52525B] uppercase tracking-wider mb-3">
            {t('adm_kpi_strip_three_short_lines_under_the_title')}
          </div>
          {[1, 2, 3].map((n) => (
            <div key={n} className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-3 last:mb-0">
              <Field label={`KPI ${n} (EN)`}>
                <input
                  type="text"
                  value={hero[`kpi${n}_en`] || ''}
                  onChange={(e) => updateHero(`kpi${n}_en`, e.target.value)}
                  className={inputCls}
                  placeholder={['Over 5,000 cars', 'Real-time bids', '500+ happy clients'][n - 1]}
                  data-testid={`info-hero-kpi${n}-en`}
                />
              </Field>
              <Field label={`KPI ${n} (UA)`}>
                <input
                  type="text"
                  value={hero[`kpi${n}_uk`] || ''}
                  onChange={(e) => updateHero(`kpi${n}_uk`, e.target.value)}
                  className={inputCls}
                  placeholder={[t('adm3_084425742c'), t('adm3_1e2ca583be'), t('adm3_5fe0801150')][n - 1]}
                  data-testid={`info-hero-kpi${n}-bg`}
                />
              </Field>
            </div>
          ))}
        </div>
      </Block>

      <Block
        title={t('backgroundImage')}
        description={t('heroBackgroundDescription')}
        footer={(
          <span>
            <strong>{t('recommendedLabel')}</strong>{' '}
            <span>Web 16:9 — JPG/WebP 1920 × 1080 px. Mobile portrait — JPG/WebP 1080 × 976 px (aspect ≈ 361:326). ≤ 5 MB. sRGB.</span>
          </span>
        )}
      >
        {/* Sync toggle — when ON, the mobile landing reuses the web image
            and the mobile upload is hidden / disabled. Useful when the same
            shot crops well on both form-factors. */}
        <label className="flex items-start gap-3 mb-5 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={hero.sync_mobile_with_web === true}
            onChange={(e) => updateHero('sync_mobile_with_web', e.target.checked)}
            className="w-4 h-4 mt-0.5 accent-[#18181B] cursor-pointer flex-shrink-0"
            data-testid="info-hero-sync-mobile"
          />
          <div className="flex-1 min-w-0">
            <span className="block text-[14px] font-medium text-[#18181B]">
              Use the same image on mobile
            </span>
            <span className="block text-[11.5px] text-[#71717A] mt-0.5 leading-snug">
              When enabled, the mobile landing reuses the web banner and ignores the dedicated mobile upload below.
            </span>
          </div>
        </label>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
          {/* ── WEB (16:9) ────────────────────────────────────────── */}
          <HeroVariantCard
            variant="web"
            aspectClass="aspect-[16/9]"
            label="Web banner · 16:9"
            ratioHint="Recommended 1920 × 1080 px"
            previewUrl={previewUrlWeb}
            currentUrl={hero.image_url || ''}
            eyebrow={hero.eyebrow_en || 'AMERICA | KOREA'}
            onUpload={(f) => uploadHeroImage(f, 'web')}
            onClear={() => updateHero('image_url', '')}
            onUrlChange={(v) => updateHero('image_url', v)}
            urlPlaceholder="/api/static/hero/your-image.jpg"
            previewTestId="info-hero-preview"
            uploadTestId="info-hero-upload-btn"
            removeTestId="info-hero-remove-btn"
            fileInputTestId="info-hero-file-input"
            urlInputTestId="info-hero-image-url"
            tipsText="Compress to keep under 1 MB when possible (TinyPNG / Squoosh). Photos with the subject on the right side work best because the left half of the banner is darkened for legibility."
            t={t}
          />

          {/* ── MOBILE (~ 361:326) ───────────────────────────────── */}
          <HeroVariantCard
            variant="mobile"
            aspectClass="aspect-[361/326]"
            label="Mobile banner · 361 : 326"
            ratioHint="Recommended 1080 × 976 px (or 720 × 650)"
            previewUrl={previewUrlMobile}
            currentUrl={hero.image_url_mobile || ''}
            eyebrow={hero.eyebrow_en || 'AMERICA | KOREA'}
            onUpload={(f) => uploadHeroImage(f, 'mobile')}
            onClear={() => updateHero('image_url_mobile', '')}
            onUrlChange={(v) => updateHero('image_url_mobile', v)}
            urlPlaceholder="/api/static/hero/your-mobile-image.jpg"
            previewTestId="info-hero-mobile-preview"
            uploadTestId="info-hero-mobile-upload-btn"
            removeTestId="info-hero-mobile-remove-btn"
            fileInputTestId="info-hero-mobile-file-input"
            urlInputTestId="info-hero-mobile-image-url"
            tipsText="Mobile crops are nearly square (361:326). Keep the subject centered. The hero shows full-bleed on phones without the left-side darkening overlay used on web."
            mirrorOverlay={false}
            disabled={hero.sync_mobile_with_web === true}
            disabledHint={
              hero.sync_mobile_with_web === true
                ? 'Sync is ON — the mobile landing currently uses the web banner. Turn off the toggle above to upload a dedicated mobile image.'
                : null
            }
            t={t}
          />
        </div>
      </Block>
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────────────
//  FAQ Editor — extracted into a sub-component for clarity
// ─────────────────────────────────────────────────────────────────────────
function FAQEditor({ data, updateFaq, updateFaqItem, addFaqItem, removeFaqItem, moveFaqItem }) {
  const { t } = useLang();
  return (
    <div className="space-y-5">
      <Block
        title={t('faqSectionSettings')}
        description={t('adm_the_faq_block_is_shown_above_the_public_footer_and')}
      >
        <label className="flex items-center gap-3 text-[14px] text-[#18181B] mb-5 cursor-pointer">
          <input
            type="checkbox"
            checked={data?.faq?.enabled !== false}
            onChange={(e) => updateFaq('enabled', e.target.checked)}
            className="w-4 h-4 accent-[#18181B] cursor-pointer"
            data-testid="info-faq-enabled"
          />
          <span className="font-medium">{t('showFaqBlock')}</span>
        </label>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="Section title (EN)">
            <input
              type="text"
              value={data?.faq?.title_en || ''}
              onChange={(e) => updateFaq('title_en', e.target.value)}
              className={inputCls}
              placeholder="FAQ"
              data-testid="info-faq-title-en"
            />
          </Field>
          <Field label="Section title (UA)">
            <input
              type="text"
              value={data?.faq?.title_uk || ''}
              onChange={(e) => updateFaq('title_uk', e.target.value)}
              className={inputCls}
              placeholder={t('adm_frequently_asked_questions')}
              data-testid="info-faq-title-uk"
            />
          </Field>
        </div>
      </Block>

      <Block
        title={t('adm_questions_answers')}
        description={`${(data?.faq?.items || []).length} item${(data?.faq?.items || []).length === 1 ? '' : 's'}. Reorder via arrows. Disabled items stay in storage but are hidden from the public site.`}
        footer={
          <div className="flex items-center justify-between">
            <span>Tip: HTML formatting (bold, lists, links) is supported in answers.</span>
            <button
              onClick={addFaqItem}
              className="inline-flex items-center gap-1.5 px-3 h-8 rounded-md bg-[#18181B] hover:bg-black text-white text-[12px] font-semibold transition-colors"
              data-testid="info-faq-add"
            >
              <Plus size={14} weight="bold" />{t('addQuestionAction')}</button>
          </div>
        }
      >
        {(data?.faq?.items || []).length === 0 && (
          <div className="text-center py-10 text-[#71717A]">
            <Question size={28} className="mx-auto mb-2" />
            <p className="text-[13px]">{t('noFaqYetClick')}<strong>{t('addQuestionAction')}</strong> {t('adm_below_to_create_your_first_item')}</p>
          </div>
        )}

        <div className="space-y-3">
          {(data?.faq?.items || []).map((item, idx) => {
            const isEnabled = item.enabled !== false;
            return (
              <div
                key={item.id || idx}
                className={`border rounded-xl overflow-hidden transition-colors ${
                  isEnabled ? 'border-[#E4E4E7] bg-white' : 'border-[#E4E4E7] bg-[#FAFAFA] opacity-80'
                }`}
                data-testid={`info-faq-item-${idx}`}
              >
                <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-[#F4F4F5] bg-[#FAFAFA]">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="inline-flex items-center justify-center w-6 h-6 rounded-md bg-[#18181B] text-white text-[11px] font-bold shrink-0">
                      {idx + 1}
                    </span>
                    <span className="text-[13px] font-semibold text-[#18181B] truncate">
                      {item.question_en || item.question_uk || <em className="text-[#A1A1AA] font-normal">{t('untitledQuestion')}</em>}
                    </span>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <button onClick={() => updateFaqItem(idx, { enabled: !isEnabled })} className="inline-flex items-center justify-center w-8 h-8 rounded-md text-[#52525B] hover:bg-[#F4F4F5] transition-colors" title={isEnabled ? 'Hide' : 'Show'} data-testid={`info-faq-toggle-${idx}`}>
                      {isEnabled ? <Eye size={16} /> : <EyeSlash size={16} />}
                    </button>
                    <button onClick={() => moveFaqItem(idx, -1)} disabled={idx === 0} className="inline-flex items-center justify-center w-8 h-8 rounded-md text-[#52525B] hover:bg-[#F4F4F5] transition-colors disabled:opacity-30 disabled:cursor-not-allowed" title={t('moveUpAction')} data-testid={`info-faq-up-${idx}`}>
                      <ArrowUp size={16} />
                    </button>
                    <button onClick={() => moveFaqItem(idx, +1)} disabled={idx === (data?.faq?.items || []).length - 1} className="inline-flex items-center justify-center w-8 h-8 rounded-md text-[#52525B] hover:bg-[#F4F4F5] transition-colors disabled:opacity-30 disabled:cursor-not-allowed" title={t('moveDownAction')} data-testid={`info-faq-down-${idx}`}>
                      <ArrowDown size={16} />
                    </button>
                    <button
                      onClick={() => {
                        if (window.confirm('Remove this FAQ item?')) removeFaqItem(idx);
                      }}
                      className="inline-flex items-center justify-center w-8 h-8 rounded-md text-[#DC2626] hover:bg-[#FEE2E2] transition-colors"
                      title={t('deleteAction')}
                      data-testid={`info-faq-delete-${idx}`}
                    >
                      <Trash size={16} />
                    </button>
                  </div>
                </div>

                <div className="p-4 space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <Field label="Question (EN)">
                      <input
                        type="text"
                        value={item.question_en || ''}
                        onChange={(e) => updateFaqItem(idx, { question_en: e.target.value })}
                        className={inputCls}
                        data-testid={`info-faq-q-en-${idx}`}
                      />
                    </Field>
                    <Field label="Question (UA)">
                      <input
                        type="text"
                        value={item.question_uk || ''}
                        onChange={(e) => updateFaqItem(idx, { question_uk: e.target.value })}
                        className={inputCls}
                        data-testid={`info-faq-q-uk-${idx}`}
                      />
                    </Field>
                  </div>

                  <div>
                    <span className="block text-[12px] font-semibold text-[#52525B] mb-1.5 uppercase tracking-wider">Answer (EN)</span>
                    <div className="bibi-admin-quill">
                      <ReactQuill
                        theme="snow"
                        value={item.answer_en || ''}
                        onChange={(v) => updateFaqItem(idx, { answer_en: v })}
                        modules={quillModules}
                      />
                    </div>
                  </div>

                  <div>
                    <span className="block text-[12px] font-semibold text-[#52525B] mb-1.5 uppercase tracking-wider">Answer (UA)</span>
                    <div className="bibi-admin-quill">
                      <ReactQuill
                        theme="snow"
                        value={item.answer_uk || ''}
                        onChange={(v) => updateFaqItem(idx, { answer_uk: v })}
                        modules={quillModules}
                      />
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {(data?.faq?.items || []).length > 0 && (
          <div className="mt-4 flex justify-end">
            <button
              onClick={addFaqItem}
              className="inline-flex items-center gap-1.5 px-3.5 h-9 rounded-lg border border-dashed border-[#D4D4D8] text-[#52525B] hover:border-[#18181B] hover:text-[#18181B] text-[12.5px] font-medium transition-colors"
              data-testid="info-faq-add-bottom"
            >
              <Plus size={14} /> {t('adm_add_another_question')}
            </button>
          </div>
        )}
      </Block>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
//  Reviews Editor — NEW
// ─────────────────────────────────────────────────────────────────────────
function ReviewsEditor({
  data,
  updateReviews,
  updateReviewItem,
  addReviewItem,
  removeReviewItem,
  moveReviewItem,
  uploadReviewImage,
}) {
  const { t } = useLang();
  const items = data?.reviews?.items || [];
  const enabledCount = items.filter((i) => i.enabled !== false).length;
  const baseline = Number(data?.reviews?.baseline_happy_customers) || 0;
  const totalCounter = baseline + enabledCount;

  return (
    <div className="space-y-5">
      <Block
        title={t('adm_reviews_block_general_settings')}
        description={t('adm_controls_the_our_clients_say_section_on_the_public')}
      >
        <label className="flex items-center gap-3 text-[14px] text-[#18181B] mb-5 cursor-pointer">
          <input
            type="checkbox"
            checked={data?.reviews?.enabled !== false}
            onChange={(e) => updateReviews('enabled', e.target.checked)}
            className="w-4 h-4 accent-[#18181B] cursor-pointer"
            data-testid="info-reviews-enabled"
          />
          <span className="font-medium">{t('showReviewsBlock')}</span>
        </label>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="Section title (EN)">
            <input
              type="text"
              value={data?.reviews?.title_en || ''}
              onChange={(e) => updateReviews('title_en', e.target.value)}
              className={inputCls}
              placeholder={t('ourClientsSay')}
              data-testid="info-reviews-title-en"
            />
          </Field>
          <Field label="Section title (UA)">
            <input
              type="text"
              value={data?.reviews?.title_uk || ''}
              onChange={(e) => updateReviews('title_uk', e.target.value)}
              className={inputCls}
              placeholder={t('adm_what_our_clients_say')}
              data-testid="info-reviews-title-uk"
            />
          </Field>
          <Field label="Subtitle (EN)" hint={t('adm_the_yellow_heading_shown_on_the_left_side_of_the_c')}>
            <input
              type="text"
              value={data?.reviews?.subtitle_en || ''}
              onChange={(e) => updateReviews('subtitle_en', e.target.value)}
              className={inputCls}
              placeholder={t('whatCustomersSay')}
            />
          </Field>
          <Field label="Subtitle (UA)">
            <input
              type="text"
              value={data?.reviews?.subtitle_uk || ''}
              onChange={(e) => updateReviews('subtitle_uk', e.target.value)}
              className={inputCls}
              placeholder={t('adm_what_clients_say_after_working_with_us')}
            />
          </Field>
        </div>
      </Block>

      <Block
        title={t('googleBadge')}
        description={t('adm_the_google_rating_badge_shown_at_the_topleft_of_th')}
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Field label="Rating (1.0 – 5.0)">
            <input
              type="number"
              step="0.1"
              min="0"
              max="5"
              value={data?.reviews?.google_rating ?? 4.9}
              onChange={(e) => updateReviews('google_rating', parseFloat(e.target.value) || 0)}
              className={inputCls}
              data-testid="info-reviews-google-rating"
            />
          </Field>
          <Field label={t('reviewsCountLabel')}>
            <input
              type="number"
              min="0"
              value={data?.reviews?.google_reviews_count ?? 0}
              onChange={(e) => updateReviews('google_reviews_count', parseInt(e.target.value, 10) || 0)}
              className={inputCls}
              data-testid="info-reviews-google-count"
            />
          </Field>
          <Field label={t('adm_31_google_reviews_link_url')} hint={t('adm_opens_when_the_badge_is_clicked')}>
            <input
              type="text"
              value={data?.reviews?.google_reviews_url || ''}
              onChange={(e) => updateReviews('google_reviews_url', e.target.value)}
              className={inputCls}
              placeholder="https://g.page/r/..."
              data-testid="info-reviews-google-url"
            />
          </Field>
        </div>
      </Block>

      <Block
        title='Happy customers counter ("460 +")'
        description='The big ghost number behind the cards. Final value shown publicly = baseline + count of enabled reviews below.'
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-end">
          <Field label={t('baselineValue')} hint={t('adm_real_number_of_happy_customers_before_the_reviews')}>
            <input
              type="number"
              min="0"
              value={baseline}
              onChange={(e) => updateReviews('baseline_happy_customers', parseInt(e.target.value, 10) || 0)}
              className={inputCls}
              data-testid="info-reviews-baseline"
            />
          </Field>
          <div className="flex items-center gap-3 p-4 bg-[#FAFAFA] border border-[#E4E4E7] rounded-lg">
            <div className="flex items-center justify-center w-12 h-12 rounded-lg bg-[#FEAE00]/15 text-[#FEAE00]">
              <User size={22} weight="bold" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[11.5px] uppercase tracking-wider text-[#71717A] font-semibold">{t('publicNumber')}</div>
              <div className="text-[24px] font-bold text-[#18181B] leading-tight">
                {totalCounter} <span className="text-[#FEAE00]">+</span>
              </div>
              <div className="text-[12px] text-[#71717A]">{baseline} baseline + {enabledCount} active review{enabledCount === 1 ? '' : 's'}</div>
            </div>
          </div>
        </div>
      </Block>

      <Block
        title={t('reviewsListLabel')}
        description={`${items.length} review${items.length === 1 ? '' : 's'}. Disabled reviews stay in storage but are hidden from the public site and excluded from the counter.`}
        footer={
          <div className="flex items-center justify-between">
            <span>Tip: square images (~300×300) work best for the avatar.</span>
            <button
              onClick={addReviewItem}
              className="inline-flex items-center gap-1.5 px-3 h-8 rounded-md bg-[#18181B] hover:bg-black text-white text-[12px] font-semibold transition-colors"
              data-testid="info-reviews-add"
            >
              <Plus size={14} weight="bold" />{t('addReviewAction')}</button>
          </div>
        }
      >
        {items.length === 0 && (
          <div className="text-center py-10 text-[#71717A]">
            <ChatCircle size={28} className="mx-auto mb-2" />
            <p className="text-[13px]">{t('noReviewsYetClick')}<strong>{t('addReviewAction')}</strong> {t('adm_below_to_create_your_first_one')}</p>
          </div>
        )}

        <div className="space-y-4">
          {items.map((item, idx) => (
            <ReviewItemCard
              key={item.id || idx}
              idx={idx}
              total={items.length}
              item={item}
              onChange={(patch) => updateReviewItem(idx, patch)}
              onMove={(dir) => moveReviewItem(idx, dir)}
              onRemove={() => {
                if (window.confirm('Remove this review?')) removeReviewItem(idx);
              }}
              onUpload={(file) => uploadReviewImage(idx, file)}
            />
          ))}
        </div>

        {items.length > 0 && (
          <div className="mt-4 flex justify-end">
            <button
              onClick={addReviewItem}
              className="inline-flex items-center gap-1.5 px-3.5 h-9 rounded-lg border border-dashed border-[#D4D4D8] text-[#52525B] hover:border-[#18181B] hover:text-[#18181B] text-[12.5px] font-medium transition-colors"
              data-testid="info-reviews-add-bottom"
            >
              <Plus size={14} /> {t('adm_add_another_review')}
            </button>
          </div>
        )}
      </Block>
    </div>
  );
}

function ReviewItemCard({ idx, total, item, onChange, onMove, onRemove, onUpload }) {
  const { t } = useLang();
  const fileRef = useRef(null);
  const isEnabled = item.enabled !== false;
  const fullImageUrl = item.image_url
    ? (/^https?:\/\//i.test(item.image_url) ? item.image_url : `${API_URL}${item.image_url}`)
    : '';

  return (
    <div
      className={`border rounded-xl overflow-hidden transition-colors ${
        isEnabled ? 'border-[#E4E4E7] bg-white' : 'border-[#E4E4E7] bg-[#FAFAFA] opacity-80'
      }`}
      data-testid={`info-reviews-item-${idx}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-[#F4F4F5] bg-[#FAFAFA]">
        <div className="flex items-center gap-2 min-w-0">
          <span className="inline-flex items-center justify-center w-6 h-6 rounded-md bg-[#18181B] text-white text-[11px] font-bold shrink-0">
            {idx + 1}
          </span>
          <span className="text-[13px] font-semibold text-[#18181B] truncate">
            {item.name || <em className="text-[#A1A1AA] font-normal">{t('unnamedReviewer')}</em>}
          </span>
          {isEnabled && (
            <span className="inline-flex items-center gap-0.5 text-[#FEAE00]">
              {[...Array(Math.floor(Math.max(0, Math.min(5, Number(item.rating) || 0))))].map((_, s) => (
                <Star key={s} size={12} weight="fill" />
              ))}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={() => onChange({ enabled: !isEnabled })}
            className="inline-flex items-center justify-center w-8 h-8 rounded-md text-[#52525B] hover:bg-[#F4F4F5] transition-colors"
            title={isEnabled ? 'Hide from public site' : 'Show on public site'}
            data-testid={`info-reviews-toggle-${idx}`}
          >
            {isEnabled ? <Eye size={16} /> : <EyeSlash size={16} />}
          </button>
          <button
            onClick={() => onMove(-1)}
            disabled={idx === 0}
            className="inline-flex items-center justify-center w-8 h-8 rounded-md text-[#52525B] hover:bg-[#F4F4F5] transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            title={t('moveUpAction')}
            data-testid={`info-reviews-up-${idx}`}
          >
            <ArrowUp size={16} />
          </button>
          <button
            onClick={() => onMove(+1)}
            disabled={idx === total - 1}
            className="inline-flex items-center justify-center w-8 h-8 rounded-md text-[#52525B] hover:bg-[#F4F4F5] transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            title={t('moveDownAction')}
            data-testid={`info-reviews-down-${idx}`}
          >
            <ArrowDown size={16} />
          </button>
          <button
            onClick={onRemove}
            className="inline-flex items-center justify-center w-8 h-8 rounded-md text-[#DC2626] hover:bg-[#FEE2E2] transition-colors"
            title={t('deleteAction')}
            data-testid={`info-reviews-delete-${idx}`}
          >
            <Trash size={16} />
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="p-4 grid grid-cols-1 md:grid-cols-[180px_1fr] gap-4">
        {/* Avatar uploader */}
        <div>
          <span className="block text-[12px] font-semibold text-[#52525B] mb-1.5 uppercase tracking-wider">{t('photoLabel')}</span>
          <div className="aspect-square w-full max-w-[180px] rounded-xl border border-[#E4E4E7] bg-[#F4F4F5] flex items-center justify-center overflow-hidden mb-2">
            {fullImageUrl ? (
              <img src={fullImageUrl} alt={item.name ? `${item.name}` : 'reviewer'} className="w-full h-full object-cover" />
            ) : (
              <ImageIcon size={36} className="text-[#A1A1AA]" />
            )}
          </div>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onUpload(f);
              if (fileRef.current) fileRef.current.value = '';
            }}
            data-testid={`info-reviews-file-${idx}`}
          />
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              className="inline-flex items-center gap-1.5 px-3 h-9 rounded-lg border border-[#E4E4E7] bg-white text-[#52525B] hover:bg-[#FAFAFA] hover:border-[#D4D4D8] text-[12.5px] font-medium transition-colors"
              data-testid={`info-reviews-upload-${idx}`}
            >
              <UploadSimple size={14} /> {fullImageUrl ? 'Replace' : 'Upload'}
            </button>
            {fullImageUrl && (
              <button
                type="button"
                onClick={() => onChange({ image_url: '' })}
                className="inline-flex items-center justify-center w-9 h-9 rounded-lg border border-[#E4E4E7] bg-white text-[#DC2626] hover:bg-[#FEE2E2] hover:border-[#FCA5A5] transition-colors"
                title={t('removePhoto')}
                data-testid={`info-reviews-clear-img-${idx}`}
              >
                <Trash size={14} />
              </button>
            )}
          </div>
        </div>

        {/* Fields */}
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Field label="Reviewer name (EN)" hint={t('adm_shown_when_the_visitors_language_is_english')}>
              <input
                type="text"
                value={item.name || ''}
                onChange={(e) => onChange({ name: e.target.value })}
                className={inputCls}
                placeholder={t('placeholderGeorgi')}
                data-testid={`info-reviews-name-${idx}`}
              />
            </Field>
            <Field label="Reviewer name (UA)" hint="Те саме ім'я українською">
              <input
                type="text"
                value={item.name_uk || ''}
                onChange={(e) => onChange({ name_uk: e.target.value })}
                className={inputCls}
                placeholder={t('adm_georgi')}
                data-testid={`info-reviews-name-uk-${idx}`}
              />
            </Field>
            <Field label="Rating (1–5)" hint="Крок 0.5 (напр. 4.5)">
              <input
                type="number"
                min="1"
                max="5"
                step="0.5"
                value={item.rating ?? 5}
                onChange={(e) => onChange({ rating: Math.max(1, Math.min(5, parseFloat(e.target.value) || 5)) })}
                className={inputCls}
                data-testid={`info-reviews-rating-${idx}`}
              />
            </Field>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Company / role (EN)" hint="Shown under the reviewer name">
              <input
                type="text"
                value={item.role_en || ''}
                onChange={(e) => onChange({ role_en: e.target.value })}
                className={inputCls}
                placeholder="Director, MedCenter"
                data-testid={`info-reviews-role-en-${idx}`}
              />
            </Field>
            <Field label="Company / role (UA)" hint="Показується під іменем">
              <input
                type="text"
                value={item.role_uk || ''}
                onChange={(e) => onChange({ role_uk: e.target.value })}
                className={inputCls}
                placeholder="Директор, МедЦентр"
                data-testid={`info-reviews-role-uk-${idx}`}
              />
            </Field>
          </div>

          <Field label="Review (EN)" hint={t('adm_plain_text_use_linebreaks_for_paragraphs')}>
            <textarea
              rows={4}
              value={item.text_en || ''}
              onChange={(e) => onChange({ text_en: e.target.value })}
              className={textareaCls}
              placeholder={t('adm_i_really_liked_the_approach_everything_was_clear_t')}
              data-testid={`info-reviews-text-en-${idx}`}
            />
          </Field>
          <Field label="Review (UA)" hint="Той самий текст українською">
            <textarea
              rows={4}
              value={item.text_uk || ''}
              onChange={(e) => onChange({ text_uk: e.target.value })}
              className={textareaCls}
              placeholder={t('adm_i_liked_the_approach_everything_was_clear_transpar')}
              data-testid={`info-reviews-text-uk-${idx}`}
            />
          </Field>
        </div>
      </div>
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────────────
//  Before / After Editor — NEW
// ─────────────────────────────────────────────────────────────────────────
function BeforeAfterEditor({
  data,
  updateBeforeAfter,
  updateBeforeAfterItem,
  addBeforeAfterItem,
  removeBeforeAfterItem,
  moveBeforeAfterItem,
  uploadBeforeAfterImage,
}) {
  const { t } = useLang();
  const items = data?.before_after?.items || [];
  return (
    <div className="space-y-5">
      <Block
        title={t('adm_before_after_block_general_settings')}
        description='Controls the "BEFORE AND AFTER" carousel on the public homepage. Each card shows two photos (auction state vs. finished car) plus model, dates and price.'
      >
        <label className="flex items-center gap-3 text-[14px] text-[#18181B] mb-5 cursor-pointer">
          <input
            type="checkbox"
            checked={data?.before_after?.enabled !== false}
            onChange={(e) => updateBeforeAfter('enabled', e.target.checked)}
            className="w-4 h-4 accent-[#18181B] cursor-pointer"
            data-testid="info-ba-enabled"
          />
          <span className="font-medium">{t('adm_show_before_after_block_on_the_public_homepage')}</span>
        </label>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="Section title (EN)">
            <input
              type="text"
              value={data?.before_after?.title_en || ''}
              onChange={(e) => updateBeforeAfter('title_en', e.target.value)}
              className={inputCls}
              placeholder={t('beforeAndAfter')}
              data-testid="info-ba-title-en"
            />
          </Field>
          <Field label="Section title (UA)">
            <input
              type="text"
              value={data?.before_after?.title_uk || ''}
              onChange={(e) => updateBeforeAfter('title_uk', e.target.value)}
              className={inputCls}
              placeholder={t('adm_before_and_after')}
              data-testid="info-ba-title-uk"
            />
          </Field>
          <Field label="Subtitle (EN) — yellow line">
            <input
              type="text"
              value={data?.before_after?.subtitle_yellow_en || ''}
              onChange={(e) => updateBeforeAfter('subtitle_yellow_en', e.target.value)}
              className={inputCls}
              placeholder={t('ourClientsReceive')}
            />
          </Field>
          <Field label="Subtitle (UA) — yellow line">
            <input
              type="text"
              value={data?.before_after?.subtitle_yellow_uk || ''}
              onChange={(e) => updateBeforeAfter('subtitle_yellow_uk', e.target.value)}
              className={inputCls}
              placeholder={t('adm_our_customers_receive')}
            />
          </Field>
          <Field label="Subtitle (EN) — white line">
            <input
              type="text"
              value={data?.before_after?.subtitle_white_en || ''}
              onChange={(e) => updateBeforeAfter('subtitle_white_en', e.target.value)}
              className={inputCls}
              placeholder="the best service"
            />
          </Field>
          <Field label="Subtitle (UA) — white line">
            <input
              type="text"
              value={data?.before_after?.subtitle_white_uk || ''}
              onChange={(e) => updateBeforeAfter('subtitle_white_uk', e.target.value)}
              className={inputCls}
              placeholder={t('adm_the_best_service')}
            />
          </Field>
        </div>
      </Block>

      <Block
        title={t('cardsLabel')}
        description={`${items.length} card${items.length === 1 ? '' : 's'}. Disabled cards stay in storage but are hidden from the public site.`}
        footer={
          <div className="flex items-center justify-between">
            <span>Tip: use a 4:5 portrait ratio (~1080×1350) for crisp before/after images.</span>
            <button
              onClick={addBeforeAfterItem}
              className="inline-flex items-center gap-1.5 px-3 h-8 rounded-md bg-[#18181B] hover:bg-black text-white text-[12px] font-semibold transition-colors"
              data-testid="info-ba-add"
            >
              <Plus size={14} weight="bold" />{t('addCardAction')}</button>
          </div>
        }
      >
        {items.length === 0 && (
          <div className="text-center py-10 text-[#71717A]">
            <ImageIcon size={28} className="mx-auto mb-2" />
            <p className="text-[13px]">{t('noCardsYetClick')}<strong>{t('addCardAction')}</strong> {t('adm_to_create_your_first_one')}</p>
          </div>
        )}

        <div className="space-y-4">
          {items.map((item, idx) => (
            <BeforeAfterItemCard
              key={item.id || idx}
              idx={idx}
              total={items.length}
              item={item}
              onChange={(patch) => updateBeforeAfterItem(idx, patch)}
              onMove={(dir) => moveBeforeAfterItem(idx, dir)}
              onRemove={() => {
                if (window.confirm('Remove this Before/After card?')) removeBeforeAfterItem(idx);
              }}
              onUpload={(side, file) => uploadBeforeAfterImage(idx, side, file)}
            />
          ))}
        </div>

        {items.length > 0 && (
          <div className="mt-4 flex justify-end">
            <button
              onClick={addBeforeAfterItem}
              className="inline-flex items-center gap-1.5 px-3.5 h-9 rounded-lg border border-dashed border-[#D4D4D8] text-[#52525B] hover:border-[#18181B] hover:text-[#18181B] text-[12.5px] font-medium transition-colors"
              data-testid="info-ba-add-bottom"
            >
              <Plus size={14} /> {t('adm_add_another_card')}
            </button>
          </div>
        )}
      </Block>
    </div>
  );
}

function BeforeAfterImagePicker({ label, url, onUpload, onClear, testid }) {
  const { t } = useLang();
  const fileRef = useRef(null);
  const fullUrl = url ? (/^https?:\/\//i.test(url) ? url : `${API_URL}${url}`) : '';
  return (
    <div>
      <span className="block text-[12px] font-semibold text-[#52525B] mb-1.5 uppercase tracking-wider">{label}</span>
      <div className="aspect-[4/5] w-full rounded-xl border border-[#E4E4E7] bg-[#F4F4F5] flex items-center justify-center overflow-hidden mb-2">
        {fullUrl ? (
          <img src={fullUrl} alt={label} className="w-full h-full object-cover" />
        ) : (
          <ImageIcon size={36} className="text-[#A1A1AA]" />
        )}
      </div>
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onUpload(f);
          if (fileRef.current) fileRef.current.value = '';
        }}
        data-testid={`${testid}-file`}
      />
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          className="inline-flex items-center gap-1.5 px-3 h-9 rounded-lg border border-[#E4E4E7] bg-white text-[#52525B] hover:bg-[#FAFAFA] hover:border-[#D4D4D8] text-[12.5px] font-medium transition-colors"
          data-testid={`${testid}-upload`}
        >
          <UploadSimple size={14} /> {fullUrl ? 'Replace' : 'Upload'}
        </button>
        {fullUrl && (
          <button
            type="button"
            onClick={onClear}
            className="inline-flex items-center justify-center w-9 h-9 rounded-lg border border-[#E4E4E7] bg-white text-[#DC2626] hover:bg-[#FEE2E2] hover:border-[#FCA5A5] transition-colors"
            title={t('removePhoto')}
            data-testid={`${testid}-clear`}
          >
            <Trash size={14} />
          </button>
        )}
      </div>
    </div>
  );
}

function BeforeAfterItemCard({ idx, total, item, onChange, onMove, onRemove, onUpload }) {
  const { t } = useLang();
  const isEnabled = item.enabled !== false;
  return (
    <div
      className={`border rounded-xl overflow-hidden transition-colors ${
        isEnabled ? 'border-[#E4E4E7] bg-white' : 'border-[#E4E4E7] bg-[#FAFAFA] opacity-80'
      }`}
      data-testid={`info-ba-item-${idx}`}
    >
      <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-[#F4F4F5] bg-[#FAFAFA]">
        <div className="flex items-center gap-2 min-w-0">
          <span className="inline-flex items-center justify-center w-6 h-6 rounded-md bg-[#18181B] text-white text-[11px] font-bold shrink-0">
            {idx + 1}
          </span>
          <span className="text-[13px] font-semibold text-[#18181B] truncate">
            {item.model || <em className="text-[#A1A1AA] font-normal">{t('unnamedModel')}</em>}
          </span>
          {item.price && (
            <span className="text-[11.5px] text-[#FEAE00] font-semibold ml-2 truncate">{item.price}</span>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button onClick={() => onChange({ enabled: !isEnabled })} className="inline-flex items-center justify-center w-8 h-8 rounded-md text-[#52525B] hover:bg-[#F4F4F5] transition-colors" title={isEnabled ? 'Hide' : 'Show'} data-testid={`info-ba-toggle-${idx}`}>
            {isEnabled ? <Eye size={16} /> : <EyeSlash size={16} />}
          </button>
          <button onClick={() => onMove(-1)} disabled={idx === 0} className="inline-flex items-center justify-center w-8 h-8 rounded-md text-[#52525B] hover:bg-[#F4F4F5] transition-colors disabled:opacity-30 disabled:cursor-not-allowed" title={t('moveUpAction')} data-testid={`info-ba-up-${idx}`}>
            <ArrowUp size={16} />
          </button>
          <button onClick={() => onMove(+1)} disabled={idx === total - 1} className="inline-flex items-center justify-center w-8 h-8 rounded-md text-[#52525B] hover:bg-[#F4F4F5] transition-colors disabled:opacity-30 disabled:cursor-not-allowed" title={t('moveDownAction')} data-testid={`info-ba-down-${idx}`}>
            <ArrowDown size={16} />
          </button>
          <button onClick={onRemove} className="inline-flex items-center justify-center w-8 h-8 rounded-md text-[#DC2626] hover:bg-[#FEE2E2] transition-colors" title={t('deleteAction')} data-testid={`info-ba-delete-${idx}`}>
            <Trash size={16} />
          </button>
        </div>
      </div>

      <div className="p-4 grid grid-cols-1 md:grid-cols-[1fr_1fr_1fr] gap-4">
        <BeforeAfterImagePicker
          label='"Before" photo (at auction)'
          url={item.before_image_url}
          onUpload={(f) => onUpload('before', f)}
          onClear={() => onChange({ before_image_url: '' })}
          testid={`info-ba-before-${idx}`}
        />
        <BeforeAfterImagePicker
          label='"After" photo (finished car)'
          url={item.after_image_url}
          onUpload={(f) => onUpload('after', f)}
          onClear={() => onChange({ after_image_url: '' })}
          testid={`info-ba-after-${idx}`}
        />

        <div className="space-y-4">
          <Field label={t('adm_model_title')}>
            <input
              type="text"
              value={item.model || ''}
              onChange={(e) => onChange({ model: e.target.value })}
              className={inputCls}
              placeholder={t('adm_bmw_328')}
              data-testid={`info-ba-model-${idx}`}
            />
          </Field>
          <Field label={t('orderDate')} hint={t('adm_free_text_eg_12122025')}>
            <input
              type="text"
              value={item.order_date || ''}
              onChange={(e) => onChange({ order_date: e.target.value })}
              className={inputCls}
              placeholder="12.12.2025"
              data-testid={`info-ba-order-date-${idx}`}
            />
          </Field>
          <Field label={t('dateOfFinishedCar')}>
            <input
              type="text"
              value={item.finished_date || ''}
              onChange={(e) => onChange({ finished_date: e.target.value })}
              className={inputCls}
              placeholder="12.04.2026"
              data-testid={`info-ba-finished-date-${idx}`}
            />
          </Field>
          <Field label="Ціна / вартість">
            <input
              type="text"
              value={item.price || ''}
              onChange={(e) => onChange({ price: e.target.value })}
              className={inputCls}
              placeholder={t('adm_6500_euro')}
              data-testid={`info-ba-price-${idx}`}
            />
          </Field>
        </div>
      </div>
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────────────
//  Partners Editor — NEW
//  Admin-managed partner / client logo cards shown on the public homepage.
//  Each item: bilingual name + short description, uploaded logo, outbound
//  link (opens in a new tab), enable toggle and manual ordering (↑/↓).
// ─────────────────────────────────────────────────────────────────────────
function PartnersEditor({
  data,
  updatePartners,
  updatePartnerItem,
  addPartnerItem,
  removePartnerItem,
  movePartnerItem,
  uploadPartnerAsset,
}) {
  const items = data?.partners?.items || [];
  const enabledCount = items.filter((i) => i.enabled !== false).length;

  return (
    <div className="space-y-5">
      <Block
        title="Partners — general settings"
        description="Controls the “Our partners” section on the public homepage. Cards are clickable and open the partner link in a new browser tab."
      >
        <label className="flex items-center gap-3 text-[14px] text-[#18181B] mb-5 cursor-pointer">
          <input
            type="checkbox"
            checked={data?.partners?.enabled !== false}
            onChange={(e) => updatePartners('enabled', e.target.checked)}
            className="w-4 h-4 accent-[#18181B] cursor-pointer"
            data-testid="info-partners-enabled"
          />
          <span className="font-medium">Show the partners section on the public site</span>
        </label>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="Section title (UA)">
            <input
              type="text"
              value={data?.partners?.title_uk || ''}
              onChange={(e) => updatePartners('title_uk', e.target.value)}
              className={inputCls}
              placeholder="Наші партнери"
              data-testid="info-partners-title-uk"
            />
          </Field>
          <Field label="Section title (EN)">
            <input
              type="text"
              value={data?.partners?.title_en || ''}
              onChange={(e) => updatePartners('title_en', e.target.value)}
              className={inputCls}
              placeholder="Our partners"
              data-testid="info-partners-title-en"
            />
          </Field>
          <Field label="Subtitle (UA)">
            <input
              type="text"
              value={data?.partners?.subtitle_uk || ''}
              onChange={(e) => updatePartners('subtitle_uk', e.target.value)}
              className={inputCls}
              placeholder="Компанії, що довіряють ECO.NOVA"
              data-testid="info-partners-subtitle-uk"
            />
          </Field>
          <Field label="Subtitle (EN)">
            <input
              type="text"
              value={data?.partners?.subtitle_en || ''}
              onChange={(e) => updatePartners('subtitle_en', e.target.value)}
              className={inputCls}
              placeholder="Companies that trust ECO.NOVA"
              data-testid="info-partners-subtitle-en"
            />
          </Field>
        </div>
      </Block>

      <Block
        title="Partner cards"
        description={`${items.length} partner${items.length === 1 ? '' : 's'} (${enabledCount} active). Disabled partners stay in storage but are hidden from the public site.`}
        footer={
          <div className="flex items-center justify-between">
            <span>Tip: a wide landscape photo (≈ 800×500) works best as the card image; the logo is an optional small badge.</span>
            <button
              onClick={addPartnerItem}
              className="inline-flex items-center gap-1.5 px-3 h-8 rounded-md bg-[#18181B] hover:bg-black text-white text-[12px] font-semibold transition-colors"
              data-testid="info-partners-add"
            >
              <Plus size={14} weight="bold" /> Add partner
            </button>
          </div>
        }
      >
        {items.length === 0 && (
          <div className="text-center py-10 text-[#71717A]">
            <Handshake size={28} className="mx-auto mb-2" />
            <p className="text-[13px]">No partners yet. Click <strong>Add partner</strong> to create your first card.</p>
          </div>
        )}

        <div className="space-y-4">
          {items.map((item, idx) => (
            <PartnerItemCard
              key={item.id || idx}
              idx={idx}
              total={items.length}
              item={item}
              onChange={(patch) => updatePartnerItem(idx, patch)}
              onMove={(dir) => movePartnerItem(idx, dir)}
              onRemove={() => {
                if (window.confirm('Remove this partner?')) removePartnerItem(idx);
              }}
              onUpload={(field, file) => uploadPartnerAsset(idx, field, file)}
            />
          ))}
        </div>

        {items.length > 0 && (
          <div className="mt-4 flex justify-end">
            <button
              onClick={addPartnerItem}
              className="inline-flex items-center gap-1.5 px-3.5 h-9 rounded-lg border border-dashed border-[#D4D4D8] text-[#52525B] hover:border-[#18181B] hover:text-[#18181B] text-[12.5px] font-medium transition-colors"
              data-testid="info-partners-add-bottom"
            >
              <Plus size={14} /> Add another partner
            </button>
          </div>
        )}
      </Block>
    </div>
  );
}

function PartnerItemCard({ idx, total, item, onChange, onMove, onRemove, onUpload }) {
  const imgRef = useRef(null);
  const logoRef = useRef(null);
  const isEnabled = item.enabled !== false;
  const fullImageUrl = item.image_url
    ? (/^https?:\/\//i.test(item.image_url) ? item.image_url : `${API_URL}${item.image_url}`)
    : '';
  const fullLogoUrl = item.logo_url
    ? (/^https?:\/\//i.test(item.logo_url) ? item.logo_url : `${API_URL}${item.logo_url}`)
    : '';
  const linkOk = !item.link || /^https?:\/\//i.test(item.link);

  return (
    <div
      className={`border rounded-xl overflow-hidden transition-colors ${
        isEnabled ? 'border-[#E4E4E7] bg-white' : 'border-[#E4E4E7] bg-[#FAFAFA] opacity-80'
      }`}
      data-testid={`info-partners-item-${idx}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-[#F4F4F5] bg-[#FAFAFA]">
        <div className="flex items-center gap-2 min-w-0">
          <span className="inline-flex items-center justify-center w-6 h-6 rounded-md bg-[#18181B] text-white text-[11px] font-bold shrink-0">
            {idx + 1}
          </span>
          <span className="text-[13px] font-semibold text-[#18181B] truncate">
            {item.name_uk || item.name_en || <em className="text-[#A1A1AA] font-normal">Unnamed partner</em>}
          </span>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={() => onChange({ enabled: !isEnabled })}
            className="inline-flex items-center justify-center w-8 h-8 rounded-md text-[#52525B] hover:bg-[#F4F4F5] transition-colors"
            title={isEnabled ? 'Hide from public site' : 'Show on public site'}
            data-testid={`info-partners-toggle-${idx}`}
          >
            {isEnabled ? <Eye size={16} /> : <EyeSlash size={16} />}
          </button>
          <button
            onClick={() => onMove(-1)}
            disabled={idx === 0}
            className="inline-flex items-center justify-center w-8 h-8 rounded-md text-[#52525B] hover:bg-[#F4F4F5] transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            title="Move up"
            data-testid={`info-partners-up-${idx}`}
          >
            <ArrowUp size={16} />
          </button>
          <button
            onClick={() => onMove(+1)}
            disabled={idx === total - 1}
            className="inline-flex items-center justify-center w-8 h-8 rounded-md text-[#52525B] hover:bg-[#F4F4F5] transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            title="Move down"
            data-testid={`info-partners-down-${idx}`}
          >
            <ArrowDown size={16} />
          </button>
          <button
            onClick={onRemove}
            className="inline-flex items-center justify-center w-8 h-8 rounded-md text-[#DC2626] hover:bg-[#FEE2E2] transition-colors"
            title="Delete"
            data-testid={`info-partners-delete-${idx}`}
          >
            <Trash size={16} />
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="p-4 space-y-4">
        {/* Cover image — full-width, prominent (this is the card hero image) */}
        <div>
          <span className="block text-[12px] font-semibold text-[#52525B] mb-1.5 uppercase tracking-wider">
            Card image <span className="text-[#A1A1AA] normal-case font-normal tracking-normal">— shown full-width at the top of the card</span>
          </span>
          <div className="relative w-full aspect-[16/9] max-h-[220px] rounded-xl border border-[#E4E4E7] bg-[#F4F4F5] flex items-center justify-center overflow-hidden">
            {fullImageUrl ? (
              <img src={fullImageUrl} alt={item.name_en || item.name_uk || 'partner image'} className="w-full h-full object-cover" />
            ) : (
              <div className="flex flex-col items-center text-[#A1A1AA]">
                <ImageIcon size={40} />
                <span className="text-[12px] mt-1">No image yet</span>
              </div>
            )}
          </div>
          <input
            ref={imgRef}
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onUpload('image_url', f);
              if (imgRef.current) imgRef.current.value = '';
            }}
            data-testid={`info-partners-img-file-${idx}`}
          />
          <div className="flex items-center gap-2 mt-2">
            <button
              type="button"
              onClick={() => imgRef.current?.click()}
              className="inline-flex items-center gap-1.5 px-3 h-9 rounded-lg border border-[#E4E4E7] bg-white text-[#52525B] hover:bg-[#FAFAFA] hover:border-[#D4D4D8] text-[12.5px] font-medium transition-colors"
              data-testid={`info-partners-img-upload-${idx}`}
            >
              <UploadSimple size={14} /> {fullImageUrl ? 'Replace image' : 'Upload image'}
            </button>
            {fullImageUrl && (
              <button
                type="button"
                onClick={() => onChange({ image_url: '' })}
                className="inline-flex items-center justify-center w-9 h-9 rounded-lg border border-[#E4E4E7] bg-white text-[#DC2626] hover:bg-[#FEE2E2] hover:border-[#FCA5A5] transition-colors"
                title="Remove image"
                data-testid={`info-partners-img-clear-${idx}`}
              >
                <Trash size={14} />
              </button>
            )}
          </div>
        </div>

        <div>
          {/* Text fields */}
          <div className="space-y-4">
            {/* Company logo — small square badge shown over the card image on the site */}
            <Field label="Company logo" hint="Small square/round logo (PNG/SVG with transparent background works best). Shown as a badge on the card.">
              <div className="flex items-center gap-4">
                <div className="relative w-20 h-20 shrink-0 rounded-xl border border-[#E4E4E7] bg-[#F4F4F5] flex items-center justify-center overflow-hidden">
                  {fullLogoUrl ? (
                    <img src={fullLogoUrl} alt={item.name_en || item.name_uk || 'partner logo'} className="w-full h-full object-contain p-1.5" />
                  ) : (
                    <div className="flex flex-col items-center text-[#A1A1AA]">
                      <ImageIcon size={22} />
                    </div>
                  )}
                </div>
                <input
                  ref={logoRef}
                  type="file"
                  accept="image/png,image/jpeg,image/webp,image/svg+xml,image/gif"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) onUpload('logo_url', f);
                    if (logoRef.current) logoRef.current.value = '';
                  }}
                  data-testid={`info-partners-logo-file-${idx}`}
                />
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => logoRef.current?.click()}
                    className="inline-flex items-center gap-1.5 px-3 h-9 rounded-lg border border-[#E4E4E7] bg-white text-[#52525B] hover:bg-[#FAFAFA] hover:border-[#D4D4D8] text-[12.5px] font-medium transition-colors"
                    data-testid={`info-partners-logo-upload-${idx}`}
                  >
                    <UploadSimple size={14} /> {fullLogoUrl ? 'Replace logo' : 'Upload logo'}
                  </button>
                  {fullLogoUrl && (
                    <button
                      type="button"
                      onClick={() => onChange({ logo_url: '' })}
                      className="inline-flex items-center justify-center w-9 h-9 rounded-lg border border-[#E4E4E7] bg-white text-[#DC2626] hover:bg-[#FEE2E2] hover:border-[#FCA5A5] transition-colors"
                      title="Remove logo"
                      data-testid={`info-partners-logo-clear-${idx}`}
                    >
                      <Trash size={14} />
                    </button>
                  )}
                </div>
              </div>
            </Field>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Company name (UA)">
                <input
                  type="text"
                  value={item.name_uk || ''}
                  onChange={(e) => onChange({ name_uk: e.target.value })}
                  className={inputCls}
                  placeholder="ЕкоПартнер"
                  data-testid={`info-partners-name-uk-${idx}`}
                />
              </Field>
              <Field label="Company name (EN)">
                <input
                  type="text"
                  value={item.name_en || ''}
                  onChange={(e) => onChange({ name_en: e.target.value })}
                  className={inputCls}
                  placeholder="EcoPartner"
                  data-testid={`info-partners-name-en-${idx}`}
                />
              </Field>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Short description (UA)">
                <textarea
                  rows={2}
                  value={item.desc_uk || ''}
                  onChange={(e) => onChange({ desc_uk: e.target.value })}
                  className={textareaCls}
                  placeholder="Ліцензований перевізник небезпечних відходів"
                  data-testid={`info-partners-desc-uk-${idx}`}
                />
              </Field>
              <Field label="Short description (EN)">
                <textarea
                  rows={2}
                  value={item.desc_en || ''}
                  onChange={(e) => onChange({ desc_en: e.target.value })}
                  className={textareaCls}
                  placeholder="Licensed hazardous-waste carrier"
                  data-testid={`info-partners-desc-en-${idx}`}
                />
              </Field>
            </div>

            <Field label="Website link" hint="Full URL — opens in a new tab when the card is clicked.">
              <div className="relative">
                <LinkSimple size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#A1A1AA]" />
                <input
                  type="text"
                  value={item.link || ''}
                  onChange={(e) => onChange({ link: e.target.value })}
                  className={`${inputCls} pl-9 ${!linkOk ? 'border-[#DC2626] focus:border-[#DC2626] focus:ring-[#DC2626]/10' : ''}`}
                  placeholder="https://partner-website.com"
                  data-testid={`info-partners-link-${idx}`}
                />
              </div>
              {!linkOk && (
                <span className="block text-[11.5px] text-[#DC2626] mt-1">Link must start with http:// or https://</span>
              )}
            </Field>
          </div>
        </div>
      </div>
    </div>
  );
}



// ═════════════════════════════════════════════════════════════════════════
//  CERTIFICATES / LICENSES EDITOR
//  Powers the homepage "Ліцензії / Our licenses" section (site_info.certificates).
// ═════════════════════════════════════════════════════════════════════════

const CERT_CATEGORIES = [
  { value: 'license', label_uk: 'Ліцензія', label_en: 'License' },
  { value: 'permit', label_uk: 'Дозвіл', label_en: 'Permit' },
  { value: 'certificate', label_uk: 'Сертифікат', label_en: 'Certificate' },
  { value: 'transport', label_uk: 'Транспорт (ADR)', label_en: 'Transport (ADR)' },
];

function CertificatesEditor({
  data,
  updateCertificates,
  updateCertificateItem,
  addCertificateItem,
  removeCertificateItem,
  moveCertificateItem,
  uploadCertificateAsset,
}) {
  const items = data?.certificates?.items || [];
  const enabledCount = items.filter((i) => i.enabled !== false).length;

  return (
    <div className="space-y-5">
      <Block
        title="Certificates & licenses — general settings"
        description="Controls the “Our licenses” section on the public homepage. Each card shows a document preview image and links to the full PDF."
      >
        <label className="flex items-center gap-3 text-[14px] text-[#18181B] mb-5 cursor-pointer">
          <input
            type="checkbox"
            checked={data?.certificates?.enabled !== false}
            onChange={(e) => updateCertificates('enabled', e.target.checked)}
            className="w-4 h-4 accent-[#18181B] cursor-pointer"
            data-testid="info-certificates-enabled"
          />
          <span className="font-medium">Show the licenses section on the public site</span>
        </label>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="Section title (UA)">
            <input
              type="text"
              value={data?.certificates?.title_uk || ''}
              onChange={(e) => updateCertificates('title_uk', e.target.value)}
              className={inputCls}
              placeholder="Наші ліцензії"
              data-testid="info-certificates-title-uk"
            />
          </Field>
          <Field label="Section title (EN)">
            <input
              type="text"
              value={data?.certificates?.title_en || ''}
              onChange={(e) => updateCertificates('title_en', e.target.value)}
              className={inputCls}
              placeholder="Our licenses"
              data-testid="info-certificates-title-en"
            />
          </Field>
          <Field label="Subtitle (UA)">
            <textarea
              rows={2}
              value={data?.certificates?.subtitle_uk || ''}
              onChange={(e) => updateCertificates('subtitle_uk', e.target.value)}
              className={textareaCls}
              placeholder="Повний пакет дозволів…"
              data-testid="info-certificates-subtitle-uk"
            />
          </Field>
          <Field label="Subtitle (EN)">
            <textarea
              rows={2}
              value={data?.certificates?.subtitle_en || ''}
              onChange={(e) => updateCertificates('subtitle_en', e.target.value)}
              className={textareaCls}
              placeholder="A complete stack of permits…"
              data-testid="info-certificates-subtitle-en"
            />
          </Field>
        </div>
      </Block>

      <Block
        title="License / certificate cards"
        description={`${items.length} document${items.length === 1 ? '' : 's'} (${enabledCount} active). Disabled documents stay in storage but are hidden from the public site.`}
        footer={
          <div className="flex items-center justify-between">
            <span>Tip: upload a portrait document preview (a scan of the first page). Attach the full PDF so visitors can open the original.</span>
            <button
              onClick={addCertificateItem}
              className="inline-flex items-center gap-1.5 px-3 h-8 rounded-md bg-[#18181B] hover:bg-black text-white text-[12px] font-semibold transition-colors"
              data-testid="info-certificates-add"
            >
              <Plus size={14} weight="bold" /> Add document
            </button>
          </div>
        }
      >
        {items.length === 0 && (
          <div className="text-center py-10 text-[#71717A]">
            <Certificate size={28} className="mx-auto mb-2" />
            <p className="text-[13px]">No documents yet. Click <strong>Add document</strong> to create your first card.</p>
          </div>
        )}

        <div className="space-y-4">
          {items.map((item, idx) => (
            <CertificateItemCard
              key={item.id || idx}
              idx={idx}
              total={items.length}
              item={item}
              onChange={(patch) => updateCertificateItem(idx, patch)}
              onMove={(dir) => moveCertificateItem(idx, dir)}
              onRemove={() => {
                if (window.confirm('Remove this document?')) removeCertificateItem(idx);
              }}
              onUpload={(field, file) => uploadCertificateAsset(idx, field, file)}
            />
          ))}
        </div>

        {items.length > 0 && (
          <div className="mt-4 flex justify-end">
            <button
              onClick={addCertificateItem}
              className="inline-flex items-center gap-1.5 px-3.5 h-9 rounded-lg border border-dashed border-[#D4D4D8] text-[#52525B] hover:border-[#18181B] hover:text-[#18181B] text-[12.5px] font-medium transition-colors"
              data-testid="info-certificates-add-bottom"
            >
              <Plus size={14} /> Add another document
            </button>
          </div>
        )}
      </Block>
    </div>
  );
}

function CertificateItemCard({ idx, total, item, onChange, onMove, onRemove, onUpload }) {
  const imgRef = useRef(null);
  const pdfRef = useRef(null);
  const isEnabled = item.enabled !== false;
  const fullImageUrl = item.image_url
    ? (/^https?:\/\//i.test(item.image_url) ? item.image_url : `${API_URL}${item.image_url}`)
    : '';
  const fullPdfUrl = item.file_url
    ? (/^https?:\/\//i.test(item.file_url) ? item.file_url : `${API_URL}${item.file_url}`)
    : '';

  return (
    <div
      className={`border rounded-xl overflow-hidden transition-colors ${
        isEnabled ? 'border-[#E4E4E7] bg-white' : 'border-[#E4E4E7] bg-[#FAFAFA] opacity-80'
      }`}
      data-testid={`info-certificates-item-${idx}`}
    >
      {/* Header row: order, enable toggle, move, remove */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#F4F4F5] bg-[#FAFAFA]">
        <div className="flex items-center gap-2.5">
          <span className="inline-flex items-center justify-center w-7 h-7 rounded-md bg-[#18181B] text-white text-[12px] font-bold">
            {item.no || idx + 1}
          </span>
          <span className="text-[12.5px] font-semibold text-[#52525B]">
            {item.title_uk || item.title_en || 'Untitled document'}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => onChange({ enabled: !isEnabled })}
            className={`inline-flex items-center gap-1 px-2 h-7 rounded-md text-[11.5px] font-medium transition-colors ${
              isEnabled ? 'text-[#16794C] hover:bg-[#DCFCE7]' : 'text-[#A1A1AA] hover:bg-[#F4F4F5]'
            }`}
            title={isEnabled ? 'Visible on site' : 'Hidden from site'}
            data-testid={`info-certificates-toggle-${idx}`}
          >
            {isEnabled ? <Eye size={15} /> : <EyeSlash size={15} />}
            {isEnabled ? 'Visible' : 'Hidden'}
          </button>
          <button
            onClick={() => onMove(-1)}
            disabled={idx === 0}
            className="inline-flex items-center justify-center w-7 h-7 rounded-md text-[#71717A] hover:bg-[#F4F4F5] disabled:opacity-30 disabled:cursor-not-allowed"
            title="Move up"
          >
            <ArrowUp size={15} />
          </button>
          <button
            onClick={() => onMove(1)}
            disabled={idx === total - 1}
            className="inline-flex items-center justify-center w-7 h-7 rounded-md text-[#71717A] hover:bg-[#F4F4F5] disabled:opacity-30 disabled:cursor-not-allowed"
            title="Move down"
          >
            <ArrowDown size={15} />
          </button>
          <button
            onClick={onRemove}
            className="inline-flex items-center justify-center w-7 h-7 rounded-md text-[#DC2626] hover:bg-[#FEE2E2]"
            title="Remove"
            data-testid={`info-certificates-remove-${idx}`}
          >
            <Trash size={15} />
          </button>
        </div>
      </div>

      <div className="p-4 grid grid-cols-1 md:grid-cols-[200px_1fr] gap-5">
        {/* Left: preview image + PDF */}
        <div className="space-y-3">
          <div className="relative rounded-lg overflow-hidden border border-[#E4E4E7] bg-[#F4F4F5] aspect-[3/4] flex items-center justify-center">
            {fullImageUrl ? (
              <img src={fullImageUrl} alt={item.title_uk || 'certificate'} className="w-full h-full object-cover object-top" />
            ) : (
              <Certificate size={40} className="text-[#A1A1AA]" />
            )}
          </div>
          <input
            ref={imgRef}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) onUpload('image_url', f); e.target.value = ''; }}
          />
          <button
            onClick={() => imgRef.current?.click()}
            className="w-full inline-flex items-center justify-center gap-1.5 px-3 h-9 rounded-lg border border-[#E4E4E7] text-[#18181B] hover:border-[#18181B] text-[12px] font-semibold transition-colors"
            data-testid={`info-certificates-upload-image-${idx}`}
          >
            <UploadSimple size={15} /> Upload preview
          </button>

          <input
            ref={pdfRef}
            type="file"
            accept="application/pdf"
            className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) onUpload('file_url', f); e.target.value = ''; }}
          />
          <button
            onClick={() => pdfRef.current?.click()}
            className="w-full inline-flex items-center justify-center gap-1.5 px-3 h-9 rounded-lg border border-[#E4E4E7] text-[#18181B] hover:border-[#18181B] text-[12px] font-semibold transition-colors"
            data-testid={`info-certificates-upload-pdf-${idx}`}
          >
            <FileText size={15} /> {item.file_url ? 'Replace PDF' : 'Upload PDF'}
          </button>
          {fullPdfUrl && (
            <a
              href={fullPdfUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="block text-center text-[11.5px] text-[#16794C] hover:underline"
            >
              Open current PDF
            </a>
          )}
        </div>

        {/* Right: fields */}
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-[110px_1fr] gap-4">
            <Field label="Order №">
              <input
                type="text"
                value={item.no || ''}
                onChange={(e) => onChange({ no: e.target.value })}
                className={inputCls}
                placeholder="01"
              />
            </Field>
            <Field label="Category">
              <select
                value={item.category || 'certificate'}
                onChange={(e) => onChange({ category: e.target.value })}
                className={inputCls}
                data-testid={`info-certificates-category-${idx}`}
              >
                {CERT_CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>{c.label_en}</option>
                ))}
              </select>
            </Field>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field label="Title (UA)">
              <input
                type="text"
                value={item.title_uk || ''}
                onChange={(e) => onChange({ title_uk: e.target.value })}
                className={inputCls}
                placeholder="Сертифікат ISO 14001:2015"
                data-testid={`info-certificates-title-uk-${idx}`}
              />
            </Field>
            <Field label="Title (EN)">
              <input
                type="text"
                value={item.title_en || ''}
                onChange={(e) => onChange({ title_en: e.target.value })}
                className={inputCls}
                placeholder="ISO 14001:2015 certificate"
              />
            </Field>
            <Field label="Description (UA)">
              <textarea
                rows={2}
                value={item.desc_uk || ''}
                onChange={(e) => onChange({ desc_uk: e.target.value })}
                className={textareaCls}
                placeholder="Система екологічного менеджменту…"
              />
            </Field>
            <Field label="Description (EN)">
              <textarea
                rows={2}
                value={item.desc_en || ''}
                onChange={(e) => onChange({ desc_en: e.target.value })}
                className={textareaCls}
                placeholder="Environmental management system…"
              />
            </Field>
            <Field label="Issuer (UA)">
              <input
                type="text"
                value={item.issuer_uk || ''}
                onChange={(e) => onChange({ issuer_uk: e.target.value })}
                className={inputCls}
                placeholder="Мінекономіки України"
              />
            </Field>
            <Field label="Issuer (EN)">
              <input
                type="text"
                value={item.issuer_en || ''}
                onChange={(e) => onChange({ issuer_en: e.target.value })}
                className={inputCls}
                placeholder="Ministry of Economy of Ukraine"
              />
            </Field>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Field label="Document №">
              <input
                type="text"
                value={item.number || ''}
                onChange={(e) => onChange({ number: e.target.value })}
                className={inputCls}
                placeholder="№ 80143.EMS.062.01-26"
                data-testid={`info-certificates-number-${idx}`}
              />
            </Field>
            <Field label="Issued (date)">
              <input
                type="text"
                value={item.issued || ''}
                onChange={(e) => onChange({ issued: e.target.value })}
                className={inputCls}
                placeholder="17.06.2026"
              />
            </Field>
            <Field label="Valid until">
              <input
                type="text"
                value={item.valid_until || ''}
                onChange={(e) => onChange({ valid_until: e.target.value })}
                className={inputCls}
                placeholder="16.06.2029"
              />
            </Field>
          </div>
        </div>
      </div>
    </div>
  );
}