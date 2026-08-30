import { useEffect, useState, useCallback } from "react";
import { fetchBoard, fetchConfig } from "../lib/api";
import Countdown from "../components/Countdown";
import Marquee from "../components/Marquee";
import ListingCard from "../components/ListingCard";
import SubmissionModal from "../components/SubmissionModal";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import { Rocket, Radio, Flame, Plus } from "lucide-react";

export default function Board() {
  const [tab, setTab] = useState("product");
  const [board, setBoard] = useState({ products: [], socials: [] });
  const [config, setConfig] = useState({ categories: [] });
  const [category, setCategory] = useState("All");
  const [modal, setModal] = useState({ open: false, mode: "submit", target: null, defaultType: "product" });

  const load = useCallback(async () => {
    try {
      const data = await fetchBoard(category === "All" ? null : category);
      setBoard(data);
    } catch { /* ignore */ }
  }, [category]);

  useEffect(() => {
    fetchConfig().then(setConfig).catch(() => {});
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 8000);
    return () => clearInterval(t);
  }, [load]);

  const openSubmit = (type) => setModal({ open: true, mode: "submit", target: null, defaultType: type });
  const openOutbid = (item) => setModal({ open: true, mode: "outbid", target: item, defaultType: item.listing_type });
  const closeModal = () => setModal(m => ({ ...m, open: false }));

  return (
    <div className="min-h-screen">
      {/* Sticky Header */}
      <header className="sticky top-0 z-40 bg-black/85 backdrop-blur border-b border-[color:var(--fb-border)]">
        <div className="max-w-7xl mx-auto flex items-center justify-between px-4 md:px-8 py-4">
          <a href="/" className="flex items-center gap-2" data-testid="logo-home">
            <span className="w-3 h-3 bg-[color:var(--fb-pink)]"></span>
            <span className="font-display font-black text-xl tracking-tight text-white">
              FRESHBOARD<span className="text-[color:var(--fb-pink)]">.LOL</span>
            </span>
          </a>
          <div className="hidden md:flex items-center gap-6">
            <Countdown variant="compact" />
            <button data-testid="header-submit-btn" onClick={() => openSubmit(tab)} className="fb-btn-primary text-xs inline-flex items-center gap-2">
              <Plus size={14} /> Buy a Rank
            </button>
          </div>
        </div>
      </header>

      <Marquee />

      {/* Hero */}
      <section className="max-w-7xl mx-auto px-4 md:px-8 pt-10 md:pt-16 pb-8">
        <div className="grid md:grid-cols-2 gap-8 items-end">
          <div>
            <div className="inline-flex items-center gap-2 border border-[color:var(--fb-border)] px-3 py-1 text-[10px] font-mono uppercase tracking-widest text-[color:var(--fb-cyan)] mb-6">
              <Flame size={12} /> Rank is bought, not voted.
            </div>
            <h1 className="font-display text-5xl md:text-7xl font-black text-white leading-[0.9] tracking-tighter">
              Pay a dollar. <br/>
              <span className="text-[color:var(--fb-pink)]">Take #1</span>. <br/>
              Get outbid.
            </h1>
            <p className="font-mono text-[color:var(--fb-text-2)] mt-6 max-w-md text-sm md:text-base">
              A Product Hunt–style board where dollars decide the order. Board wipes clean every night at midnight IST.
              No accounts, no votes, no drama — just bids.
            </p>
            <div className="flex flex-wrap gap-3 mt-8">
              <button data-testid="hero-submit-product" onClick={() => openSubmit("product")} className="fb-btn-primary inline-flex items-center gap-2">
                <Rocket size={16} /> Launch a Product
              </button>
              <button data-testid="hero-submit-social" onClick={() => openSubmit("social")} className="fb-btn-ghost inline-flex items-center gap-2">
                <Radio size={16} /> Promote a Post
              </button>
            </div>
          </div>
          <div className="md:justify-self-end">
            <Countdown variant="hero" />
            <div className="mt-4 flex gap-2 flex-wrap">
              <Stat label="Min bid" value={`$${config.min_bid ?? 1}`} />
              <Stat label="Boost" value={`$${config.boost_price ?? 10}`} accent="cyan" />
              <Stat label="Live listings" value={(board.products.length + board.socials.length).toString()} accent="green" />
            </div>
          </div>
        </div>
      </section>

      {/* Board Tabs */}
      <section className="max-w-7xl mx-auto px-4 md:px-8 pb-16">
        <Tabs value={tab} onValueChange={setTab} className="w-full">
          <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
            <TabsList data-testid="section-tabs" className="bg-[color:var(--fb-surface)] border border-[color:var(--fb-border)] p-1 h-auto rounded-none">
              <TabsTrigger
                value="product"
                data-testid="tab-products"
                className="rounded-none font-mono text-xs uppercase tracking-widest px-6 py-3 data-[state=active]:bg-[color:var(--fb-pink)] data-[state=active]:text-black"
              >
                Products · {board.products.length}
              </TabsTrigger>
              <TabsTrigger
                value="social"
                data-testid="tab-socials"
                className="rounded-none font-mono text-xs uppercase tracking-widest px-6 py-3 data-[state=active]:bg-[color:var(--fb-cyan)] data-[state=active]:text-black"
              >
                Social Promotions · {board.socials.length}
              </TabsTrigger>
            </TabsList>

            {tab === "product" && (
              <div className="flex items-center gap-2 flex-wrap max-w-full overflow-x-auto">
                {["All", ...config.categories].map(c => (
                  <button
                    key={c}
                    data-testid={`cat-${c}`}
                    onClick={() => setCategory(c)}
                    className={`text-[10px] font-mono uppercase tracking-widest px-3 py-1.5 border transition-colors ${category === c ? "border-[color:var(--fb-pink)] text-[color:var(--fb-pink)]" : "border-[color:var(--fb-border)] text-[color:var(--fb-text-2)] hover:text-white"}`}
                  >
                    {c}
                  </button>
                ))}
              </div>
            )}
          </div>

          <TabsContent value="product" className="mt-0">
            <ListGrid items={board.products} onOutbid={openOutbid} emptyType="product" onSubmit={() => openSubmit("product")} />
          </TabsContent>
          <TabsContent value="social" className="mt-0">
            <ListGrid items={board.socials} onOutbid={openOutbid} emptyType="social" onSubmit={() => openSubmit("social")} />
          </TabsContent>
        </Tabs>
      </section>

      <footer className="border-t border-[color:var(--fb-border)] py-8 px-4 md:px-8">
        <div className="max-w-7xl mx-auto flex flex-wrap justify-between items-center gap-4 font-mono text-xs text-[color:var(--fb-muted)]">
          <span>© FRESHBOARD.LOL — RESET MIDNIGHT IST</span>
          <span>MADE WITH SPITE + STRIPE</span>
        </div>
      </footer>

      <SubmissionModal
        open={modal.open}
        onClose={closeModal}
        mode={modal.mode}
        target={modal.target}
        defaultType={modal.defaultType}
      />
    </div>
  );
}

