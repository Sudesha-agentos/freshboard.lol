import { useState, useEffect, useRef } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "./ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "./ui/select";
import { Zap, Rocket, TrendingUp, Sparkles, Loader2 } from "lucide-react";
import { submitListing, outbidListing, fetchConfig, previewUrl } from "../lib/api";
import { toast } from "sonner";

const PLACEHOLDER_IMG = "https://images.unsplash.com/photo-1650800543888-9ef964fc33d2?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2ODh8MHwxfHNlYXJjaHw0fHwzZCUyMGdlb21ldHJ5JTIwbWluaW1hbHxlbnwwfHx8YmxhY2t8MTc4ODExNzI3NXww&ixlib=rb-4.1.0&q=85";

export default function SubmissionModal({ open, onClose, mode, target, defaultType = "product" }) {
  const [config, setConfig] = useState({ categories: [], min_bid: 1, boost_price: 10, boost_reach: 5 });
  const [listingType, setListingType] = useState(defaultType);
  const [form, setForm] = useState({
    title: "", tagline: "", description: "", url: "", image_url: "",
    category: "", platform: "x",
  });
  const [bid, setBid] = useState("1");
  const [boost, setBoost] = useState(false);
  const [busy, setBusy] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const previewedRef = useRef("");
  const debounceRef = useRef(null);

  useEffect(() => {
    fetchConfig().then(setConfig).catch(() => {});
  }, []);

  useEffect(() => {
    if (mode === "outbid" && target) {
      const min = (Number(target.current_bid) + 1).toFixed(2);
      setBid(min);
    } else {
      setBid(String(config.min_bid || 1));
      setListingType(defaultType);
      setForm({ title: "", tagline: "", description: "", url: "", image_url: "", category: config.categories?.[0] || "", platform: "x" });
      setBoost(false);
      previewedRef.current = "";
    }
  }, [mode, target, open, config, defaultType]);

  const runPreview = async (url) => {
    const clean = (url || "").trim();
    if (!/^https?:\/\/[^\s]+$/i.test(clean)) return;
    if (previewedRef.current === clean) return;
    previewedRef.current = clean;
    setPreviewing(true);
    try {
      const data = await previewUrl(clean);
      setForm(f => ({
        ...f,
        title: f.title || data.title || "",
        tagline: f.tagline || data.tagline || "",
        image_url: f.image_url || data.image_url || "",
      }));
    } catch { /* silent — user can fill manually */ }
    finally { setPreviewing(false); }
  };

  const onUrlChange = (e) => {
    const v = e.target.value;
    setForm(f => ({ ...f, url: v }));
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => runPreview(v), 600);
  };

  const update = (k) => (e) => setForm(f => ({ ...f, [k]: e.target?.value ?? e }));

  const onSubmit = async (e) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    try {
      let res;
      const origin_url = window.location.origin;
      if (mode === "outbid") {
        res = await outbidListing({
          listing_id: target.id,
          bid_amount: Number(bid),
          add_boost: boost,
          origin_url,
        });
      } else {
        const payload = {
          listing_type: listingType,
          title: form.title,
          tagline: form.tagline,
          description: form.description,
          url: form.url,
          image_url: form.image_url || PLACEHOLDER_IMG,
          bid_amount: Number(bid),
          add_boost: boost,
          origin_url,
        };
        if (listingType === "product") payload.category = form.category || config.categories[0];
        else payload.platform = form.platform;
        res = await submitListing(payload);
      }
      if (res.checkout_url) {
        window.location.href = res.checkout_url;
      } else {
        toast.error("Checkout failed");
      }
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Something went wrong");
      setBusy(false);
    }
  };

  const total = Number(bid || 0) + (boost ? config.boost_price : 0);
  const minBid = mode === "outbid" && target ? Number(target.current_bid) + 0.01 : config.min_bid;
  const isOutbid = mode === "outbid";

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent
        data-testid="submission-modal"
        className="bg-[color:var(--fb-surface)] border border-[color:var(--fb-border)] text-white max-w-lg rounded-none"
      >
        <DialogHeader>
          <DialogTitle className="font-display text-2xl">
            {isOutbid ? (
              <span className="flex items-center gap-2"><TrendingUp className="text-[color:var(--fb-pink)]" /> Outbid #{target?.rank}</span>
            ) : (
              <span className="flex items-center gap-2"><Rocket className="text-[color:var(--fb-pink)]" /> Claim your spot</span>
            )}
          </DialogTitle>
          <DialogDescription className="text-[color:var(--fb-text-2)] font-mono text-xs">
            {isOutbid
              ? `Bid higher than $${Number(target?.current_bid || 0).toFixed(2)} to take rank #${target?.rank}. Previous holder drops one spot.`
              : "Pay to rank. Highest bid = #1. Board resets midnight IST."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={onSubmit} className="space-y-4 mt-2">
          {!isOutbid && (
            <div className="grid grid-cols-2 gap-2">
              {["product", "social"].map(t => (
                <button
                  key={t}
                  type="button"
                  data-testid={`type-${t}`}
                  onClick={() => setListingType(t)}
                  className={`fb-btn-ghost text-xs ${listingType === t ? "!border-[color:var(--fb-pink)] !text-[color:var(--fb-pink)]" : ""}`}
                >
                  {t === "product" ? "Product" : "Social Post"}
                </button>
              ))}
            </div>
          )}

          {!isOutbid && (
            <>
              <div>
                <label className="text-xs font-mono uppercase tracking-widest text-[color:var(--fb-text-2)] flex items-center gap-2">
                  URL (external link)
                  {previewing && (
                    <span className="inline-flex items-center gap-1 text-[color:var(--fb-cyan)] normal-case tracking-normal">
                      <Loader2 size={10} className="animate-spin" /> fetching…
                    </span>
                  )}
                </label>
                <input
                  data-testid="input-url"
                  className="fb-input mt-1"
                  value={form.url}
                  onChange={onUrlChange}
                  onBlur={() => runPreview(form.url)}
                  placeholder="https://your-product.com"
                  required
                />
                <p className="mt-1 text-[10px] font-mono text-[color:var(--fb-muted)] flex items-center gap-1">
                  <Sparkles size={10} className="text-[color:var(--fb-cyan)]" />
                  paste your link — we'll auto-fill title, tagline, and thumbnail
                </p>
              </div>

              {form.image_url && (
                <div className="flex items-center gap-3 p-2 border border-[color:var(--fb-border)] bg-black/40" data-testid="preview-card">
                  <img
                    src={form.image_url}
                    alt=""
                    onError={(e) => { e.currentTarget.style.display = "none"; }}
                    className="w-12 h-12 object-cover border border-[color:var(--fb-border)] shrink-0"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="text-xs text-white truncate">{form.title || "—"}</div>
                    <div className="text-[10px] font-mono text-[color:var(--fb-text-2)] truncate">{form.tagline || "no tagline"}</div>
                  </div>
                </div>
              )}

              <div>
                <label className="text-xs font-mono uppercase tracking-widest text-[color:var(--fb-text-2)]">Title</label>
                <input data-testid="input-title" className="fb-input mt-1" value={form.title} onChange={update("title")} required maxLength={100} />
              </div>
              <div>
                <label className="text-xs font-mono uppercase tracking-widest text-[color:var(--fb-text-2)]">Tagline</label>
                <input data-testid="input-tagline" className="fb-input mt-1" value={form.tagline} onChange={update("tagline")} required maxLength={140} />
              </div>
              <div>
                <label className="text-xs font-mono uppercase tracking-widest text-[color:var(--fb-text-2)]">Thumbnail image URL <span className="opacity-60">(optional)</span></label>
                <input data-testid="input-image" className="fb-input mt-1" value={form.image_url} onChange={update("image_url")} placeholder="https://..." />
              </div>

              {listingType === "product" && (
                <div>
                  <label className="text-xs font-mono uppercase tracking-widest text-[color:var(--fb-text-2)]">Category</label>
                  <Select value={form.category || config.categories[0]} onValueChange={(v) => setForm(f => ({ ...f, category: v }))}>
                    <SelectTrigger data-testid="input-category" className="fb-input mt-1 rounded-none">
                      <SelectValue placeholder="Pick a category" />
                    </SelectTrigger>
                    <SelectContent className="bg-[color:var(--fb-surface-2)] border-[color:var(--fb-border)] text-white rounded-none">
                      {config.categories.map(c => (
                        <SelectItem key={c} value={c} className="font-mono">{c}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {listingType === "social" && (
                <div>
                  <label className="text-xs font-mono uppercase tracking-widest text-[color:var(--fb-text-2)]">Platform</label>
                  <Select value={form.platform} onValueChange={(v) => setForm(f => ({ ...f, platform: v }))}>
                    <SelectTrigger data-testid="input-platform" className="fb-input mt-1 rounded-none">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-[color:var(--fb-surface-2)] border-[color:var(--fb-border)] text-white rounded-none">
                      <SelectItem value="x" className="font-mono">X (Twitter)</SelectItem>
                      <SelectItem value="instagram" className="font-mono">Instagram</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}
            </>
          )}

          <div>
            <label className="text-xs font-mono uppercase tracking-widest text-[color:var(--fb-text-2)]">
              {isOutbid ? `Your bid (min $${minBid.toFixed(2)})` : `Bid amount (min $${config.min_bid})`}
            </label>
            <div className="flex items-center gap-2 mt-1">
              <span className="font-display text-2xl text-[color:var(--fb-green)]">$</span>
              <input
                data-testid="input-bid"
                type="number"
                step="0.01"
                min={minBid}
                className="fb-input"
                value={bid}
                onChange={(e) => setBid(e.target.value)}
                required
              />
            </div>
          </div>

          <label className="flex items-start gap-3 p-3 border border-[color:var(--fb-border)] bg-black/40 cursor-pointer">
            <input
              data-testid="input-boost"
              type="checkbox"
              checked={boost}
              onChange={(e) => setBoost(e.target.checked)}
              className="mt-1 accent-[color:var(--fb-cyan)]"
            />
            <div>
              <div className="flex items-center gap-2 text-white text-sm">
                <Zap size={14} className="text-[color:var(--fb-cyan)]" /> Add Share Boost — ${config.boost_price}
              </div>
              <p className="text-xs text-[color:var(--fb-text-2)] mt-1">Push your listing to {config.boost_reach} extra channels.</p>
            </div>
          </label>

          <div className="flex items-center justify-between pt-2 border-t border-[color:var(--fb-border)]">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-widest text-[color:var(--fb-text-2)]">Total</div>
              <div data-testid="total-amount" className="font-display text-3xl text-white">${total.toFixed(2)}</div>
            </div>
            <button data-testid="submit-checkout" type="submit" disabled={busy} className="fb-btn-primary">
              {busy ? "Redirecting..." : (isOutbid ? "Pay to Outbid" : "Pay & List")}
            </button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
