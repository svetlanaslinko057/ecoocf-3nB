import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ChevronRight, Package, Truck, FileText, ShieldCheck, AlertTriangle } from "lucide-react";
import { WasteAPI } from "@/lib/api";
import { useSeo } from "@/lib/seo";
import { useLang } from "@/i18n";
import { hazardClassLabel } from "@/lib/wasteMeta";
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from "@/components/ui/accordion";
import { RequestDialog } from "@/components/RequestDialog";
import "./eco-pages.css";

const T = {
  uk: {
    seoFallback: "Код відходу",
    seoDescPre: "Утилізація відходу ", seoDescPost: ": опис, клас небезпеки, зберігання, транспорт, документи, ціна.",
    notFound: "Код не знайдено.", toDirectory: "До довідника", loading: "Завантаження…",
    directory: "Довідник",
    haz: "Небезпечні *", nonHaz: "Ненебезпечні",
    classLbl: (c) => `Клас ${c}`, mirror: "Дзеркальний: ",
    descTitle: "Опис", storageTitle: "Як зберігати", transportTitle: "Як транспортувати",
    utilTitle: "Як утилізується", docsTitle: "Необхідні документи",
    faqTitle: "Часті питання",
    faqQ1: "Чи є цей відхід небезпечним?",
    faqA1Yes: "Так, код позначено символом * — це небезпечний відхід, який потребує спеціального поводження.",
    faqA1No: "Ні, цей код не належить до небезпечних.",
    faqA1Mirror: (m) => ` Дзеркальний код: ${m}.`,
    faqQ2: "Яка мінімальна партія?",
    faqA2: (kg, unit) => `Мінімальна партія — від ${kg} ${unit}. Для менших об’ємів уточнюйте у менеджера.`,
    unitUnit: "од.", unitKg: "кг",
    priceTitle: "Орієнтовна ціна", priceFrom: (v) => `від ${v} грн`, onRequest: "За запитом",
    accepted: "Приймаємо",
    minBatch: "Мін. партія", specTransport: "Спецтранспорт", needContainer: "Потрібна тара",
    yes: "Так", no: "Ні",
    notLicensed: ["Цей код наразі ", "поза нашою ліцензією", " — ми його не приймаємо. Залиште контакти, і ми підкажемо ліцензованого оператора."],
    contactUs: "Зв’язатися з нами",
    createRequest: "Створити заявку", calcCost: "Розрахувати вартість",
    hazNote: "Небезпечний відхід — потребує окремого пакування та документів.",
  },
  en: {
    seoFallback: "Waste code",
    seoDescPre: "Disposal of waste ", seoDescPost: ": description, hazard class, storage, transport, documents, price.",
    notFound: "Code not found.", toDirectory: "To the directory", loading: "Loading…",
    directory: "Directory",
    haz: "Hazardous *", nonHaz: "Non-hazardous",
    classLbl: (c) => `Class ${c}`, mirror: "Mirror: ",
    descTitle: "Description", storageTitle: "How to store", transportTitle: "How to transport",
    utilTitle: "How it's disposed of", docsTitle: "Required documents",
    faqTitle: "Frequently asked",
    faqQ1: "Is this waste hazardous?",
    faqA1Yes: "Yes, the code is marked with * — this is hazardous waste that requires special handling.",
    faqA1No: "No, this code is not classified as hazardous.",
    faqA1Mirror: (m) => ` Mirror code: ${m}.`,
    faqQ2: "What is the minimum batch?",
    faqA2: (kg, unit) => `Minimum batch — from ${kg} ${unit}. For smaller volumes, check with a manager.`,
    unitUnit: "pcs", unitKg: "kg",
    priceTitle: "Indicative price", priceFrom: (v) => `from ${v} UAH`, onRequest: "On request",
    accepted: "Accepted",
    minBatch: "Min. batch", specTransport: "Special transport", needContainer: "Container needed",
    yes: "Yes", no: "No",
    notLicensed: ["This code is currently ", "outside our licence", " — we don't accept it. Leave your contacts and we'll suggest a licensed operator."],
    contactUs: "Contact us",
    createRequest: "Create a request", calcCost: "Calculate the cost",
    hazNote: "Hazardous waste — requires separate packaging and documents.",
  },
};

const Block = ({ icon: Icon, title, children }) => (
  <div className="einfo">
    <h2 className="einfo__title"><Icon /> {title}</h2>
    <div className="einfo__body">{children}</div>
  </div>
);

