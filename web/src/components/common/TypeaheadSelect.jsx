import { useEffect, useMemo, useRef, useState } from "react";

/**
 * Themed typeahead select with inline ghost-text completion, Tab/Enter commit,
 * and prefix-first matching. Mirrors the desktop app's QComboBox + QCompleter
 * behavior (InlineCompletion + MatchStartsWith + CompleterEventFilter).
 */
export default function TypeaheadSelect({
  id,
  options,
  value,
  onChange,
  placeholder = "Search...",
  disabled = false,
  invalid = false,
  allowClear = false
}) {
  const [inputText, setInputText] = useState("");
  const [open, setOpen] = useState(false);
  const [highlightIndex, setHighlightIndex] = useState(0);
  const containerRef = useRef(null);
  const inputRef = useRef(null);
  const listRef = useRef(null);
  const committingRef = useRef(false);

  // Sync display text when value changes externally (and dropdown is closed)
  useEffect(() => {
    if (!open) {
      const selected = options.find((opt) => opt.value === value);
      setInputText(selected ? selected.label : "");
    }
  }, [value, options, open]);

  // Filter & sort: prefix matches first, then contains matches
  const filtered = useMemo(() => {
    const query = inputText.trim().toLowerCase();
    if (!query) return options;

    const prefixMatches = [];
    const containsMatches = [];

    for (const opt of options) {
      const label = opt.label.toLowerCase();
      if (label.startsWith(query)) {
        prefixMatches.push(opt);
      } else if (label.includes(query)) {
        containsMatches.push(opt);
      }
    }

    return [...prefixMatches, ...containsMatches];
  }, [inputText, options]);

  // Best prefix match for ghost text — the first option whose label starts with typed text
  const ghostText = useMemo(() => {
    const query = inputText.trim().toLowerCase();
    if (!query) return "";
    const match = options.find((opt) => opt.label.toLowerCase().startsWith(query));
    return match ? match.label : "";
  }, [inputText, options]);

  // Commit the given option: set value, close dropdown
  function commitOption(opt, { blur = true } = {}) {
    committingRef.current = true;
    onChange(opt.value);
    setInputText(opt.label);
    setOpen(false);
    setHighlightIndex(0);
    if (blur) {
      inputRef.current?.blur();
    }
    requestAnimationFrame(() => { committingRef.current = false; });
  }

  // Commit the best available match (highlighted item, or first filtered item)
  function commitBestMatch({ blur = true } = {}) {
    const target = highlightIndex >= 0 && highlightIndex < filtered.length
      ? filtered[highlightIndex]
      : filtered[0];

    if (target) {
      commitOption(target, { blur });
      return true;
    }
    return false;
  }

  function handleInputChange(event) {
    const text = event.target.value;
    setInputText(text);
    setHighlightIndex(0);
    if (!open) setOpen(true);
  }

  function handleInputFocus() {
    if (!disabled) {
      setOpen(true);
      setHighlightIndex(0);
    }
  }

  function handleInputKeyDown(event) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      setHighlightIndex((current) => Math.min(current + 1, filtered.length - 1));

    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlightIndex((current) => Math.max(current - 1, 0));

    } else if (event.key === "Enter") {
      // Commit the current match but do NOT let the event bubble up to the form
      // (mirrors desktop: Enter commits the completion but doesn't trigger Save)
      event.preventDefault();
      event.stopPropagation();
      commitBestMatch({ blur: false });

    } else if (event.key === "Tab") {
      // Tab commits the completion and allows default tab behavior (focus moves)
      // Do NOT call preventDefault — let native Tab focus-advance happen
      if (filtered.length > 0 && inputText.trim()) {
        commitBestMatch({ blur: false });
      } else {
        setOpen(false);
        const selected = options.find((opt) => opt.value === value);
        setInputText(selected ? selected.label : "");
      }

    } else if (event.key === "Escape") {
      event.stopPropagation();
      setOpen(false);
      const selected = options.find((opt) => opt.value === value);
      setInputText(selected ? selected.label : "");
      inputRef.current?.blur();
    }
  }

  function handleInputBlur() {
    requestAnimationFrame(() => {
      if (committingRef.current) return;
      if (containerRef.current && !containerRef.current.contains(document.activeElement)) {
        setOpen(false);
        if (allowClear && !inputText.trim()) {
          onChange("");
          setInputText("");
        } else {
          const selected = options.find((opt) => opt.value === value);
          setInputText(selected ? selected.label : "");
        }
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
        if (allowClear && !inputRef.current?.value.trim()) {
          onChange("");
          setInputText("");
        } else {
          const selected = options.find((opt) => opt.value === value);
          setInputText(selected ? selected.label : "");
        }
      }
    }
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [open, options, value, allowClear, onChange]);

  // Ghost text: the full suggestion shown faintly behind the input
  const showGhost = open && ghostText && inputText.trim() && ghostText.toLowerCase() !== inputText.trim().toLowerCase();
  const showClear = allowClear && !disabled && value;

  function handleClear(event) {
    event.preventDefault();
    event.stopPropagation();
    committingRef.current = true;
    onChange("");
    setInputText("");
    setOpen(false);
    setHighlightIndex(0);
    inputRef.current?.focus();
    requestAnimationFrame(() => { committingRef.current = false; });
  }

  return (
    <div className="typeahead-select" ref={containerRef}>
      <div className="typeahead-input-wrap">
        {showGhost ? (
          <span className="typeahead-ghost" aria-hidden="true">
            <span className="typeahead-ghost-typed">{inputText}</span>
            <span className="typeahead-ghost-suffix">{ghostText.slice(inputText.length)}</span>
          </span>
        ) : null}
        <input
          id={id}
          ref={inputRef}
          className={`text-input typeahead-input${invalid ? " invalid" : ""}${showClear ? " typeahead-has-clear" : ""}`}
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
          aria-autocomplete="both"
          aria-controls={`${id}-listbox`}
          aria-activedescendant={highlightIndex >= 0 ? `${id}-opt-${highlightIndex}` : undefined}
        />
      </div>
      {showClear ? (
        <button
          className="typeahead-clear"
          type="button"
          aria-label="Clear selection"
          tabIndex={-1}
          onMouseDown={handleClear}
        >
          &#x2715;
        </button>
      ) : null}
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
                commitOption(opt);
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
