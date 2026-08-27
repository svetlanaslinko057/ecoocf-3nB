/**
 * AdminFooterPage — full editor for the public-site footer.
 *
 * Everything rendered by <EcoFooter/> is editable here and persisted to
 * `app_settings.footer` via PUT /api/admin/settings/footer. Anonymous browsers
 * read the result from GET /api/public/footer.
 */
import React, { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import {
  Layout, Plus, Trash2, Save, RotateCcw, GripVertical, ExternalLink,
  Loader2, Phone, Mail, MapPin, Megaphone, Building2, Link2, Share2, BadgeCheck,
} from "lucide-react";
import { FooterAPI } from "@/lib/api";

const SOCIAL_NETWORKS = ["linkedin", "facebook", "instagram", "telegram", "youtube", "twitter"];

/* ── tiny presentational helpers ─────────────────────────────────────────── */
const Card = ({ icon: Icon, title, desc, children, testId }) => (
  <section className="bg-white border border-[#E4E4E7] rounded-2xl p-5" data-testid={testId}>
    <div className="flex items-start gap-3 mb-4">
      {Icon && (
        <div className="w-9 h-9 rounded-xl bg-[#1c211c] text-[#3E9F57] flex items-center justify-center shrink-0">
          <Icon size={17} />
        </div>
      )}
      <div className="min-w-0">
        <h2 className="text-[15px] font-semibold text-[#18181B] leading-tight">{title}</h2>
        {desc && <p className="text-[12px] text-[#71717A] mt-0.5">{desc}</p>}
      </div>
    </div>
    {children}
  </section>
);

const Label = ({ children }) => (
  <span className="block text-[10.5px] font-semibold uppercase tracking-[0.12em] text-[#71717A] mb-1.5">{children}</span>
);

const Input = (props) => (
  <input
    {...props}
    className={
      "w-full px-3 py-2.5 rounded-lg border border-[#E4E4E7] text-[13.5px] text-[#18181B] " +
      "outline-none focus:border-[#2f5d3d] focus:ring-2 focus:ring-[#2f5d3d]/15 transition " +
      (props.className || "")
    }
  />
);

const Textarea = (props) => (
  <textarea
    {...props}
    className={
      "w-full px-3 py-2.5 rounded-lg border border-[#E4E4E7] text-[13.5px] text-[#18181B] leading-relaxed " +
      "outline-none focus:border-[#2f5d3d] focus:ring-2 focus:ring-[#2f5d3d]/15 transition resize-y " +
      (props.className || "")
    }
  />
);

const Field = ({ label, value, onChange, placeholder, type = "text", testId }) => (
  <label className="block">
    <Label>{label}</Label>
    <Input type={type} value={value ?? ""} placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)} data-testid={testId} />
  </label>
);

const Toggle = ({ checked, onChange, label, testId }) => (
  <button type="button" onClick={() => onChange(!checked)} data-testid={testId}
    className="inline-flex items-center gap-2.5 select-none">
    <span className={"relative w-10 h-6 rounded-full transition-colors " + (checked ? "bg-[#2f5d3d]" : "bg-[#D4D4D8]")}>
      <span className={"absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform " + (checked ? "translate-x-4" : "")} />
    </span>
    <span className="text-[13px] font-medium text-[#3F3F46]">{label}</span>
  </button>
);

const IconBtn = ({ onClick, title, children, danger, testId }) => (
  <button type="button" onClick={onClick} title={title} data-testid={testId}
    className={"p-2 rounded-lg border text-[#52525B] transition-colors " +
      (danger ? "border-red-200 hover:bg-red-50 hover:text-red-600" : "border-[#E4E4E7] hover:bg-[#FAFAFA]")}>
    {children}
  </button>
);

