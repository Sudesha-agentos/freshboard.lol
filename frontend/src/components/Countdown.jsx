import { useEffect, useState } from "react";
import { fetchResetInfo } from "../lib/api";

function pad(n) { return String(n).padStart(2, "0"); }

export default function Countdown({ variant = "hero" }) {
  const [seconds, setSeconds] = useState(null);

  useEffect(() => {
    let alive = true;
    const sync = async () => {
      try {
        const info = await fetchResetInfo();
        if (alive) setSeconds(info.seconds_until_reset);
      } catch { /* ignore */ }
    };
    sync();
    const tick = setInterval(() => setSeconds(s => (s == null ? s : Math.max(0, s - 1))), 1000);
    const resync = setInterval(sync, 60_000);
    return () => { alive = false; clearInterval(tick); clearInterval(resync); };
  }, []);

  if (seconds == null) return null;

  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;

  if (variant === "compact") {
    return (
      <span data-testid="countdown-compact" className="font-mono text-xs text-[color:var(--fb-yellow)]">
        RESET IN {pad(h)}:{pad(m)}:{pad(s)} IST
      </span>
    );
  }

  return (
    <div data-testid="countdown-hero" className="flex flex-col items-start">
      <span className="font-mono text-xs tracking-[0.4em] text-[color:var(--fb-text-2)] uppercase">
        Board resets in (IST)
      </span>
      <div className="font-display text-6xl md:text-8xl font-black text-white mt-2">
        <span data-testid="countdown-h">{pad(h)}</span>
        <span className="text-[color:var(--fb-pink)]">:</span>
        <span data-testid="countdown-m">{pad(m)}</span>
        <span className="text-[color:var(--fb-pink)]">:</span>
        <span data-testid="countdown-s">{pad(s)}</span>
      </div>
    </div>
  );
}
