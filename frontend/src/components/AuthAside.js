import React from "react";
import EcoLivingCanvas from "@/components/EcoLivingCanvas";
import { useLang } from "@/i18n";

/**
 * AuthAside — the right ~1/3 panel shared by the client login & reset screens.
 * Hosts the long-running ECO animation plus an editorial overlay (UA + EN).
 */
const COPY = {
  uk: {
    quote: "Відповідальна утилізація — це система, а не разова послуга.",
    bullets: [
      "Історія всіх заявок, договорів та актів — в одному кабінеті",
      "Повторне замовлення в один клік",
      "Прозорий статус кожної заявки та персональний менеджер",
    ],
  },
  en: {
    quote: "Responsible disposal is a system, not a one-off service.",
    bullets: [
      "History of all requests, contracts and acts — in one cabinet",
      "Reorder in a single click",
      "Transparent status for every request and a personal manager",
    ],
  },
};

export default function AuthAside({ quote, bullets }) {
  const { lang } = useLang();
  const L = COPY[lang === "en" ? "en" : "uk"];
  const q = quote || L.quote;
  const items = bullets || L.bullets;
  return (
    <aside className="client-auth__right" aria-hidden="true">
      <EcoLivingCanvas />
      <div className="eco-living__overlay">
        <p className="eco-living__quote">{q}</p>
        <ul className="eco-living__bullets">
          {items.map((b, i) => (
            <li key={i}>{b}</li>
          ))}
        </ul>
      </div>
    </aside>
  );
}
