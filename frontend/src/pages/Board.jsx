import { useEffect, useState, useCallback } from "react";
import { fetchBoard, fetchConfig } from "../lib/api";
import Countdown from "../components/Countdown";
import Marquee from "../components/Marquee";
import ListingCard from "../components/ListingCard";
import SubmissionModal from "../components/SubmissionModal";
import ActivityFeed from "../components/ActivityFeed";
import ProductHero from "../components/ProductHero";
import StatsBar from "../components/StatsBar";
import WinnersRibbon from "../components/WinnersRibbon";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import { Rocket, Plus, RefreshCw } from "lucide-react";

export default function Board() {
  const [tab, setTab] = useState("product");
  const [board, setBoard] = useState({ products: [], socials: [] });
  const [config, setConfig] = useState({ categories: [] });
  const [category, setCategory] = useState("All");
  const [modal, setModal] = useState({ open: false, mode: "submit", target: null, defaultType: "product" });
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (spin = false) => {
    if (spin) setRefreshing(true);
    try {
      const data = await fetchBoard(category === "All" ? null : category);
      setBoard(data);
    } catch { /* ignore */ }
    finally { if (spin) setTimeout(() => setRefreshing(false), 400); }
  }, [category]);

  useEffect(() => {
    fetchConfig().then(setConfig).catch(() => {});
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(() => load(false), 8000);
    return () => clearInterval(t);
  }, [load]);

  const openSubmit = (type) => setModal({ open: true, mode: "submit", target: null, defaultType: type });
  const openOutbid = (item) => setModal({ open: true, mode: "outbid", target: item, defaultType: item.listing_type });
  const closeModal = () => setModal(m => ({ ...m, open: false }));

  const claimTop = (top) => {
    if (top) return openOutbid(top);
    openSubmit("product");
  };

  return (
    <div className="min-h-screen">
      {/* Sticky Header */}
      <header className="sticky top-0 z-40 bg-black/85 backdrop-blur border-b border-[color:var(--fb-border)]">
        <div className="max-w-7xl mx-auto flex items-center justify-between px-4 md:px-8 py-3 md:py-4 gap-3">
          <a href="/" className="flex items-center gap-2 min-w-0" data-testid="logo-home">
            <span className="w-2.5 h-2.5 sm:w-3 sm:h-3 bg-[color:var(--fb-pink)] shrink-0"></span>
            <span className="font-display font-black text-base sm:text-xl tracking-tight text-white truncate">
              FRESHBOARD<span className="text-[color:var(--fb-pink)]">.LOL</span>
            </span>
          </a>
          <div className="flex items-center gap-3 sm:gap-6">
            <span className="hidden sm:block"><Countdown variant="compact" /></span>
            <button data-testid="header-submit-btn" onClick={() => openSubmit(tab)} className="fb-btn-primary text-[11px] sm:text-xs px-3 sm:px-4 py-2 sm:py-3 inline-flex items-center gap-1.5 sm:gap-2 whitespace-nowrap">
              <Plus size={14} /> <span className="hidden xs:inline">Buy a </span>Rank
            </button>
          </div>
        </div>
        <div className="sm:hidden bg-black px-4 pb-3 border-t border-[color:var(--fb-border)] pt-2">
          <Countdown variant="compact" />
        </div>
      </header>

      <Marquee />

      {/* Product-forward hero (centered, short) */}
      <section className="max-w-7xl mx-auto px-4 md:px-8 pt-6 md:pt-10">
        <WinnersRibbon />
        <ProductHero onClaim={claimTop} onLaunch={() => openSubmit("product")} />
      </section>

      {/* Board Tabs + Activity Sidebar */}
      <section className="max-w-7xl mx-auto px-4 md:px-8 pb-12 md:pb-16">
        <div className="grid lg:grid-cols-[1fr,320px] gap-6 lg:gap-8">
          <div className="min-w-0">
            <Tabs value={tab} onValueChange={setTab} className="w-full">
              <div className="flex flex-wrap items-center justify-between gap-3 mb-4 md:mb-6">
                <TabsList data-testid="section-tabs" className="bg-[color:var(--fb-surface)] border border-[color:var(--fb-border)] p-1 h-auto rounded-none w-full sm:w-auto">
                  <TabsTrigger
                    value="product"
                    data-testid="tab-products"
                    className="flex-1 sm:flex-none rounded-none font-mono text-[10px] sm:text-xs uppercase tracking-widest px-3 sm:px-6 py-2 sm:py-3 data-[state=active]:bg-[color:var(--fb-pink)] data-[state=active]:text-black"
                  >
                    Products · {board.products.length}
                  </TabsTrigger>
                  <TabsTrigger
                    value="social"
                    data-testid="tab-socials"
                    className="flex-1 sm:flex-none rounded-none font-mono text-[10px] sm:text-xs uppercase tracking-widest px-3 sm:px-6 py-2 sm:py-3 data-[state=active]:bg-[color:var(--fb-cyan)] data-[state=active]:text-black"
                  >
                    Socials · {board.socials.length}
                  </TabsTrigger>
                </TabsList>
                <button
                  onClick={() => load(true)}
                  data-testid="refresh-btn"
                  className="fb-btn-ghost text-[10px] sm:text-xs inline-flex items-center gap-1.5 px-3 py-2"
                  aria-label="Refresh"
                >
                  <RefreshCw size={12} className={refreshing ? "animate-spin" : ""} />
                  <span className="hidden sm:inline">Refresh</span>
                </button>
              </div>

              {tab === "product" && (
                <div className="mb-4 md:mb-6 -mx-4 px-4 md:mx-0 md:px-0 overflow-x-auto scrollbar-none">
                  <div className="flex items-center gap-2 min-w-max pb-2">
                    {["All", ...config.categories].map(c => (
                      <button
                        key={c}
                        data-testid={`cat-${c}`}
                        onClick={() => setCategory(c)}
                        className={`text-[10px] font-mono uppercase tracking-widest px-3 py-1.5 border whitespace-nowrap transition-colors ${category === c ? "border-[color:var(--fb-pink)] text-[color:var(--fb-pink)]" : "border-[color:var(--fb-border)] text-[color:var(--fb-text-2)] hover:text-white"}`}
                      >
                        {c}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <TabsContent value="product" className="mt-0">
                <ListGrid items={board.products} onOutbid={openOutbid} emptyType="product" onSubmit={() => openSubmit("product")} />
              </TabsContent>
              <TabsContent value="social" className="mt-0">
                <ListGrid items={board.socials} onOutbid={openOutbid} emptyType="social" onSubmit={() => openSubmit("social")} />
              </TabsContent>
            </Tabs>
          </div>

          <div className="space-y-4 md:space-y-6">
            <ActivityFeed />
          </div>
        </div>

        <div className="mt-10 md:mt-16">
          <StatsBar />
        </div>
      </section>

      <footer className="border-t border-[color:var(--fb-border)] py-6 md:py-8 px-4 md:px-8">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 sm:gap-4 font-mono text-[10px] sm:text-xs text-[color:var(--fb-muted)]">
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

function ListGrid({ items, onOutbid, emptyType, onSubmit }) {
  if (!items.length) {
    return (
      <div data-testid={`empty-${emptyType}`} className="border border-dashed border-[color:var(--fb-border)] p-8 md:p-12 text-center">
        <div className="font-display text-2xl sm:text-3xl md:text-4xl font-black text-white mb-2">
          BOARD IS EMPTY.
        </div>
        <p className="font-mono text-xs sm:text-sm text-[color:var(--fb-text-2)] max-w-md mx-auto">
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
