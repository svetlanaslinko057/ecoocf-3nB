import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ClientAPI } from "@/lib/clientApi";
import { money } from "@/lib/wasteMeta";
import { useClientCopy } from "./clientCopy";
import { Layers, Activity, CheckCircle2, Wallet, Phone, Mail, ArrowUpRight } from "lucide-react";

const STAGE_TONE = {
  new: "tone-blue", quote: "tone-amber", contract: "tone-violet",
  pickup: "tone-cyan", utilization: "tone-green", act: "tone-green", archived: "tone-grey",
};

export default function ClientOverview() {
  const navigate = useNavigate();
  const { L, lang, stageLabel } = useClientCopy();
  const [summary, setSummary] = useState(null);
  const [manager, setManager] = useState(null);
  const [recent, setRecent] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [s, r] = await Promise.all([ClientAPI.summary(), ClientAPI.requests()]);
        setSummary(s.summary);
        setManager(s.manager || null);
        setRecent((r.items || []).slice(0, 5));
      } catch (e) {
        /* handled by 401 -> layout redirect */
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const fmtMoney = (v) => {
    const cur = lang === "en" ? "UAH" : "грн";
    try { return money ? money(v || 0) : `${v || 0} ${cur}`; } catch { return `${v || 0} ${cur}`; }
  };

  if (loading) return <div className="cl-skel" data-testid="overview-loading">{L.loading}</div>;

  const s = summary || {};
  const kpis = [
    { label: L.kpiTotal, value: s.total_requests ?? 0, icon: Layers, testid: "overview-kpi-total-requests" },
    { label: L.kpiActive, value: s.open_requests ?? 0, icon: Activity, testid: "overview-kpi-active-requests" },
    { label: L.kpiCompleted, value: s.completed_requests ?? 0, icon: CheckCircle2, testid: "overview-kpi-completed-requests" },
    { label: L.kpiAmount, value: fmtMoney(s.total_amount), icon: Wallet, testid: "overview-kpi-amount" },
  ];

  return (
    <div data-testid="client-overview">
      <div className="cl-head">
        <div>
          <p className="cl-eyebrow">{L.ovEyebrow}</p>
          <h1 className="cl-h1">{L.overviewH}</h1>
        </div>
        <Link to="/client/requests" state={{ openNew: true }} className="cl-btn cl-btn--primary" data-testid="overview-new-request">
          {L.newRequest}
        </Link>
      </div>

      <div className="cl-kpis">
        {kpis.map((k) => {
          const Icon = k.icon;
          return (
            <div className="cl-kpi" key={k.label} data-testid={k.testid}>
              <span className="cl-kpi__ic"><Icon size={19} strokeWidth={2} /></span>
              <span className="cl-kpi__val">{k.value}</span>
              <span className="cl-kpi__lbl">{k.label}</span>
            </div>
          );
        })}
      </div>

      {manager && (
        <div className="cl-card cl-manager" data-testid="client-manager-card">
          <div className="cl-manager__avatar" aria-hidden="true">
            {(manager.name || manager.email || "?").trim().charAt(0).toUpperCase()}
          </div>
          <div className="cl-manager__body">
            <span className="cl-manager__eyebrow">{L.managerEyebrow}</span>
            <span className="cl-manager__name">{manager.name || manager.email}</span>
            <div className="cl-manager__contacts">
              {manager.phone && (
                <a href={`tel:${manager.phone}`} className="cl-btn cl-btn--ghost cl-btn--sm" data-testid="manager-call-button">
                  <Phone size={15} /> {manager.phone}
                </a>
              )}
              {manager.email && (
                <a href={`mailto:${manager.email}`} className="cl-btn cl-btn--ghost cl-btn--sm" data-testid="manager-email-button">
                  <Mail size={15} /> {manager.email}
                </a>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="cl-card">
        <div className="cl-card__head">
          <h2 className="cl-h2">{L.recentH}</h2>
          <Link to="/client/requests" className="cl-link" data-testid="overview-all-requests">{L.allRequests} <ArrowUpRight size={14} style={{ display: "inline", verticalAlign: "-2px" }} /></Link>
        </div>
        {recent.length === 0 ? (
          <div className="cl-empty" data-testid="overview-empty">
            <span className="cl-kpi__ic" style={{ width: 52, height: 52, borderRadius: 16 }}><Layers size={24} /></span>
            <p>{L.ovEmpty}</p>
            <Link to="/client/requests" state={{ openNew: true }} className="cl-btn cl-btn--primary">{L.createRequest}</Link>
          </div>
        ) : (
          <ul className="cl-list" data-testid="overview-recent-requests">
            {recent.map((r) => (
              <li key={r.id} className="cl-row" onClick={() => navigate(`/client/requests/${r.id}`)} data-testid="overview-recent-row">
                <div className="cl-row__main">
                  <span className="cl-row__id">{r.id}</span>
                  <span className="cl-row__items">
                    {(r.items || []).map((i) => i.waste_code).slice(0, 3).join(", ") || "\u2014"}
                  </span>
                </div>
                <span className={`cl-chip ${STAGE_TONE[r.stage] || "tone-grey"}`}>{stageLabel(r.stage, r.stage_label)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
