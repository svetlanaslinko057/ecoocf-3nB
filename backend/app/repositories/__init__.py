"""
Domain repositories — Phase 5.3 ownership boundaries.
=====================================================

A repository in this codebase is a NAMED BOUNDARY OF BUSINESS
OWNERSHIP over a single Mongo collection. It is NOT a generic
database wrapper, it is NOT a CRUD abstraction, and it does
NOT expose `update_one`-shaped escape hatches.

Per ``PHASE5_MIDPOINT_ARCHITECTURE_NOTES.md §10`` (architect's
post-C-7 reframing): **repositories are scaffolding for
ownership reconstruction**, not a target pattern in their own
right. The real Phase 5 targets are runtime legibility,
orchestration visibility, side-effect formalization, and
bounded change surfaces. Each repository extraction is one
more piece of ownership coming into view.

The only operational purpose of these classes is to make the
single-writer rule per ``PHASE5_1_OWNERSHIP_MAP.md §7.1``
mechanically enforceable: every mutation to the underlying
collection goes through one of a small set of NAMED BUSINESS
OPERATIONS that express the actual workflow vocabulary
(`seed_defaults`, `create_template`, `mark_paid`,
`attach_vessel_candidate` — not `save`, `update`, `upsert`).

Members (as of Phase 5.4 / C-1):
  * `workflow_templates.WorkflowTemplateRepository`  (C-1, P5.3)
  * `history_reports.HistoryReportRepository`        (C-2, P5.3)
  * `admin_security.AdminSecurityRepository`         (C-3, P5.3)
  * `provider_stats.ProviderStatsRepository`         (C-4, P5.3)
  * `invoice_templates.InvoiceTemplateRepository`    (C-5, P5.3)
  * `service_catalog.ServiceCatalogRepository`       (C-6, P5.3)
  * `app_settings.AppSettingsRepository`             (C-7, P5.3)
  * `email_templates.EmailTemplateRepository`        (C-8, P5.3)
  * `notification_rules.NotificationRuleRepository`  (C-9, P5.3)
  * `email_outbox.EmailOutboxRepository`             (C-10, P5.3)
  * `audit_events.AuditEventsRepository`             (C-11, P5.3)
  * `security_audit.SecurityAuditRepository`         (C-1,  P5.4)

C-11 closed Phase 5.3 with the dual-audit topology partially
formalized (audit_events extracted, audit_log documented as
Type V sibling). Phase 5.4 / C-1 (this commit) completes the
audit-family ownership boundary by extracting audit_log into
its own SecurityAuditRepository — WITHOUT merging the two
collections, WITHOUT a shared base class, WITHOUT an
AuditService facade. The dual-audit topology now consists of
TWO sibling repositories owning TWO sibling collections.

Phase 5.4 sequence (per architect):
  C-1  SecurityAuditRepository      ← THIS COMMIT
  C-2  IntegrationConfigsRepository (cross-domain READ/WRITE tension)
  C-3  app.state migration prep     (lifespan refactor)
  C-4  bridge retirement wave       (retire `from server import db`)
  C-5  side-effect formalization    (emit / orchestration boundary)
"""

from app.repositories.workflow_templates import WorkflowTemplateRepository
from app.repositories.history_reports import HistoryReportRepository
from app.repositories.admin_security import AdminSecurityRepository
from app.repositories.provider_stats import ProviderStatsRepository
from app.repositories.invoice_templates import InvoiceTemplateRepository
from app.repositories.service_catalog import ServiceCatalogRepository
from app.repositories.app_settings import AppSettingsRepository
from app.repositories.email_templates import EmailTemplateRepository
from app.repositories.notification_rules import NotificationRuleRepository
from app.repositories.email_outbox import EmailOutboxRepository
from app.repositories.audit_events import AuditEventsRepository
from app.repositories.security_audit import SecurityAuditRepository
from app.repositories.integration_configs import IntegrationConfigsRepository

__all__ = [
    "WorkflowTemplateRepository",
    "HistoryReportRepository",
    "AdminSecurityRepository",
    "ProviderStatsRepository",
    "InvoiceTemplateRepository",
    "ServiceCatalogRepository",
    "AppSettingsRepository",
    "EmailTemplateRepository",
    "NotificationRuleRepository",
    "EmailOutboxRepository",
    "AuditEventsRepository",
    "SecurityAuditRepository",
    "IntegrationConfigsRepository",
]
