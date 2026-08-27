import React, { useEffect, useState } from "react";
import { ClientAPI } from "@/lib/clientApi";
import { useClientCopy } from "./clientCopy";

export default function ClientDocuments() {
  const { L } = useClientCopy();
  const [docs, setDocs] = useState({ contracts: [], acts: [] });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const d = await ClientAPI.documents();
        setDocs({ contracts: d.contracts || [], acts: d.acts || [] });
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <div className="cl-skel">{L.loading}</div>;

  const empty = docs.contracts.length === 0 && docs.acts.length === 0;

  return (
    <div data-testid="client-documents">
      <div className="cl-head">
        <div>
          <p className="cl-eyebrow">{L.docEyebrow}</p>
          <h1 className="cl-h1">{L.documentsH}</h1>
        </div>
      </div>

      {empty ? (
        <div className="cl-card"><div className="cl-empty"><p>{L.docEmpty}</p></div></div>
      ) : (
        <>
          <div className="cl-card">
            <h2 className="cl-h2">{L.contracts}</h2>
            {docs.contracts.length === 0 ? <p className="cl-td-sub">{L.none}</p> : (
              <ul className="cl-docs">
                {docs.contracts.map((c) => (
                  <li key={c.id}>
                    <span className="cl-doc__tag">{L.tagContract}</span>
                    <b>{c.number}</b>
                    <span className="cl-td-sub">{(c.created_at || "").slice(0, 10)}</span>
                    <em>{c.amount ? `${c.amount} ${c.currency || "UAH"}` : ""}</em>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="cl-card">
            <h2 className="cl-h2">{L.actsH}</h2>
            {docs.acts.length === 0 ? <p className="cl-td-sub">{L.none}</p> : (
              <ul className="cl-docs">
                {docs.acts.map((a) => (
                  <li key={a.id}>
                    <span className="cl-doc__tag cl-doc__tag--green">{L.tagAct}</span>
                    <b>{a.number}</b>
                    <span className="cl-td-sub">{(a.created_at || "").slice(0, 10)}</span>
                    <em>{a.total_weight_kg ? `${a.total_weight_kg} ${L.kg}` : ""}</em>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </div>
  );
}
