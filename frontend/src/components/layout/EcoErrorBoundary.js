import React from "react";

/**
 * EcoErrorBoundary — graceful fallback for non-critical visual layers
 * (WebGL, GSAP, etc). Prevents the whole page from crashing if a
 * cosmetic component throws (e.g. Three.js + React 19 StrictMode
 * double-mount edge case).
 */
export default class EcoErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    if (typeof console !== "undefined" && console.warn) {
      // eslint-disable-next-line no-console
      console.warn("[EcoErrorBoundary] suppressed cosmetic error:", error?.message);
    }
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || null;
    }
    return this.props.children;
  }
}
