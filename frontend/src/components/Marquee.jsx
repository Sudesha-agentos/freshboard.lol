export default function Marquee({ items }) {
  const list = items && items.length ? items : [
    "FRESHBOARD.LOL",
    "RANK IS BOUGHT, NOT VOTED",
    "$1 MIN BID",
    "BOARD RESETS MIDNIGHT IST",
    "OUTBID OR GO HOME",
    "SHIP + PAY = RANK",
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
