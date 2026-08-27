/**
 * ClientContracts — B2B customer read-only view of the Contract Execution Engine.
 * Договори · квартали (план/факт) · акти · рахунки · звіт еколога. Без редагування.
 */
import React, { useEffect, useState } from "react";
import { ClientAPI } from "@/lib/clientApi";

const money = (v, cur = "UAH") =>
  v == null ? "—" : `${Number(v).toLocaleString("uk-UA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${cur}`;
const kg = (v) => (v == null ? "0" : Number(v).toLocaleString("uk-UA", { maximumFractionDigits: 1 }));

const STATUS_UK = {
  draft: "Чернетка", sent: "Надіслано", agreed: "Погоджено", signed: "Підписано",
  active: "Активний", closed: "Закрито", cancelled: "Скасовано",
  pending: "Очікує", paid: "Оплачено", overdue: "Прострочено",
};

export default function ClientContracts() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sel, setSel] = useState(null);
  const [detail, setDetail] = useState(null);
  const [dLoading, setDLoading] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const r = await ClientAPI.ceContracts();
        setItems(r.items || []);
        if ((r.items || []).length) openDetail(r.items[0].id);
      } catch { /* ignore */ }
      finally { setLoading(false); }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openDetail = async (id) => {
    setSel(id); setDLoading(true);
    try { setDetail(await ClientAPI.ceContract(id)); }
    catch { setDetail(null); }
    finally { setDLoading(false); }
  };

  const openPdf = async (contractId, reportId) => {
    try {
      const blob = await ClientAPI.ceReportPdf(contractId, reportId);
      window.open(URL.createObjectURL(blob), "_blank");
    } catch { /* ignore */ }
  };

  if (loading) return <div className="cl-card" style={{ padding: 24 }}>Завантаження…</div>;

  if (!items.length)
    return (
      <div className="cl-card" style={{ padding: 32, textAlign: "center" }} data-testid="client-contracts-empty">
        <h2 style={{ margin: 0 }}>Договори</h2>
        <p style={{ color: "#64748b" }}>Наразі у вас немає активних договорів з графіком виконання.</p>
      </div>
    );

  const fin = detail?.financials || {};
  const cur = detail?.contract?.currency || "UAH";

  return (
    <div data-testid="client-contracts-page">
      <h1 style={{ fontSize: 24, fontWeight: 800, margin: "4px 0 16px" }}>Мої договори</h1>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
        {items.map((c) => (
          <button key={c.id} onClick={() => openDetail(c.id)} data-testid={`client-contract-${c.id}`}
            style={{
              padding: "8px 14px", borderRadius: 12, cursor: "pointer", fontWeight: 600,
              border: sel === c.id ? "2px solid #0E5E3A" : "1px solid #cbd5e1",
              background: sel === c.id ? "#ecfdf5" : "#fff", color: "#0f172a",
            }}>
            {c.number || c.title || c.id}
          </button>
        ))}
      </div>

      {dLoading || !detail ? (
        <div className="cl-card" style={{ padding: 24 }}>Завантаження договору…</div>
      ) : (
        <>
          {/* financial summary */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))", gap: 12, marginBottom: 20 }}>
            {[
              ["Договірна", fin.contract_value, "#0f172a"],
              ["Виконано", fin.executed_value, "#0E5E3A"],
              ["Виставлено", fin.invoiced_value, "#1d4ed8"],
              ["Оплачено", fin.paid_value, "#0E5E3A"],
              ["Залишок", fin.remaining_value, "#b45309"],
            ].map(([label, val, color]) => (
              <div key={label} className="cl-card" style={{ padding: 14 }} data-testid={`client-fin-${label}`}>
                <div style={{ fontSize: 11, textTransform: "uppercase", color: "#64748b", fontWeight: 700 }}>{label}</div>
                <div style={{ fontSize: 20, fontWeight: 800, color, marginTop: 4 }}>{money(val, cur)}</div>
              </div>
            ))}
          </div>

          {/* periods */}
          <SectionTitle title="Графік виконання (план / факт)" />
          {(detail.periods || []).map((p) => (
            <div key={p.id} className="cl-card" style={{ padding: 16, marginBottom: 12 }} data-testid={`client-period-${p.label}`}>
              <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8, marginBottom: 8 }}>
                <b>{p.label} <span style={{ fontWeight: 400, color: "#64748b", fontSize: 12 }}>{p.date_from} → {p.date_to}</span></b>
                <span style={{ fontSize: 13 }}>
                  План: <b>{money(p.totals?.planned_amount, cur)}</b> · Факт: <b style={{ color: "#0E5E3A" }}>{money(p.totals?.executed_amount, cur)}</b>
                </span>
              </div>
              <div style={{ overflowX: "auto" }}>
                <table className="cl-table" style={{ width: "100%", fontSize: 13, borderCollapse: "collapse" }}>
                  <thead><tr style={{ textAlign: "left", color: "#64748b" }}>
                    <th style={th}>Код</th><th style={th}>Найменування</th>
                    <th style={thR}>План, кг</th><th style={thR}>Факт, кг</th><th style={thR}>Сума (факт)</th>
                  </tr></thead>
                  <tbody>
                    {(p.lines || []).map((l) => (
                      <tr key={l.waste_code} style={{ borderTop: "1px solid #eef2f7" }}>
                        <td style={{ ...td, fontFamily: "monospace" }}>{l.waste_code}</td>
                        <td style={td}>{l.name}</td>
                        <td style={tdR}>{kg(l.planned_kg)}</td>
                        <td style={tdR}>{kg(l.actual_kg)}</td>
                        <td style={{ ...tdR, color: "#0E5E3A", fontWeight: 600 }}>{money(l.actual_amount, cur)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {(p.extra_works || []).length > 0 && (
                <div style={{ marginTop: 8, fontSize: 12, color: "#475569" }}>
                  Дод. роботи: {(p.extra_works || []).map((e) => `${e.label} — ${money(e.amount, cur)}`).join(" · ")}
                </div>
              )}
            </div>
          ))}

          {/* acts */}
          <SectionTitle title={`Акти утилізації (${(detail.acts || []).length})`} />
          <div className="cl-card" style={{ padding: 8, marginBottom: 16 }}>
            {(detail.acts || []).length === 0 ? <div style={{ padding: 12, color: "#64748b" }}>Немає</div> :
              (detail.acts || []).map((a) => (
                <Row key={a.id} testid={`client-act-${a.id}`}
                  left={`${a.number || "Акт"} · ${a.act_date || ""}`}
                  mid={`${kg(a.total_weight_kg)} кг · ${a.utilization_method || "—"}`}
                  right={STATUS_UK[a.status] || a.status} />
              ))}
          </div>

          {/* invoices */}
          <SectionTitle title={`Рахунки (${(detail.invoices || []).length})`} />
          <div className="cl-card" style={{ padding: 8, marginBottom: 16 }}>
            {(detail.invoices || []).length === 0 ? <div style={{ padding: 12, color: "#64748b" }}>Немає</div> :
              (detail.invoices || []).map((inv) => (
                <Row key={inv.id} testid={`client-invoice-${inv.id}`}
                  left={inv.number || inv.id}
                  mid={money(inv.amount ?? inv.total, cur)}
                  right={STATUS_UK[inv.status] || inv.status} />
              ))}
          </div>

          {/* ecologist reports */}
          <SectionTitle title={`Звіт еколога (${(detail.ecologist_reports || []).length})`} />
          <div className="cl-card" style={{ padding: 8 }}>
            {(detail.ecologist_reports || []).length === 0 ? <div style={{ padding: 12, color: "#64748b" }}>Ще не сформовано</div> :
              (detail.ecologist_reports || []).map((r) => (
                <div key={r.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 12px", borderTop: "1px solid #eef2f7" }} data-testid={`client-report-${r.id}`}>
                  <div>
                    <b>{r.number}</b> {r.status === "final" ? "· фінал" : "· чернетка"}
                    <div style={{ fontSize: 12, color: "#64748b" }}>Факт: {kg(r.actual_kg)} кг · {(r.utilization_methods || []).join(", ") || "—"}</div>
                  </div>
                  <button onClick={() => openPdf(detail.contract.id, r.id)} data-testid={`client-report-pdf-${r.id}`}
                    style={{ padding: "6px 12px", borderRadius: 10, border: "1px solid #0E5E3A", background: "#fff", color: "#0E5E3A", fontWeight: 600, cursor: "pointer" }}>
                    Завантажити PDF
                  </button>
                </div>
              ))}
          </div>
        </>
      )}
    </div>
  );
}

const th = { padding: "6px 8px", fontWeight: 600 };
const thR = { ...th, textAlign: "right" };
const td = { padding: "6px 8px" };
const tdR = { ...td, textAlign: "right" };

const SectionTitle = ({ title }) => (
  <h3 style={{ fontSize: 15, fontWeight: 700, color: "#0E5E3A", margin: "18px 0 8px" }}>{title}</h3>
);

const Row = ({ left, mid, right, testid }) => (
  <div data-testid={testid} style={{ display: "flex", justifyContent: "space-between", gap: 8, padding: "10px 12px", borderTop: "1px solid #eef2f7", fontSize: 13 }}>
    <span style={{ fontWeight: 600 }}>{left}</span>
    <span style={{ color: "#475569" }}>{mid}</span>
    <span style={{ color: "#0f172a" }}>{right}</span>
  </div>
);
