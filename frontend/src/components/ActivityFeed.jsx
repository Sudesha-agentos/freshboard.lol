import { useEffect, useState } from "react";
import { fetchActivity } from "../lib/api";
import { timeAgo, money } from "../lib/format";
import { TrendingUp, Rocket } from "lucide-react";
import { Link } from "react-router-dom";
import useBoardSocket from "../lib/useBoardSocket";

export default function ActivityFeed() {
  const [items, setItems] = useState([]);

  const load = async () => {
    try {
      const data = await fetchActivity(12);
      setItems(data.items || []);
    } catch { /* ignore */ }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, []);

  useBoardSocket(() => { load(); });

  return (
    <aside data-testid="activity-feed" className="border border-[color:var(--fb-border)] bg-[color:var(--fb-surface)]">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[color:var(--fb-border)]">
        <h2 className="font-mono text-xs uppercase tracking-widest text-white">Latest activity</h2>
        <span className="w-2 h-2 rounded-full bg-[color:var(--fb-green)] animate-pulse" />
      </div>
      <ul className="max-h-[420px] overflow-y-auto">
        {items.length === 0 && (
          <li className="px-4 py-6 text-xs font-mono text-[color:var(--fb-muted)]">
            No bids yet today. The first bid takes #1.
          </li>
        )}
        {items.map((it, i) => (
          <li key={`${it.id}-${i}`} className="border-b border-[color:var(--fb-border)] last:border-b-0">
            <Link
              to={`/product/${it.id}`}
              className="flex items-center gap-3 px-4 py-3 hover:bg-black/40 transition-colors"
            >
              <img src={it.image_url} alt="" className="w-8 h-8 border border-[color:var(--fb-border)] object-cover shrink-0" loading="lazy" />
              <div className="min-w-0 flex-1">
                <div className="text-sm text-white font-alt truncate">{it.title}</div>
                <div className="text-[10px] font-mono text-[color:var(--fb-muted)] flex items-center gap-1.5 flex-wrap">
                  {it.rank && <span className="text-[color:var(--fb-text-2)]">#{it.rank}</span>}
                  {it.rank && <span>·</span>}
                  <span>
                    {it.purpose === "share" ? (
                      <span className="inline-flex items-center gap-0.5"><TrendingUp size={9} /> shared</span>
                    ) : (
                      <span className="inline-flex items-center gap-0.5"><Rocket size={9} /> listed</span>
                    )}
                  </span>
                  <span>·</span>
                  <span className="text-[color:var(--fb-text-2)]">{Math.round(Number(it.current_bid || 0))} cr</span>
                  <span>·</span>
                  <span>{timeAgo(it.at)}</span>
                </div>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </aside>
  );
}
