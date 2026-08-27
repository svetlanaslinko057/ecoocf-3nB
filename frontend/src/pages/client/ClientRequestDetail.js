import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ClientAPI } from "@/lib/clientApi";
import { useClientCopy } from "./clientCopy";

const STAGE_ORDER = ["new", "quote", "contract", "pickup", "utilization", "act"];

export default function ClientRequestDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { L, stageLabel } = useClientCopy();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const d = await ClientAPI.request(id);
        setData(d);
      } catch (e) {
        setErr(e?.response?.status === 403 ? L.errNoAccess : L.errNotFound);
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (loading) return <div className="cl-skel">{L.loading}</div>;
  if (err) return (
    <div className="cl-card"><div className="cl-empty"><p>{err}</p>
      <button className="cl-btn cl-btn--ghost" onClick={() => navigate("/client/requests")}>{L.backToRequests}</button>
    </div></div>
  );

  const r = data.request;
  const timeline = data.timeline || [];
  const docs = data.documents || {};
  const currentStage = r.stage;
  const reachedIdx = STAGE_ORDER.indexOf(currentStage);

  const doReorder = async () => {
    const d = await ClientAPI.reorder(r.id);
    if (d.request_id) navigate(`/client/requests/${d.request_id}`);
  };

  return (
    <div data-testid="client-request-detail">
      <button className="cl-back" onClick={() => navigate("/client/requests")}>{L.backAll}</button>
      <div className="cl-head">
        <div>
          <p className="cl-eyebrow">{L.requestWord} {r.id}</p>
          <h1 className="cl-h1">{stageLabel(currentStage, r.stage_label)}</h1>
        </div>
        <button className="cl-btn cl-btn--ghost" onClick={doReorder} data-testid="detail-reorder">{L.repeatOrder}</button>
      </div>

      {/* Stage progress */}
      <div className="cl-stages" data-testid="detail-stages">
        {STAGE_ORDER.map((st, i) => (
          <div key={st} className={`cl-stage ${i <= reachedIdx ? "is-done" : ""} ${st === currentStage ? "is-current" : ""}`}>
            <span className="cl-stage__dot" />
            <span className="cl-stage__lbl">{stageLabel(st)}</span>
          </div>
        ))}
      </div>

      <div className="cl-grid2">
        <div className="cl-card">
          <h2 className="cl-h2">{L.itemsH}</h2>
          <ul className="cl-items">
            {(r.items || []).map((it, i) => (
              <li key={i}>
                <b>{it.waste_code}</b> <span>{it.name}</span>
                <em>{it.qty != null ? `${it.qty} ${it.unit || L.kg}` : ""}</em>
                {it.hazardous && <span className="cl-haz">{L.hazardous}</span>}
              </li>
            ))}
          </ul>
          {r.comment && <p className="cl-comment">«{r.comment}»</p>}
          <div className="cl-meta-row">
            <span>{L.amountLbl} <b>{r.amount != null ? `${r.amount} ${r.currency || "UAH"}` : L.tbc}</b></span>
            {r.total_weight_kg ? <span>{L.weightLbl} <b>{r.total_weight_kg} {L.kg}</b></span> : null}
          </div>
        </div>

        <div className="cl-card">
          <h2 className="cl-h2">{L.timelineH}</h2>
          <ul className="cl-timeline">
            {timeline.length === 0 && <li className="cl-td-sub">{L.noEvents}</li>}
            {timeline.map((t, i) => (
              <li key={i}>
                <span className="cl-timeline__dot" />
                <div>
                  <b>{stageLabel(t.stage, t.stage)}</b>
                  <span className="cl-td-sub">{(t.at || "").slice(0, 16).replace("T", " ")}</span>
                  {t.note && <p>{t.note}</p>}
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="cl-card">
        <h2 className="cl-h2">{L.documentsH}</h2>
        {(docs.contracts || []).length === 0 && (docs.acts || []).length === 0 ? (
          <p className="cl-td-sub">{L.detailDocsEmpty}</p>
        ) : (
          <ul className="cl-docs">
            {(docs.contracts || []).map((c) => (
              <li key={c.id}><span className="cl-doc__tag">{L.tagContract}</span> {c.number} <em>{c.amount ? `${c.amount} ${c.currency || "UAH"}` : ""}</em></li>
            ))}
            {(docs.acts || []).map((a) => (
              <li key={a.id}><span className="cl-doc__tag">{L.tagAct}</span> {a.number} <em>{a.total_weight_kg ? `${a.total_weight_kg} ${L.kg}` : ""}</em></li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
