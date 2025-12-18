import { useNavigate } from "react-router-dom";
import Icon from "./Icon.jsx";

export default function BackButton({ label = "Back", to }) {
  const navigate = useNavigate();

  const handleClick = () => {
    if (to) {
      navigate(to);
    } else {
      // Prefer going back in history; if no history, fall back to dashboard
      if (window.history.length > 1) {
        navigate(-1);
      } else {
        navigate("/dashboard");
      }
    }
  };

  return (
    <button
      type="button"
      className="btn btn--ghost"
      onClick={handleClick}
      style={{ display: "inline-flex", alignItems: "center", gap: "var(--space-2)" }}
    >
      <Icon name="arrow-left" size={16} />
      <span>{label}</span>
    </button>
  );
}


