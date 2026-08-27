/**
 * seedI18n.js - Frontend translation helper for legacy MongoDB seed data.
 *
 * Cabinet pages render data (invoices, shipment timeline events, notifications)
 * that was seeded UK-only. Until the backend exposes per-language fields for every
 * seed record, this helper translates known UK strings into EN on the fly.
 *
 * Usage:
 *   import { tSeed } from '../utils/seedI18n';
 *   <p>{tSeed(invoice.description, lang)}</p>
 *
 * If the string is unknown, returns it unchanged (UK fallback).
 */

// Dictionary of UK -> { en } mappings for well-known seed data.
const SEED_DICT = {
  'Готово до видачі': { en: 'Ready for pickup' },
  '🏁 Готово до видачі': { en: '🏁 Ready for pickup' },
  'за Audi Q7': { en: 'for Audi Q7' },
  'за Mercedes-Benz': { en: 'for Mercedes-Benz' },
  'за BMW': { en: 'for BMW' },
  'за Tesla': { en: 'for Tesla' },
  ' за ': { en: ' for ' },
  // Invoice description fragments
  'Вартість авто': { en: 'Vehicle cost' },
  'Послуги': { en: 'Services' },
  'Депозит': { en: 'Deposit' },
  'Доставка': { en: 'Delivery' },
  'Доставка та логістика': { en: 'Delivery & logistics' },
  'Основна оплата': { en: 'Main payment' },
  'Передплата': { en: 'Advance payment' },
  'Повна оплата': { en: 'Full payment' },
  ' від ': { en: ' from ' },
  // City names
  'Київ': { en: 'Kyiv' },
  // Common surnames used in seed
  'Демо': { en: 'Demo' },
  'BIB-2026-0487 на Audi Q7 Premium Plus очікує вашого підпису': { en: 'BIB-2026-0487 for Audi Q7 Premium Plus awaits your signature' },
  'BIBI Cars': { en: 'BIBI Cars' },
  'Klaipeda, LT': { en: 'Klaipeda, LT' },
  'Mercedes-Benz GLE 450 прибуло в порт': { en: 'Mercedes-Benz GLE 450 arrived at port' },
  'Near Port': { en: 'Near Port' },
  'Odesa, UA': { en: 'Odesa, UA' },
  'Olha Tkachuk': { en: 'Olha Tkachuk' },
  'Tesla Model 3 доставлено': { en: 'Tesla Model 3 delivered' },
  'Ірина Петренко': { en: 'Iryna Petrenko' },
  'Авто': { en: 'Car' },
  'Авто завантажено на судно': { en: 'Car loaded onto vessel' },
  'Автомобіль у Клайпеді. Митне оформлення розпочато.': { en: 'Car in Klaipeda. Customs clearance started.' },
  'Автомобіль успішно передано. Дякуємо за вибір BIBI Cars!': { en: 'Car successfully handed over. Thank you for choosing BIBI Cars!' },
  'Атлантичний океан': { en: 'Atlantic Ocean' },
  'В дорозі': { en: 'In Transit' },
  'Ви виграли аукціон!': { en: 'You won the auction!' },
  'Відплив з порту': { en: 'Departed from port' },
  'Депозит за': { en: 'Deposit for' },
  'Депозит за Audi Q7 Premium Plus 2024': { en: 'Deposit for Audi Q7 Premium Plus 2024' },
  'Договір': { en: 'Contract' },
  'Договір BIB-2026-0312 на Mercedes-Benz GLE 450 успішно підписано': { en: 'Contract BIB-2026-0312 for Mercedes-Benz GLE 450 successfully signed' },
  'Договір готовий до підпису': { en: 'Contract ready for signature' },
  'Договір підписано': { en: 'Contract signed' },
  'Дякуємо за вибір': { en: 'Thank you for choosing' },
  'Дякуємо за вибір BIBI Cars!': { en: 'Thank you for choosing BIBI Cars!' },
  'Завантажено на судно': { en: 'Loaded onto vessel' },
  'Здається, ви тут вперше': { en: 'It seems you\'re new here' },
  'Знайдемо машину разом': { en: 'Let\'s find a car together' },
  'Контракт підписано': { en: 'Contract signed' },
  'Лот': { en: 'Lot' },
  'Лот Mercedes-Benz GLE 450 успішно придбано за': { en: 'Lot Mercedes-Benz GLE 450 successfully purchased for' },
  'Митне оформлення': { en: 'Customs clearance' },
  'Митне оформлення розпочато': { en: 'Customs clearance started' },
  'Митниця пройдена': { en: 'Customs passed' },
  'Наближається до порту': { en: 'Approaching port' },
  'Олександр': { en: 'Oleksandr' },
  'Олександр Демо': { en: 'Oleksandr Demo' },
  'Оплату отримано': { en: 'Payment received' },
  'Перевірте свої контактні дані': { en: 'Check your contact details' },
  'Передплата за': { en: 'Prepayment for' },
  'Передплата за Mercedes-Benz GLE 450 2023': { en: 'Advance payment for Mercedes-Benz GLE 450 2023' },
  'Платіж': { en: 'Payment' },
  'Платіж INV-2026-0421 на $30,640 зараховано': { en: 'Payment INV-2026-0421 for $30,640 credited' },
  'Платіж зараховано': { en: 'Payment credited' },
  'Повна оплата за': { en: 'Full payment for' },
  'Повна оплата за BMW X5 xDrive40i 2023': { en: 'Full payment for BMW X5 xDrive40i 2023' },
  'Повна оплата за Tesla Model 3 Long Range 2022': { en: 'Full payment for Tesla Model 3 Long Range 2022' },
  'Прибув у порт': { en: 'Arrived at port' },
  'Підпишіть договір': { en: 'Sign the contract' },
  'Рахунок': { en: 'Invoice' },
  'Рахунок INV-2026-0312 на $19,260 — оплатіть до 23.04.2026': { en: 'Invoice INV-2026-0312 for $19,260 — pay by 23.04.2026' },
  'Рахунок на депозит за': { en: 'Invoice for deposit for' },
  'Середина океану': { en: 'Mid-ocean' },
  'Судно прибуває в порт призначення': { en: 'Vessel arriving at destination port' },
  'Тесла Model 3 доставлено': { en: 'Tesla Model 3 delivered' },
  'зараховано': { en: 'credited' },
  'оплатіть до': { en: 'pay by' },
  'очікує вашого підпису': { en: 'awaits your signature' },
  'прибуло в порт': { en: 'arrived at port' },
  'успішно передано': { en: 'successfully handed over' },
  'успішно придбано за': { en: 'successfully purchased for' },
  'успішно підписано': { en: 'successfully signed' },
  '⚓ Прибуття в порт': { en: '⚓ Arrived at Port' },
  '⚓ Прибуття в порт Клайпеда': { en: '⚓ Arrived at Klaipeda Port' },
  '✅ Автомобіль отримано': { en: '✅ Car received' },
  '✓ Платіж зараховано': { en: '✓ Payment credited' },
  '🎉 Ви виграли аукціон!': { en: '🎉 You won the auction!' },
  '🏁 Дякуємо за вибір BIBI Cars!': { en: '🏁 Thank you for choosing BIBI Cars!' },
  '🏗 Розвантаження': { en: '🏗 Unloading' },
  '🏗️ Розвантаження': { en: '🏗️ Unloading' },
  '📄 Договір готовий до підпису': { en: '📄 Contract ready for signature' },
  '📋 Митниця пройдена': { en: '📋 Customs passed' },
  '📍 Near Port': { en: '📍 Near Port' },
  '🚢 Mercedes-Benz GLE 450 прибуло в порт': { en: '🚢 Mercedes-Benz GLE 450 arrived at port' },
};

