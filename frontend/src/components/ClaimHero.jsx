import { useEffect, useState } from "react";
import { fetchTopToday } from "../lib/api";
import { Rocket, ArrowUpRight, TrendingUp } from "lucide-react";
import { money } from "../lib/format";
import { Link } from "react-router-dom";

export default function ClaimHero({ onClaim }) {
  const [top, setTop] = useState(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const data = await fetchTopToday(1);
        if (alive) setTop(data.items?.[0] || null);
      } catch { /* ignore */ }
    };
    load();
    const t = setInterval(load, 8000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  if (!top) {
    return (
      <div
        data-testid="claim-hero-empty"
        className="border border-[color:var(--fb-pink)] bg-[color:var(--fb-surface)] p-4 sm:p-6"
      >
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <div className="text-[10px] font-mono uppercase tracking-widest text-[color:var(--fb-cyan)]">Board is empty</div>
            <div className="font-display text-2xl sm:text-3xl font-black text-white mt-1">
              Claim <span className="text-[color:var(--fb-yellow)]">#1</span> for <span className="text-[color:var(--fb-green)]">$1</span>
            </div>
          </div>
          <button
            data-testid="claim-hero-btn"
            onClick={onClaim}
            className="fb-btn-primary inline-flex items-center gap-2 self-start sm:self-auto"
          >
            <Rocket size={16} /> Take #1 now
          </button>
        </div>
      </div>
    );
  }

  const nextBid = (Number(top.current_bid) + 1).toFixed(0);

  return (
    <div
      data-testid="claim-hero"
      className="border border-[color:var(--fb-pink)] bg-[color:var(--fb-surface)] p-4 sm:p-6"
    >
      <div className="flex flex-col md:flex-row md:items-center gap-4">
        <Link to={`/product/${top.id}`} className="w-14 h-14 sm:w-16 sm:h-16 shrink-0 border border-[color:var(--fb-border)] bg-black overflow-hidden">
          <img src={top.image_url} alt="" className="w-full h-full object-cover" />
        </Link>
        <div className="flex-1 min-w-0">
          <div className="text-[10px] font-mono uppercase tracking-widest text-[color:var(--fb-cyan)]">Currently #1</div>
          <a
            href={top.url}
            target="_blank"
            rel="noreferrer noopener"
            className="group inline-flex items-baseline gap-1 max-w-full"
          >
            <h2 className="font-alt text-lg sm:text-xl md:text-2xl font-bold text-white group-hover:text-[color:var(--fb-pink)] truncate">
              {top.title}
            </h2>
            <ArrowUpRight size={16} className="shrink-0 text-[color:var(--fb-text-2)] group-hover:text-[color:var(--fb-pink)]" />
          </a>
          <p className="text-xs sm:text-sm text-[color:var(--fb-text-2)] mt-1 line-clamp-2">{top.tagline}</p>
        </div>
        <div className="flex items-center justify-between md:justify-end gap-4 md:gap-6 pt-3 md:pt-0 border-t md:border-t-0 border-[color:var(--fb-border)]">
          <div className="text-left md:text-right">
            <div className="text-[10px] font-mono uppercase tracking-widest text-[color:var(--fb-text-2)]">Current bid</div>
            <div className="font-display text-2xl sm:text-3xl md:text-4xl font-black text-[color:var(--fb-yellow)]">
              {money(top.current_bid, { compact: true })}
            </div>
          </div>
          <button
            data-testid="claim-1-btn"
            onClick={() => onClaim(top)}
            className="fb-btn-primary inline-flex items-center gap-2 whitespace-nowrap"
          >
            <TrendingUp size={14} /> Claim #1 for ${nextBid}
          </button>
        </div>
      </div>
    </div>
  );
}
