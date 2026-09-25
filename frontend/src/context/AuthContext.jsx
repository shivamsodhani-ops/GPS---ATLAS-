import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api, registerUnauthorizedHandler } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const logoutLocal = useCallback(() => {
    localStorage.removeItem("atlas_token");
    setUser(null);
  }, []);

  useEffect(() => {
    registerUnauthorizedHandler(logoutLocal);
  }, [logoutLocal]);

  useEffect(() => {
    const token = localStorage.getItem("atlas_token");
    if (!token) {
      setLoading(false);
      return;
    }
    api
      .get("/api/auth/me")
      .then((res) => setUser(res.data))
      .catch(() => logoutLocal())
      .finally(() => setLoading(false));
  }, [logoutLocal]);

  async function login(email, password) {
    const res = await api.post("/api/auth/login", { email, password });
    localStorage.setItem("atlas_token", res.data.access_token);
    setUser(res.data.user);
    return res.data.user;
  }

  async function logout() {
    try {
      await api.post("/api/auth/logout");
    } catch {
      /* ignore */
    }
    logoutLocal();
  }

  function refreshUser(patch) {
    setUser((u) => ({ ...u, ...patch }));
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
