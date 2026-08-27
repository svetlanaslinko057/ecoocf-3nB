/**
 * AdminContactsPage — single source of truth for the public contact data shown
 * in the site header, footer and Contacts page.
 *
 * Reads/writes GET|PUT /api/waste/admin/site-contacts (admin only). Anonymous
 * visitors read the result via GET /api/public/contacts. Phone + email values
 * are validated both client- and server-side.
 */
import React, { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import { Phone, Mail, MapPin, Clock, Plus, Trash2, Save, Loader2, Contact, Send } from "lucide-react";
import { WasteAdminAPI } from "@/lib/api";
import { refreshPublicContacts } from "@/lib/usePublicContacts";
import { validatePhone, validateEmail } from "@/lib/validators";

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

const Input = ({ invalid, ...props }) => (
  <input
    {...props}
    className={`w-full h-10 px-3 rounded-xl border bg-white text-[14px] text-[#18181B] outline-none focus:ring-2 focus:ring-[#3E9F57]/30 focus:border-[#3E9F57] ${
      invalid ? "border-[#d9714a] bg-[#fdf4f0]" : "border-[#E4E4E7]"
    }`}
  />
);

function ContactRows({ rows, setRows, kind, lang = "uk" }) {
  const isPhone = kind === "phone";
  const placeholder = isPhone ? "+380 67 123 45 67" : "name@company.ua";
  const addLabel = isPhone ? "Додати телефон" : "Додати email";

  const update = (i, key, val) => {
    const next = rows.map((r, idx) => (idx === i ? { ...r, [key]: val } : r));
    setRows(next);
  };
  const remove = (i) => setRows(rows.filter((_, idx) => idx !== i));
  const add = () => setRows([...rows, { label: "", value: "" }]);

  const check = (val) => {
    if (!val) return null;
    const res = isPhone ? validatePhone(val, lang) : validateEmail(val, { required: true, lang });
    return res.ok ? null : res.error;
  };

  return (
    <div className="space-y-3">
      {rows.map((r, i) => {
        const err = check(r.value);
        return (
          <div key={i} className="flex gap-2 items-start" data-testid={`${kind}-row-${i}`}>
            <div className="w-40 shrink-0">
              <Input
                value={r.label}
                onChange={(e) => update(i, "label", e.target.value)}
                placeholder="Підпис"
                data-testid={`${kind}-label-${i}`}
              />
            </div>
            <div className="flex-1 min-w-0">
              <Input
                value={r.value}
                onChange={(e) => update(i, "value", e.target.value)}
                placeholder={placeholder}
                invalid={!!err}
                data-testid={`${kind}-value-${i}`}
              />
              {err && <p className="text-[11px] text-[#c0451c] mt-1">{err}</p>}
            </div>
            <button
              type="button"
              onClick={() => remove(i)}
              className="h-10 w-10 shrink-0 grid place-items-center rounded-xl border border-[#E4E4E7] text-[#a1463a] hover:bg-[#fdf4f0]"
              data-testid={`${kind}-remove-${i}`}
              aria-label="Видалити"
            >
              <Trash2 size={15} />
            </button>
          </div>
        );
      })}
      <button
        type="button"
        onClick={add}
        className="inline-flex items-center gap-1.5 text-[13px] font-medium text-[#2f5d3d] hover:text-[#3E9F57]"
        data-testid={`${kind}-add`}
      >
        <Plus size={15} /> {addLabel}
      </button>
    </div>
  );
}

export default function AdminContactsPage() {
  const [data, setData] = useState({
    phones: [], emails: [], address: "", working_hours: "",
    telegram: "", viber: "", messenger: "",
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await WasteAdminAPI.getSiteContacts();
      const c = r.contacts || {};
      setData({
        phones: c.phones && c.phones.length ? c.phones : [{ label: "", value: "" }],
        emails: c.emails && c.emails.length ? c.emails : [{ label: "", value: "" }],
        address: c.address || "",
        working_hours: c.working_hours || "",
        telegram: c.telegram || "",
        viber: c.viber || "",
        messenger: c.messenger || "",
      });
    } catch (e) {
      toast.error("Не вдалося завантажити контакти");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const save = async () => {
    // Client-side guard so the operator sees errors instantly.
    for (const p of data.phones) {
      if (p.value && !validatePhone(p.value, "uk").ok) {
        toast.error(`Некоректний телефон: ${p.value}`); return;
      }
    }
    for (const em of data.emails) {
      if (em.value && !validateEmail(em.value, { required: true, lang: "uk" }).ok) {
        toast.error(`Некоректний email: ${em.value}`); return;
      }
    }
    setSaving(true);
    try {
      const payload = {
        phones: data.phones.filter((p) => (p.value || "").trim()),
        emails: data.emails.filter((e) => (e.value || "").trim()),
        address: data.address,
        working_hours: data.working_hours,
        telegram: data.telegram,
        viber: data.viber,
        messenger: data.messenger,
      };
      await WasteAdminAPI.saveSiteContacts(payload);
      refreshPublicContacts();
      toast.success("Контакти збережено — оновлено в хедері, футері та на сторінці контактів");
    } catch (e) {
      const detail = e?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : "Не вдалося зберегти");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center gap-2 text-[#71717A]" data-testid="contacts-loading">
        <Loader2 className="animate-spin" size={18} /> Завантаження…
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto space-y-5" data-testid="admin-contacts-page">
      <header className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#1c211c] text-[#3E9F57] grid place-items-center">
            <Contact size={19} />
          </div>
          <div>
            <h1 className="text-[20px] font-bold text-[#18181B] leading-tight">Контакти сайту</h1>
            <p className="text-[12.5px] text-[#71717A]">Телефони та пошти для хедера, футера й сторінки «Контакти»</p>
          </div>
        </div>
        <button
          onClick={save}
          disabled={saving}
          className="inline-flex items-center gap-2 h-10 px-4 rounded-xl bg-[#2f5d3d] text-white text-[14px] font-semibold hover:bg-[#244c31] disabled:opacity-60"
          data-testid="contacts-save"
        >
          {saving ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />}
          Зберегти
        </button>
      </header>

      <Card icon={Phone} title="Телефони" desc="Перший номер показується в хедері та як основний на сайті" testId="contacts-phones-card">
        <ContactRows rows={data.phones} setRows={(r) => setData((d) => ({ ...d, phones: r }))} kind="phone" />
      </Card>

      <Card icon={Mail} title="Email-адреси" desc="Перша адреса — основна (хедер/футер)" testId="contacts-emails-card">
        <ContactRows rows={data.emails} setRows={(r) => setData((d) => ({ ...d, emails: r }))} kind="email" />
      </Card>

      <Card icon={MapPin} title="Адреса та графік" testId="contacts-misc-card">
        <div className="space-y-3">
          <div>
            <span className="block text-[10.5px] font-semibold uppercase tracking-[0.12em] text-[#71717A] mb-1.5">Адреса</span>
            <Input value={data.address} onChange={(e) => setData((d) => ({ ...d, address: e.target.value }))}
              placeholder="м. Київ, вул. Лісова, 12" data-testid="contacts-address" />
          </div>
          <div>
            <span className="flex items-center gap-1.5 text-[10.5px] font-semibold uppercase tracking-[0.12em] text-[#71717A] mb-1.5">
              <Clock size={12} /> Графік роботи
            </span>
            <Input value={data.working_hours} onChange={(e) => setData((d) => ({ ...d, working_hours: e.target.value }))}
              placeholder="Пн–Пт: 9:00–18:00" data-testid="contacts-hours" />
          </div>
        </div>
      </Card>

      <Card icon={Send} title="Месенджери (необов'язково)" testId="contacts-messengers-card">
        <div className="grid sm:grid-cols-3 gap-3">
          {[
            ["telegram", "Telegram", "https://t.me/…"],
            ["viber", "Viber", "viber://…"],
            ["messenger", "Messenger", "https://m.me/…"],
          ].map(([key, label, ph]) => (
            <div key={key}>
              <span className="block text-[10.5px] font-semibold uppercase tracking-[0.12em] text-[#71717A] mb-1.5">{label}</span>
              <Input value={data[key]} onChange={(e) => setData((d) => ({ ...d, [key]: e.target.value }))}
                placeholder={ph} data-testid={`contacts-${key}`} />
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
