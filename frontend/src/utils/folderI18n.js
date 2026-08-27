/**
 * BIBI Cars — Block 7.2 — Folder taxonomy localization
 * ========================================================
 *
 * Maps canonical folder slugs to localized display names.
 * Used by FileManager UI to render the system folders.
 */

export const SYSTEM_FOLDER_LABELS = {
  uk: {
    customer_docs:   'Документи клієнта',
    vehicle_docs:    'Документи по авто',
    contracts:       'Договори',
    vehicle_photos:  'Фото авто',
    other:           'Інше',
  },
  en: {
    customer_docs:   'Customer documents',
    vehicle_docs:    'Vehicle documents',
    contracts:       'Contracts',
    vehicle_photos:  'Vehicle photos',
    other:           'Other',
  },
  bg: {
    customer_docs:   'Документи на клиента',
    vehicle_docs:    'Документи за автомобила',
    contracts:       'Договори',
    vehicle_photos:  'Снимки на автомобила',
    other:           'Друго',
  },
};

// Legacy English names that may still exist in the DB before migration.
export const LEGACY_NAME_TO_SLUG = {
  Contracts:    'contracts',
  Invoices:     'customer_docs',
  Registration: 'customer_docs',
  Adaptation:   'vehicle_docs',
  Photos:       'vehicle_photos',
  Delivery:     'vehicle_docs',
  Other:        'other',
};

/**
 * Returns the localized name for a folder document.
 * Falls back to ``folder.name`` if the slug is unknown.
 */
export function folderDisplayName(folder, lang = 'uk') {
  if (!folder) return '';
  const dict = SYSTEM_FOLDER_LABELS[lang] || SYSTEM_FOLDER_LABELS.uk;
  const slug = folder.slug || LEGACY_NAME_TO_SLUG[folder.name];
  if (slug && dict[slug]) return dict[slug];
  return folder.name || '';
}
