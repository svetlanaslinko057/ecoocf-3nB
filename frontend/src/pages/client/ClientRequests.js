import React, { useEffect, useState, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { ClientAPI } from "@/lib/clientApi";
import NewRequestModal from "./NewRequestModal";
import { useClientCopy } from "./clientCopy";

const STAGE_TONE = {
  new: "tone-blue", quote: "tone-amber", contract: "tone-violet",
  pickup: "tone-cyan", utilization: "tone-green", act: "tone-green", archived: "tone-grey",
};

export default function ClientRequests() {
  const navigate = useNavigate();
  const location = useLocation();
  const { L, stageLabel } = useClientCopy();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showNew, setShowNew] = useState(false);
  const [reordering, setReordering] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await ClientAPI.requests();
      setItems(d.items || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (location.state && location.state.openNew) setShowNew(true);
  }, [location.state]);

  const doReorder = async (e, id) => {
    e.stopPropagation();
    setReordering(id);
    try {
      const d = await ClientAPI.reorder(id);
      await load();
      if (d.request_id) navigate(`/client/requests/${d.request_id}`);
    } finally {
      setReordering("");
    }
  };

  return (
    <div data-testid="client-requests">
      <div className="cl-head">
        <div>
          <p className="cl-eyebrow">{L.reqEyebrow}</p>
          <h1 className="cl-h1">{L.requestsH}</h1>
        </div>
        <button className="cl-btn cl-btn--primary" onClick={() => setShowNew(true)} data-testid="requests-new">
          {L.newRequest}
        </button>
      </div>

      {loading ? (
        <div className="cl-skel">{L.loading}</div>
      ) : items.length === 0 ? (
        <div className="cl-card">
          <div className="cl-empty">
            <p>{L.reqEmpty}</p>
            <button className="cl-btn cl-btn--primary" onClick={() => setShowNew(true)}>{L.createFirst}</button>
          </div>
        </div>
      ) : (
        <div className="cl-card cl-card--flush">
          <table className="cl-table">
            <thead>
              <tr>
                <th>{L.thNumDate}</th>
                <th>{L.thItems}</th>
                <th>{L.thStatus}</th>
                <th>{L.thAmount}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <tr key={r.id} onClick={() => navigate(`/client/requests/${r.id}`)} data-testid={`request-row-${r.id}`}>
                  <td>
                    <div className="cl-td-main">{r.id}</div>
                    <div className="cl-td-sub">{(r.created_at || "").slice(0, 10)}</div>
                  </td>
                  <td>{(r.items || []).map((i) => i.waste_code).slice(0, 3).join(", ") || "\u2014"}</td>
                  <td><span className={`cl-chip ${STAGE_TONE[r.stage] || "tone-grey"}`}>{stageLabel(r.stage, r.stage_label)}</span></td>
                  <td>{r.amount != null ? `${r.amount} ${r.currency || "UAH"}` : "\u2014"}</td>
                  <td className="cl-td-actions">
                    <button
                      className="cl-btn cl-btn--ghost cl-btn--sm"
                      onClick={(e) => doReorder(e, r.id)}
                      disabled={reordering === r.id}
                      data-testid={`reorder-${r.id}`}
                    >
                      {reordering === r.id ? "\u2026" : L.repeat}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showNew && (
        <NewRequestModal
          onClose={() => setShowNew(false)}
          onCreated={(id) => {
            setShowNew(false);
            load();
            if (id) navigate(`/client/requests/${id}`);
          }}
        />
      )}
    </div>
  );
}
