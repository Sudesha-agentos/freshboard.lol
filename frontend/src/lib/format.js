import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";

dayjs.extend(relativeTime);

export function timeAgo(iso) {
  if (!iso) return "";
  try {
    return dayjs(iso).fromNow();
  } catch {
    return "";
  }
}

export function money(n, opts = {}) {
  const v = Number(n || 0);
  if (opts.compact && v >= 1000) return `$${(v / 1000).toFixed(1)}k`;
  return `$${v.toFixed(2)}`;
}

export function moneyInt(n) {
  const v = Math.round(Number(n || 0));
  return v.toLocaleString("en-US");
}
