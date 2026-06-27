// Simple, flat line icons (no emojis). 24x24, inherit color via currentColor.
const P = {
  logo: <path d="M12 2l9 7-9 13L3 9z" />,
  plus: <path d="M12 5v14M5 12h14" />,
  hire: <><circle cx="9" cy="8" r="3.2" /><path d="M3.5 20a5.5 5.5 0 0 1 11 0" /><path d="M18 7v6M21 10h-6" /></>,
  search: <><circle cx="11" cy="11" r="7" /><path d="M16.5 16.5L21 21" /></>,
  wallet: <><rect x="3" y="6" width="18" height="13" rx="2.5" /><path d="M3 10h18" /><circle cx="16.5" cy="14" r="1.3" /></>,
  play: <path d="M7 5l12 7-12 7z" />,
  shield: <path d="M12 3l8 3v6c0 4.5-3.2 7.7-8 9-4.8-1.3-8-4.5-8-9V6z" />,
  reset: <><path d="M20 11a8 8 0 1 0-2.3 6" /><path d="M20 4v6h-6" /></>,
  transfer: <><path d="M4 9h13l-3.5-3.5M20 15H7l3.5 3.5" /></>,
  arrow: <path d="M5 12h14M13 6l6 6-6 6" />,
  block: <><circle cx="12" cy="12" r="9" /><path d="M6 6l12 12" /></>,
  close: <path d="M6 6l12 12M18 6L6 18" />,
  lock: <><rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></>,
  receipt: <><path d="M6 3h12v18l-3-2-3 2-3-2-3 2z" /><path d="M9 8h6M9 12h6" /></>,
};

export function Icon({ name }) {
  return (
    <svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {P[name] || null}
    </svg>
  );
}
