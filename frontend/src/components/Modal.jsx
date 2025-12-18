import { useEffect } from "react";
import PropTypes from "prop-types";

export default function Modal({ isOpen = true, onClose, title, children, footer }) {
  useEffect(() => {
    document.body.style.overflow = "hidden";
    
    const handleEscape = (e) => {
      if (e.key === "Escape") onClose();
    };
    
    document.addEventListener("keydown", handleEscape);
    
    return () => {
      document.body.style.overflow = "";
      document.removeEventListener("keydown", handleEscape);
    };
  }, [onClose]);

  // Support both isOpen prop and conditional rendering
  if (isOpen === false) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal__header">
          <h2 className="modal__title">{title}</h2>
          <button 
            className="btn-icon" 
            onClick={onClose} 
            aria-label="Close"
            style={{ fontSize: "var(--font-size-xl)" }}
          >
            ×
          </button>
        </div>
        <div className="modal__body">{children}</div>
        {footer && <div className="modal__footer">{footer}</div>}
      </div>
    </div>
  );
}

Modal.propTypes = {
  isOpen: PropTypes.bool,
  onClose: PropTypes.func.isRequired,
  title: PropTypes.string.isRequired,
  children: PropTypes.node.isRequired,
  footer: PropTypes.node,
};

