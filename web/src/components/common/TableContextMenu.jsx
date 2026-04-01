import { useEffect, useRef } from "react";

export default function TableContextMenu({ position, items, onClose }) {
  const menuRef = useRef(null);

  useEffect(() => {
    function handleClick(event) {
      if (menuRef.current && !menuRef.current.contains(event.target)) onClose();
    }
    function handleKey(event) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [onClose]);

  const style = {
    position: "fixed",
    zIndex: 1500,
    left: Math.min(position.x, window.innerWidth - 220),
    top: Math.min(position.y, window.innerHeight - items.length * 36 - 16),
  };

  return (
    <div className="table-context-menu" ref={menuRef} style={style} role="menu">
      {items.map((item, i) =>
        item.divider
          ? <div key={i} className="context-menu-divider" role="separator" />
          : (
            <button
              key={i}
              className={`context-menu-item${item.danger ? " danger" : ""}`}
              type="button"
              role="menuitem"
              disabled={item.disabled}
              onClick={() => { item.action(); onClose(); }}
            >
              {item.label}
            </button>
          )
      )}
    </div>
  );
}
