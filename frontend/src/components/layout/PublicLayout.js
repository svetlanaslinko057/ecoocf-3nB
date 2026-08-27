/**
 * ECO Public Layout — single unified shell for ALL public pages.
 * Premium sticky header (EcoNav) + dark footer (EcoFooter) + site-wide custom
 * cursor + page-transition curtain. Scroll resets to top on route change.
 *
 * Wraps the public tree in <InquiryProvider/> so the header CTA, the floating
 * action button and any page can open the site-wide callback/inquiry modal.
 */
import React, { useEffect, Suspense } from "react";
import { Outlet, useLocation } from "react-router-dom";
import EcoNav from "./EcoNav";
import EcoFooter from "./EcoFooter";
import EcoCursor from "./EcoCursor";
import EcoCurtain from "./EcoCurtain";
import CookieConsent from "@/components/CookieConsent";
import RouteFallback from "@/components/RouteFallback";
import { InquiryProvider } from "@/context/InquiryContext";
import "./eco-shell.css";

/* The floating «Замовити дзвінок» launcher now lives INSIDE the provider —
   the button itself morphs into the inquiry card (see InquiryModal.js). */

export default function PublicLayout() {
  const { pathname } = useLocation();

  useEffect(() => {
    document.body.classList.add("eco-public");
    return () => {
      document.body.classList.remove("eco-public");
      document.documentElement.removeAttribute("data-nav-theme");
    };
  }, []);

  // Reset scroll on navigation. The home page ("/") owns its per-section
  // nav-theme (set by Home.js via ScrollTrigger); for every other public
  // page (light / milky background) force the default light header so the
  // dark "/" theme never leaks onto them.
  useEffect(() => {
    window.scrollTo(0, 0);
    if (pathname !== "/") {
      document.documentElement.removeAttribute("data-nav-theme");
    }
  }, [pathname]);

  return (
    <InquiryProvider>
      <div className="eco-shell">
        <EcoCursor />
        <EcoCurtain />
        <EcoNav />
        <main className="eco-shell__main"><Suspense fallback={<RouteFallback />}><Outlet /></Suspense></main>
        <EcoFooter />
        <CookieConsent />
      </div>
    </InquiryProvider>
  );
}
