import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchListing, trackClick } from "../lib/api";
import { timeAgo, money } from "../lib/format";
import { ArrowLeft, ArrowUpRight, TrendingUp, Zap, MousePointerClick, Loader2 } from "lucide-react";
import SubmissionModal from "../components/SubmissionModal";
import Marquee from "../components/Marquee";
import Countdown from "../components/Countdown";

export default function ProductDetail() {
  const { id } = useParams();
  const [item, setItem] = useState(null);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const data = await fetchListing(id);
        if (alive) { setItem(data); setLoading(false); }
      } catch {
        if (alive) setLoading(false);
      }
    };
    load();
    const t = setInterval(load, 8000);
    return () => { alive = false; clearInterval(t); };
  }, [id]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="animate-spin text-[color:var(--fb-cyan)]" size={40} />
      </div>
    );
  }

  if (!item) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center px-4 text-center">
        <h1 className="font-display text-3xl text-white">Listing not found.</h1>
        <Link to="/" className="fb-btn-primary mt-6">Back to board</Link>
      </div>
    );
  }

  const nextBid = (Number(item.current_bid) + 1).toFixed(0);
  const platformLabel = item.platform === "x" ? "X" : item.platform === "instagram" ? "IG" : null;

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 bg-black/85 backdrop-blur border-b border-[color:var(--fb-border)]">
        <div className="max-w-5xl mx-auto flex items-center justify-between px-4 md:px-8 py-3 md:py-4">
          <Link to="/" data-testid="detail-back" className="flex items-center gap-2 text-white font-mono text-xs uppercase tracking-widest">
            <ArrowLeft size={14} /> Board
          </Link>
          <Countdown variant="compact" />
        </div>
      </header>

      <Marquee />

      <main className="max-w-5xl mx-auto px-4 md:px-8 py-8 md:py-12">
        <div className="grid md:grid-cols-3 gap-6 md:gap-8">
          <div className="md:col-span-2">
            <div className="flex items-start gap-4 mb-6">
              <img src={item.image_url} alt="" className="w-20 h-20 md:w-28 md:h-28 border border-[color:var(--fb-border)] object-cover" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap mb-2">
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
                  {item.boosted && (
                    <span className="text-[10px] font-mono px-2 py-0.5 border border-[color:var(--fb-cyan)] text-[color:var(--fb-cyan)] uppercase tracking-widest inline-flex items-center gap-1">
                      <Zap size={10} /> BOOSTED
                    </span>
                  )}
                </div>
                <h1 className="font-alt text-2xl md:text-4xl font-bold text-white leading-tight">{item.title}</h1>
                <p className="text-sm md:text-base text-[color:var(--fb-text-2)] mt-2">{item.tagline}</p>
              </div>
            </div>

            {item.description && (
              <p className="text-sm md:text-base text-[color:var(--fb-text-2)] leading-relaxed whitespace-pre-wrap">
                {item.description}
              </p>
            )}

            <a
              href={item.url}
              target="_blank"
              rel="noreferrer noopener"
              onClick={() => trackClick(item.id)}
              data-testid="detail-visit-link"
              className="fb-btn-ghost inline-flex items-center gap-2 mt-6"
            >
              Visit {new URL(item.url).hostname} <ArrowUpRight size={16} />
            </a>
          </div>

          <aside className="border border-[color:var(--fb-border)] bg-[color:var(--fb-surface)] p-5 md:p-6 h-fit md:sticky md:top-24">
            <div className="text-[10px] font-mono uppercase tracking-widest text-[color:var(--fb-text-2)]">Current bid</div>
            <div className="font-display text-4xl md:text-5xl font-black text-[color:var(--fb-yellow)] mt-1">
              {money(item.current_bid, { compact: true })}
            </div>
            <div className="text-[10px] font-mono text-[color:var(--fb-muted)] mt-1">
              Updated {timeAgo(item.last_bid_at_iso)}
            </div>

            <button
              data-testid="detail-outbid-btn"
              onClick={() => setModal(true)}
              className="fb-btn-primary w-full mt-4 inline-flex items-center justify-center gap-2"
            >
              <TrendingUp size={16} /> Claim this rank for ${nextBid}
            </button>

            {Number(item.click_count || 0) > 0 && (
              <div className="mt-4 pt-4 border-t border-[color:var(--fb-border)] flex items-center gap-2 text-xs font-mono text-[color:var(--fb-text-2)]">
                <MousePointerClick size={12} />
                {Number(item.click_count).toLocaleString()} clicks
              </div>
            )}
            <div className="mt-2 text-xs font-mono text-[color:var(--fb-muted)]">
              Listed {timeAgo(item.created_at_iso)}
            </div>
          </aside>
        </div>
      </main>

      <SubmissionModal
        open={modal}
        onClose={() => setModal(false)}
        mode="outbid"
        target={item}
        defaultType={item.listing_type}
      />
    </div>
  );
}
