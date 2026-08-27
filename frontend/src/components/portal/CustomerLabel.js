// Reusable clickable customer label used EVERYWHERE a client appears in the CRM
// (invoices, payments, requests, contracts, acts, tasks, activity, …).
//
// Renders "Company — email" (fallback "Name — email"). The EMAIL portion is a
// link to the stable Customer 360 route (/app/customers/:id). We never show the
// raw customer_id as the primary text.
import React from "react";
import { Link } from "react-router-dom";
import { Mail, Building2 } from "lucide-react";
import { toCustomerDTO } from "@/lib/customerLabel";

export default function CustomerLabel({
  customer,          // resolved DTO or raw row (customerId/customerEmail/…)
  row,               // alias for `customer`
  showIcon = true,
  className = "",
  compact = false,
  onNavigate,        // optional callback (e.g. close a drawer before routing)
}) {
  const dto = toCustomerDTO(customer || row);
  if (!dto) return <span className="text-slate-400">—</span>;

  const primary = dto.company_name || dto.full_name;

  // No email → still show something meaningful, and link the whole thing.
  if (!dto.email) {
    const inner = <span className="font-medium text-slate-800">{primary || dto.id || "—"}</span>;
    return dto.href ? (
      <Link to={dto.href} onClick={onNavigate} className={`hover:underline ${className}`} data-testid="customer-label-link">
        {inner}
      </Link>
    ) : (
      <span className={className}>{inner}</span>
    );
  }

  return (
    <span className={`inline-flex min-w-0 flex-col ${className}`} data-testid="customer-label">
      {primary && !compact && (
        dto.href ? (
          <Link
            to={dto.href}
            onClick={onNavigate}
            className="inline-flex items-center gap-1 truncate text-sm font-semibold text-slate-800 hover:text-emerald-800 hover:underline"
            data-testid="customer-name-link"
            title="Відкрити картку клієнта"
          >
            {showIcon && <Building2 className="h-3.5 w-3.5 shrink-0 text-slate-400" />}
            <span className="truncate">{primary}</span>
          </Link>
        ) : (
          <span className="inline-flex items-center gap-1 truncate text-sm font-medium text-slate-800">
            {showIcon && <Building2 className="h-3.5 w-3.5 shrink-0 text-slate-400" />}
            <span className="truncate">{primary}</span>
          </span>
        )
      )}
      {dto.href ? (
        <Link
          to={dto.href}
          onClick={onNavigate}
          className="inline-flex items-center gap-1 truncate text-[13px] font-medium text-emerald-700 hover:text-emerald-800 hover:underline"
          data-testid="customer-email-link"
          title={`Відкрити картку клієнта · ${dto.email}`}
        >
          {showIcon && <Mail className="h-3.5 w-3.5 shrink-0" />}
          <span className="truncate">{dto.email}</span>
        </Link>
      ) : (
        <span className="truncate text-[13px] text-slate-600">{dto.email}</span>
      )}
    </span>
  );
}
