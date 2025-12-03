import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

export default function Navbar() {
  const { adminEmail } = useAuth();

  return (
    <header className="navbar">
      <div>
        <h1 className="navbar__title">IoT Operations</h1>
        <p className="navbar__subtitle">Telemetry ingestion overview</p>
      </div>
      <nav className="navbar__links">
        <NavLink to="/dashboard">Dashboard</NavLink>
        <NavLink to="/devices">Devices</NavLink>
      </nav>
      <div className="navbar__auth">
        <span>{adminEmail}</span>
      </div>
    </header>
  );
}


