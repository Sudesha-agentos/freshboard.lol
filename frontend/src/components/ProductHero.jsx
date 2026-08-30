import { useEffect, useState } from "react";
import { fetchTopToday } from "../lib/api";
import { Rocket, ArrowUpRight, Flame } from "lucide-react";
import { Link } from "react-router-dom";

/**
 * Product-forward hero: features the current #1 as the star of the page.
 * The bid is present but subtle — a small chip. Product name, image, and story lead.
 */
export default function ProductHero({ onClaim, onLaunch }) {
  const [top, setTop] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const data = await fetchTopToday(1);
        if (alive) { setTop(data.items?.[0] || null); setLoading(false); }
      } catch { if (alive) setLoading(false); }
    };
    load();
    const t = setInterval(load, 8000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  if (loading) {
    return <div className="h-[300px]" />;
  }

  if (!top) {
    return (
      <section data-testid="hero-empty" className="text-center py-10 md:py-16 max-w-3xl mx-auto">
        <div className="inline-flex items-center gap-2 border border-[color:var(--fb-border)] px-3 py-1 text-[10px] font-mono uppercase tracking-widest text-[color:var(--fb-cyan)] mb-6">
          <Flame size={12} /> Rank is bought, not voted
        </div>
        <h1 className="font-display text-4xl sm:text-5xl md:text-6xl font-black text-white leading-[0.95] tracking-tighter">
          The board is <span className="text-[color:var(--fb-pink)]">empty</span>.
        </h1>
        <p className="font-mono text-[color:var(--fb-text-2)] mt-4 text-sm md:text-base max-w-xl mx-auto">
          First bid takes #1. One dollar minimum. Wiped clean every midnight IST.
        </p>
        <div className="flex justify-center gap-3 mt-6">
          <button data-testid="hero-launch-btn" onClick={onLaunch} className="fb-btn-primary inline-flex items-center gap-2">
            <Rocket size={16} /> Take #1 now
          </button>
        </div>
      </section>
    );
  }

  return (
    <section data-testid="hero-product" className="text-center py-8 md:py-14 max-w-3xl mx-auto">
      <div className="inline-flex items-center gap-2 border border-[color:var(--fb-border)] px-3 py-1 text-[10px] font-mono uppercase tracking-widest text-[color:var(--fb-yellow)] mb-6">
        <Flame size={12} /> Today's #1 · bid ${Number(top.current_bid).toFixed(0)}
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
          Open {new URL(top.url).hostname.replace(/^www\./, "")} <ArrowUpRight size={14} />
        </a>
        <button
          data-testid="hero-claim-1"
          onClick={() => onClaim(top)}
          className="fb-btn-ghost inline-flex items-center gap-2"
        >
          Take #1 for ${Number(top.current_bid + 1).toFixed(0)}
        </button>
      </div>
    </section>
  );
}
