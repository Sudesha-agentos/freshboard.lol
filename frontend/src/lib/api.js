import axios from "axios";

const BACKEND_URL = (process.env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "");
export const API = BACKEND_URL ? `${BACKEND_URL}/api` : "/api";

export const api = axios.create({
  baseURL: API,
  timeout: 12_000,
  validateStatus: (s) => s >= 200 && s < 300,
});

api.interceptors.response.use((res) => {
  const data = res.data;
  if (typeof data === "string" && data.trimStart().startsWith("<")) {
    return Promise.reject(new Error("API unavailable"));
  }
  return res;
});

function isPlainObject(v) {
  return !!v && typeof v === "object" && !Array.isArray(v);
}

function asArray(v) {
  return Array.isArray(v) ? v : [];
}

export function asBoard(data) {
  if (!isPlainObject(data)) return { products: [], socials: [] };
  return {
    ...data,
    products: asArray(data.products),
    socials: asArray(data.socials),
  };
}

export function asConfig(data) {
  if (!isPlainObject(data)) {
    return { categories: [], credits_per_share: 5, welcome_credits: 5 };
  }
  return {
    ...data,
    categories: asArray(data.categories),
    credits_per_share: Number(data.credits_per_share) || 5,
    welcome_credits: Number(data.welcome_credits) || 5,
  };
}

const empty = (fallback) => () => fallback;

export const fetchBoard = (category) =>
  api.get("/board", { params: category && category !== "All" ? { category } : {} })
    .then(r => asBoard(r.data))
    .catch(empty(asBoard(null)));

export const fetchConfig = () =>
  api.get("/config").then(r => asConfig(r.data)).catch(empty(asConfig(null)));

export const fetchResetInfo = () =>
  api.get("/reset-info").then(r => (isPlainObject(r.data) ? r.data : {})).catch(empty({}));

export const fetchActivity = (limit = 12) =>
  api.get("/activity", { params: { limit } })
    .then(r => ({ items: asArray(isPlainObject(r.data) ? r.data.items : null) }))
    .catch(empty({ items: [] }));

export const fetchStats = () =>
  api.get("/stats").then(r => (isPlainObject(r.data) ? r.data : null)).catch(empty(null));

export const fetchTopToday = (limit = 3) =>
  api.get("/top-today", { params: { limit } })
    .then(r => ({ items: asArray(isPlainObject(r.data) ? r.data.items : null) }))
    .catch(empty({ items: [] }));

export const fetchYesterdayTop = () =>
  api.get("/yesterday-top")
    .then(r => ({ item: isPlainObject(r.data) ? r.data.item || null : null }))
    .catch(empty({ item: null }));

export const fetchListing = (id) =>
  api.get(`/listings/${id}`).then(r => r.data);

export const trackClick = (id) =>
  api.post(`/listings/${id}/click`).then(r => r.data).catch(() => {});

export const previewUrl = (url) => api.post("/preview", { url }).then(r => r.data);

export const submitListing = (payload) => api.post("/submit", payload).then(r => r.data);
export const searchCompanies = (q) =>
  api.get("/companies", { params: q ? { q } : {} })
    .then(r => ({ items: asArray(isPlainObject(r.data) ? r.data.items : null) }))
    .catch(empty({ items: [] }));
export const startShare = (payload) => api.post("/share/start", payload).then(r => r.data);
export const verifyShare = (payload) => api.post("/share/verify", payload).then(r => r.data);
export const fetchShareStatus = (token) => api.get(`/share/status/${token}`).then(r => r.data);
export const hitShare = (token) => api.get(`/share/hit/${token}`).then(r => r.data);
export const shareListing = (id, target, postUrl) =>
  api.post(`/listings/${id}/share`, { target, post_url: postUrl }).then(r => r.data);
