import React, { useState } from "react";
import { WasteAPI } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { toast } from "@/components/ui/sonner";
import { HazardBadge } from "@/components/common";
import { useLang } from "@/i18n";

const T = {
  uk: {
    errCode: "Вкажіть код або тип відходу", errPhone: "Вкажіть телефон для зв’язку",
    ok: "Заявку надіслано! Менеджер зв’яжеться з вами найближчим часом.",
    fail: "Не вдалося надіслати заявку. Спробуйте ще раз.",
    title: "Створити заявку на утилізацію",
    desc: "Залиште контакти — ми підготуємо прорахунок і документи.", wasteIs: "Відхід: ",
    codeLbl: "Код / тип відходу", codePh: "напр. 18 01 03*",
    qty: "Об’єм, кг", company: "Компанія", companyPh: "Назва",
    name: "Ім’я", phone: "Телефон *", email: "Email", comment: "Коментар",
    cancel: "Скасувати", sending: "Надсилання…", send: "Надіслати заявку",
  },
  en: {
    errCode: "Specify the waste code or type", errPhone: "Specify a contact phone",
    ok: "Request sent! A manager will contact you shortly.",
    fail: "Failed to send the request. Please try again.",
    title: "Create a disposal request",
    desc: "Leave your contacts — we'll prepare an estimate and documents.", wasteIs: "Waste: ",
    codeLbl: "Waste code / type", codePh: "e.g. 18 01 03*",
    qty: "Volume, kg", company: "Company", companyPh: "Name",
    name: "Name", phone: "Phone *", email: "Email", comment: "Comment",
    cancel: "Cancel", sending: "Sending…", send: "Send request",
  },
};

export function RequestDialog({ open, onOpenChange, prefillCode = "", prefillName = "" }) {
  const { lang } = useLang();
  const L = T[lang] || T.uk;
  const [form, setForm] = useState({
    waste_code: prefillCode, qty: "", company_name: "", contact_name: "", contact_phone: "", contact_email: "", comment: "",
  });
  const [submitting, setSubmitting] = useState(false);

  React.useEffect(() => {
    if (open) setForm((f) => ({ ...f, waste_code: prefillCode || f.waste_code }));
  }, [open, prefillCode]);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async () => {
    if (!form.waste_code.trim()) return toast.error(L.errCode);
    if (!form.contact_phone.trim()) return toast.error(L.errPhone);
    setSubmitting(true);
    try {
      await WasteAPI.createPublicRequest({
        company_name: form.company_name, contact_name: form.contact_name,
        contact_phone: form.contact_phone, contact_email: form.contact_email, comment: form.comment,
        items: [{ waste_code: form.waste_code.trim(), qty: form.qty ? Number(form.qty) : null }],
      });
      toast.success(L.ok);
      onOpenChange(false);
      setForm({ waste_code: "", qty: "", company_name: "", contact_name: "", contact_phone: "", contact_email: "", comment: "" });
    } catch (e) {
      toast.error(L.fail);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg" data-testid="request-dialog">
        <DialogHeader>
          <DialogTitle>{L.title}</DialogTitle>
          <DialogDescription>{L.desc}{prefillName ? ` ${L.wasteIs}${prefillName}` : ""}</DialogDescription>
        </DialogHeader>
        <div className="grid gap-3">
          <div className="grid gap-1.5">
            <Label>{L.codeLbl} {form.waste_code && <HazardBadge hazardous={form.waste_code.includes("*")} />}</Label>
            <Input value={form.waste_code} onChange={set("waste_code")} placeholder={L.codePh} data-testid="request-code-input" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5"><Label>{L.qty}</Label><Input type="number" value={form.qty} onChange={set("qty")} placeholder="100" data-testid="request-qty-input" /></div>
            <div className="grid gap-1.5"><Label>{L.company}</Label><Input value={form.company_name} onChange={set("company_name")} placeholder={L.companyPh} data-testid="request-company-input" /></div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5"><Label>{L.name}</Label><Input value={form.contact_name} onChange={set("contact_name")} data-testid="request-name-input" /></div>
            <div className="grid gap-1.5"><Label>{L.phone}</Label><Input value={form.contact_phone} onChange={set("contact_phone")} placeholder="+380…" data-testid="request-phone-input" /></div>
          </div>
          <div className="grid gap-1.5"><Label>{L.email}</Label><Input value={form.contact_email} onChange={set("contact_email")} data-testid="request-email-input" /></div>
          <div className="grid gap-1.5"><Label>{L.comment}</Label><Textarea value={form.comment} onChange={set("comment")} rows={2} data-testid="request-comment-input" /></div>
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>{L.cancel}</Button>
          <Button onClick={submit} disabled={submitting} data-testid="request-submit-button">{submitting ? L.sending : L.send}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
