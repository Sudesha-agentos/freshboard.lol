import { useEffect, useState } from "react";
import { fetchTopToday } from "../lib/api";
import { hostnameOf } from "../lib/format";
import { Rocket, ArrowUpRight, Flame, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import useBoardSocket from "../lib/useBoardSocket";
import ShareMenu from "./ShareMenu";

export default function ProductHero({ onLaunch }) {
  const [top, setTop] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const data = await fetchTopToday(1);
      setTop(data?.items?.[0] || null);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, []);

  useBoardSocket(() => { load(); });

  if (loading) return <div className="h-[300px]" />;

  if (!top) {
    return (
      <section data-testid="hero-empty" className="text-center py-10 md:py-16 max-w-3xl mx-auto">
        <div className="inline-flex items-center gap-2 border border-[color:var(--fb-border)] px-3 py-1 text-[10px] font-mono uppercase tracking-widest text-[color:var(--fb-cyan)] mb-6">
          <Flame size={12} /> Rank is shared, not voted
        </div>
        <h1 className="font-display text-4xl sm:text-5xl md:text-6xl font-black text-white leading-[0.95] tracking-tighter">
          The board is <span className="text-[color:var(--fb-pink)]">empty</span>.
        </h1>
        <p className="font-mono text-[color:var(--fb-text-2)] mt-4 text-sm md:text-base max-w-xl mx-auto">
          Add your product for free. Share a real post to earn credits. Highest credits = #1.
        </p>
        <div className="flex justify-center gap-3 mt-6">
          <button data-testid="hero-launch-btn" onClick={onLaunch} className="fb-btn-primary inline-flex items-center gap-2">
            <Rocket size={16} /> Launch for free
          </button>
        </div>
      </section>
    );
  }

  const credits = Math.round(Number(top.current_bid) || 0);

  return (
    <section data-testid="hero-product" className="text-center py-8 md:py-14 max-w-3xl mx-auto">
      <div className="inline-flex items-center gap-2 border border-[color:var(--fb-border)] px-3 py-1 text-[10px] font-mono uppercase tracking-widest text-[color:var(--fb-yellow)] mb-6">
        <Flame size={12} /> Today's #1 · {credits} credits
      </div>

      <Link to={`/product/${top.id}`} className="inline-block mb-5">
        <img
          src={top.image_url}
          alt=""
          className="w-20 h-20 md:w-24 md:h-24 mx-auto border border-[color:var(--fb-border)] object-cover"
        />
      </Link>

      <h1 className="font-display text-3xl sm:text-5xl md:text-6xl font-black text-white leading-[0.95] tracking-tighter">
        {top.title}
      </h1>
      <p className="font-mono text-[color:var(--fb-text-2)] mt-4 text-sm md:text-base max-w-xl mx-auto">
        {top.tagline}
      </p>

      <div className="flex flex-wrap justify-center gap-3 mt-7">
        <a
          data-testid="hero-visit"
          href={top.url}
          target="_blank"
          rel="noreferrer noopener"
          className="fb-btn-primary inline-flex items-center gap-2"
        >
          Open {hostnameOf(top.url) || "site"} <ArrowUpRight size={14} />
        </a>
        <ShareMenu listing={top} credits={credits}>
          <button
            data-testid="hero-share"
            className="fb-btn-ghost inline-flex items-center gap-2"
          >
            <Sparkles size={14} /> Share this to boost
          </button>
        </ShareMenu>
      </div>
    </section>
  );
}
