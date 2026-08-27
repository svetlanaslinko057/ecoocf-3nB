import React from "react";

/**
 * Lightweight route-level loader shown ONLY while a lazily-loaded page chunk
 * is being fetched (code-splitting). It changes no content — it just avoids a
 * blank flash during the brief chunk download on first visit to a route.
 */
export default function RouteFallback() {
  return (
    <div
      role="status"
      aria-label="Loading"
      style={{
        minHeight: "60vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "inherit",
      }}
    >
      <span
        style={{
          width: 34,
          height: 34,
          borderRadius: "50%",
          border: "3px solid rgba(120,140,110,0.25)",
          borderTopColor: "#3e9f57",
          display: "inline-block",
          animation: "ecoRouteSpin 0.8s linear infinite",
        }}
      />
      <style>{`@keyframes ecoRouteSpin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}
