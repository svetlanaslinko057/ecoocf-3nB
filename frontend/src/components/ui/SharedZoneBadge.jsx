/**
 * SharedZoneBadge (legacy export)
 * ───────────────────────────────────────────────────────────────────
 * Backward-compatible shim. The badge was generalised into
 * <RoleZoneBadge variant="…"> so we can reuse the same visual marker
 * for HR, Tasks, Dashboard slices etc. — not just CRM.
 *
 * Existing imports of `SharedZoneBadge` keep working: this file now
 * just renders <RoleZoneBadge variant="crm"> with the same i18n
 * fallbacks (shared_crm_badge / _roles / _tooltip).
 */

import React from 'react';
import RoleZoneBadge from './RoleZoneBadge';

const SharedZoneBadge = ({ className = '' }) => (
  <RoleZoneBadge variant="crm" className={className} />
);

export default SharedZoneBadge;
