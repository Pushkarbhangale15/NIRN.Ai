import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api, setAuthToken, setOnUnauthorized } from "./api.js";

const AuthContext = createContext(null);

const TOKEN_KEY = "nirn_auth_token";

export function AuthProvider({ children }) {
  const [officer, setOfficer] = useState(null);
  const [loading, setLoading] = useState(true);

  const clearAuth = useCallback(() => {
    setOfficer(null);
    setAuthToken(null);
    try { sessionStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ }
  }, []);

  // CRITICAL: this effect resolves in the background — it never blocks
  // first render. The navbar swaps in officer-aware items once it
  // resolves; the rest of the page (including the fully public Home
  // page) renders immediately regardless.
  useEffect(() => {
    setOnUnauthorized(() => {
      clearAuth();
    });

    const token = (() => {
      try { return sessionStorage.getItem(TOKEN_KEY); } catch { return null; }
    })();

    if (!token) {
      setLoading(false);
      return;
    }

    setAuthToken(token);
    api.getMe()
      .then((me) => setOfficer(me))
      .catch(() => clearAuth())
      .finally(() => setLoading(false));
  }, [clearAuth]);

  const login = useCallback(async (loginId, password) => {
    const res = await api.login(loginId, password);
    setAuthToken(res.access_token);
    try { sessionStorage.setItem(TOKEN_KEY, res.access_token); } catch { /* ignore */ }
    setOfficer(res.officer);
    return res.officer;
  }, []);

  const logout = useCallback(() => {
    clearAuth();
  }, [clearAuth]);

  const refreshMe = useCallback(async () => {
    const me = await api.getMe();
    setOfficer(me);
    return me;
  }, []);

  const value = {
    officer,
    isAuthenticated: Boolean(officer),
    isAdmin: officer?.role === "admin",
    isReviewer: officer?.role === "reviewer",
    loading,
    login,
    logout,
    refreshMe,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
