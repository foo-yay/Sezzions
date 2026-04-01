import { useEffect, useRef, useState } from "react";

/**
 * Themed typeahead select with keyboard navigation and autocomplete filtering.
 * Replaces native <select> for cross-entity FK dropdowns.
 */
export default function TypeaheadSelect({
  id,
  options,
  value,
  onChange,
  placeholder = "Search...",
  disabled = false,
  invalid = false
}) {
  const [inputText, setInputText] = useState("");
  const [open, setOpen] = useState(false);
  const [highlightIndex, setHighlightIndex] = useState(-1);
  const containerRef = useRef(null);
  const inputRef = useRef(null);
  const listRef = useRef(null);

  // Sync display text when value changes externally
  useEffect(() => {
    if (!open) {
      const selected = options.find((opt) => opt.value === value);
      setInputText(selected ? selected.label : "");
    }
  }, [value, options, open]);

  const filtered = inputText.trim()
    ? options.filter((opt) =>
        opt.label.toLowerCase().includes(inputText.trim().toLowerCase())
      )
    : options;

  function selectOption(opt) {
    onChange(opt.value);
    setInputText(opt.label);
    setOpen(false);
    setHighlightIndex(-1);
    inputRef.current?.blur();
  }

  function handleInputChange(event) {
    setInputText(event.target.value);
    setHighlightIndex(-1);
    if (!open) setOpen(true);
  }

  function handleInputFocus() {
    if (!disabled) {
      setOpen(true);
      setHighlightIndex(-1);
    }
  }

  function handleInputKeyDown(event) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlightIndex((current) => Math.min(current + 1, filtered.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlightIndex((current) => Math.max(current - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (highlightIndex >= 0 && highlightIndex < filtered.length) {
        selectOption(filtered[highlightIndex]);
      }
    } else if (event.key === "Escape") {
      event.stopPropagation();
      setOpen(false);
      const selected = options.find((opt) => opt.value === value);
      setInputText(selected ? selected.label : "");
      inputRef.current?.blur();
    } else if (event.key === "Tab") {
      setOpen(false);
      const selected = options.find((opt) => opt.value === value);
      setInputText(selected ? selected.label : "");
    }
  }

  function handleInputBlur(event) {
    // Delay close so click on option can fire
    requestAnimationFrame(() => {
      if (containerRef.current && !containerRef.current.contains(document.activeElement)) {
        setOpen(false);
        const selected = options.find((opt) => opt.value === value);
        setInputText(selected ? selected.label : "");
      }
    });
  }

  // Scroll highlighted item into view
  useEffect(() => {
    if (highlightIndex >= 0 && listRef.current) {
      const item = listRef.current.children[highlightIndex];
      if (item) item.scrollIntoView({ block: "nearest" });
    }
  }, [highlightIndex]);

  // Close on outside click
  useEffect(() => {
    if (!open) return undefined;
    function handlePointerDown(event) {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setOpen(false);
        const selected = options.find((opt) => opt.value === value);
        setInputText(selected ? selected.label : "");
      }
    }
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [open, options, value]);

  return (
    <div className="typeahead-select" ref={containerRef}>
      <input
        id={id}
        ref={inputRef}
        className={`text-input typeahead-input${invalid ? " invalid" : ""}`}
        type="text"
        autoComplete="off"
        placeholder={placeholder}
        value={inputText}
        disabled={disabled}
        onChange={handleInputChange}
        onFocus={handleInputFocus}
        onBlur={handleInputBlur}
        onKeyDown={handleInputKeyDown}
        role="combobox"
        aria-expanded={open}
        aria-autocomplete="list"
        aria-controls={`${id}-listbox`}
        aria-activedescendant={highlightIndex >= 0 ? `${id}-opt-${highlightIndex}` : undefined}
      />
      <span className="typeahead-chevron" aria-hidden="true">
        {open ? "\u25B4" : "\u25BE"}
      </span>
      {open && filtered.length > 0 ? (
        <ul
          id={`${id}-listbox`}
          ref={listRef}
          className="typeahead-dropdown"
          role="listbox"
        >
          {filtered.map((opt, idx) => (
            <li
              key={opt.value}
              id={`${id}-opt-${idx}`}
              className={`typeahead-option${idx === highlightIndex ? " highlighted" : ""}${opt.value === value ? " selected" : ""}`}
              role="option"
              aria-selected={opt.value === value}
              onMouseDown={(event) => {
                event.preventDefault();
                selectOption(opt);
              }}
              onMouseEnter={() => setHighlightIndex(idx)}
            >
              {opt.label}
            </li>
          ))}
        </ul>
      ) : null}
      {open && filtered.length === 0 ? (
        <ul id={`${id}-listbox`} className="typeahead-dropdown" role="listbox">
          <li className="typeahead-option typeahead-no-results">No matching users</li>
        </ul>
      ) : null}
    </div>
  );
}
