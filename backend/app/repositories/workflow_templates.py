"""
WorkflowTemplateRepository — Phase 5.3 / C-1.
=============================================

Canonical owner of the `db.workflow_templates` Mongo collection.
After this commit, all mutations to that collection flow through
this class. The router `app/routers/admin_workflow_templates.py`
becomes the single HTTP surface that calls into the repository
for mutations; the public read endpoint in `server.py` uses the
repository's public-list method.

Business operations (named verbs, NOT generic CRUD)
----------------------------------------------------

* Reads:
    - ``list_templates(*, order)``     full collection, ordered by `created_at`
    - ``get_template(tpl_id)``          single template by id
    - ``count_templates()``             cardinality (used by seed gate)

* Writes:
    - ``seed_default_templates()``     idempotent first-hit seed
                                       (3 hard-coded system templates)
    - ``create_template(...)``         create a new user template
    - ``update_template(...)``         patch name/description/steps
    - ``delete_template(tpl_id)``      delete a NON-default template
                                       (system defaults are guarded
                                       at the Mongo query level, NOT
                                       application-level)

Legacy behaviour preserved 1:1 (Phase 5.3 / C-1 mandate)
--------------------------------------------------------

These quirks live in the legacy router and are reproduced here
verbatim. Changing any of them is OUT OF SCOPE for this commit.

* **Race in first-hit seed.** Two concurrent admin GETs into an
  empty collection will each see empty, each insert 3 docs, and
  the collection will end up with 6 default templates with
  distinct ids. Legacy has this race; we do not fix it here.
* **Steps normalisation drops items without `label`.** A POST or
  PATCH that supplies `steps=[{"key": "x"}]` (no label) results
  in a stored document with empty `steps`. Legacy had no
  post-normalisation non-empty check; we do not add one.
* **Default-protection is a Mongo predicate, not application logic.**
  `delete_template` matches on `{"id": tpl_id, "is_default": {"$ne": True}}`.
  A default template returns `False` ("not deleted") from the
  repository — same shape as "id not found". The router maps both
  to HTTP 404 with a combined message exactly as legacy did.
* **Server-generated fields.** `id` (`wft_<10-hex>`), `created_at`,
  and `created_by` are set inside the repository for `create_*`
  paths. `updated_at` is set inside `update_template`. Callers do
  NOT pass these.
* **Sort direction is part of the business contract.** Admin
  listing uses `-1` (newest first); public listing uses `+1`
  (chronological). The repository takes an explicit `order`
  parameter rather than two near-duplicate methods, but the two
  call sites use exactly the two legacy orderings.

What this repository does NOT do (deliberately)
-----------------------------------------------

*  No generic `update(filter, doc)` escape hatch.
*  No `save()` / `upsert()` shortcut.
*  No exposed Mongo cursor objects.
*  No DTO normalisation — returns dicts in the exact legacy shape
   (per Phase 5.1 rule: DTOs are 5.5+ concern, not 5.3).
*  No HTTP exceptions — raises plain Python exceptions only on
   programmer error; the router translates business-result
   booleans into HTTP status codes.
*  No `_id` leak — every projection / pop matches legacy.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal


# Hard-coded system defaults. Kept private to the repository so the
# router cannot mutate them, and so any future seed evolution is
# guaranteed to be a single edit-point.
_DEFAULT_TEMPLATES: list[dict] = [
    {
        "name": "Standard (3 steps)",
        "description": "Basic flow for most services",
        "category": "generic",
        "steps": [
            {"key": "pending",     "label": "Pending"},
            {"key": "in_progress", "label": "In progress"},
            {"key": "completed",   "label": "Completed"},
        ],
    },
    {
        "name": "Import USA",
        "description": "Full USA vehicle import lifecycle (auction → handover)",
        "category": "import_usa",
        "steps": [
            {"key": "invoice_paid",       "label": "Invoice paid"},
            {"key": "purchase_prep",      "label": "Vehicle purchase preparation"},
            {"key": "auction_payment",    "label": "Auction / payment processing"},
            {"key": "logistics_started",  "label": "Logistics started"},
            {"key": "documents_prepared", "label": "Documents prepared"},
            {"key": "completed",          "label": "Completed"},
        ],
    },
    {
        "name": "Import Korea",
        "description": "Full Korea vehicle import lifecycle",
        "category": "import_korea",
        "steps": [
            {"key": "invoice_paid",       "label": "Invoice paid"},
            {"key": "purchase_prep",      "label": "Vehicle purchase preparation"},
            {"key": "korea_logistics",    "label": "Korea logistics"},
            {"key": "fedex_transit",      "label": "FedEx transit"},
            {"key": "documents_prepared", "label": "Documents prepared"},
            {"key": "completed",          "label": "Completed"},
        ],
    },
    {
        "name": "Adaptation BG",
        "description": "Vehicle adaptation for Bulgaria",
        "category": "adaptation",
        "steps": [
            {"key": "invoice_paid",     "label": "Invoice paid"},
            {"key": "technical_review", "label": "Technical review"},
            {"key": "adaptation_work",  "label": "Adaptation work"},
            {"key": "quality_check",    "label": "Quality check"},
            {"key": "completed",        "label": "Completed"},
        ],
    },
    {
        "name": "Registration / Certification",
        "description": "KAT registration & certification flow",
        "category": "registration",
        "steps": [
            {"key": "invoice_paid",        "label": "Invoice paid"},
            {"key": "documents_collected", "label": "Documents collected"},
            {"key": "kat_process",         "label": "KAT / certification process"},
            {"key": "approval_received",   "label": "Approval received"},
            {"key": "completed",           "label": "Completed"},
        ],
    },
    {
        "name": "Detailing",
        "description": "Pre-sale vehicle preparation",
        "category": "detailing",
        "steps": [
            {"key": "invoice_paid", "label": "Invoice paid"},
            {"key": "scheduled",    "label": "Scheduled"},
            {"key": "in_progress",  "label": "In progress"},
            {"key": "completed",    "label": "Completed"},
        ],
    },
    {
        "name": "Logistics (full cycle)",
        "description": "Pickup → delivery flow",
        "category": "logistics",
        "steps": [
            {"key": "pickup",    "label": "Pickup"},
            {"key": "transit",   "label": "In transit"},
            {"key": "customs",   "label": "Customs"},
            {"key": "delivery",  "label": "Delivery"},
            {"key": "delivered", "label": "Delivered"},
        ],
    },
    {
        "name": "Custom Service",
        "description": "Generic 3-step flow",
        "category": "custom",
        "steps": [
            {"key": "invoice_paid", "label": "Invoice paid"},
            {"key": "in_progress",  "label": "In progress"},
            {"key": "completed",    "label": "Completed"},
        ],
    },
]


def _now_iso() -> str:
    """UTC now as ISO-8601 string (matches legacy `datetime.now(timezone.utc).isoformat()`)."""
    return datetime.now(timezone.utc).isoformat()


def _new_template_id() -> str:
    """Generate a new template id (`wft_<10-hex>`) — same shape as legacy."""
    return f"wft_{uuid.uuid4().hex[:10]}"


def _normalise_steps(steps: list[dict]) -> list[dict]:
    """Normalise step records to the persisted `{key, label}` shape.

    Drops any step without a `label`. Matches legacy line:

        [{"key": (s.get("key") or "").strip(),
          "label": (s.get("label") or "").strip()}
         for s in steps if s.get("label")]

    Legacy quirk preserved: this MAY return an empty list, and that
    empty list is silently accepted by the create/update paths. Do
    not add a non-empty post-check here — callers rely on the
    legacy permissive behaviour.
    """
    return [
        {
            "key":   (s.get("key")   or "").strip(),
            "label": (s.get("label") or "").strip(),
        }
        for s in steps
        if s.get("label")
    ]


class WorkflowTemplateRepository:
    """Owner of ``db.workflow_templates``.

    The repository instance is cheap to construct (just stores a
    reference to the Motor handle); construct one per request, or
    cache one at module level — either works. The factory in
    ``app/routers/admin_workflow_templates.py`` constructs per-call
    to keep the lazy-bridge pattern consistent with the rest of
    the codebase (until Phase 5.8 introduces DI).
    """

    # The collection name lives here, not at the call site, so a
    # future rename / sharding decision is a single edit.
    COLLECTION = "workflow_templates"

    def __init__(self, db: Any) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def list_templates(
        self,
        *,
        order: Literal["asc", "desc"] = "desc",
        limit: int = 200,
    ) -> list[dict]:
        """Return all templates ordered by ``created_at``.

        Parameters
        ----------
        order:
            ``"desc"`` for admin listing (newest first; legacy default).
            ``"asc"``  for public listing (chronological; matches the
            public ``GET /api/workflow-templates`` endpoint).
        limit:
            Same ``length=200`` as legacy ``to_list(length=200)``.
        """
        direction = -1 if order == "desc" else 1
        cursor = self._db[self.COLLECTION].find({}, {"_id": 0}).sort("created_at", direction)
        return await cursor.to_list(length=limit)

    async def get_template(self, tpl_id: str) -> dict | None:
        """Fetch a single template by id, or ``None`` if not found.

        Used after ``update_template`` to return the post-update
        document to the caller (legacy: line 170 of router).
        """
        return await self._db[self.COLLECTION].find_one({"id": tpl_id}, {"_id": 0})

    async def count_templates(self) -> int:
        """Return collection cardinality.

        Currently used only by the seed gate of ``list_templates`` in
        the admin handler. The handler still uses the legacy
        ``if not items`` pattern (which is equivalent for ``length=200``
        — if the collection has any docs, ``items`` is non-empty), but
        this method exists so future callers can ask the cardinality
        question without round-tripping the whole list.
        """
        return await self._db[self.COLLECTION].count_documents({})

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    async def seed_default_templates(self) -> list[dict]:
        """Insert the 3 hard-coded default templates, return them.

        Idempotent re-call is NOT enforced at this level — the caller
        (admin ``list_templates`` GET) gates this behind an emptiness
        check, matching legacy first-hit-seed semantics. Calling this
        method on a non-empty collection will create duplicates with
        new ids.

        Legacy race preserved: two concurrent GETs into an empty
        collection both pass the emptiness check, both call this
        method, and the collection ends up with 6 default templates.
        Fixing that is a Phase 6 hardening concern, not a Phase 5
        cleanup concern.
        """
        seeds = [
            {
                **dict(template),
                "id": _new_template_id(),
                "created_at": _now_iso(),
                "is_default": True,
            }
            for template in _DEFAULT_TEMPLATES
        ]
        await self._db[self.COLLECTION].insert_many(seeds)
        # Drop any Mongo `_id` that insert_many may have set on the dicts
        for s in seeds:
            s.pop("_id", None)
        return seeds

    async def create_template(
        self,
        *,
        name: str,
        description: str,
        steps: list[dict],
        created_by: str | None,
    ) -> dict:
        """Create a new (non-default) template.

        Pre-conditions (asserted by the caller / router):
          * ``name`` is a non-empty stripped string
          * ``steps`` is a list (legacy quirk: may become empty
            after normalisation; we still persist the doc)

        Server-set fields: ``id``, ``created_at``, ``is_default=False``.
        Caller-supplied: ``name``, ``description``, ``steps``, ``created_by``.

        Returns the inserted document (without Mongo ``_id``).
        """
        doc = {
            "id":          _new_template_id(),
            "name":        name,
            "description": description,
            "steps":       _normalise_steps(steps),
            "is_default":  False,
            "created_at":  _now_iso(),
            "created_by":  created_by,
        }
        await self._db[self.COLLECTION].insert_one(doc)
        doc.pop("_id", None)
        return doc

    async def update_template(
        self,
        tpl_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        steps: list[dict] | None = None,
    ) -> dict | None:
        """Patch name / description / steps of an existing template.

        Only fields explicitly provided (not ``None``) are updated.
        Sets ``updated_at`` server-side. If ``tpl_id`` is not found,
        returns ``None``.

        Pre-conditions (asserted by the caller / router):
          * at least one of ``name`` / ``description`` / ``steps`` is
            not ``None`` (legacy ``Nothing to update`` check)
          * if ``steps`` is supplied, it is a non-empty list at the
            input layer (legacy quirk: may become empty after
            normalisation; we still apply the patch)
        """
        upd: dict[str, Any] = {}
        if name is not None:
            upd["name"] = name
        if description is not None:
            upd["description"] = description
        if steps is not None:
            upd["steps"] = _normalise_steps(steps)
        upd["updated_at"] = _now_iso()

        r = await self._db[self.COLLECTION].update_one({"id": tpl_id}, {"$set": upd})
        if r.matched_count == 0:
            return None
        return await self.get_template(tpl_id)

    async def delete_template(self, tpl_id: str) -> bool:
        """Delete a NON-default template.

        Default-protection is implemented as a Mongo query predicate
        (``"is_default": {"$ne": True}``), NOT as application logic.
        Two failure modes therefore collapse into a single ``False``
        return:

          * template id does not exist
          * template exists but ``is_default == True``

        The router maps both to HTTP 404 with the legacy combined
        error message. This preserves the legacy contract byte-for-byte.

        Returns ``True`` if a document was actually deleted.
        """
        r = await self._db[self.COLLECTION].delete_one({
            "id":         tpl_id,
            "is_default": {"$ne": True},
        })
        return r.deleted_count > 0


__all__ = ["WorkflowTemplateRepository"]
