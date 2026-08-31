import { useEffect, useMemo, useState } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogTrigger,
} from "./ui/dialog";
import { Twitter, Linkedin, Facebook, MessageCircle, Sparkles, Check, ExternalLink, Copy, Search, X } from "lucide-react";
import { searchCompanies, startShare, verifyShare, fetchShareStatus } from "../lib/api";
import { toast } from "sonner";

const TARGETS = [
  { key: "x",        label: "X (Twitter)", icon: Twitter,       color: "text-white" },
  { key: "linkedin", label: "LinkedIn",    icon: Linkedin,      color: "text-[#0A66C2]" },
  { key: "reddit",   label: "Reddit",      icon: MessageCircle, color: "text-[#FF4500]" },
  { key: "facebook", label: "Facebook",    icon: Facebook,      color: "text-[#1877F2]" },
  { key: "whatsapp", label: "WhatsApp",    icon: MessageCircle, color: "text-[#25D366]" },
];

const TEXT_IN_COMPOSE = new Set(["x", "reddit", "whatsapp"]);

function defaultTemplate(name) {
  return `Check out ${name} in freshboard.lol`;
}

function rankMatch(title, q) {
  const t = (title || "").toLowerCase();
  if (t === q) return 0;
  if (t.startsWith(q)) return 1;
  return 2;
}

function buildComposeUrl(target, listingUrl, text) {
  const u = encodeURIComponent(listingUrl);
  const t = encodeURIComponent(text);
  switch (target) {
    case "x":        return `https://twitter.com/intent/tweet?text=${t}&url=${u}`;
    case "linkedin": return `https://www.linkedin.com/sharing/share-offsite/?url=${u}`;
    case "reddit":   return `https://reddit.com/submit?url=${u}&title=${t}`;
    case "facebook": return `https://www.facebook.com/sharer/sharer.php?u=${u}`;
    case "whatsapp": return `https://api.whatsapp.com/send?text=${t}`;
    default:         return null;
  }
}

function asCompany(listing) {
  if (!listing?.id) return null;
  return {
    id: listing.id,
    title: listing.title,
    image_url: listing.image_url,
    credits: listing.current_bid ?? listing.credits,
  };
}

