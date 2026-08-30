import { useState, useEffect, useRef } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "./ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "./ui/select";
import { Rocket, Sparkles, Loader2, PartyPopper } from "lucide-react";
import { submitListing, fetchConfig, previewUrl } from "../lib/api";
import { toast } from "sonner";
import ShareMenu from "./ShareMenu";
import { useNavigate } from "react-router-dom";

const DEFAULT_IMG = "https://images.unsplash.com/photo-1650800543888-9ef964fc33d2?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2ODh8MHwxfHNlYXJjaHw0fHwzZCUyMGdlb21ldHJ5JTIwbWluaW1hbHxlbnwwfHx8YmxhY2t8MTc4ODExNzI3NXww&ixlib=rb-4.1.0&q=85";

export default function SubmissionModal({ open, onClose, defaultType = "product" }) {
  const [config, setConfig] = useState({ categories: [], credits_per_share: 5, welcome_credits: 5 });
  const [listingType, setListingType] = useState(defaultType);
  const [form, setForm] = useState({
    title: "", tagline: "", description: "", url: "", image_url: "",
    category: "", platform: "x",
  });
  const [busy, setBusy] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [submitted, setSubmitted] = useState(null); // { id, credits, title, url, image_url, listing_type }
  const previewedRef = useRef("");
  const debounceRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    fetchConfig().then(setConfig).catch(() => {});
  }, []);

  useEffect(() => {
    if (!open) return;
    setListingType(defaultType);
    setForm({ title: "", tagline: "", description: "", url: "", image_url: "", category: config.categories?.[0] || "", platform: "x" });
    setSubmitted(null);
    previewedRef.current = "";
  }, [open, defaultType, config]);

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
    } catch { /* silent */ }
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
      const payload = {
        listing_type: listingType,
        title: form.title,
        tagline: form.tagline,
        description: form.description,
        url: form.url,
        image_url: form.image_url || DEFAULT_IMG,
      };
      if (listingType === "product") payload.category = form.category || config.categories[0];
      else payload.platform = form.platform;

      const res = await submitListing(payload);
      setSubmitted({
        id: res.listing_id,
        credits: res.credits,
        title: form.title,
        url: form.url,
        image_url: form.image_url || DEFAULT_IMG,
        listing_type: listingType,
      });
      toast.success("You're on the board.", { description: `Start with ${res.credits} credits — share to climb.` });
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Something went wrong");
    } finally { setBusy(false); }
  };

  const done = submitted;

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent
        data-testid="submission-modal"
        className="bg-[color:var(--fb-surface)] border border-[color:var(--fb-border)] text-white w-[calc(100vw-1.5rem)] max-w-lg rounded-none max-h-[90vh] overflow-y-auto p-4 sm:p-6"
      >
        {!done && (
          <>
            <DialogHeader>
              <DialogTitle className="font-display text-2xl">
                <span className="flex items-center gap-2"><Rocket className="text-[color:var(--fb-pink)]" /> Get on the board</span>
              </DialogTitle>
              <DialogDescription className="text-[color:var(--fb-text-2)] font-mono text-xs">
                Free to list. You start with {config.welcome_credits} credits and earn +{config.credits_per_share} for every share. Highest credits = #1.
              </DialogDescription>
            </DialogHeader>

            <form onSubmit={onSubmit} className="space-y-4 mt-2">
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

              <div>
                <label className="text-xs font-mono uppercase tracking-widest text-[color:var(--fb-text-2)] flex items-center gap-2">
                  URL (your link)
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

              <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-[color:var(--fb-border)]">
                <div>
                  <div className="text-[10px] font-mono uppercase tracking-widest text-[color:var(--fb-text-2)]">Starting credits</div>
                  <div data-testid="starting-credits" className="font-display text-2xl text-[color:var(--fb-green)]">
                    {config.welcome_credits}
                  </div>
                </div>
                <button data-testid="submit-listing" type="submit" disabled={busy} className="fb-btn-primary">
                  {busy ? "Adding…" : "Add to board"}
                </button>
              </div>
            </form>
          </>
        )}

        {done && (
          <div className="text-center py-2" data-testid="submitted-view">
            <PartyPopper size={40} className="mx-auto text-[color:var(--fb-yellow)]" />
            <h2 className="font-display text-3xl font-black text-white mt-3">You're on the board.</h2>
            <p className="font-mono text-sm text-[color:var(--fb-text-2)] mt-2">
              Starting credits: <span className="text-[color:var(--fb-green)]">{done.credits}</span>. Each share adds +{config.credits_per_share} — pick a channel below.
            </p>

            <div className="mt-6 flex justify-center">
              <ShareMenu
                listing={{ id: done.id, title: done.title, url: done.url }}
                credits={done.credits}
                onCredited={(c) => setSubmitted(s => ({ ...s, credits: c }))}
              >
                <button data-testid="share-cta" className="fb-btn-primary inline-flex items-center gap-2">
                  <Sparkles size={14} /> Share to earn credits
                </button>
              </ShareMenu>
            </div>

            <div className="mt-6 flex justify-center gap-2">
              <button
                onClick={() => { onClose(); navigate(`/product/${done.id}`); }}
                className="fb-btn-ghost text-xs"
              >
                View listing
              </button>
              <button
                onClick={() => onClose()}
                className="fb-btn-ghost text-xs"
                data-testid="close-modal"
              >
                Back to board
              </button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
