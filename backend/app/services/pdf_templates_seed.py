"""
Sprint 3 - Default HTML templates for the BIBI Cars PDF Engine.

These templates are seeded into ``document_templates`` collection on
first boot. Admin can edit them at any time via
``/api/admin/document-templates``.

Variables available (passed by app.services.pdf_engine.render):
  customer       - dict, customer entity (firstName, lastName, email, phone, ...)
  manager        - dict, staff entity managing the deal
  company        - dict, company branding (name, address, vat, logo_url)
  invoice        - dict, invoice document
  order          - dict, order document
  vehicle        - dict (optional), vehicle (make, model, year, vin, ...)
  calculation    - dict (optional), captured cost snapshot
  generated_at   - ISO-8601 string
  version        - integer (1, 2, ...) - this generation's version
  signatures     - dict { signed_by, signed_at } (placeholder)

All templates use Jinja2 ``{{ var }}`` syntax with ``| default("...")`` filters
so missing fields render gracefully.
"""

_BASE_CSS = """
  @page { size: A4; margin: 18mm; @bottom-right { content: "Page " counter(page) " / " counter(pages); font-size: 9pt; color: #71717A; } }
  body { font-family: 'Helvetica', 'Arial', sans-serif; color: #18181B; font-size: 11pt; line-height: 1.4; }
  h1 { font-size: 18pt; margin: 0 0 8mm; color: #18181B; }
  h2 { font-size: 13pt; margin: 8mm 0 3mm; color: #3F3F46; border-bottom: 1px solid #E4E4E7; padding-bottom: 2mm; }
  h3 { font-size: 11pt; margin: 5mm 0 2mm; }
  .header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10mm; padding-bottom: 6mm; border-bottom: 2px solid #18181B; }
  .brand { font-size: 22pt; font-weight: 900; letter-spacing: 0.5pt; color: #18181B; }
  .brand-sub { font-size: 9pt; color: #71717A; margin-top: 1mm; }
  .doc-meta { text-align: right; font-size: 9pt; color: #71717A; }
  .doc-meta .num { font-size: 13pt; color: #18181B; font-weight: 700; }
  .row { display: flex; gap: 12mm; margin-bottom: 4mm; }
  .col { flex: 1; }
  .col label { display: block; font-size: 8pt; color: #71717A; text-transform: uppercase; letter-spacing: 0.5pt; margin-bottom: 1mm; }
  .col span { font-weight: 600; font-size: 11pt; }
  table { width: 100%; border-collapse: collapse; margin: 4mm 0; }
  th { text-align: left; background: #F4F4F5; padding: 3mm; font-size: 9pt; text-transform: uppercase; color: #3F3F46; letter-spacing: 0.5pt; }
  td { padding: 3mm; border-bottom: 1px solid #E4E4E7; font-size: 10pt; }
  .total-row { font-weight: 700; font-size: 12pt; background: #18181B; color: white; }
  .total-row td { color: white; }
  .signatures { margin-top: 20mm; display: flex; gap: 15mm; }
  .sig-block { flex: 1; }
  .sig-line { border-top: 1px solid #18181B; padding-top: 2mm; font-size: 9pt; }
  .sig-label { font-size: 8pt; color: #71717A; text-transform: uppercase; }
  .small { font-size: 8pt; color: #71717A; }
  .badge { display: inline-block; padding: 1mm 3mm; background: #18181B; color: white; font-size: 8pt; text-transform: uppercase; letter-spacing: 0.5pt; border-radius: 2mm; }
  .footer { position: running(footer); font-size: 8pt; color: #71717A; text-align: center; border-top: 1px solid #E4E4E7; padding-top: 2mm; }
"""

_CONTRACT_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Service Contract</title>
<style>__BASE_CSS__</style></head><body>
<div class="header">
  <div>
    <div class="brand">{{ company.name | default("BIBI CARS") }}</div>
    <div class="brand-sub">{{ company.address | default("Sofia, Bulgaria") }} | {{ company.email | default("info@bibi.cars") }}</div>
    <div class="brand-sub">{{ company.vat | default("") }}</div>
  </div>
  <div class="doc-meta">
    <div class="badge">SERVICE CONTRACT</div>
    <div class="num">No. {{ invoice.id | default(order.id) | default("") }}</div>
    <div>Date: {{ generated_at[:10] }}</div>
    <div>Version: v{{ version | default(1) }}</div>
  </div>
</div>

<h1>Service Contract</h1>
<p>This contract is entered between <strong>{{ company.name | default("BIBI CARS LTD") }}</strong> ("Service Provider") and the Customer named below, for the services described in Section 2.</p>

<h2>1. Customer details</h2>
<div class="row">
  <div class="col"><label>Full name</label><span>{{ customer.firstName | default("") }} {{ customer.lastName | default("") }}</span></div>
  <div class="col"><label>Email</label><span>{{ customer.email | default("-") }}</span></div>
  <div class="col"><label>Phone</label><span>{{ customer.phone | default("-") }}</span></div>
