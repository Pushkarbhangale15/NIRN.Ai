import { createContext, useContext, useEffect, useState } from "react";
import { api, getStoredToken, setStoredToken } from "./api.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [officer, setOfficer] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) {
      setLoading(false);
      return;
    }
    api
      .me()
      .then(setOfficer)
      .catch(() => setStoredToken(null))
      .finally(() => setLoading(false));
  }, []);

  const login = async (loginId, password) => {
    const res = await api.login(loginId, password);
    setStoredToken(res.access_token);
    setOfficer(res.officer);
    return res.officer;
  };

  const logout = () => {
    setStoredToken(null);
    setOfficer(null);
  };

  return (
    <AuthContext.Provider value={{ officer, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
