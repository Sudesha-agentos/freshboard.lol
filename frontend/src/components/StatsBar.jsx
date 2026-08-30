import { useEffect, useState } from "react";
import { fetchStats } from "../lib/api";
import { moneyInt } from "../lib/format";

export default function StatsBar() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const s = await fetchStats();
        if (alive) setStats(s);
      } catch { /* ignore */ }
    };
    load();
    const t = setInterval(load, 30000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  if (!stats) return null;

  return (
    <div data-testid="stats-bar" className="border border-[color:var(--fb-border)] bg-black p-4 sm:p-6 text-center">
      <div className="font-mono text-[10px] sm:text-xs uppercase tracking-widest text-[color:var(--fb-text-2)]">
        Since launch, the crowd earned
      </div>
      <div className="font-display text-3xl sm:text-5xl md:text-6xl font-black text-[color:var(--fb-green)] fb-glow-green mt-1">
        {moneyInt(stats.total_credits)} <span className="text-2xl sm:text-3xl">credits</span>
      </div>
      <div className="font-mono text-[10px] sm:text-xs text-[color:var(--fb-text-2)] mt-1">
        via {stats.total_shares} shares · {stats.active_today} listings live today
      </div>
    </div>
  );
}
