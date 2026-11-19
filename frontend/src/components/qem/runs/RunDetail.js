import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Square, Trash2 } from "lucide-react";
import { runsApi, apiError, noiseLabel } from "@/lib/runs";
import { METHOD_LABEL } from "@/lib/qem";
import RunResults from "@/components/qem/runs/RunResults";

export default function RunDetail({ runId, isOwner, onDeleted }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["run", runId], queryFn: () => runsApi.get(runId), refetchInterval: (qq) => (qq.state.data?.status === "running" ? 1500 : false) });
  const run = q.data;
  if (!run) return <div className="overline animate-pulse">Loading run…</div>;
  const act = async (fn, msg) => {
    try { await fn(); toast.success(msg); qc.invalidateQueries({ queryKey: ["runs"] }); qc.invalidateQueries({ queryKey: ["run", runId] }); } catch (x) { toast.error(apiError(x)); }
  };
  const p = run.progress;
  const pctDone = p.chunks_total ? Math.min(100, Math.round((100 * p.chunks_started) / p.chunks_total)) : 0;
  return (
    <div className="card p-5 space-y-5 rise" data-testid="run-detail">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-display text-xl font-semibold" data-testid="run-detail-name">{run.name}</div>
          <div className="text-xs text-slate-400 mt-1 max-w-3xl">
            {run.spec.instances.join(", ")} · noise {run.spec.noise.map(noiseLabel).join(", ")} · N {run.spec.shots.join("/")} · {run.spec.repetitions} reps · {run.spec.methods.map((m) => METHOD_LABEL[m]).join(", ")} · ZNE {run.spec.zne.scale_factors.join(",")} {run.spec.zne.folding} · seed {run.spec.seed}
          </div>
        </div>
        {isOwner && (
          <div className="flex gap-2">
            {run.status === "running"
              ? <button className="btn" data-testid="run-cancel-button" onClick={() => act(() => runsApi.cancel(runId), "Run cancelled")}><Square size={14} /> Cancel</button>
              : <button className="btn" data-testid="run-delete-button" onClick={() => window.confirm("Remove this run from the list?") && act(() => runsApi.remove(runId), "Run removed").then(onDeleted)}><Trash2 size={14} /> Remove</button>}
          </div>
        )}
      </div>
      {run.status === "running" && (
        <div className="space-y-2" data-testid="run-progress">
          <div className="flex justify-between overline"><span>{p.stage === "analysing" ? "Running statistics" : `Simulating ${p.chunks_started}/${p.chunks_total} circuit × noise blocks`}</span><span>{p.stage === "analysing" ? "" : `${pctDone}%`}</span></div>
          <div className="h-1.5 rounded bg-white/5 overflow-hidden"><div className="h-full bg-sky-400 transition-[width] duration-500" style={{ width: `${p.stage === "analysing" ? 100 : pctDone}%` }} /></div>
          <pre className="text-[11px] text-slate-500 font-mono overflow-auto max-h-40" data-testid="run-log-tail">{p.log_tail.join("\n")}</pre>
        </div>
      )}
      {run.status === "failed" && <pre className="text-xs text-rose-300 whitespace-pre-wrap" data-testid="run-error">{run.error}</pre>}
      {run.status === "cancelled" && <div className="text-sm text-slate-400" data-testid="run-cancelled-note">This run was cancelled before it finished.</div>}
      {run.status === "completed" && (
        <>
          <div className="flex flex-wrap gap-3" data-testid="run-summary">
            {[["Raw estimates", run.result?.n_raw_rows], ["Conditions", run.result?.n_conditions], ["Paired tests", run.result?.n_tests], ["Failed rows", run.result?.n_failed_rows], ["Wall time", `${run.wall_s?.toFixed(1)}s`]].map(([k, v]) => (
              <div key={k} className="card px-4 py-3"><div className="overline">{k}</div><div className="num text-xl font-semibold">{typeof v === "number" ? v.toLocaleString() : v}</div></div>
            ))}
          </div>
          <RunResults run={run} />
        </>
      )}
    </div>
  );
}
