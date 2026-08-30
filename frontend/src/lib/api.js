import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API });

export const fetchBoard = (category) =>
  api.get("/board", { params: category && category !== "All" ? { category } : {} }).then(r => r.data);

export const fetchConfig = () => api.get("/config").then(r => r.data);
export const fetchResetInfo = () => api.get("/reset-info").then(r => r.data);

export const submitListing = (payload) => api.post("/submit", payload).then(r => r.data);
export const outbidListing = (payload) => api.post("/outbid", payload).then(r => r.data);
export const paymentStatus = (sessionId) =>
  api.get(`/payments/status/${sessionId}`).then(r => r.data);
