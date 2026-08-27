// Debounced company / establishment autocomplete backed by
// GET /api/public/company-suggest (operator companies + UA registry seed).
import React, { useEffect, useRef, useState } from "react";
import { PublicAPI } from "@/lib/clientApi";
import "./CompanyAutocomplete.css";

export default function CompanyAutocomplete({
  value,
  onChange,
  onSelect,
  placeholder = "",
  testId = "company-autocomplete",
  lang = "uk",
  inputClassName = "",
}) {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState(-1);
  const boxRef = useRef(null);
  const timer = useRef(null);
  const skipNext = useRef(false);

  const hint = lang === "en" ? "Suggestions from the company registry" : "Підказки з реєстру компаній";
  const noRes = lang === "en" ? "No matches — you can type freely" : "Немає збігів — можна ввести вручну";

  useEffect(() => {
    if (skipNext.current) {
      skipNext.current = false;
      return;
    }
    const q = (value || "").trim();
    if (timer.current) clearTimeout(timer.current);
    if (q.length < 2) {
      setItems([]);
      setOpen(false);
      return;
    }
    timer.current = setTimeout(async () => {
      setLoading(true);
      try {
        const r = await PublicAPI.companySuggest(q, 8);
        setItems((r && r.items) || []);
        setOpen(true);
        setActive(-1);
      } catch (e) {
        setItems([]);
      } finally {
        setLoading(false);
      }
    }, 250);
    return () => timer.current && clearTimeout(timer.current);
  }, [value]);

  useEffect(() => {
    const onDoc = (e) => {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const choose = (it) => {
    skipNext.current = true;
    onChange(it.name);
    if (onSelect) onSelect(it);
    setOpen(false);
    setItems([]);
  };

  const onKey = (e) => {
    if (!open || !items.length) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, items.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter" && active >= 0) {
      e.preventDefault();
      choose(items[active]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div className="cac" ref={boxRef}>
      <input
        className={`cac__input ${inputClassName}`}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => items.length && setOpen(true)}
        onKeyDown={onKey}
        placeholder={placeholder}
        data-testid={testId}
        autoComplete="off"
        role="combobox"
        aria-expanded={open}
        aria-autocomplete="list"
      />
      {open && (
        <div className="cac__menu" data-testid={`${testId}-menu`}>
          {loading && <div className="cac__hint">…</div>}
          {!loading && items.length === 0 && <div className="cac__hint">{noRes}</div>}
          {items.map((it, i) => (
            <button
              type="button"
              key={`${it.name}-${i}`}
              className={`cac__item ${i === active ? "is-active" : ""}`}
              onMouseEnter={() => setActive(i)}
              onClick={() => choose(it)}
              data-testid={`${testId}-option-${i}`}
            >
              <span className="cac__name">{it.name}</span>
              <span className="cac__meta">
                {it.known_client && <em className="cac__badge">{lang === "en" ? "client" : "клієнт"}</em>}
                {it.edrpou ? `ЄДРПОУ ${it.edrpou}` : it.region || ""}
              </span>
            </button>
          ))}
          {items.length > 0 && <div className="cac__foot">{hint}</div>}
        </div>
      )}
    </div>
  );
}
