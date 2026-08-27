import { useEffect } from "react";

/** Lightweight client-side SEO: sets <title> + meta description. */
export function useSeo(title, description) {
  useEffect(() => {
    if (title) document.title = `${title} · ECO.NOVA — Утилізація небезпечних відходів`;
    if (description) {
      let m = document.querySelector('meta[name="description"]');
      if (!m) {
        m = document.createElement("meta");
        m.setAttribute("name", "description");
        document.head.appendChild(m);
      }
      m.setAttribute("content", description);
    }
  }, [title, description]);
}