/* ── main page ───────────────────────────────────────────────────────────── */
export default function AdminFooterPage() {
  const [cfg, setCfg] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await FooterAPI.getAdmin();
      setCfg(res.footer);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Не вдалося завантажити налаштування футера");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const save = async () => {
    setSaving(true);
    try {
      const res = await FooterAPI.save(cfg);
      setCfg(res.footer);
      toast.success("Футер збережено — зміни вже на сайті");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Помилка збереження");
    } finally {
      setSaving(false);
    }
  };

  // section updaters
  const setSection = (key, patch) => setCfg((c) => ({ ...c, [key]: { ...(c[key] || {}), ...patch } }));
  const setRoot = (key, value) => setCfg((c) => ({ ...c, [key]: value }));

  if (loading || !cfg) {
    return (
      <div className="p-6 flex items-center justify-center text-[#71717A] gap-2">
        <Loader2 className="animate-spin" size={18} /> Завантаження…
      </div>
    );
  }

  const brand = cfg.brand || {};
  const cta = cfg.cta || {};
  const contacts = cfg.contacts || {};
  const company = cfg.company || {};
  const newsletter = cfg.newsletter || {};

  return (
    <div className="max-w-5xl mx-auto space-y-5 pb-28" data-testid="admin-footer-page">
      {/* Header */}
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-2xl bg-[#1c211c] text-[#3E9F57] flex items-center justify-center shrink-0">
          <Layout size={20} />
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="text-[20px] font-bold text-[#18181B] leading-tight">Футер сайту</h1>
          <p className="text-[12.5px] text-[#71717A] mt-0.5">
            Контакти, компанія, навігація, соцмережі та розсилка публічного сайту — усе редагується тут.
          </p>
        </div>
      </div>

      <div className="space-y-5">
        {/* Brand */}
        <Card icon={BadgeCheck} title="Бренд" desc="Логотип-напис, слоган та великий вотермарк унизу футера" testId="footer-brand-card">
          <div className="grid sm:grid-cols-3 gap-4">
            <Field label="Назва" value={brand.name} onChange={(v) => setSection("brand", { name: v })} testId="footer-field-brand-name" />
            <Field label="Акцент-символ" value={brand.accentChar} onChange={(v) => setSection("brand", { accentChar: v })} placeholder="." />
            <Field label="Вотермарк (великий)" value={brand.wordmark} onChange={(v) => setSection("brand", { wordmark: v })} placeholder="ECO" />
          </div>
          <div className="mt-4">
            <Label>Слоган</Label>
            <Textarea rows={2} value={brand.tagline ?? ""} onChange={(e) => setSection("brand", { tagline: e.target.value })} data-testid="footer-field-tagline" />
          </div>
          <div className="mt-4">
            <Toggle checked={!!brand.showWordmark} onChange={(v) => setSection("brand", { showWordmark: v })} label="Показувати великий вотермарк" testId="footer-toggle-wordmark" />
          </div>
        </Card>

        {/* CTA */}
        <Card icon={Megaphone} title="Кнопки заклику (CTA)" desc="Дві кнопки у блоці бренду" testId="footer-cta-card">
          <Toggle checked={!!cta.enabled} onChange={(v) => setSection("cta", { enabled: v })} label="Показувати кнопки" testId="footer-toggle-cta" />
          <div className="grid sm:grid-cols-2 gap-4 mt-4">
            <Field label="Основна — текст" value={cta.primaryLabel} onChange={(v) => setSection("cta", { primaryLabel: v })} />
            <Field label="Основна — посилання" value={cta.primaryHref} onChange={(v) => setSection("cta", { primaryHref: v })} placeholder="/calculator" />
            <Field label="Друга — текст" value={cta.secondaryLabel} onChange={(v) => setSection("cta", { secondaryLabel: v })} />
            <Field label="Друга — посилання" value={cta.secondaryHref} onChange={(v) => setSection("cta", { secondaryHref: v })} placeholder="/contacts" />
          </div>
        </Card>

        {/* Columns */}
        <Card icon={Link2} title="Колонки посилань" desc="Навігаційні колонки футера (можна додавати/видаляти)" testId="footer-columns-card">
          <div className="space-y-4">
            {(cfg.columns || []).map((col, ci) => (
              <div key={ci} className="rounded-xl border border-[#E4E4E7] bg-[#FAFAFA] p-4">
                <div className="flex items-center gap-2 mb-3">
                  <GripVertical size={15} className="text-[#A1A1AA]" />
                  <Input value={col.title ?? ""} placeholder="Назва колонки"
                    onChange={(e) => setRoot("columns", cfg.columns.map((c, i) => i === ci ? { ...c, title: e.target.value } : c))}
                    className="font-semibold !py-2" data-testid={`footer-col-title-${ci}`} />
                  <IconBtn danger title="Видалити колонку" testId={`footer-col-del-${ci}`}
                    onClick={() => setRoot("columns", cfg.columns.filter((_, i) => i !== ci))}>
                    <Trash2 size={15} />
                  </IconBtn>
                </div>
                <div className="space-y-2">
                  {(col.links || []).map((lnk, li) => (
                    <div key={li} className="flex items-center gap-2">
                      <Input value={lnk.label ?? ""} placeholder="Текст"
                        onChange={(e) => setRoot("columns", cfg.columns.map((c, i) => i === ci
                          ? { ...c, links: c.links.map((l, j) => j === li ? { ...l, label: e.target.value } : l) } : c))}
                        className="!py-2" />
                      <Input value={lnk.href ?? ""} placeholder="/посилання"
                        onChange={(e) => setRoot("columns", cfg.columns.map((c, i) => i === ci
                          ? { ...c, links: c.links.map((l, j) => j === li ? { ...l, href: e.target.value } : l) } : c))}
                        className="!py-2" />
                      <IconBtn danger title="Видалити" onClick={() => setRoot("columns", cfg.columns.map((c, i) => i === ci
                        ? { ...c, links: c.links.filter((_, j) => j !== li) } : c))}>
                        <Trash2 size={14} />
                      </IconBtn>
                    </div>
                  ))}
                  <button type="button" data-testid={`footer-col-addlink-${ci}`}
                    onClick={() => setRoot("columns", cfg.columns.map((c, i) => i === ci
                      ? { ...c, links: [...(c.links || []), { label: "", href: "" }] } : c))}
                    className="inline-flex items-center gap-1.5 text-[12.5px] font-medium text-[#2f5d3d] hover:underline mt-1">
                    <Plus size={14} /> Додати посилання
                  </button>
                </div>
              </div>
            ))}
            <button type="button" data-testid="footer-add-column"
              onClick={() => setRoot("columns", [...(cfg.columns || []), { title: "Нова колонка", links: [] }])}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-dashed border-[#C7CDC2] text-[13px] font-medium text-[#2f5d3d] hover:bg-[#FAFAFA]">
              <Plus size={15} /> Додати колонку
            </button>
          </div>
        </Card>

        {/* Contacts */}
        <Card icon={Phone} title="Контакти" desc="Телефони, пошта, адреса, графік роботи" testId="footer-contacts-card">
          <Field label="Заголовок колонки" value={contacts.title} onChange={(v) => setSection("contacts", { title: v })} />
          <div className="grid sm:grid-cols-2 gap-4 mt-4">
            <Field label="Телефон" value={contacts.phone} onChange={(v) => setSection("contacts", { phone: v })} testId="footer-field-phone" />
            <Field label="Телефон — посилання (tel:)" value={contacts.phoneHref} onChange={(v) => setSection("contacts", { phoneHref: v })} placeholder="tel:+380..." />
            <Field label="Телефон 2 (опц.)" value={contacts.phone2} onChange={(v) => setSection("contacts", { phone2: v })} />
            <Field label="Телефон 2 — посилання" value={contacts.phone2Href} onChange={(v) => setSection("contacts", { phone2Href: v })} placeholder="tel:+380..." />
            <Field label="Email" value={contacts.email} onChange={(v) => setSection("contacts", { email: v })} testId="footer-field-email" />
            <Field label="Email 2 (опц.)" value={contacts.email2} onChange={(v) => setSection("contacts", { email2: v })} />
            <Field label="Адреса" value={contacts.address} onChange={(v) => setSection("contacts", { address: v })} />
            <Field label="Графік роботи" value={contacts.hours} onChange={(v) => setSection("contacts", { hours: v })} placeholder="Пн–Пт, 9:00–18:00" />
            <Field label="Текст «вхід для клієнтів»" value={contacts.clientLoginLabel} onChange={(v) => setSection("contacts", { clientLoginLabel: v })} />
            <Field label="Посилання «вхід для клієнтів»" value={contacts.clientLoginHref} onChange={(v) => setSection("contacts", { clientLoginHref: v })} placeholder="/client/login" />
          </div>
        </Card>

        {/* Company */}
        <Card icon={Building2} title="Дані компанії" desc="Юридична назва та реквізити (у нижньому рядку футера)" testId="footer-company-card">
          <div className="grid sm:grid-cols-3 gap-4">
            <Field label="Юридична назва" value={company.legalName} onChange={(v) => setSection("company", { legalName: v })} />
            <Field label="ЄДРПОУ" value={company.edrpou} onChange={(v) => setSection("company", { edrpou: v })} />
            <Field label="Реєстрація (опц.)" value={company.registration} onChange={(v) => setSection("company", { registration: v })} />
          </div>
          <div className="mt-4">
            <Field label="Копірайт (текст після ©)" value={cfg.copyright} onChange={(v) => setRoot("copyright", v)} testId="footer-field-copyright" />
          </div>
        </Card>

        {/* Newsletter */}
        <Card icon={Mail} title="Розсилка" desc="Форма підписки (email зберігається у newsletter_subscribers)" testId="footer-newsletter-card">
          <Toggle checked={!!newsletter.enabled} onChange={(v) => setSection("newsletter", { enabled: v })} label="Показувати форму розсилки" testId="footer-toggle-newsletter" />
          <div className="grid sm:grid-cols-2 gap-4 mt-4">
            <Field label="Заголовок" value={newsletter.title} onChange={(v) => setSection("newsletter", { title: v })} />
            <Field label="Текст кнопки" value={newsletter.buttonLabel} onChange={(v) => setSection("newsletter", { buttonLabel: v })} />
            <Field label="Плейсхолдер поля" value={newsletter.placeholder} onChange={(v) => setSection("newsletter", { placeholder: v })} />
            <Field label="Текст після підписки" value={newsletter.successText} onChange={(v) => setSection("newsletter", { successText: v })} />
          </div>
          <div className="mt-4">
            <Label>Опис</Label>
            <Textarea rows={2} value={newsletter.description ?? ""} onChange={(e) => setSection("newsletter", { description: e.target.value })} />
          </div>
        </Card>

        {/* Socials */}
        <Card icon={Share2} title="Соцмережі" desc="Іконки соцмереж (порожнє посилання — не показується)" testId="footer-socials-card">
          <div className="space-y-2">
            {(cfg.socials || []).map((s, i) => (
              <div key={i} className="flex items-center gap-2">
                <select value={s.network || "linkedin"}
                  onChange={(e) => setRoot("socials", cfg.socials.map((x, j) => j === i ? { ...x, network: e.target.value } : x))}
                  className="px-3 py-2.5 rounded-lg border border-[#E4E4E7] text-[13px] bg-white outline-none focus:border-[#2f5d3d]"
                  data-testid={`footer-social-net-${i}`}>
                  {SOCIAL_NETWORKS.map((n) => <option key={n} value={n}>{n}</option>)}
                </select>
                <Input value={s.label ?? ""} placeholder="Назва"
                  onChange={(e) => setRoot("socials", cfg.socials.map((x, j) => j === i ? { ...x, label: e.target.value } : x))}
                  className="!py-2 max-w-[160px]" />
                <Input value={s.href ?? ""} placeholder="https://…"
                  onChange={(e) => setRoot("socials", cfg.socials.map((x, j) => j === i ? { ...x, href: e.target.value } : x))}
                  className="!py-2" />
                <IconBtn danger title="Видалити" onClick={() => setRoot("socials", cfg.socials.filter((_, j) => j !== i))}>
                  <Trash2 size={14} />
                </IconBtn>
              </div>
            ))}
            <button type="button" data-testid="footer-add-social"
              onClick={() => setRoot("socials", [...(cfg.socials || []), { network: "linkedin", label: "LinkedIn", href: "" }])}
              className="inline-flex items-center gap-1.5 text-[12.5px] font-medium text-[#2f5d3d] hover:underline mt-1">
              <Plus size={14} /> Додати соцмережу
            </button>
          </div>
        </Card>

        {/* Badges + bottom links */}
        <Card icon={BadgeCheck} title="Бейджі та нижні посилання" desc="Маркери довіри та юридичні посилання у нижньому рядку" testId="footer-badges-card">
          <div className="grid md:grid-cols-2 gap-6">
            <div>
              <Label>Бейджі (маркери довіри)</Label>
              <div className="space-y-2">
                {(cfg.badges || []).map((b, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <Input value={b ?? ""} placeholder="Текст бейджа"
                      onChange={(e) => setRoot("badges", cfg.badges.map((x, j) => j === i ? e.target.value : x))} className="!py-2" />
                    <IconBtn danger title="Видалити" onClick={() => setRoot("badges", cfg.badges.filter((_, j) => j !== i))}>
                      <Trash2 size={14} />
                    </IconBtn>
                  </div>
                ))}
                <button type="button" onClick={() => setRoot("badges", [...(cfg.badges || []), ""])}
                  className="inline-flex items-center gap-1.5 text-[12.5px] font-medium text-[#2f5d3d] hover:underline mt-1">
                  <Plus size={14} /> Додати бейдж
                </button>
              </div>
            </div>
            <div>
              <Label>Нижні посилання</Label>
              <div className="space-y-2">
                {(cfg.bottomLinks || []).map((l, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <Input value={l.label ?? ""} placeholder="Текст"
                      onChange={(e) => setRoot("bottomLinks", cfg.bottomLinks.map((x, j) => j === i ? { ...x, label: e.target.value } : x))} className="!py-2" />
                    <Input value={l.href ?? ""} placeholder="/посилання"
                      onChange={(e) => setRoot("bottomLinks", cfg.bottomLinks.map((x, j) => j === i ? { ...x, href: e.target.value } : x))} className="!py-2" />
                    <IconBtn danger title="Видалити" onClick={() => setRoot("bottomLinks", cfg.bottomLinks.filter((_, j) => j !== i))}>
                      <Trash2 size={14} />
                    </IconBtn>
                  </div>
                ))}
                <button type="button" onClick={() => setRoot("bottomLinks", [...(cfg.bottomLinks || []), { label: "", href: "" }])}
                  className="inline-flex items-center gap-1.5 text-[12.5px] font-medium text-[#2f5d3d] hover:underline mt-1">
                  <Plus size={14} /> Додати посилання
                </button>
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* Sticky save bar */}
      <div className="fixed bottom-0 left-0 right-0 z-30 bg-white/90 backdrop-blur border-t border-[#E4E4E7]">
        <div className="max-w-5xl mx-auto px-6 py-3 flex items-center justify-between gap-3">
          <span className="text-[12px] text-[#71717A] hidden sm:flex items-center gap-1.5">
            <ExternalLink size={13} /> Зміни одразу застосовуються на публічному сайті
          </span>
          <div className="flex items-center gap-2 ml-auto">
            <button type="button" onClick={load} disabled={saving}
              className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-lg border border-[#E4E4E7] text-[13px] font-medium text-[#52525B] hover:bg-[#FAFAFA] disabled:opacity-50"
              data-testid="footer-reset-btn">
              <RotateCcw size={15} /> Скинути зміни
            </button>
            <button type="button" onClick={save} disabled={saving}
              className="inline-flex items-center gap-2 px-6 py-2.5 rounded-lg bg-[#2f5d3d] text-white text-[13px] font-semibold hover:bg-[#264c32] disabled:opacity-60"
              data-testid="footer-save-btn">
              {saving ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />}
              Зберегти
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
