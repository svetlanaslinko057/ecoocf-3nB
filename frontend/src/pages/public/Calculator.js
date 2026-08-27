import React, { useEffect, useRef, useState } from "react";
import { Search, Loader2, ArrowRight, Truck, Package, Zap, AlertTriangle } from "lucide-react";
import { WasteAPI } from "@/lib/api";
import { useSeo } from "@/lib/seo";
import { useLang } from "@/i18n";
import { REGIONS, money } from "@/lib/wasteMeta";
import { Switch } from "@/components/ui/switch";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { RequestDialog } from "@/components/RequestDialog";
import "./eco-pages.css";

const T = {
  uk: {
    seoTitle: "Калькулятор вартості",
    seoDesc: "Розрахуйте орієнтовну вартість утилізації небезпечних відходів: код, вага, регіон, тара, транспорт.",
    eyebrow: "Калькулятор",
    title: "Розрахунок вартості утилізації",
    lead: "Оберіть відхід, вкажіть об’єм і логістику — отримайте орієнтовний розрахунок із прозорою деталізацією.",
    step1: "1. Що утилізуємо?",
    searchPh: "Назва або код відходу",
    haz: "Небезпечні *", nonHaz: "Ненебезпечні",
    step2: "2. Об’єм, кг", step3: "3. Регіон",
    needContainer: "Потрібна тара / контейнери",
    needTransport: "Потрібен забір / транспорт",
    urgent: "Терміново",
    calculating: "Розрахунок…", getEstimate: "Отримати розрахунок",
    summary: "Підсумок",
    summaryHint: "Оберіть відхід та натисніть «Отримати розрахунок».",
    totalFrom: "Разом від", unit: "грн",
    createRequest: "Створити заявку",
  },
  en: {
    seoTitle: "Cost calculator",
    seoDesc: "Estimate the cost of hazardous-waste disposal: code, weight, region, containers, transport.",
    eyebrow: "Calculator",
    title: "Disposal cost calculation",
    lead: "Pick the waste, enter the volume and logistics — get an indicative estimate with transparent breakdown.",
    step1: "1. What are we disposing of?",
    searchPh: "Waste name or code",
    haz: "Hazardous *", nonHaz: "Non-hazardous",
    step2: "2. Volume, kg", step3: "3. Region",
    needContainer: "Containers / packaging needed",
    needTransport: "Pickup / transport needed",
    urgent: "Urgent",
    calculating: "Calculating…", getEstimate: "Get the estimate",
    summary: "Summary",
    summaryHint: "Pick a waste and press “Get the estimate”.",
    totalFrom: "Total from", unit: "UAH",
    createRequest: "Create a request",
  },
};

