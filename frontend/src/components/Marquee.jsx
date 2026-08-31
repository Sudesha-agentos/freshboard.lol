export default function Marquee({ items }) {
  const list = items && items.length ? items : [
    "PUBLISH YOUR APP HERE",
    "GET TOP VISIBILITY",
    "FREE TO LIST — SHARE TO CLIMB",
    "HIGHEST CREDITS STAY ON TOP",
    "+5 CREDITS PER VERIFIED SHARE",
    "BOARD RESETS MIDNIGHT IST",
    "FRESHBOARD.LOL",
  ];
  const loop = [...list, ...list];
  return (
    <div className="border-y border-[color:var(--fb-border)] bg-black overflow-hidden py-3">
      <div className="fb-marquee whitespace-nowrap font-mono text-sm">
        {loop.map((t, i) => (
          <span key={i} className="flex items-center gap-4">
            <span className="text-[color:var(--fb-pink)]">◆</span>
            <span className="text-white/80 tracking-widest">{t}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
