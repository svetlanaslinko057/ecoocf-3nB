/**
 * ClientAuthShell — shared split-screen wrapper for all client auth routes
 * (login / register / forgot / reset). Left = form (paper), right = living ECO
 * animation panel with quote + bullets. Scoped under .client-auth.
 */
import React from "react";
import { Link } from "react-router-dom";
import EcoLivingPanel from "./EcoLivingPanel";
import "../../pages/client/client-auth.css";

export default function ClientAuthShell({ children, pulseKey = 0 }) {
  return (
    <div className="client-auth">
      <div className="client-auth__grid">
        <div className="client-auth__left">
          <div className="client-auth__container">{children}</div>
        </div>
        <aside className="client-auth__right" aria-hidden="true">
          <EcoLivingPanel pulseKey={pulseKey} />
          <div className="eco-living__overlay">
            <p className="eco-living__quote">
              «Відповідальна утилізація — це система, а не разова послуга.»
            </p>
            <ul className="eco-living__bullets">
              <li>Історія всіх замовлень та повторні заявки</li>
              <li>Договори, рахунки, акти й сертифікати в одному місці</li>
              <li>Прозорий статус кожної заявки та ваш менеджер</li>
            </ul>
          </div>
        </aside>
      </div>
    </div>
  );
}

export function AuthBrand() {
  return (
    <Link to="/" className="client-auth__brand" aria-label="ECO.NOVA — на головну" data-testid="auth-brand-home">
      <span className="eco-wordmark">ECO<span className="eco-wordmark__dot" /><span className="eco-wordmark__nova">NOVA</span></span>
      <span className="client-auth__brand-sub">Utilization Platform</span>
    </Link>
  );
}
