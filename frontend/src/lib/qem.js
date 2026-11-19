import axios from "axios";

export const API = `${process.env.REACT_APP_BACKEND_URL}/api/qem`;
export const get = (path, params) => axios.get(`${API}${path}`, { params }).then((r) => r.data);

export const METHODS = ["baseline", "readout", "zne_linear", "zne_richardson", "combined_linear", "combined_richardson"];
export const METHOD_LABEL = {
  baseline: "Baseline", readout: "Readout (REM)", zne_linear: "ZNE-linear", zne_richardson: "ZNE-Richardson",
  combined_linear: "REM+ZNE-linear", combined_richardson: "REM+ZNE-Richardson",
};
export const METHOD_COLOR = {
  baseline: "#94a3b8", readout: "#38bdf8", zne_linear: "#f59e0b", zne_richardson: "#f97316",
  combined_linear: "#10b981", combined_richardson: "#e879f9",
};
export const fmt = (v, d = 3) => (v === null || v === undefined || Number.isNaN(v) ? "–" : Math.abs(v) >= 1e300 ? (v > 0 ? "∞" : "−∞") : Number(v).toPrecision(d));
export const pct = (v) => (v === null || v === undefined ? "–" : `${(v * 100).toFixed(1)}%`);