export default function ShareMenu({ listing, credits, onCredited, children }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState([]);
  const [company, setCompany] = useState(() => asCompany(listing));
  const [picking, setPicking] = useState(false);
  const [hi, setHi] = useState(0);
  const [target, setTarget] = useState(null);
  const [template, setTemplate] = useState(() => defaultTemplate(listing?.title || "this company"));
  const [token, setToken] = useState(null);
  const [postUrl, setPostUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [claiming, setClaiming] = useState(false);
  const [done, setDone] = useState(false);
  const [waitingHit, setWaitingHit] = useState(false);

  const listingUrl = company ? `${window.location.origin}/product/${company.id}` : "";

  useEffect(() => {
    if (!open) return;
    const fallback = asCompany(listing);
    setCompany(fallback);
    setPicking(!fallback);
    setQuery("");
    setTarget(null);
    setTemplate(defaultTemplate(fallback?.title || listing?.title || "this company"));
    setToken(null);
    setPostUrl("");
    setBusy(false);
    setClaiming(false);
    setDone(false);
    setWaitingHit(false);
    setHi(0);
    searchCompanies("").then(d => setMatches(d.items || [])).catch(() => setMatches([]));
  }, [open, listing]);

  useEffect(() => {
    if (!open || !picking) return;
    const t = setTimeout(() => {
      searchCompanies(query.trim()).then(d => setMatches(d.items || [])).catch(() => {});
    }, 180);
    return () => clearTimeout(t);
  }, [query, open, picking]);

  const options = useMemo(() => {
    const seen = new Set();
    const out = [];
    const seed = asCompany(listing);
    const q = query.trim().toLowerCase();
    if (seed && (!q || (seed.title || "").toLowerCase().includes(q))) {
      seen.add(seed.id);
      out.push(seed);
    }
    for (const it of matches) {
      if (!it?.id || seen.has(it.id)) continue;
      seen.add(it.id);
      out.push(it);
    }
    if (q) out.sort((a, b) => rankMatch(a.title, q) - rankMatch(b.title, q));
    return out.slice(0, 8);
  }, [listing, matches, query]);

  useEffect(() => { setHi(0); }, [options]);

  const pickCompany = (c) => {
    if (!c?.id) return;
    setCompany(c);
    setPicking(false);
    setQuery("");
    setTemplate(defaultTemplate(c.title));
    setToken(null);
    setDone(false);
    setWaitingHit(false);
  };

  const startChange = () => {
    setCompany(null);
    setPicking(true);
    setQuery("");
    setTarget(null);
    setToken(null);
    setDone(false);
    setWaitingHit(false);
  };

  const pickTarget = (key) => {
    setTarget(key);
    setToken(null);
    setDone(false);
    setWaitingHit(false);
  };

  const ensureIntent = async () => {
    if (!company || !target) return null;
    if (token) return token;
    const data = await startShare({
      listing_id: company.id,
      target,
      origin: window.location.origin,
    });
    setToken(data.token);
    if (data.template) setTemplate(data.template);
    return data.token;
  };

  const openComposer = async () => {
    if (!company || !target || busy) return;
    setBusy(true);
    try {
      await ensureIntent();
      const text = (template || defaultTemplate(company.title)).trim();
      if (!TEXT_IN_COMPOSE.has(target)) {
        try { await navigator.clipboard.writeText(text); } catch { /* noop */ }
        toast.message("Template copied", { description: "Paste it into the post, then come back with the live link." });
      }
      const url = buildComposeUrl(target, listingUrl, text);
      if (url) window.open(url, "_blank", "noopener,noreferrer,width=640,height=560");
      if (target === "whatsapp") setWaitingHit(true);
    } catch {
      toast.error("Could not start share");
    } finally { setBusy(false); }
  };

  const copyTemplate = async () => {
    try {
      await navigator.clipboard.writeText((template || "").trim());
      toast.success("Copied — paste it into your post.");
    } catch {
      toast.error("Could not copy");
    }
  };

  useEffect(() => {
    if (!waitingHit || !token || done) return;
    const tick = async () => {
      try {
        const s = await fetchShareStatus(token);
        if (s.credited) {
          setDone(true);
          setWaitingHit(false);
          toast.success(`+5 credits for ${company?.title || s.title}`, {
            description: "Someone opened your WhatsApp link. They move up if they now lead.",
          });
          onCredited && onCredited(s.credits, s.listing_id);
        }
      } catch { /* keep polling */ }
    };
    tick();
    const id = setInterval(tick, 3000);
    return () => clearInterval(id);
  }, [waitingHit, token, done, company, onCredited]);

  const claim = async () => {
    if (!company || !target || claiming || target === "whatsapp") return;
    const url = postUrl.trim();
    if (!url) {
      toast.error("Paste the live post URL after you publish.");
      return;
    }
    setClaiming(true);
    try {
      const tok = await ensureIntent();
      const data = await verifyShare({ token: tok, post_url: url });
      if (data.credited) {
        setDone(true);
        toast.success(`+5 credits for ${company.title}`, {
          description: "The post checked out. They move up if they now lead.",
        });
        onCredited && onCredited(data.credits, data.listing_id || company.id);
      } else if (data.reason === "already_shared") {
        toast.info("Already counted on this channel.", { description: "Try another platform for +5 more." });
        setDone(true);
      } else if (data.reason === "post_already_used") {
        toast.info("That post was already used.", { description: "Publish a new one to earn credits." });
      } else {
        toast.error("Could not verify that post");
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not verify that post");
    } finally { setClaiming(false); }
  };

  const onSearchKey = (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHi(i => Math.min(options.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHi(i => Math.max(0, i - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (options[hi]) pickCompany(options[hi]);
      else toast.error("Pick a company from the list. Typed names do not count.");
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {children}
      </DialogTrigger>
      <DialogContent
        data-testid={`share-menu-${listing?.id || "pick"}`}
        className="bg-[color:var(--fb-surface)] border border-[color:var(--fb-border)] text-white w-[calc(100vw-1.5rem)] max-w-md rounded-none max-h-[90vh] overflow-y-auto p-4 sm:p-6"
      >
        <DialogHeader>
          <DialogTitle className="font-display text-xl flex items-center gap-2">
            <Sparkles className="text-[color:var(--fb-cyan)]" size={18} /> Share to climb
          </DialogTitle>
          <DialogDescription className="text-[color:var(--fb-text-2)] font-mono text-xs">
            Select the company from the list — typing alone does not count. Then publish. Only a real share is +5.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 mt-1">
          <div>
            <label className="text-[10px] font-mono uppercase tracking-widest text-[color:var(--fb-text-2)]">
              Sharing on behalf of
            </label>

            {company && !picking ? (
              <div
                data-testid="share-company-selected"
                className="mt-2 flex items-center gap-2 border border-[color:var(--fb-green)] bg-black/40 px-3 py-2"
              >
                {company.image_url && (
                  <img src={company.image_url} alt="" className="w-8 h-8 object-cover border border-[color:var(--fb-border)] shrink-0" />
                )}
                <div className="min-w-0 flex-1">
                  <div className="text-sm text-white truncate flex items-center gap-1.5">
                    <Check size={12} className="text-[color:var(--fb-green)] shrink-0" />
                    {company.title}
                  </div>
                  <div className="text-[10px] font-mono text-[color:var(--fb-muted)]">
                    {Math.round(Number(company.credits ?? credits ?? 0))} cr · selected
                  </div>
                </div>
                <button
                  type="button"
                  data-testid="share-company-change"
                  onClick={startChange}
                  className="fb-btn-ghost text-[10px] px-2 py-1 inline-flex items-center gap-1"
                >
                  <X size={10} /> Change
                </button>
              </div>
            ) : (
              <>
                <div className="relative mt-1">
                  <Search size={12} className="absolute left-3 top-1/2 -translate-y-1/2 text-[color:var(--fb-muted)]" />
                  <input
                    data-testid="share-company-input"
                    className="fb-input pl-8"
                    placeholder="Type a name, then click it"
                    value={query}
                    autoFocus
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={onSearchKey}
                  />
                </div>
                <p className="mt-1 text-[10px] font-mono text-[color:var(--fb-muted)]">
                  Click the matching row. A typed name that is not selected will not boost anyone.
                </p>
                <ul className="mt-2 border border-[color:var(--fb-border)] max-h-44 overflow-y-auto bg-black/40">
                  {options.length === 0 && (
                    <li className="px-3 py-3 text-[11px] font-mono text-[color:var(--fb-muted)]">
                      No company on the board matches. Add them first.
                    </li>
                  )}
                  {options.map((c, i) => (
                    <li key={c.id}>
                      <button
                        type="button"
                        data-testid={`share-company-${c.id}`}
                        onClick={() => pickCompany(c)}
                        className={`w-full flex items-center gap-2 px-3 py-2 text-left ${i === hi ? "bg-[color:var(--fb-pink)]/15" : "hover:bg-black/50"}`}
                      >
                        {c.image_url && (
                          <img src={c.image_url} alt="" className="w-7 h-7 object-cover border border-[color:var(--fb-border)] shrink-0" />
                        )}
                        <span className="flex-1 text-sm text-white truncate">{c.title}</span>
                        <span className="text-[10px] font-mono text-[color:var(--fb-text-2)]">
                          {Math.round(Number(c.credits || 0))}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>

          {company && !picking && (
            <div>
              <div className="text-[10px] font-mono uppercase tracking-widest text-[color:var(--fb-text-2)] mb-2">
                Platform
              </div>
              <div className="grid grid-cols-2 gap-2">
                {TARGETS.map(t => {
                  const Icon = t.icon;
                  const on = target === t.key;
                  return (
                    <button
                      key={t.key}
                      type="button"
                      onClick={() => pickTarget(t.key)}
                      data-testid={`share-${t.key}-${listing?.id || company.id}`}
                      className={`fb-btn-ghost text-[11px] px-3 py-2 inline-flex items-center gap-2 ${on ? "!border-[color:var(--fb-cyan)] !text-[color:var(--fb-cyan)]" : ""}`}
                    >
                      <Icon size={14} className={on ? "text-[color:var(--fb-cyan)]" : t.color} />
                      {t.label}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {company && !picking && target && (
            <>
              <div>
                <label className="text-[10px] font-mono uppercase tracking-widest text-[color:var(--fb-text-2)]">
                  Post text — add your take, keep this line
                </label>
                <textarea
                  data-testid="share-template"
                  className="fb-input mt-1 min-h-[88px] resize-y"
                  value={template}
                  onChange={(e) => setTemplate(e.target.value)}
                />
                <div className="mt-2 flex flex-wrap gap-2">
                  <button
                    type="button"
                    data-testid="share-open"
                    onClick={openComposer}
                    disabled={busy}
                    className="fb-btn-primary text-[11px] px-3 py-2 inline-flex items-center gap-1.5"
                  >
                    <ExternalLink size={12} /> {busy ? "Opening…" : `Open ${TARGETS.find(t => t.key === target)?.label}`}
                  </button>
                  <button
                    type="button"
                    data-testid="share-copy"
                    onClick={copyTemplate}
                    className="fb-btn-ghost text-[11px] px-3 py-2 inline-flex items-center gap-1.5"
                  >
                    <Copy size={12} /> Copy text
                  </button>
                </div>
              </div>

              {target === "whatsapp" ? (
                <div className="border border-[color:var(--fb-border)] p-3 bg-black/30">
                  <p className="text-[11px] font-mono text-[color:var(--fb-text-2)] leading-relaxed">
                    WhatsApp chats are private. Send the message with the unique FreshBoard link. +5 lands when <span className="text-white">someone else</span> opens that link — opening WhatsApp yourself does not count.
                  </p>
                  <div className="mt-3 text-[10px] font-mono uppercase tracking-widest text-[color:var(--fb-muted)]">
                    {done ? "Counted" : waitingHit ? "Waiting for a click on your link…" : "Send, then wait"}
                  </div>
                </div>
              ) : (
                <div>
                  <label className="text-[10px] font-mono uppercase tracking-widest text-[color:var(--fb-text-2)]">
                    Live post URL
                  </label>
                  <input
                    data-testid="share-post-url"
                    className="fb-input mt-1"
                    placeholder="https://x.com/you/status/…"
                    value={postUrl}
                    onChange={(e) => setPostUrl(e.target.value)}
                  />
                  <p className="mt-1 text-[10px] font-mono text-[color:var(--fb-muted)] leading-relaxed">
                    We fetch the public post. It must mention {company.title} and freshboard.lol. Compose windows do not count.
                  </p>
                  <button
                    type="button"
                    data-testid="share-claim"
                    onClick={claim}
                    disabled={claiming || done}
                    className="fb-btn-primary w-full mt-3 inline-flex items-center justify-center gap-2"
                  >
                    {done ? <><Check size={14} /> Counted</> : claiming ? "Checking post…" : "Claim +5"}
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
