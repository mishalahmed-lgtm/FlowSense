import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { adminLogin } from "../api/client.js";

const AuthContext = createContext(null);

const TOKEN_STORAGE_KEY = "iot_admin_token";
const USER_STORAGE_KEY = "iot_user_data";

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_STORAGE_KEY));
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem(USER_STORAGE_KEY);
    return stored ? JSON.parse(stored) : null;
  });

  useEffect(() => {
    if (token) {
      localStorage.setItem(TOKEN_STORAGE_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  }, [token]);

  useEffect(() => {
    if (user) {
      localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
    } else {
      localStorage.removeItem(USER_STORAGE_KEY);
    }
  }, [user]);

  const value = useMemo(
    () => ({
      token,
      user,
      isAuthenticated: Boolean(token && user),
      isAdmin: user?.role === 'admin',
      isTenantAdmin: user?.role === 'tenant_admin',
      hasModule: (moduleName) => {
        if (user?.role === 'admin') return true; // Admins have all modules
        return user?.enabled_modules?.includes(moduleName) || false;
      },
      login: ({ accessToken, userData }) => {
        setToken(accessToken);
        setUser(userData);
      },
      logout: () => {
        setToken(null);
        setUser(null);
        localStorage.removeItem(TOKEN_STORAGE_KEY);
        localStorage.removeItem(USER_STORAGE_KEY);
      },
      // Backwards compatibility
      adminEmail: user?.email,
    }),
    [token, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}


