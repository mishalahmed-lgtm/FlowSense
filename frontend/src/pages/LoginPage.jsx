import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { adminLogin } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";

export default function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [formData, setFormData] = useState({
    email: "",
    password: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await adminLogin(formData.email, formData.password);
      
      // Update auth context with token and user data
      login({
        accessToken: response.access_token,
        userData: response.user,
      });

      // Redirect to dashboard
      navigate("/dashboard");
    } catch (err) {
      const message = err.response?.data?.detail || "Login failed. Please check your credentials.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(135deg, var(--color-primary-600) 0%, var(--color-primary-800) 100%)",
        padding: "var(--space-4)",
      }}
    >
      <div
        className="card"
        style={{
          maxWidth: "420px",
          width: "100%",
          boxShadow: "var(--shadow-2xl)",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: "var(--space-8)" }}>
          <div
            style={{
              width: "80px",
              height: "80px",
              background: "var(--color-primary-600)",
              borderRadius: "var(--radius-lg)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto var(--space-4)",
              fontSize: "2.5rem",
              color: "white",
              fontWeight: "bold",
            }}
          >
            FS
          </div>
          <h1 style={{ marginBottom: "var(--space-2)" }}>FlowSense</h1>
          <p style={{ color: "var(--color-text-secondary)", margin: 0 }}>
            IoT Platform Admin Console
          </p>
        </div>

        <form onSubmit={handleSubmit} className="form">
          {error && (
            <div
              className="card"
              style={{
                borderColor: "var(--color-error-500)",
                padding: "var(--space-3)",
                marginBottom: "var(--space-4)",
              }}
            >
              <p className="text-error" style={{ margin: 0, fontSize: "var(--font-size-sm)" }}>
                {error}
              </p>
            </div>
          )}

          <div className="form-group">
            <label className="form-label">Email Address</label>
            <input
              className="form-input"
              type="email"
              value={formData.email}
              onChange={(e) =>
                setFormData({ ...formData, email: e.target.value })
              }
              placeholder="your.email@example.com"
              required
              autoFocus
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Password</label>
            <input
              className="form-input"
              type="password"
              value={formData.password}
              onChange={(e) =>
                setFormData({ ...formData, password: e.target.value })
              }
              placeholder="Enter your password"
              required
              disabled={loading}
            />
          </div>

          <button
            type="submit"
            className="btn btn--primary"
            style={{ width: "100%", marginTop: "var(--space-4)" }}
            disabled={loading || !formData.email || !formData.password}
          >
            {loading ? "Signing in..." : "Sign In"}
          </button>
        </form>

        <div
          style={{
            marginTop: "var(--space-6)",
            padding: "var(--space-4)",
            background: "var(--color-gray-50)",
            borderRadius: "var(--radius-md)",
            fontSize: "var(--font-size-sm)",
          }}
        >
          <p style={{ margin: 0, color: "var(--color-text-secondary)" }}>
            <strong>Demo Credentials:</strong>
          </p>
          <p style={{ margin: "var(--space-2) 0 0", color: "var(--color-text-secondary)" }}>
            Admin: <code>admin@flowsense.com</code> / <code>AdminFlow</code>
          </p>
          <p style={{ margin: "var(--space-2) 0 0", color: "var(--color-text-secondary)" }}>
            Tenant: <code>tenant@flowsense.com</code> / <code>tenantFlow</code>
          </p>
        </div>
      </div>
    </div>
  );
}

