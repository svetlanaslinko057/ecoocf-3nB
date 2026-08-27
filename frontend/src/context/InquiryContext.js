import React, { createContext, useContext, useState, useCallback } from "react";
import InquiryModal from "@/components/InquiryModal";

const Ctx = createContext(null);

export function useInquiry() {
  const v = useContext(Ctx);
  return v || { openInquiry: () => {}, toggleInquiry: () => {}, close: () => {}, isOpen: false };
}

export function InquiryProvider({ children }) {
  const [state, setState] = useState({ open: false, type: "callback", code: "", title: "" });

  const openInquiry = useCallback((opts = {}) => {
    setState({
      open: true,
      type: opts.type || "callback",
      code: opts.code || "",
      title: opts.title || "",
    });
  }, []);

  const close = useCallback(() => setState((s) => ({ ...s, open: false })), []);

  const toggleInquiry = useCallback((opts = {}) => {
    setState((s) => (s.open
      ? { ...s, open: false }
      : { open: true, type: opts.type || "callback", code: opts.code || "", title: opts.title || "" }));
  }, []);

  return (
    <Ctx.Provider value={{ openInquiry, toggleInquiry, close, isOpen: state.open }}>
      {children}
      <InquiryModal state={state} onClose={close} onToggle={toggleInquiry} />
    </Ctx.Provider>
  );
}
