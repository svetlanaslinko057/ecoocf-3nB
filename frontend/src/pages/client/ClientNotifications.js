import React, { useEffect, useState, useCallback } from "react";
import { ClientAPI } from "@/lib/clientApi";
import { useClientCopy } from "./clientCopy";

const PRIORITY_LABEL = { high: "!", normal: "", low: "" };

function fmt(iso) {
  if (!iso) return "";
  try { return new Date(iso).toLocaleString("uk-UA", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }); }
  catch { return iso; }
}

export default function ClientNotifications() {
  const { L } = useClientCopy();
  const [items, setItems] = useState([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const r = await ClientAPI.notifications({ limit: 100 });
      setItems(r.items || []);
      setUnread(r.unread || 0);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const openItem = async (n) => {
    if (n.read) return;
    try {
      await ClientAPI.markNotificationRead(n.id);
      setItems((p) => p.map((x) => (x.id === n.id ? { ...x, read: true } : x)));
      setUnread((u) => Math.max(0, u - 1));
    } catch { /* ignore */ }
  };

  const markAll = async () => {
    try { await ClientAPI.markAllNotificationsRead(); setItems((p) => p.map((x) => ({ ...x, read: true }))); setUnread(0); }
    catch { /* ignore */ }
  };

  if (loading) return <div className="cl-skel">{L.loading}</div>;

  return (
    <div data-testid="client-notifications">
      <div className="cl-head">
        <div>
          <p className="cl-eyebrow">{L.msgEyebrow}</p>
          <h1 className="cl-h1">{L.messagesH}</h1>
        </div>
        {unread > 0 && (
          <button className="cl-btn cl-btn--ghost" onClick={markAll} data-testid="client-msg-mark-all">{L.markAllRead}</button>
        )}
      </div>

      {items.length === 0 ? (
        <div className="cl-card"><div className="cl-empty"><p>{L.msgEmpty}</p></div></div>
      ) : (
        <div className="cl-card" style={{ padding: 0 }}>
          <ul className="cl-msglist">
            {items.map((n) => (
              <li
                key={n.id}
                className={`cl-msg ${n.read ? "" : "cl-msg--unread"}`}
                onClick={() => openItem(n)}
                data-testid="client-msg-row"
              >
                <div className="cl-msg__main">
                  <div className="cl-msg__title">
                    {!n.read && <span className="cl-msg__dot" />}
                    {n.priority === "high" && <span className="cl-msg__prio">!</span>}
                    {n.title}
                  </div>
                  {n.body && <div className="cl-msg__body">{n.body}</div>}
                  <div className="cl-msg__meta">
                    {n.from_name ? `${n.from_name}` : "ECO"} · {fmt(n.created_at)}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
