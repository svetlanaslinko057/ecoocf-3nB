// Single source of truth for how a customer is DISPLAYED and LINKED across the
// whole CRM. Golden rule: navigate by the stable customer_id, show the email
// (email can change, so it is never used as the route key). Never surface the
// raw customer_id as the primary text.

/**
 * Normalise any customer-bearing object into a UI DTO.
 * Accepts either:
 *   - a resolved DTO  { id, email, company_name, display_label, ... }
 *   - a raw row       { customerId, customerEmail, customerName, company_name }
 *   - a customer doc  { id, email, name, company_name }
 */
export function toCustomerDTO(src) {
  if (!src) return null;
  // Already-resolved DTO from the backend resolver
  if (src.display_label && (src.id || src.customer_360_url)) {
    return {
      id: src.id || "",
      email: src.email || "",
      full_name: src.full_name || "",
      company_name: src.company_name || "",
      label: src.display_label,
      href: src.customer_360_url || (src.id ? `/app/customers/${src.id}` : ""),
    };
  }
  const id = src.id || src.customerId || src.customer_id || "";
  const email = src.email || src.customerEmail || "";
  const full_name = src.full_name || src.name || src.customerName || "";
  const company_name = src.company_name || src.companyName || "";
  const primary = company_name || full_name;
  let label;
  if (primary && email) label = `${primary} — ${email}`;
  else if (primary) label = primary;
  else if (email) label = email;
  else label = id || "—";
  return {
    id,
    email,
    full_name,
    company_name,
    label,
    href: id ? `/app/customers/${id}` : "",
  };
}

/** Convenience: just the display label string. */
export function customerLabel(src) {
  const dto = toCustomerDTO(src);
  return dto ? dto.label : "—";
}
