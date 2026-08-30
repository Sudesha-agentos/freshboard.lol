import { ArrowUpRight, Flame, Zap, TrendingUp } from "lucide-react";

function money(n) {
  const v = Number(n || 0);
  return v >= 1000 ? `$${(v / 1000).toFixed(1)}k` : `$${v.toFixed(2)}`;
}

export default function ListingCard({ item, onOutbid, featured }) {
  const isOne = item.rank === 1;
  const cardCls = `fb-card ${isOne ? "fb-glow-yellow" : ""} p-4 md:p-5 flex flex-col md:flex-row gap-4 relative`;
  const platformLabel = item.platform === "x" ? "𝕏 POST" : item.platform === "instagram" ? "IG POST" : null;

  return (
    <div data-testid={`listing-card-${item.id}`} className={cardCls}>
      {isOne && (
        <div className="absolute -top-3 left-4 bg-[color:var(--fb-yellow)] text-black text-[10px] font-mono font-bold tracking-widest px-2 py-1">
          TOP OF THE BOARD
        </div>
      )}

      <div className="flex items-start gap-4 flex-1 min-w-0">
        <div className="flex flex-col items-center min-w-[56px]">
          <span className={`font-display ${isOne ? "text-5xl text-[color:var(--fb-yellow)]" : "text-3xl text-white"} font-black`}>
            #{item.rank}
          </span>
          {item.boosted && (
            <span className="mt-1 flex items-center gap-1 text-[10px] font-mono text-[color:var(--fb-cyan)]">
              <Zap size={10} /> BOOSTED
            </span>
          )}
        </div>

        <div className="w-16 h-16 md:w-20 md:h-20 shrink-0 border border-[color:var(--fb-border)] bg-black overflow-hidden">
          <img src={item.image_url} alt="" className="w-full h-full object-cover" loading="lazy" />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            {item.category && (
              <span className="text-[10px] font-mono px-2 py-0.5 border border-[color:var(--fb-border)] text-[color:var(--fb-text-2)] uppercase tracking-widest">
                {item.category}
              </span>
            )}
            {platformLabel && (
              <span className="text-[10px] font-mono px-2 py-0.5 border border-[color:var(--fb-cyan)] text-[color:var(--fb-cyan)] uppercase tracking-widest">
                {platformLabel}
              </span>
            )}
          </div>
          <a
            data-testid={`listing-link-${item.id}`}
            href={item.url}
            target="_blank"
            rel="noreferrer noopener"
            className="group inline-flex items-baseline gap-1"
          >
            <h3 className="font-alt text-lg md:text-xl font-bold text-white group-hover:text-[color:var(--fb-pink)] truncate">
              {item.title}
            </h3>
            <ArrowUpRight size={16} className="text-[color:var(--fb-text-2)] group-hover:text-[color:var(--fb-pink)]" />
          </a>
          <p className="text-sm text-[color:var(--fb-text-2)] mt-1 line-clamp-2">{item.tagline}</p>
        </div>
      </div>

      <div className="flex md:flex-col items-end md:items-end justify-between gap-3 md:min-w-[180px]">
        <div className="text-right">
          <div className="text-[10px] font-mono text-[color:var(--fb-text-2)] tracking-widest uppercase">
            Current bid
          </div>
          <div data-testid={`bid-amount-${item.id}`} className={`font-display font-black text-3xl md:text-4xl ${isOne ? "text-[color:var(--fb-yellow)]" : "text-[color:var(--fb-green)] fb-glow-green"}`}>
            {money(item.current_bid)}
          </div>
        </div>
        <button
          data-testid={`outbid-btn-${item.id}`}
          onClick={() => onOutbid(item)}
          className="fb-btn-primary inline-flex items-center gap-2 text-xs"
        >
          <TrendingUp size={14} /> Outbid
        </button>
      </div>
    </div>
  );
}
