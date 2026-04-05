export default function Icon({ name, className }) {
  const svgProps = {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.8",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": "true",
    className
  };

  switch (name) {
    case "menu":
      return (
        <svg {...svgProps}>
          <path d="M4 7h16" />
          <path d="M4 12h16" />
          <path d="M4 17h16" />
        </svg>
      );
    case "notifications":
      return (
        <svg {...svgProps}>
          <path d="M15 18H9" />
          <path d="M18 16V11a6 6 0 0 0-12 0v5l-2 2h16z" />
        </svg>
      );
    case "account":
      return (
        <svg {...svgProps}>
          <path d="M20 21a8 8 0 0 0-16 0" />
          <circle cx="12" cy="8" r="4" />
        </svg>
      );
    case "settings":
      return (
        <svg {...svgProps}>
          <path d="M10 5H4" />
          <path d="M20 5h-4" />
          <path d="M14 5a2 2 0 1 1-4 0 2 2 0 0 1 4 0Z" />
          <path d="M6 12H4" />
          <path d="M20 12h-8" />
          <path d="M12 12a2 2 0 1 1-4 0 2 2 0 0 1 4 0Z" />
          <path d="M20 19h-4" />
          <path d="M10 19H4" />
          <path d="M18 19a2 2 0 1 1-4 0 2 2 0 0 1 4 0Z" />
        </svg>
      );
    case "setup":
      return (
        <svg {...svgProps}>
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1 1 0 0 0 .2 1.1l.1.1a1 1 0 0 1 0 1.4l-1.3 1.3a1 1 0 0 1-1.4 0l-.1-.1a1 1 0 0 0-1.1-.2 1 1 0 0 0-.6.9V20a1 1 0 0 1-1 1h-2a1 1 0 0 1-1-1v-.2a1 1 0 0 0-.6-.9 1 1 0 0 0-1.1.2l-.1.1a1 1 0 0 1-1.4 0l-1.3-1.3a1 1 0 0 1 0-1.4l.1-.1a1 1 0 0 0 .2-1.1 1 1 0 0 0-.9-.6H4a1 1 0 0 1-1-1v-2a1 1 0 0 1 1-1h.2a1 1 0 0 0 .9-.6 1 1 0 0 0-.2-1.1l-.1-.1a1 1 0 0 1 0-1.4l1.3-1.3a1 1 0 0 1 1.4 0l.1.1a1 1 0 0 0 1.1.2 1 1 0 0 0 .6-.9V4a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v.2a1 1 0 0 0 .6.9 1 1 0 0 0 1.1-.2l.1-.1a1 1 0 0 1 1.4 0l1.3 1.3a1 1 0 0 1 0 1.4l-.1.1a1 1 0 0 0-.2 1.1 1 1 0 0 0 .9.6H20a1 1 0 0 1 1 1v2a1 1 0 0 1-1 1h-.2a1 1 0 0 0-.9.6Z" />
        </svg>
      );
    case "users":
      return (
        <svg {...svgProps}>
          <path d="M16 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2" />
          <circle cx="9.5" cy="7" r="3.5" />
          <path d="M20 8.5a3 3 0 0 0-2-2.83" />
          <path d="M20 16a3 3 0 0 0-3-3h-1" />
        </svg>
      );
    case "sites":
      return (
        <svg {...svgProps}>
          <path d="M12 21s6-5.7 6-11a6 6 0 1 0-12 0c0 5.3 6 11 6 11Z" />
          <circle cx="12" cy="10" r="2.5" />
        </svg>
      );
    case "cards":
      return (
        <svg {...svgProps}>
          <rect x="3" y="6" width="18" height="12" rx="2" />
          <path d="M3 10h18" />
          <path d="M7 15h3" />
        </svg>
      );
    case "methodTypes":
      return (
        <svg {...svgProps}>
          <path d="M8 7h8" />
          <path d="M8 12h8" />
          <path d="M8 17h5" />
          <path d="M5 7h.01" />
          <path d="M5 12h.01" />
          <path d="M5 17h.01" />
        </svg>
      );
    case "redemptionMethods":
      return (
        <svg {...svgProps}>
          <path d="M9 7H5v4" />
          <path d="M5 11a7 7 0 1 0 2-4" />
        </svg>
      );
    case "gameTypes":
      return (
        <svg {...svgProps}>
          <rect x="5" y="5" width="14" height="14" rx="2" />
          <circle cx="9" cy="9" r="1" fill="currentColor" stroke="none" />
          <circle cx="15" cy="9" r="1" fill="currentColor" stroke="none" />
          <circle cx="9" cy="15" r="1" fill="currentColor" stroke="none" />
          <circle cx="15" cy="15" r="1" fill="currentColor" stroke="none" />
        </svg>
      );
    case "games":
      return (
        <svg {...svgProps}>
          <path d="M6 12h12" />
          <path d="M8 12V9a4 4 0 0 1 8 0v3" />
          <rect x="4" y="12" width="16" height="7" rx="3" />
          <path d="M9 15h.01" />
          <path d="M15 15h.01" />
        </svg>
      );
    case "tools":
      return (
        <svg {...svgProps}>
          <path d="M14.5 6.5a3.5 3.5 0 0 0-4.95 4.95l-4.05 4.05a1.5 1.5 0 1 0 2.12 2.12l4.05-4.05a3.5 3.5 0 0 0 4.95-4.95l-2.12 2.12-2.12-2.12 2.12-2.12Z" />
        </svg>
      );
    case "purchases":
      return (
        <svg {...svgProps}>
          <path d="M12 2v20" />
          <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
        </svg>
      );
    case "upload":
      return (
        <svg {...svgProps}>
          <path d="M12 16V5" />
          <path d="m7 10 5-5 5 5" />
          <path d="M5 19h14" />
        </svg>
      );
    case "search":
      return (
        <svg {...svgProps}>
          <circle cx="11" cy="11" r="6" />
          <path d="m20 20-3.5-3.5" />
        </svg>
      );
    case "filterMenu":
      return (
        <svg {...svgProps}>
          <path d="M4 7h16" />
          <path d="M7 12h10" />
          <path d="M10 17h4" />
        </svg>
      );
    case "chevronDown":
      return (
        <svg {...svgProps}>
          <path d="m6 9 6 6 6-6" />
        </svg>
      );
    case "chevronRight":
      return (
        <svg {...svgProps}>
          <path d="m9 6 6 6-6 6" />
        </svg>
      );
    default:
      return null;
  }
}
