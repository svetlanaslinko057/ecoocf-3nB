import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { AuthAPI, setToken, getToken } from "@/lib/api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const bootstrap = useCallback(async () => {
    if (!getToken()) { setLoading(false); return; }
    try {
      const me = await AuthAPI.me();
      setUser(me.user || me);
    } catch {
      setToken(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { bootstrap(); }, [bootstrap]);

  const applyAuth = async (res) => {
    const token = res.access_token || res.token;
    if (!token) throw new Error("Не вдалося отримати токен");
    setToken(token);
    const me = await AuthAPI.me().catch(() => res.user || null);
    const resolved = me?.user || me || res.user || null;
    setUser(resolved);
    return resolved;
  };

  const login = async (email, password) => {
    const res = await AuthAPI.login(email, password);
    // 2FA (Google Authenticator) challenge — no token issued yet
    if (res.challenge === "totp") {
      return { challenge: "totp", user_id: res.user_id, user_email: res.user_email };
    }
    return applyAuth(res);
  };

  // Second factor: verify Google Authenticator TOTP and finish login.
  const verify2fa = async (user_id, code) => {
    const res = await AuthAPI.verify2fa(user_id, code);
    return applyAuth(res);
  };

  const refreshUser = async () => {
    const me = await AuthAPI.me().catch(() => null);
    if (me) setUser(me.user || me);
  };

  const logout = () => { setToken(null); setUser(null); };

  return (
    <AuthCtx.Provider value={{ user, loading, login, verify2fa, refreshUser, logout, isAuthed: !!user }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
