/**
 * Analytics Tracker
 * 
 * Lightweight event tracking for BIBI Cars
 * Uses sendBeacon for non-blocking delivery
 */

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Generate or retrieve session ID
const getSessionId = () => {
  let id = localStorage.getItem('bibi_sid');
  if (!id) {
    id = `sid_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    localStorage.setItem('bibi_sid', id);
  }
  return id;
};

// Get UTM parameters
const getUTM = () => {
  const params = new URLSearchParams(window.location.search);
  return {
    source: params.get('utm_source') || undefined,
    campaign: params.get('utm_campaign') || undefined,
    medium: params.get('utm_medium') || undefined,
  };
};

// Save UTM on first visit
const saveUTM = () => {
  const utm = getUTM();
  if (utm.source || utm.campaign) {
    localStorage.setItem('bibi_utm', JSON.stringify(utm));
  }
};

// Get saved UTM (persisted from first visit)
const getSavedUTM = () => {
  try {
    const saved = localStorage.getItem('bibi_utm');
    return saved ? JSON.parse(saved) : getUTM();
  } catch {
    return getUTM();
  }
};

// Track start time for duration calculation
let pageLoadTime = Date.now();
let hasInteracted = false;

// Track interaction
const trackInteraction = () => {
  hasInteracted = true;
};

// Initialize interaction tracking
if (typeof window !== 'undefined') {
  window.addEventListener('click', trackInteraction, { once: true });
  window.addEventListener('scroll', trackInteraction, { once: true });
  window.addEventListener('keydown', trackInteraction, { once: true });
}

/**
 * Track event
 * @param {string} event - Event name
 * @param {object} data - Event data
 */
export const track = (event, data = {}) => {
  if (typeof window === 'undefined') return;

  const duration = Math.round((Date.now() - pageLoadTime) / 1000);
  
  const payload = {
    event,
    sessionId: getSessionId(),
    customerId: localStorage.getItem('bibi_customer_id') || undefined,
    url: window.location.pathname,
    referrer: document.referrer,
    utm: getSavedUTM(),
    data,
    duration,
    hasInteraction: hasInteracted,
    ts: Date.now(),
  };

  // Use sendBeacon for non-blocking delivery
  if (navigator.sendBeacon) {
    navigator.sendBeacon(
      `${API_URL}/api/analytics/track`,
      JSON.stringify(payload)
    );
  } else {
    // Fallback to fetch
    fetch(`${API_URL}/api/analytics/track`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      keepalive: true,
    }).catch(() => {});
  }
};

/**
 * Track page view
 */
export const trackPageView = () => {
  pageLoadTime = Date.now();
  hasInteracted = false;
  
  // Save UTM on first visit
  saveUTM();
  
  track('page_view', {
    title: document.title,
    path: window.location.pathname,
  });
};

/**
 * Track VIN search
 */
export const trackVinSearch = (vin) => {
  track('vin_search', { vin });
};

/**
 * Track quote creation
 */
export const trackQuoteCreated = (quoteData) => {
  track('quote_created', quoteData);
};

/**
 * Track lead creation
 */
export const trackLeadCreated = (leadData) => {
  track('lead_created', leadData);
};

/**
 * Track car view
 */
export const trackCarView = (carData) => {
  track('car_view', carData);
};

/**
 * Track calculator use
 */
export const trackCalculatorUsed = (calcData) => {
  track('calculator_used', calcData);
};

/**
 * Track WhatsApp click
 */
export const trackWhatsAppClick = () => {
  track('whatsapp_click');
};

/**
 * Track Telegram click
 */
export const trackTelegramClick = () => {
  track('telegram_click');
};

/**
 * Set customer ID (call after login)
 */
export const setCustomerId = (customerId) => {
  localStorage.setItem('bibi_customer_id', customerId);
  
  // Link session to customer
  fetch(`${API_URL}/api/analytics/link-session`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      sessionId: getSessionId(),
      customerId,
    }),
  }).catch(() => {});
};

/**
 * Auto-track page views on navigation
 */
export const initAnalytics = () => {
  if (typeof window === 'undefined') return;

  // Track initial page view
  trackPageView();

  // Track on history changes
  const originalPushState = history.pushState;
  history.pushState = function(...args) {
    originalPushState.apply(this, args);
    trackPageView();
  };

  window.addEventListener('popstate', trackPageView);
};

export default {
  track,
  trackPageView,
  trackVinSearch,
  trackQuoteCreated,
  trackLeadCreated,
  trackCarView,
  trackCalculatorUsed,
  trackWhatsAppClick,
  trackTelegramClick,
  setCustomerId,
  initAnalytics,
};