</div>
<div class="row">
  <div class="col"><label>Country</label><span>{{ customer.country | default("-") }}</span></div>
  <div class="col"><label>City</label><span>{{ customer.city | default("-") }}</span></div>
  <div class="col"><label>Address</label><span>{{ customer.address | default("-") }}</span></div>
</div>

{% if vehicle %}
<h2>2. Vehicle</h2>
<div class="row">
  <div class="col"><label>Make / Model</label><span>{{ vehicle.make | default("") }} {{ vehicle.model | default("") }}</span></div>
  <div class="col"><label>Year</label><span>{{ vehicle.year | default("-") }}</span></div>
  <div class="col"><label>VIN</label><span style="font-family:monospace;">{{ vehicle.vin | default("-") }}</span></div>
</div>
{% endif %}

<h2>{% if vehicle %}3{% else %}2{% endif %}. Services</h2>
<table>
  <thead><tr><th>#</th><th>Service</th><th style="text-align:right">Qty</th><th style="text-align:right">Unit price</th><th style="text-align:right">Total</th></tr></thead>
  <tbody>
  {% for item in invoice['items'] | default([]) %}
    <tr>
      <td>{{ loop.index }}</td>
      <td>{{ item.name | default("") }}{% if item.description %}<br><span class="small">{{ item.description }}</span>{% endif %}</td>
      <td style="text-align:right">{{ item.qty | default(1) }}</td>
      <td style="text-align:right">{{ "%.2f"|format(item.price | default(0) | float) }}</td>
      <td style="text-align:right">{{ "%.2f"|format(item.line_total | default((item.price | default(0) | float) * (item.qty | default(1) | float))) }}</td>
    </tr>
  {% endfor %}
    <tr class="total-row"><td colspan="4" style="text-align:right">Total ({{ invoice.currency | default("USD") | upper }})</td><td style="text-align:right">{{ "%.2f"|format(invoice.total | default(invoice.amount) | default(0) | float) }}</td></tr>
  </tbody>
</table>

<h2>{% if vehicle %}4{% else %}3{% endif %}. Terms</h2>
<p class="small">4.1 The Service Provider will deliver the services listed above according to the BIBI Cars standard SLA.</p>
<p class="small">4.2 Payment is due upon contract signing. Late payments may incur penalties per company policy.</p>
<p class="small">4.3 This contract is governed by the laws of the Service Provider's jurisdiction.</p>

<div class="signatures">
  <div class="sig-block">
    <div class="sig-line">{{ company.name | default("BIBI CARS LTD") }}</div>
    <div class="sig-label">Service Provider · {{ manager.name | default(manager.email) | default("_______") }}</div>
  </div>
  <div class="sig-block">
    <div class="sig-line">{{ customer.firstName | default("") }} {{ customer.lastName | default("") }}</div>
    <div class="sig-label">Customer signature</div>
  </div>
</div>
</body></html>"""

_ACCEPTANCE_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Acceptance Act</title>
<style>__BASE_CSS__</style></head><body>
<div class="header">
  <div>
    <div class="brand">{{ company.name | default("BIBI CARS") }}</div>
    <div class="brand-sub">{{ company.address | default("Sofia, Bulgaria") }}</div>
  </div>
  <div class="doc-meta">
    <div class="badge">ACCEPTANCE ACT</div>
    <div class="num">No. {{ order.id | default("") }}</div>
    <div>Date: {{ generated_at[:10] }}</div>
    <div>Version: v{{ version | default(1) }}</div>
  </div>
</div>

<h1>Acceptance Act of Completed Works</h1>
<p>This Act confirms that the works specified in the contract have been completed by <strong>{{ company.name | default("BIBI CARS LTD") }}</strong> and accepted by the Customer below.</p>

<h2>Customer</h2>
<div class="row">
  <div class="col"><label>Full name</label><span>{{ customer.firstName | default("") }} {{ customer.lastName | default("") }}</span></div>
  <div class="col"><label>Phone</label><span>{{ customer.phone | default("-") }}</span></div>
  <div class="col"><label>Country</label><span>{{ customer.country | default("-") }}</span></div>
</div>

{% if vehicle %}
<h2>Vehicle</h2>
<div class="row">
  <div class="col"><label>Make / Model</label><span>{{ vehicle.make | default("") }} {{ vehicle.model | default("") }}</span></div>
  <div class="col"><label>Year</label><span>{{ vehicle.year | default("-") }}</span></div>
  <div class="col"><label>VIN</label><span style="font-family:monospace;">{{ vehicle.vin | default("-") }}</span></div>
</div>
{% endif %}

<h2>Completed services</h2>
<table>
  <thead><tr><th>#</th><th>Service</th><th>Status</th><th>Completed at</th></tr></thead>
  <tbody>
  {% for step in order['steps'] | default([]) %}
    <tr>
      <td>{{ loop.index }}</td>
      <td>{{ step.label | default(step.service_name) | default(step.key) }}</td>
      <td>{{ step.status | default("-") | upper }}</td>
      <td>{{ step.completed_at[:10] if step.completed_at else "-" }}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>

<p>Total agreed sum: <strong>{{ "%.2f"|format(order.amount | default(0) | float) }} {{ order.currency | default("USD") | upper }}</strong></p>
<p class="small">By signing this Act, the Customer acknowledges that the services have been delivered to the agreed quality standards. No claims or further obligations remain.</p>

<div class="signatures">
  <div class="sig-block">
    <div class="sig-line">{{ company.name | default("BIBI CARS LTD") }}</div>
    <div class="sig-label">Service Provider · {{ manager.name | default(manager.email) | default("_______") }}</div>
  </div>
  <div class="sig-block">
    <div class="sig-line">{{ customer.firstName | default("") }} {{ customer.lastName | default("") }}</div>
    <div class="sig-label">Customer signature</div>
  </div>
</div>
</body></html>"""