export default function WasteCodePage() {
  const { slug } = useParams();
  const { lang } = useLang();
  const L = T[lang] || T.uk;
  const [code, setCode] = useState(null);
  const [mirror, setMirror] = useState(null);
  const [lic, setLic] = useState(null);
  const [open, setOpen] = useState(false);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    setNotFound(false);
    WasteAPI.codeBySlug(slug).then((r) => {
      setCode(r.code); setMirror(r.mirror);
      WasteAPI.licenseCheck(r.code.code).then(setLic).catch(() => {});
    }).catch(() => setNotFound(true));
  }, [slug]);

  useSeo(code ? `${code.code} — ${code.name}` : L.seoFallback, code ? `${L.seoDescPre}${code.code}${L.seoDescPost}` : "");

  if (notFound) return <div className="epage"><section className="epage-sec"><div className="estate estate--center">{L.notFound} <Link to="/waste" style={{ color: "var(--eco-green)" }}>{L.toDirectory}</Link></div></section></div>;
  if (!code) return <div className="epage"><section className="epage-sec"><div className="estate">{L.loading}</div></section></div>;

  const unitWord = code.price_unit === "шт" ? L.unitUnit : L.unitKg;

  return (
    <div className="epage" data-testid="waste-code-page">
      <section className="epage-hero">
        <div className="epage-hero__inner">
          <nav className="ecrumb">
            <Link to="/waste">{L.directory}</Link>
            <ChevronRight />
            <Link to={`/waste/category/${code.category}`}>{code.category_name}</Link>
            <ChevronRight />
            <span className="ecrumb__current">{code.code}</span>
          </nav>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginBottom: 18 }}>
            <span className={`epill ${code.hazardous ? "epill--haz" : "epill--ok"}`}>{code.hazardous ? L.haz : L.nonHaz}</span>
            {code.hazard_class && <span className="epill">{hazardClassLabel(code.hazard_class, lang) || L.classLbl(code.hazard_class)}</span>}
            {code.mirror_code && <span className="epill">{L.mirror}{code.mirror_code}</span>}
          </div>
          <h1 className="epage__title" style={{ fontSize: "clamp(40px, 5.6vw, 80px)" }}>{code.code}</h1>
          <p className="epage__lead" style={{ marginTop: 16 }}>{code.name}</p>
        </div>
      </section>

      <section className="epage-sec">
        <div className="egrid esplit--detail">
          <div style={{ display: "grid", gap: 16 }}>
            <Block icon={FileText} title={L.descTitle}>{code.description}</Block>
            <Block icon={Package} title={L.storageTitle}>{code.storage}</Block>
            <Block icon={Truck} title={L.transportTitle}>{code.transport}</Block>
            <Block icon={ShieldCheck} title={L.utilTitle}>{code.utilization_process}</Block>
            <Block icon={FileText} title={L.docsTitle}>
              <ul>{(code.required_docs || []).map((d) => <li key={d}>{d}</li>)}</ul>
            </Block>

            <div style={{ marginTop: 8 }}>
              <h2 className="ecard__title" style={{ fontSize: 22, marginBottom: 8 }}>{L.faqTitle}</h2>
              <Accordion type="single" collapsible>
                <AccordionItem value="1"><AccordionTrigger>{L.faqQ1}</AccordionTrigger><AccordionContent>{code.hazardous ? L.faqA1Yes : L.faqA1No}{code.mirror_code ? L.faqA1Mirror(code.mirror_code) : ""}</AccordionContent></AccordionItem>
                <AccordionItem value="2"><AccordionTrigger>{L.faqQ2}</AccordionTrigger><AccordionContent>{L.faqA2(code.min_order_kg, unitWord)}</AccordionContent></AccordionItem>
              </Accordion>
            </div>
          </div>

          {/* Right rail */}
          <aside style={{ position: "sticky", top: 110 }}>
            <div className="esurface">
              <div className="esummary__label">{L.priceTitle}</div>
              <div className="esummary__total" style={{ marginTop: 6 }}>
                {code.price_from != null ? L.priceFrom(code.price_from) : L.onRequest}
                {code.price_from != null && <span style={{ fontSize: 16, fontWeight: 400, color: "var(--eco-muted)" }}>/{code.price_unit}</span>}
              </div>
              {lic && <div style={{ marginTop: 14 }}><span className={`epill ${lic.accepted ? "epill--ok" : "epill--haz"}`}><i />{lic.accepted ? L.accepted : L.onRequest}</span></div>}
              <div style={{ marginTop: 18, display: "grid", gap: 10 }}>
                <div className="esummary__row"><span>{L.minBatch}</span><b>{code.min_order_kg} {unitWord}</b></div>
                <div className="esummary__row"><span>{L.specTransport}</span><b>{code.requires_transport ? L.yes : L.no}</b></div>
                <div className="esummary__row"><span>{L.needContainer}</span><b>{code.requires_container ? L.yes : L.no}</b></div>
              </div>
              {lic && lic.accepted === false ? (
                <div className="enote enote--haz" style={{ marginTop: 20, flexDirection: "column", alignItems: "stretch" }} data-testid="codepage-not-accepted">
                  <span>{L.notLicensed[0]}<b>{L.notLicensed[1]}</b>{L.notLicensed[2]}</span>
                  <Link to="/contacts" className="ebtn ebtn--ghost" style={{ width: "100%", justifyContent: "center", marginTop: 14, height: 46 }}>{L.contactUs}</Link>
                </div>
              ) : (
                <>
                  <button className="ebtn ebtn--primary" style={{ width: "100%", justifyContent: "center", marginTop: 20 }} onClick={() => setOpen(true)} data-testid="codepage-create-request-button" data-cursor>{L.createRequest}</button>
                  <Link to="/calculator" className="ebtn ebtn--ghost" style={{ width: "100%", justifyContent: "center", marginTop: 10 }}>{L.calcCost}</Link>
                </>
              )}
              {code.hazardous && <div className="enote enote--info" style={{ marginTop: 18 }}><AlertTriangle /> {L.hazNote}</div>}
            </div>
          </aside>
        </div>
        <RequestDialog open={open} onOpenChange={setOpen} prefillCode={code.code} prefillName={code.name} />
      </section>
    </div>
  );
}
