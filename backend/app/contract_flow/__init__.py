"""Universal Contract Template & Acceptance Flow (ECO.NOVA).

A universal contract layer that works with ANY contract type and ANY uploaded
template. It is intentionally template-driven: nothing about a single concrete
document is hard-coded. It reuses existing customers/companies, notifications,
PDF engine and IBAN billing — it does NOT duplicate the Contract Execution
Engine (schedule/pricing/financials).

Key principles (per TZ):
  * Two-level blocking: a contract can be created/previewed/sent even with an
    incomplete legal profile, but it CANNOT be accepted / paid / activated
    until the legal profile is complete AND all required template variables
    are present.
  * Payment is IBAN-only (bank transfer + proof upload + manual manager
    confirmation). Payment is NOT an electronic signature; client acceptance,
    payment confirmation and manager approval are stored separately.
  * Every generation produces a new immutable version with a checksum; any
    change to legal data or template after acceptance invalidates acceptance
    and forces re-acceptance.
"""
