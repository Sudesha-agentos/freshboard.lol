import { ArrowUpRight, Zap, TrendingUp, MousePointerClick } from "lucide-react";
import { Link } from "react-router-dom";
import { trackClick } from "../lib/api";
import { timeAgo, money } from "../lib/format";

export default function ListingCard({ item, onOutbid }) {
  const isOne = item.rank === 1;
  const platformLabel = item.platform === "x" ? "𝕏" : item.platform === "instagram" ? "IG" : null;
  const nextBid = (Number(item.current_bid) + 1).toFixed(0);

  const handleClick = () => { trackClick(item.id); };

  return (
    <div
      data-testid={`listing-card-${item.id}`}
      className={`fb-card p-3 sm:p-4 md:p-5 flex flex-col md:flex-row gap-3 md:gap-4 relative ${isOne ? "border-[color:var(--fb-yellow)]" : ""}`}
    >
      {/* MAIN — rank, image, product */}
      <div className="flex items-start gap-3 sm:gap-4 flex-1 min-w-0">
        <div className="flex flex-col items-center min-w-[38px] sm:min-w-[48px]">
          <span className={`font-display font-black ${isOne ? "text-2xl sm:text-3xl text-[color:var(--fb-yellow)]" : "text-xl sm:text-2xl text-[color:var(--fb-text-2)]"}`}>
            #{item.rank}
          </span>
        </div>

        <Link
          to={`/product/${item.id}`}
          className="w-14 h-14 sm:w-16 sm:h-16 md:w-20 md:h-20 shrink-0 border border-[color:var(--fb-border)] bg-black overflow-hidden"
        >
          <img src={item.image_url} alt="" className="w-full h-full object-cover" loading="lazy" />
        </Link>

        <div className="flex-1 min-w-0">
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
          <p className="text-xs sm:text-sm text-[color:var(--fb-text-2)] mt-1 line-clamp-2 leading-relaxed">
            {item.tagline}
          </p>
          <div className="flex items-center gap-1.5 flex-wrap mt-2 text-[10px] font-mono text-[color:var(--fb-muted)] uppercase tracking-widest">
            {item.category && (
              <span className="text-[color:var(--fb-text-2)]">{item.category}</span>
            )}
            {platformLabel && (
              <span className="text-[color:var(--fb-cyan)]">{platformLabel}</span>
            )}
            {(item.category || platformLabel) && <span>·</span>}
            <span>{timeAgo(item.last_bid_at_iso)}</span>
            {Number(item.click_count || 0) > 0 && (
              <>
                <span>·</span>
                <span className="inline-flex items-center gap-0.5">
                  <MousePointerClick size={9} /> {Number(item.click_count).toLocaleString()}
                </span>
              </>
            )}
            {item.boosted && (
              <>
                <span>·</span>
                <span className="text-[color:var(--fb-cyan)] inline-flex items-center gap-0.5">
                  <Zap size={9} /> boost
                </span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* RIGHT — subtle bid chip + claim CTA */}
      <div className="flex items-center justify-between md:justify-end gap-3 md:gap-4 md:min-w-[200px] pt-2 md:pt-0 md:pl-4 md:border-l border-t md:border-t-0 border-[color:var(--fb-border)]">
        <div className="text-[10px] font-mono text-[color:var(--fb-text-2)]">
          <span className="uppercase tracking-widest opacity-60">bid</span>{" "}
          <span data-testid={`bid-amount-${item.id}`} className="text-[color:var(--fb-text)]">
            {money(item.current_bid, { compact: true })}
          </span>
        </div>
        <button
          data-testid={`outbid-btn-${item.id}`}
          onClick={() => onOutbid(item)}
          className="fb-btn-primary inline-flex items-center gap-1.5 text-[11px] sm:text-xs px-3 sm:px-4 py-2 whitespace-nowrap"
        >
          <TrendingUp size={12} /> Claim for ${nextBid}
        </button>
      </div>
    </div>
  );
}
