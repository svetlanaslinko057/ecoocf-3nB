// Single source of truth for public contact data (header / footer / Contacts).
// Fetched once and cached at module level so every consumer shares one request.
import { useEffect, useState } from "react";
import { PublicAPI } from "@/lib/clientApi";

const FALLBACK = {
  phones: [{ label: "Гаряча лінія", value: "+380 66 788 04 45" }],
  emails: [{ label: "Загальний", value: "Econova2013@ukr.net" }],
  address: "Україна, Житомирська обл., Звягельський р-н, м. Баранівка, вул. Івана Франка, 104А",
  working_hours: "Пн–Пт: 9:00–18:00",
  telegram: "",
  viber: "",
  messenger: "",
};

let _cache = null;
let _inflight = null;
const _subs = new Set();

async function _load() {
  if (_cache) return _cache;
  if (!_inflight) {
    _inflight = PublicAPI.contacts()
      .then((r) => {
        _cache = (r && r.contacts) || FALLBACK;
        return _cache;
      })
      .catch(() => {
        _cache = FALLBACK;
        return _cache;
      })
      .finally(() => {
        _inflight = null;
        _subs.forEach((fn) => fn(_cache));
      });
  }
  return _inflight;
}

/** Invalidate the cache (call after an admin saves new contacts). */
export function refreshPublicContacts() {
  _cache = null;
  _load();
}

export function usePublicContacts() {
  const [contacts, setContacts] = useState(_cache || FALLBACK);
  useEffect(() => {
    let alive = true;
    const sub = (c) => alive && setContacts(c);
    _subs.add(sub);
    _load().then((c) => alive && setContacts(c));
    return () => {
      alive = false;
      _subs.delete(sub);
    };
  }, []);
  // Convenience accessors
  const primaryPhone = (contacts.phones && contacts.phones[0]) || null;
  const primaryEmail = (contacts.emails && contacts.emails[0]) || null;
  return { contacts, primaryPhone, primaryEmail };
}