export default function Calculator() {
  const { lang } = useLang();
  const L = T[lang] || T.uk;
  useSeo(L.seoTitle, L.seoDesc);
  const [picked, setPicked] = useState(null);
  const [q, setQ] = useState("");
  const [opts, setOpts] = useState([]);
  const [searching, setSearching] = useState(false);
  const [openList, setOpenList] = useState(false);
  const [weight, setWeight] = useState(100);
  const [region, setRegion] = useState("kyiv");
  const [container, setContainer] = useState(false);
  const [transport, setTransport] = useState(true);
  const [urgent, setUrgent] = useState(false);
  const [result, setResult] = useState(null);
  const [calculating, setCalculating] = useState(false);
  const [reqOpen, setReqOpen] = useState(false);
  const boxRef = useRef(null);
  const tmr = useRef(null);
  const suppress = useRef(false);

  useEffect(() => {
    const onClick = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setOpenList(false); };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  useEffect(() => {
    if (tmr.current) clearTimeout(tmr.current);
    if (!q.trim()) { setOpts([]); return; }
    if (suppress.current) { suppress.current = false; setOpts([]); setOpenList(false); return; }
    setSearching(true);
    tmr.current = setTimeout(async () => {
      try { const r = await WasteAPI.search(q.trim(), 8); setOpts(r.items || []); setOpenList(true); }
      catch { setOpts([]); } finally { setSearching(false); }
    }, 250);
    return () => tmr.current && clearTimeout(tmr.current);
  }, [q]);

  const choose = (it) => { suppress.current = true; setPicked(it); setQ(`${it.code} — ${it.name}`); setOpenList(false); setOpts([]); setResult(null); };

  const calc = async () => {
    if (!picked) return;
    setCalculating(true);
    try {
      const r = await WasteAPI.price({
        wasteCode: picked.code, weight: Number(weight) || 0, region,
        container: container ? "needed" : "provided", transport, urgent,
      });
      setResult(r);
    } finally { setCalculating(false); }
  };

  return (
    <div className="epage" data-testid="calculator-page">
      <section className="epage-hero">
        <div className="epage-hero__inner">
          <div className="epage__eyebrow"><i />{L.eyebrow}</div>
          <h1 className="epage__title">{L.title}</h1>
          <p className="epage__lead">{L.lead}</p>
        </div>
      </section>

      <section className="epage-sec">
        <div className="egrid esplit">
          {/* form */}
          <div className="esurface">
            <label className="elabel">{L.step1}</label>
            <div className="einput-wrap" ref={boxRef}>
              <Search />
              <input
                value={q}
                onChange={(e) => { setQ(e.target.value); setPicked(null); }}
                placeholder={L.searchPh}
                data-testid="calculator-waste-input"
                className="einput einput--search"
              />
              {searching && <Loader2 className="einput-spin animate-spin" />}
              {openList && opts.length > 0 && (
                <div className="eoptions">
                  {opts.map((it) => (
                    <button key={it.code} type="button" onMouseDown={(e) => { e.preventDefault(); choose(it); }} data-testid="calculator-waste-option" className="eoption">
                      <span className="pointer-events-none" style={{ minWidth: 0 }}>
                        <span className="eoption__code">{it.code}</span>
                        <span className="eoption__name">{it.name.slice(0, 40)}</span>
                      </span>
                      <span className={`epill ${it.hazardous ? "epill--haz" : "epill--ok"}`}>{it.hazardous ? L.haz : L.nonHaz}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="egrid egrid--2" style={{ marginTop: 22 }}>
              <div className="efield">
                <label className="elabel">{L.step2}</label>
                <input type="number" value={weight} onChange={(e) => setWeight(e.target.value)} data-testid="calculator-kg-input" className="einput" />
              </div>
              <div className="efield">
                <label className="elabel">{L.step3}</label>
                <Select value={region} onValueChange={setRegion}>
                  <SelectTrigger data-testid="calculator-region-select" style={{ height: 54, borderRadius: 12 }}><SelectValue /></SelectTrigger>
                  <SelectContent>{REGIONS.map((r) => <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>

            <div style={{ marginTop: 22, display: "grid", gap: 12 }}>
              <div className="etoggle-row">
                <span className="etoggle-row__label"><Package /> {L.needContainer}</span>
                <Switch checked={container} onCheckedChange={setContainer} data-testid="calculator-container-switch" />
              </div>
              <div className="etoggle-row">
                <span className="etoggle-row__label"><Truck /> {L.needTransport}</span>
                <Switch checked={transport} onCheckedChange={setTransport} data-testid="calculator-transport-switch" />
              </div>
              <div className="etoggle-row">
                <span className="etoggle-row__label"><Zap /> {L.urgent}</span>
                <Switch checked={urgent} onCheckedChange={setUrgent} data-testid="calculator-urgent-switch" />
              </div>
            </div>

            <button className="ebtn ebtn--primary" style={{ width: "100%", justifyContent: "center", marginTop: 24 }} disabled={!picked || calculating} onClick={calc} data-testid="calculator-submit-button" data-cursor>
              {calculating ? L.calculating : L.getEstimate}
            </button>
          </div>

          {/* summary */}
          <div className="esurface" style={{ position: "sticky", top: 110 }}>
            <div className="esummary__label">{L.summary}</div>
            {!result && <p className="ecard__desc" style={{ marginTop: 14 }}>{L.summaryHint}</p>}
            {result && result.ok && (
              <div style={{ marginTop: 14 }} data-testid="calculator-price-breakdown">
                <div className="eoption__code" style={{ fontSize: 18 }}>{result.code}</div>
                <div style={{ marginTop: 16, display: "grid", gap: 10 }}>
                  {(result.breakdown || []).map((b) => (
                    <div key={b.key} className="esummary__row"><span>{b.label}</span><b>{money(b.amount)} {L.unit}</b></div>
                  ))}
                </div>
                <div style={{ height: 1, background: "var(--eco-line)", margin: "18px 0" }} />
                <div className="esummary__row" style={{ alignItems: "baseline" }}>
                  <span>{L.totalFrom}</span>
                  <span className="esummary__total" data-testid="calculator-total">{money(result.price)} {L.unit}</span>
                </div>
                <p className="ecard__desc" style={{ marginTop: 10 }}>{result.note}</p>
                <button className="ebtn ebtn--primary" style={{ width: "100%", justifyContent: "center", marginTop: 20 }} onClick={() => setReqOpen(true)} data-testid="calculator-create-request-button" data-cursor>
                  {L.createRequest} <ArrowRight />
                </button>
              </div>
            )}
            {result && !result.ok && (
              <div className="enote enote--haz" style={{ marginTop: 14 }}><AlertTriangle />{result.reason}</div>
            )}
          </div>
        </div>
        <RequestDialog open={reqOpen} onOpenChange={setReqOpen} prefillCode={picked?.code || ""} prefillName={picked?.name || ""} />
      </section>
    </div>
  );
}
