import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { adminLogin } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import Icon from "../components/Icon.jsx";

export default function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [formData, setFormData] = useState({
    email: "",
    password: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showPassword, setShowPassword] = useState(false);

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
        background: "var(--color-primary-600)",
        padding: "var(--space-4)",
      }}
    >
      <div
        className="card"
        style={{
          maxWidth: "420px",
          width: "100%",
          boxShadow: "var(--shadow-2xl)",
          backgroundColor: "var(--color-bg-primary)",
          border: "1px solid var(--color-border-medium)",
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
              fontWeight: "var(--font-weight-bold)",
            }}
          >
            FS
          </div>
          <h1 style={{ 
            marginBottom: "var(--space-2)",
            fontSize: "var(--font-size-2xl)",
            fontWeight: "var(--font-weight-bold)",
            color: "var(--color-text-primary)"
          }}>FlowSense</h1>
          <p style={{ 
            color: "var(--color-text-secondary)", 
            margin: 0,
            fontSize: "var(--font-size-sm)"
          }}>
            IoT Platform Admin Console
          </p>
        </div>

        <form onSubmit={handleSubmit} className="form" autoComplete="off">
          {error && (
            <div
              className="badge badge--error"
              style={{
                display: "block",
                padding: "var(--space-4)",
                marginBottom: "var(--space-4)",
              }}
            >
              {error}
            </div>
          )}

          <div className="form-group">
            <label className="form-label" htmlFor="email" style={{ 
              color: "var(--color-text-primary)",
              fontWeight: "var(--font-weight-medium)",
              marginBottom: "var(--space-2)"
            }}>
              Email Address
            </label>
            <input
              id="email"
              name="email"
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
              autoComplete="off"
              data-lpignore="true"
              style={{
                width: "100%",
                padding: "var(--space-4)",
                backgroundColor: "var(--color-bg-secondary)",
                border: "1px solid var(--color-border-medium)",
                color: "var(--color-text-primary)",
                fontSize: "var(--font-size-base)",
                minHeight: "48px",
                boxSizing: "border-box",
              }}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="password" style={{ 
              color: "var(--color-text-primary)",
              fontWeight: "var(--font-weight-medium)",
              marginBottom: "var(--space-2)"
            }}>
              Password
            </label>
            <div style={{ position: "relative" }}>
              <input
                id="password"
                name="password"
                className="form-input"
                type={showPassword ? "text" : "password"}
                value={formData.password}
                onChange={(e) =>
                  setFormData({ ...formData, password: e.target.value })
                }
                placeholder="Enter your password"
                required
                disabled={loading}
                autoComplete="off"
                data-lpignore="true"
                data-form-type="other"
                style={{ 
                  width: "100%",
                  padding: "var(--space-4)",
                  paddingRight: "var(--space-12)",
                  backgroundColor: "var(--color-bg-secondary)",
                  border: "1px solid var(--color-border-medium)",
                  color: "var(--color-text-primary)",
                  fontSize: "var(--font-size-base)",
                  minHeight: "48px",
                  boxSizing: "border-box",
                }}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{
                  position: "absolute",
                  right: "var(--space-4)",
                  top: "50%",
                  transform: "translateY(-50%)",
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  color: "var(--color-text-tertiary)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  padding: "var(--space-2)",
                  transition: "color var(--transition-fast)",
                  width: "32px",
                  height: "32px",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = "var(--color-text-primary)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = "var(--color-text-tertiary)";
                }}
                disabled={loading}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? (
                  <Icon name="eye-off" size={20} />
                ) : (
                  <Icon name="eye" size={20} />
                )}
              </button>
            </div>
          </div>

          <button
            type="submit"
            className="btn btn--primary"
            style={{ 
              width: "100%", 
              marginTop: "var(--space-6)",
              padding: "var(--space-4)",
              fontSize: "var(--font-size-base)",
              fontWeight: "var(--font-weight-semibold)",
              minHeight: "48px",
              cursor: loading || !formData.email || !formData.password ? "not-allowed" : "pointer",
            }}
            disabled={loading || !formData.email || !formData.password}
          >
            {loading ? "Signing in..." : "Sign In"}
          </button>
        </form>
      </div>
    </div>
  );
}

