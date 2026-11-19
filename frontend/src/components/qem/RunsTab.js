import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { LogOut } from "lucide-react";
import { runsApi, getToken, setToken } from "@/lib/runs";
import RunLogin from "@/components/qem/runs/RunLogin";
import RunForm from "@/components/qem/runs/RunForm";
import RunList from "@/components/qem/runs/RunList";
import RunDetail from "@/components/qem/runs/RunDetail";

export default function RunsTab() {
  const qc = useQueryClient();
  const [owner, setOwner] = useState(null);
  const [selected, setSelected] = useState(null);
  const opts = useQuery({ queryKey: ["run-options"], queryFn: runsApi.options });
  const runs = useQuery({ queryKey: ["runs"], queryFn: runsApi.list, refetchInterval: (q) => (q.state.data?.some((r) => r.status === "running") ? 2000 : false) });
  useEffect(() => {
    if (!getToken()) return setOwner(false);
    runsApi.me().then(() => setOwner(true)).catch(() => { setToken(null); setOwner(false); });
  }, []);
  const list = runs.data || [];
  const busy = list.some((r) => r.status === "running");
  const current = selected || list[0]?.run_id;
  const started = (id) => { setSelected(id); qc.invalidateQueries({ queryKey: ["runs"] }); };
  return (
    <div className="space-y-6" data-testid="run-simulations-tab">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="overline">Run your own experiments</div>
          <h2 className="font-display text-3xl font-bold tracking-tight mt-1">Simulation runs</h2>
          <p className="text-sm text-slate-400 mt-2 max-w-2xl">Choose a design, run it on the Qiskit Aer simulator and get the same aggregation and paired statistical tests as the published study. Each run is saved separately; the published results in the other tabs are never changed.</p>
        </div>
        {owner && <button className="btn" data-testid="run-logout-button" onClick={() => { setToken(null); setOwner(false); }}><LogOut size={14} /> Sign out</button>}
      </div>
      {owner === false && <RunLogin onLogin={() => setOwner(true)} />}
      {owner && opts.data && <RunForm opts={opts.data} busy={busy} onStarted={started} />}
      <RunList runs={list} loading={runs.isLoading} selected={current} onSelect={setSelected} />
      {current && <RunDetail key={current} runId={current} isOwner={!!owner} onDeleted={() => setSelected(null)} />}
    </div>
  );
}