function Stat({ label, value, accent }) {
  const colors = { cyan: "var(--fb-cyan)", green: "var(--fb-green)", yellow: "var(--fb-yellow)" };
  const c = colors[accent] || "var(--fb-text)";
  return (
    <div className="border border-[color:var(--fb-border)] px-3 py-2 bg-black/40 min-w-[92px]">
      <div className="text-[9px] font-mono uppercase tracking-widest text-[color:var(--fb-text-2)]">{label}</div>
      <div className="font-display text-xl font-bold" style={{ color: c }}>{value}</div>
    </div>
  );
}

function ListGrid({ items, onOutbid, emptyType, onSubmit }) {
  if (!items.length) {
    return (
      <div data-testid={`empty-${emptyType}`} className="border border-dashed border-[color:var(--fb-border)] p-12 text-center">
        <div className="font-display text-3xl md:text-4xl font-black text-white mb-2">
          BOARD IS EMPTY.
        </div>
        <p className="font-mono text-sm text-[color:var(--fb-text-2)] max-w-md mx-auto">
          First bid takes #1. Minimum $1. Board resets every night at midnight IST — so today's #1 buys nothing tomorrow.
        </p>
        <button onClick={onSubmit} className="fb-btn-primary mt-6 inline-flex items-center gap-2">
          <Rocket size={16} /> Take #1 now
        </button>
      </div>
    );
  }
  return (
    <div className="space-y-3">
      {items.map(it => (
        <ListingCard key={it.id} item={it} onOutbid={onOutbid} />
      ))}
    </div>
  );
}
