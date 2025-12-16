import { useState } from "react";
import PropTypes from "prop-types";

export default function Collapsible({ title, children, defaultOpen = false }) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="collapsible">
      <button
        className="collapsible__header"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
      >
        <h3 className="collapsible__title">{title}</h3>
        <span className="collapsible__icon">▼</span>
      </button>
      <div className={`collapsible__content ${isOpen ? "collapsible__content--open" : ""}`}>
        {children}
      </div>
    </div>
  );
}

Collapsible.propTypes = {
  title: PropTypes.string.isRequired,
  children: PropTypes.node.isRequired,
  defaultOpen: PropTypes.bool,
};