_INVOICE_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Invoice</title>
<style>__BASE_CSS__</style></head><body>
<div class="header">
  <div>
    <div class="brand">{{ company.name | default("BIBI CARS") }}</div>
    <div class="brand-sub">{{ company.address | default("Sofia, Bulgaria") }}</div>
    <div class="brand-sub">{{ company.email | default("") }}</div>
  </div>
  <div class="doc-meta">
    <div class="badge">INVOICE</div>
    <div class="num">{{ invoice.id | default("") }}</div>
    <div>Issue date: {{ generated_at[:10] }}</div>
    <div>Due date: {{ invoice.dueDate | default("-") }}</div>
    <div>Status: <strong>{{ invoice.status | default("pending") | upper }}</strong></div>
  </div>
</div>

<h2>Bill to</h2>
<div class="row">
  <div class="col">
    <label>Customer</label>
    <span>{{ customer.firstName | default("") }} {{ customer.lastName | default("") }}</span>
  </div>
  <div class="col"><label>Email</label><span>{{ customer.email | default("-") }}</span></div>
  <div class="col"><label>Phone</label><span>{{ customer.phone | default("-") }}</span></div>
</div>

<h2>Items</h2>
<table>
  <thead><tr><th>#</th><th>Service</th><th style="text-align:right">Qty</th><th style="text-align:right">Unit price</th><th style="text-align:right">Line total</th></tr></thead>
  <tbody>
  {% for item in invoice['items'] | default([]) %}
    <tr>
      <td>{{ loop.index }}</td>
      <td>{{ item.name | default("") }}</td>
      <td style="text-align:right">{{ item.qty | default(1) }}</td>
      <td style="text-align:right">{{ "%.2f"|format(item.price | default(0) | float) }}</td>
      <td style="text-align:right">{{ "%.2f"|format(item.line_total | default((item.price | default(0) | float) * (item.qty | default(1) | float))) }}</td>
    </tr>
  {% endfor %}
    <tr class="total-row"><td colspan="4" style="text-align:right">Total due ({{ invoice.currency | default("USD") | upper }})</td><td style="text-align:right">{{ "%.2f"|format(invoice.total | default(invoice.amount) | default(0) | float) }}</td></tr>
  </tbody>
</table>

<h3>Payment instructions</h3>
<p class="small">Please pay this invoice via Stripe using the secure link sent by your manager, or contact <strong>{{ manager.email | default(company.email) | default("info@bibi.cars") }}</strong> for alternative payment methods.</p>

<p class="small">Thank you for choosing BIBI Cars.</p>
</body></html>"""

# Inject shared base CSS into every template
_CONTRACT_HTML    = _CONTRACT_HTML.replace("__BASE_CSS__", _BASE_CSS)
_ACCEPTANCE_HTML  = _ACCEPTANCE_HTML.replace("__BASE_CSS__", _BASE_CSS)
_INVOICE_HTML     = _INVOICE_HTML.replace("__BASE_CSS__", _BASE_CSS)

DEFAULT_TEMPLATES = [
    {
        "type":     "contract",
        "name":     "Standard Service Contract (EN)",
        "language": "en",
        "html":     _CONTRACT_HTML,
        "meta":     {"paper_size": "A4", "margin_mm": 18},
    },
    {
        "type":     "acceptance_act",
        "name":     "Standard Acceptance Act (EN)",
        "language": "en",
        "html":     _ACCEPTANCE_HTML,
        "meta":     {"paper_size": "A4", "margin_mm": 18},
    },
    {
        "type":     "invoice",
        "name":     "Standard Invoice PDF (EN)",
        "language": "en",
        "html":     _INVOICE_HTML,
        "meta":     {"paper_size": "A4", "margin_mm": 18},
    },
]
