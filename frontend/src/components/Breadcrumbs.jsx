import { Link } from "react-router-dom";
import PropTypes from "prop-types";

export default function Breadcrumbs({ items }) {
  return (
    <nav className="breadcrumbs" aria-label="Breadcrumb">
      {items.map((item, index) => {
        const isLast = index === items.length - 1;
        return (
          <span key={index} className="breadcrumbs__item-wrapper">
            {isLast ? (
              <span className="breadcrumbs__item breadcrumbs__item--active">
                {item.label}
              </span>
            ) : (
              <>
                <Link to={item.path} className="breadcrumbs__item">
                  {item.label}
                </Link>
                <span className="breadcrumbs__separator" aria-hidden="true">
                  /
                </span>
              </>
            )}
          </span>
        );
      })}
    </nav>
  );
}

Breadcrumbs.propTypes = {
  items: PropTypes.arrayOf(
    PropTypes.shape({
      label: PropTypes.string.isRequired,
      path: PropTypes.string.isRequired,
    })
  ).isRequired,
};

