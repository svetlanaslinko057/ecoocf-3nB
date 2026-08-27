"""Unified Admin Platform — Phase D1.5.

An **additive** layer that unifies discovery and cross-domain navigation for
staff without refactoring any existing CRM / Waste / Operations / SEO / Content
schema. Everything here is either:

  * READ-ONLY aggregation over existing collections (global search, dashboard),
  * or brand-new *universal* collections + adapters (Slice 2: activity, comments,
    attachments, audit, draft-status adapter).

Slice 1 (this commit): Global Search, Unified Dashboard, Relation resolver.
"""
