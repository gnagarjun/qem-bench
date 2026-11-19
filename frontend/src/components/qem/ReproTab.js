import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Copy, Download } from "lucide-react";
import { get, fmt, METHOD_LABEL } from "@/lib/qem";

const CITATION = `@software{gopalaswamy2026qembench,
  author = {Gopalaswamy, Nagarjun},
  title = {QEM-Bench: A Resource-Aware Benchmarking Framework for Quantum Error Mitigation},
  year = {2026}, version = {0.1.0}, note = {Independent researcher}
}`;

const copy = (text, msg) => navigator.clipboard.writeText(text).then(() => toast.success(msg), () => toast.error("Clipboard unavailable"));

export default function ReproTab({ overview }) {
  const q = useQuery({ queryKey: ["repro"], queryFn: () => get("/reproducibility") });
  const d = q.data;
  const exportJson = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(overview, null, 2)], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url; a.download = "qem-bench-summary.json"; a.click(); URL.revokeObjectURL(url);
    toast.success("Summary exported");
  };
  if (!d) return <div className="overline animate-pulse">Loading…</div>;
  return (
    <div className="grid lg:grid-cols-2 gap-6" data-testid="reproducibility-tab">
      <div className="card p-5 space-y-3 min-w-0">
        <div className="overline">Run provenance</div>
        <div className="text-sm">Run: <span className="num" data-testid="reproducibility-run-id" style={{ wordBreak: "break-all" }}>{d.runs.join(", ")}</span></div>
        <div className="text-sm">Config hash: <span className="num text-sky-300" data-testid="reproducibility-config-hash">{d.config_hashes.join(", ")}</span></div>
        <div className="text-sm">Schema: <span className="num">{d.schema_version}</span> · raw files: <span className="num">{d.manifest.aggregated_from[0].raw_files ? Object.keys(d.manifest.aggregated_from[0].raw_files).length : 0}</span> (SHA-256 in manifest)</div>
        <div className="overline pt-3">Environment</div>
        <div className="num text-xs text-slate-300 space-y-1 break-all" data-testid="reproducibility-environment">
          <div>python {d.environment.python} · {d.environment.platform} · {d.environment.cpu_count} CPUs</div>
          {Object.entries(d.environment.packages).map(([k, v]) => <div key={k}>{k}=={v}</div>)}
        </div>
      </div>
      <div className="space-y-6 min-w-0">
        <div className="card p-5">
          <div className="overline mb-3">Reproduce</div>
          <pre className="num text-xs bg-black/40 rounded-lg p-4 overflow-x-auto" data-testid="reproducibility-commands">{d.commands.join("\n")}</pre>
          <div className="flex flex-wrap gap-2 mt-4">
            <button className="btn" data-testid="btn-copy-commands" onClick={() => copy(d.commands.join("\n"), "Commands copied")}><Copy size={14} /> Copy commands</button>
            <button className="btn" data-testid="btn-copy-citation" onClick={() => copy(CITATION, "BibTeX citation copied")}><Copy size={14} /> Copy citation</button>
            <button className="btn" data-testid="btn-export-json" onClick={exportJson}><Download size={14} /> Export summary JSON</button>
          </div>
        </div>
        <div className="card overflow-x-auto">
          <div className="p-5 pb-2"><div className="overline">Wall-clock timing study (per-shot Aer, N=4096, machine-specific)</div></div>
          <table className="qtable" data-testid="timing-table">
            <thead><tr><th>Instance</th><th>Method</th><th>Total (s)</th><th>SD</th><th>Calibration (s)</th></tr></thead>
            <tbody>{d.timing.map((t, i) => (
              <tr key={i}><td>{t.instance}</td><td>{METHOD_LABEL[t.method]}</td><td className="num">{fmt(t.t_total_mean, 3)}</td><td className="num">{fmt(t.t_total_sd, 2)}</td><td className="num">{fmt(t.t_calibration_mean, 2)}</td></tr>
            ))}</tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
