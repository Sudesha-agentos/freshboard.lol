import { useState } from "react";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";
import { Twitter, Linkedin, Facebook, MessageCircle, Link2, Sparkles, Check } from "lucide-react";
import { api } from "../lib/api";
import { toast } from "sonner";

const TARGETS = [
  { key: "x",         label: "X (Twitter)", icon: Twitter,       color: "text-white" },
  { key: "linkedin",  label: "LinkedIn",    icon: Linkedin,      color: "text-[#0A66C2]" },
  { key: "reddit",    label: "Reddit",      icon: MessageCircle, color: "text-[#FF4500]" },
  { key: "facebook",  label: "Facebook",    icon: Facebook,      color: "text-[#1877F2]" },
  { key: "whatsapp",  label: "WhatsApp",    icon: MessageCircle, color: "text-[#25D366]" },
  { key: "copy",      label: "Copy link",   icon: Link2,         color: "text-[color:var(--fb-cyan)]" },
];

function buildShareUrl(target, listingUrl, title) {
  const u = encodeURIComponent(listingUrl);
  const t = encodeURIComponent(`${title} — vote on FreshBoard.lol`);
  switch (target) {
    case "x":         return `https://twitter.com/intent/tweet?url=${u}&text=${t}`;
    case "linkedin":  return `https://www.linkedin.com/sharing/share-offsite/?url=${u}`;
    case "reddit":    return `https://reddit.com/submit?url=${u}&title=${t}`;
    case "facebook":  return `https://www.facebook.com/sharer/sharer.php?u=${u}`;
    case "whatsapp":  return `https://api.whatsapp.com/send?text=${t}%20${u}`;
    default:          return null;
  }
}

export default function ShareMenu({ listing, credits, onCredited, children, side = "bottom", align = "end" }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(null);
  const [awarded, setAwarded] = useState({});

  const shareUrl = `${window.location.origin}/product/${listing.id}`;

  const handleShare = async (target) => {
    if (busy) return;
    setBusy(target);

    if (target === "copy") {
      try { await navigator.clipboard.writeText(shareUrl); } catch { /* noop */ }
    } else {
      const url = buildShareUrl(target, shareUrl, listing.title);
      if (url) window.open(url, "_blank", "noopener,noreferrer,width=640,height=560");
    }

    try {
      const { data } = await api.post(`/listings/${listing.id}/share`, { target });
      if (data.credited) {
        setAwarded(a => ({ ...a, [target]: true }));
        toast.success(`+${(data.credits - (credits || 0)) || 5} credits`, {
          description: target === "copy" ? "Link copied — credits added." : "Thanks for sharing.",
        });
        onCredited && onCredited(data.credits);
      } else {
        toast.info("Already shared on this channel.", { description: "Try another channel for more credits." });
        setAwarded(a => ({ ...a, [target]: true }));
      }
    } catch (e) {
      toast.error("Could not record share");
    } finally { setBusy(null); }
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        {children}
      </PopoverTrigger>
      <PopoverContent
        side={side}
        align={align}
        data-testid={`share-menu-${listing.id}`}
        className="bg-[color:var(--fb-surface)] border border-[color:var(--fb-border)] text-white p-0 rounded-none w-64"
      >
        <div className="px-3 py-2 border-b border-[color:var(--fb-border)] flex items-center gap-2">
          <Sparkles size={12} className="text-[color:var(--fb-cyan)]" />
          <span className="text-[10px] font-mono uppercase tracking-widest text-[color:var(--fb-text-2)]">
            +5 credits per channel
          </span>
        </div>
        <ul>
          {TARGETS.map(t => {
            const Icon = t.icon;
            const done = awarded[t.key];
            return (
              <li key={t.key}>
                <button
                  onClick={() => handleShare(t.key)}
                  disabled={busy === t.key}
                  data-testid={`share-${t.key}-${listing.id}`}
                  className="w-full flex items-center gap-3 px-3 py-2.5 text-left text-sm hover:bg-black/40 transition-colors disabled:opacity-50"
                >
                  <Icon size={14} className={t.color} />
                  <span className="flex-1">{t.label}</span>
                  {done ? (
                    <Check size={12} className="text-[color:var(--fb-green)]" />
                  ) : (
                    <span className="text-[10px] font-mono text-[color:var(--fb-green)]">+5</span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
