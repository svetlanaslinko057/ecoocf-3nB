"""
Wave 19 — Portal DTOs (trimmed projections).

These Pydantic shapes describe **exactly** what the customer-facing portal
is allowed to see. Admin bundles MUST NOT leak through here.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PortalLoginRequest(BaseModel):
    email: str
    password: str


class PortalMeResponse(BaseModel):
    customerId: str
    email: str
    name: str
    phone: Optional[str] = ""
    picture: Optional[str] = ""


class PortalDealSummary(BaseModel):
    id: str
    vehicle: str            # e.g. "BMW X5 2021"
    vin: Optional[str] = None
    status: str             # high-level status ("in_transit" / "at_port" / "delivered" ...)
    statusLabel: str        # human readable
    photo: Optional[str] = None
    eta: Optional[str] = None
    createdAt: Optional[str] = None


class PortalDealDetail(PortalDealSummary):
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    lot: Optional[str] = None
    auction: Optional[str] = None
    photos: List[str] = Field(default_factory=list)


# ── Delivery Timeline (read-only) ──────────────────────────────────────
class PortalMilestone(BaseModel):
    key: str
    label: str
    state: str          # "done" | "current" | "upcoming"
    occurredAt: Optional[str] = None


class PortalDeliveryTimeline(BaseModel):
    dealId: str
    currentMilestone: Optional[str] = None
    eta: Optional[str] = None
    progressPercent: int = 0
    milestones: List[PortalMilestone] = Field(default_factory=list)


# ── Documents (read-only list) ─────────────────────────────────────────
class PortalDocument(BaseModel):
    id: str
    kind: str           # contract | invoice | transport | customs | other
    label: str
    filename: Optional[str] = None
    sizeBytes: Optional[int] = None
    uploadedAt: Optional[str] = None
    downloadUrl: str    # always served via /api/portal/documents/{id}/download


class PortalDocumentsList(BaseModel):
    dealId: str
    items: List[PortalDocument] = Field(default_factory=list)


# ── Payments (Finance360 trimmed) ──────────────────────────────────────
class PortalInvoice(BaseModel):
    id: str
    number: Optional[str] = None
    amount: float = 0.0
    currency: str = "USD"
    status: str = "open"     # open | paid | overdue
    dueDate: Optional[str] = None
    paidAt: Optional[str] = None
    issuedAt: Optional[str] = None


class PortalPayments(BaseModel):
    dealId: str
    currency: str = "USD"
    totalAmount: float = 0.0
    paidAmount: float = 0.0
    outstandingAmount: float = 0.0
    nextDueDate: Optional[str] = None
    history: List[PortalInvoice] = Field(default_factory=list)


# ── Notifications (Wave 18 trimmed) ────────────────────────────────────
class PortalNotification(BaseModel):
    id: str
    event: str          # e.g. "new_eta" / "contract_ready" / "payment_received" / "car_arrived"
    title: str
    body: Optional[str] = ""
    createdAt: Optional[str] = None
    readAt: Optional[str] = None
    dealId: Optional[str] = None


class PortalNotificationsInbox(BaseModel):
    items: List[PortalNotification] = Field(default_factory=list)
    total: int = 0
    unread: int = 0


# ── Portal Home aggregate (5 blocks in one call for fast first paint) ──
class PortalHomeResponse(BaseModel):
    customer: PortalMeResponse
    activeDeal: Optional[PortalDealDetail] = None
    delivery: Optional[PortalDeliveryTimeline] = None
    documents: Optional[PortalDocumentsList] = None
    payments: Optional[PortalPayments] = None
    notifications: PortalNotificationsInbox = PortalNotificationsInbox()
    otherDeals: List[PortalDealSummary] = Field(default_factory=list)
