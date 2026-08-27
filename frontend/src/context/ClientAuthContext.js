import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { ClientAPI, getClientToken, setClientToken } from "@/lib/clientApi";

const Ctx = createContext(null);

export function useClientAuth() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useClientAuth must be used within ClientAuthProvider");
  return v;
}

export function ClientAuthProvider({ children }) {
  const [customer, setCustomer] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!getClientToken()) {
      setCustomer(null);
      setLoading(false);
      return;
    }
    try {
      const d = await ClientAPI.me();
      setCustomer(d.customer || null);
    } catch (e) {
      setClientToken(null);
      setCustomer(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const login = useCallback(
    (token, cust) => {
      setClientToken(token);
      if (cust) {
        setCustomer(cust);
        setLoading(false);
      } else {
        refresh();
      }
    },
    [refresh]
  );

  const logout = useCallback(() => {
    setClientToken(null);
    setCustomer(null);
  }, []);

  return (
    <Ctx.Provider value={{ customer, loading, login, logout, refresh, isAuthed: !!customer }}>
      {children}
    </Ctx.Provider>
  );
}
