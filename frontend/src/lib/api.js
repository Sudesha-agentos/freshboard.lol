import axios from "axios";

const BACKEND_URL = (process.env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "");
export const API = BACKEND_URL ? `${BACKEND_URL}/api` : "/api";

export const api = axios.create({ baseURL: API });

export const fetchBoard = (category) =>
  api.get("/board", { params: category && category !== "All" ? { category } : {} }).then(r => r.data);

export const fetchConfig = () => api.get("/config").then(r => r.data);
export const fetchResetInfo = () => api.get("/reset-info").then(r => r.data);
export const fetchActivity = (limit = 12) => api.get("/activity", { params: { limit } }).then(r => r.data);
export const fetchStats = () => api.get("/stats").then(r => r.data);
export const fetchTopToday = (limit = 3) => api.get("/top-today", { params: { limit } }).then(r => r.data);
export const fetchYesterdayTop = () => api.get("/yesterday-top").then(r => r.data);
export const fetchListing = (id) => api.get(`/listings/${id}`).then(r => r.data);
export const trackClick = (id) => api.post(`/listings/${id}/click`).then(r => r.data).catch(() => {});
export const previewUrl = (url) => api.post("/preview", { url }).then(r => r.data);

export const submitListing = (payload) => api.post("/submit", payload).then(r => r.data);
export const searchCompanies = (q) =>
  api.get("/companies", { params: q ? { q } : {} }).then(r => r.data);
export const startShare = (payload) => api.post("/share/start", payload).then(r => r.data);
export const verifyShare = (payload) => api.post("/share/verify", payload).then(r => r.data);
export const fetchShareStatus = (token) => api.get(`/share/status/${token}`).then(r => r.data);
export const hitShare = (token) => api.get(`/share/hit/${token}`).then(r => r.data);
export const shareListing = (id, target, postUrl) =>
  api.post(`/listings/${id}/share`, { target, post_url: postUrl }).then(r => r.data);
