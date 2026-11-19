import axios from "axios";

const BASE = `${process.env.REACT_APP_BACKEND_URL}/api`;
const KEY = "qem_owner_token";

export const getToken = () => localStorage.getItem(KEY);
export const setToken = (t) => (t ? localStorage.setItem(KEY, t) : localStorage.removeItem(KEY));
const auth = () => (getToken() ? { Authorization: `Bearer ${getToken()}` } : {});

export const runsApi = {
  login: (password) => axios.post(`${BASE}/auth/login`, { password }).then((r) => r.data.token),
  me: () => axios.get(`${BASE}/auth/me`, { headers: auth() }).then((r) => r.data),
  options: () => axios.get(`${BASE}/runs/options`).then((r) => r.data),
  list: () => axios.get(`${BASE}/runs`).then((r) => r.data),
  get: (id) => axios.get(`${BASE}/runs/${id}`).then((r) => r.data),
  start: (body) => axios.post(`${BASE}/runs`, body, { headers: auth() }).then((r) => r.data),
  cancel: (id) => axios.post(`${BASE}/runs/${id}/cancel`, {}, { headers: auth() }).then((r) => r.data),
  remove: (id) => axios.delete(`${BASE}/runs/${id}`, { headers: auth() }).then((r) => r.data),
  conditions: (id, params) => axios.get(`${BASE}/runs/${id}/conditions`, { params }).then((r) => r.data),
  tests: (id, params) => axios.get(`${BASE}/runs/${id}/tests`, { params }).then((r) => r.data),
};

export function apiError(e) {
  const d = e?.response?.data?.detail;
  if (!d) return e?.message || "Something went wrong. Please try again.";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x?.msg || JSON.stringify(x)).join(" ");
  return d.msg || String(d);
}

export const noiseLabel = (n) => n.label || n.base;
