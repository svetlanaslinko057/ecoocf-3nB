/**
 * Localize a notification (Доопр #22 — fix the «UI is EN, notification is UK» bug).
 *
 * Backend stores `i18n_key` + `i18n_params` along with English fallback
 * `title`/`message`. This helper renders the correct language based on
 * the user's current i18n choice.
 */
export function localizeNotification(n, t) {
  if (!n || !n.i18n_key) return { title: n?.title || '', message: n?.message || '' };
  const p = n.i18n_params || {};
  const tt = (key, fallback) => { const v = t(key); return (!v || v === key) ? fallback : v; };
  const interp = (s) => String(s || '').replace(/\{(\w+)\}/g, (_, k) => (p[k] !== undefined ? p[k] : `{${k}}`));
  let title = '', body = '';
  switch (n.i18n_key) {
    case 'notif_new_lead':
      title = tt('notifNewLead', 'New lead');
      body  = `${p.name || '—'} · ${p.phone || '—'}`
            + (p.source && p.source !== 'manual' ? ` · ${tt('notifSource', 'source')}: ${p.source}` : '')
            + (p.country ? ` · ${tt('notifCountry', 'country')}: ${p.country}` : '');
      break;
    case 'notif_lead_assigned':
      title = tt('notifLeadAssigned', 'A new lead was assigned to you');
      body  = `${p.name || '—'} · ${p.phone || '—'}`
            + (p.assignedBy ? ` · ${tt('notifBy', 'by')} ${p.assignedBy}` : '');
      break;
    case 'notif_new_lead_unassigned':
      title = tt('notifNewLeadUnassigned', 'New lead (unassigned)');
      body  = `${p.name || '—'} · ${p.phone || '—'}`;
      break;
    case 'notif_lead_reminder_30':
      title = tt('notifLeadReminder30', 'Lead not processed for 30 min');
      body  = `${p.name || '—'} · ${p.phone || '—'}`;
      break;
    case 'notif_lead_reminder_2h':
      title = tt('notifLeadReminder2h', 'Lead not processed for 2 hours');
      body  = `${p.name || '—'} · ${p.phone || '—'}`;
      break;
    case 'notif_bulk_in':
      title = interp(tt('notifBulkIn', 'You have been assigned {count} {entity}(s) by {actor}'));
      body  = interp(tt('notifBulkInBody', '{count} transferred · {tasksMoved} open tasks'));
      break;
    case 'notif_bulk_out':
      title = interp(tt('notifBulkOut', 'Transferred to manager {target}'));
      body  = interp(tt('notifBulkOutBody', '{count} {entity}(s) · {tasksMoved} tasks'));
      break;
    case 'notif_sla_warning_mgr':
      title = interp(tt('notifSlaWarningMgr', 'Lead SLA warning ({minutes} min)'));
      body  = interp(tt('notifSlaWarningMgrBody', 'Lead «{lead}» still has no first response after {minutes} min.'));
      break;
    case 'notif_sla_warning_tl':
      title = interp(tt('notifSlaWarningTl', 'Team SLA warning: {minutes} min without response'));
      body  = interp(tt('notifSlaWarningTlBody', '{manager} has not responded to lead «{lead}» yet.'));
      break;
    case 'notif_sla_escalated_mgr':
      title = interp(tt('notifSlaEscalatedMgr', 'Lead escalated — SLA breach ({minutes} min)'));
      body  = interp(tt('notifSlaEscalatedMgrBody', 'Lead «{lead}» has no response. Escalated to your team lead.'));
      break;
    case 'notif_sla_escalated_tl':
      title = interp(tt('notifSlaEscalatedTl', 'Lead escalated to you (SLA breach)'));
      body  = interp(tt('notifSlaEscalatedTlBody', 'Lead «{lead}» owned by {manager} hit the {minutes}-min escalation threshold.'));
      break;
    default:
      title = n.title || '';
      body  = n.message || '';
  }
  return { title, message: body };
}

export default localizeNotification;
