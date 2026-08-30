import { ArrowUpRight, Zap, TrendingUp, MousePointerClick } from "lucide-react";
import { Link } from "react-router-dom";
import { trackClick } from "../lib/api";
import { timeAgo, money } from "../lib/format";

export default function ListingCard({ item, onOutbid }) {
  const isOne = item.rank === 1;
  const cardCls = `fb-card ${isOne ? "fb-glow-yellow" : ""} p-3 sm:p-4 md:p-5 flex flex-col md:flex-row gap-3 md:gap-4 relative`;
  const platformLabel = item.platform === "x" ? "𝕏" : item.platform === "instagram" ? "IG" : null;
  const nextBid = (Number(item.current_bid) + 1).toFixed(0);

  const handleClick = () => {
    trackClick(item.id);
  };

  return (
    <div data-testid={`listing-card-${item.id}`} className={cardCls}>
      {isOne && (
        <div className="absolute -top-3 left-3 sm:left-4 bg-[color:var(--fb-yellow)] text-black text-[10px] font-mono font-bold tracking-widest px-2 py-1">
          TOP OF THE BOARD
        </div>
      )}

      {/* LEFT — rank, image, main info */}
      <div className="flex items-start gap-3 sm:gap-4 flex-1 min-w-0">
        <div className="flex flex-col items-center min-w-[44px] sm:min-w-[56px]">
          <span className={`font-display font-black ${isOne ? "text-3xl sm:text-4xl md:text-5xl text-[color:var(--fb-yellow)]" : "text-2xl sm:text-3xl text-white"}`}>
            #{item.rank}
          </span>
          {item.boosted && (
            <span className="mt-1 flex items-center gap-1 text-[9px] sm:text-[10px] font-mono text-[color:var(--fb-cyan)]">
              <Zap size={10} /> BOOST
            </span>
          )}
        </div>

        <Link
          to={`/product/${item.id}`}
          className="w-14 h-14 sm:w-16 sm:h-16 md:w-20 md:h-20 shrink-0 border border-[color:var(--fb-border)] bg-black overflow-hidden"
        >
          <img src={item.image_url} alt="" className="w-full h-full object-cover" loading="lazy" />
        </Link>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap mb-1">
            {item.category && (
              <span className="text-[9px] sm:text-[10px] font-mono px-1.5 sm:px-2 py-0.5 border border-[color:var(--fb-border)] text-[color:var(--fb-text-2)] uppercase tracking-widest">
                {item.category}
              </span>
            )}
            {platformLabel && (
              <span className="text-[9px] sm:text-[10px] font-mono px-1.5 sm:px-2 py-0.5 border border-[color:var(--fb-cyan)] text-[color:var(--fb-cyan)] uppercase tracking-widest">
                {platformLabel}
              </span>
            )}
            {item.last_bid_at_iso && (
              <span className="text-[9px] sm:text-[10px] font-mono text-[color:var(--fb-muted)]">
                · {timeAgo(item.last_bid_at_iso)}
              </span>
            )}
          </div>
          <a
            data-testid={`listing-link-${item.id}`}
            href={item.url}
            target="_blank"
            rel="noreferrer noopener"
            onClick={handleClick}
            className="group inline-flex items-baseline gap-1 max-w-full"
          >
            <h3 className="font-alt text-base sm:text-lg md:text-xl font-bold text-white group-hover:text-[color:var(--fb-pink)] truncate">
              {item.title}
            </h3>
            <ArrowUpRight size={16} className="shrink-0 text-[color:var(--fb-text-2)] group-hover:text-[color:var(--fb-pink)]" />
          </a>
          <p className="text-xs sm:text-sm text-[color:var(--fb-text-2)] mt-1 line-clamp-2">{item.tagline}</p>
          {Number(item.click_count || 0) > 0 && (
            <div className="mt-1.5 flex items-center gap-1 text-[10px] font-mono text-[color:var(--fb-muted)]">
              <MousePointerClick size={10} /> {Number(item.click_count).toLocaleString()} clicks
            </div>
          )}
        </div>
      </div>

      {/* RIGHT — bid and outbid */}
      <div className="flex md:flex-col items-center md:items-end justify-between gap-2 md:gap-3 md:min-w-[180px] pt-2 md:pt-0 border-t md:border-t-0 border-[color:var(--fb-border)]">
        <div className="text-left md:text-right">
          <div className="text-[9px] sm:text-[10px] font-mono text-[color:var(--fb-text-2)] tracking-widest uppercase">
            Current bid
          </div>
          <div data-testid={`bid-amount-${item.id}`} className={`font-display font-black text-2xl sm:text-3xl md:text-4xl ${isOne ? "text-[color:var(--fb-yellow)]" : "text-[color:var(--fb-green)] fb-glow-green"}`}>
            {money(item.current_bid, { compact: true })}
          </div>
        </div>
        <button
          data-testid={`outbid-btn-${item.id}`}
          onClick={() => onOutbid(item)}
          className="fb-btn-primary inline-flex items-center gap-1.5 text-[11px] sm:text-xs px-3 sm:px-4 py-2 sm:py-3 whitespace-nowrap"
        >
          <TrendingUp size={12} /> Claim for ${nextBid}
        </button>
      </div>
    </div>
  );
}
