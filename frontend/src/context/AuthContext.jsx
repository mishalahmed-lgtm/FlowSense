import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { adminLogin } from "../api/client.js";

const AuthContext = createContext(null);

const TOKEN_STORAGE_KEY = "iot_admin_token";
const EMAIL_STORAGE_KEY = "iot_admin_email";
const DEFAULT_ADMIN_EMAIL = import.meta.env.VITE_ADMIN_EMAIL || "admin@example.com";
const DEFAULT_ADMIN_PASSWORD = import.meta.env.VITE_ADMIN_PASSWORD || "admin123";

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_STORAGE_KEY));
  const [adminEmail, setAdminEmail] = useState(() => localStorage.getItem(EMAIL_STORAGE_KEY));
  const [isBootstrapping, setIsBootstrapping] = useState(!token);
  const [bootstrapError, setBootstrapError] = useState(null);
  const [bootstrapAttempt, setBootstrapAttempt] = useState(0);

  useEffect(() => {
    if (token) {
      localStorage.setItem(TOKEN_STORAGE_KEY, token);
      setBootstrapError(null);
      setIsBootstrapping(false);
    } else {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  }, [token]);

  useEffect(() => {
    if (adminEmail) {
      localStorage.setItem(EMAIL_STORAGE_KEY, adminEmail);
    } else {
      localStorage.removeItem(EMAIL_STORAGE_KEY);
    }
  }, [adminEmail]);

  useEffect(() => {
    if (token) {
      return;
    }

    let cancelled = false;

    async function autoLogin() {
      setIsBootstrapping(true);
      setBootstrapError(null);
      try {
        const response = await adminLogin(DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD);
        if (cancelled) {
          return;
        }
        setToken(response.access_token);
        setAdminEmail(DEFAULT_ADMIN_EMAIL);
      } catch (error) {
        if (cancelled) {
          return;
        }
        const message = error.response?.data?.detail || "Automatic admin login failed";
        setBootstrapError(message);
      } finally {
        if (!cancelled) {
          setIsBootstrapping(false);
        }
      }
    }

    autoLogin();

    return () => {
      cancelled = true;
    };
  }, [token, bootstrapAttempt]);

  const value = useMemo(
    () => ({
      token,
      adminEmail,
      isAuthenticated: Boolean(token),
      isBootstrapping,
      bootstrapError,
      retryBootstrap: () => setBootstrapAttempt((attempt) => attempt + 1),
      login: ({ accessToken, email }) => {
        setToken(accessToken);
        setAdminEmail(email);
      },
      logout: () => {
        setToken(null);
        setAdminEmail(null);
        setBootstrapError(null);
      },
    }),
    [token, adminEmail, isBootstrapping, bootstrapError],
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


