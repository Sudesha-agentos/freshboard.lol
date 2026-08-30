import { useEffect, useState } from "react";
import { fetchYesterdayTop } from "../lib/api";
import { Crown } from "lucide-react";
import { Link } from "react-router-dom";
import { money } from "../lib/format";

export default function WinnersRibbon() {
  const [item, setItem] = useState(null);

  useEffect(() => {
    let alive = true;
    fetchYesterdayTop()
      .then(d => { if (alive) setItem(d.item); })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  if (!item) return null;

  return (
    <div
      data-testid="winners-ribbon"
      className="border border-[color:var(--fb-border)] bg-black/40 max-w-3xl mx-auto"
    >
      <Link
        to={`/product/${item.id}`}
        className="flex items-center gap-3 px-3 sm:px-4 py-2 sm:py-2.5 hover:bg-black/60 transition-colors"
      >
        <Crown size={14} className="text-[color:var(--fb-yellow)] shrink-0" />
        <span className="text-[10px] font-mono uppercase tracking-widest text-[color:var(--fb-yellow)] shrink-0">
          Yesterday's #1
        </span>
        <img
          src={item.image_url}
          alt=""
          className="w-6 h-6 border border-[color:var(--fb-border)] object-cover shrink-0"
        />
        <span className="text-sm text-white font-alt truncate">{item.title}</span>
        <span className="ml-auto text-[10px] font-mono text-[color:var(--fb-text-2)] shrink-0">
          {money(item.current_bid, { compact: true })}
        </span>
      </Link>
    </div>
  );
}