// Sorted keys for substring replacement (longest first to win)
const SORTED_KEYS = Object.keys(SEED_DICT).sort((a, b) => b.length - a.length);

/**
 * Translate a seed string. Returns the original if unknown. Tries:
 *   1. Exact match
 *   2. Substring replacement (longest match first)
 */
export function tSeed(text, lang) {
  if (!text || typeof text !== 'string') return text;
  if (lang === 'uk' || !lang) return text;
  if (lang !== 'en' && lang !== 'bg') return text;
  // Exact match
  const exact = SEED_DICT[text];
  if (exact && exact[lang]) return exact[lang];
  // Substring substitution
  let result = text;
  for (const uk of SORTED_KEYS) {
    if (result.includes(uk)) {
      const tr = SEED_DICT[uk][lang];
      if (tr) result = result.split(uk).join(tr);
    }
  }
  return result;
}

const FIELD_NAMES = ['title', 'description', 'message', 'body', 'label', 'name', 'subtitle', 'text'];

/** Translate common string fields on an object. */
export function tSeedObject(obj, lang) {
  if (!obj || typeof obj !== 'object') return obj;
  const out = { ...obj };
  for (const f of FIELD_NAMES) {
    if (typeof out[f] === 'string') {
      out[f] = tSeed(out[f], lang);
    }
  }
  return out;
}

export default tSeed;
