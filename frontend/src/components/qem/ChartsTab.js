import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";
import { get, METHODS, METHOD_COLOR, METHOD_LABEL, fmt } from "@/lib/qem";
import Select from "@/components/qem/Select";

const AX = { stroke: "#64748b", fontSize: 11, fontFamily: "JetBrains Mono" };
const TT = { contentStyle: { background: "#111622", border: "1px solid rgba(255,255,255,0.1)", fontSize: 12 }, labelStyle: { color: "#94a3b8" } };

function ShotsChart({ instance, noise, comparison }) {
  const q = useQuery({ queryKey: ["series", instance, noise, comparison], queryFn: () => get("/series", { instance, noise, comparison }) });
  const rows = {};
  (q.data?.points || []).forEach((p) => { rows[p.shots_per_circuit] = { ...(rows[p.shots_per_circuit] || { shots: p.shots_per_circuit }), [p.method]: p.rmse }; });
  const data = Object.values(rows).sort((a, b) => a.shots - b.shots);
  return (
    <div className="card p-5" data-testid={`rmse-vs-shots-chart-${comparison.toLowerCase()}`}>
      <div className="overline">Comparison {comparison} · {comparison === "A" ? "equal primary shots" : "equal total budget"}</div>
      <h3 className="font-display text-lg font-semibold mt-1">RMSE vs shots per circuit — {instance} ({q.data?.observable})</h3>
      <div className="h-72 mt-3">
        <ResponsiveContainer>
          <LineChart data={data} margin={{ left: 4, right: 12, top: 8 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" />
            <XAxis dataKey="shots" scale="log" domain={["auto", "auto"]} type="number" ticks={data.map((d) => d.shots)} tick={AX} />
            <YAxis scale="log" domain={["auto", "auto"]} type="number" tick={AX} tickFormatter={(v) => fmt(v, 2)} width={52} />
            <Tooltip {...TT} formatter={(v, n) => [fmt(v, 3), METHOD_LABEL[n]]} labelFormatter={(l) => `N = ${l}`} />
            <Legend formatter={(v) => <span style={{ fontSize: 11, color: "#cbd5e1" }}>{METHOD_LABEL[v]}</span>} />
            {METHODS.map((m) => <Line key={m} dataKey={m} stroke={METHOD_COLOR[m]} strokeWidth={2} dot={{ r: 2.5 }} isAnimationActive />)}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function ParetoChart({ instance, noise }) {
  const q = useQuery({ queryKey: ["pareto", instance, noise], queryFn: () => get("/pareto", { instance, noise }) });
  const pts = q.data?.points || [];
  const front = pts.filter((p) => p.pareto_optimal);
  return (
    <div className="card p-5" data-testid="pareto-frontier-chart">
      <div className="overline">Accuracy vs resource expenditure (comparison A accounting)</div>
      <h3 className="font-display text-lg font-semibold mt-1">Pareto frontier — {instance}, {noise} noise</h3>
      <div className="h-80 mt-3">
        <ResponsiveContainer>
          <ScatterChart margin={{ left: 4, right: 12, top: 8 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" />
            <XAxis dataKey="total_shots" name="total shots" scale="log" domain={["auto", "auto"]} type="number" tick={AX} tickFormatter={(v) => v.toExponential(0)} />
            <YAxis dataKey="rmse" name="RMSE" scale="log" domain={["auto", "auto"]} type="number" tick={AX} tickFormatter={(v) => fmt(v, 2)} width={52} />
            <ZAxis range={[40, 40]} />
            <Tooltip {...TT} formatter={(v, n) => [fmt(v, 4), n]} />
            <Legend formatter={(v) => <span style={{ fontSize: 11, color: "#cbd5e1" }}>{v}</span>} />
            {METHODS.map((m) => <Scatter key={m} name={METHOD_LABEL[m]} data={pts.filter((p) => p.method === m)} fill={METHOD_COLOR[m]} />)}
            <Scatter name="Pareto frontier" data={front} fill="none" line={{ stroke: "#f8fafc", strokeWidth: 1.2 }} shape={() => null} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <p className="text-xs text-slate-400 mt-2" data-testid="pareto-optimal-count">{front.length} non-dominated configurations: {[...new Set(front.map((p) => METHOD_LABEL[p.method]))].join(", ")}</p>
    </div>
  );
}

export default function ChartsTab({ filters }) {
  const core = filters.instance;
  const [instance, setInstance] = useState("ghz_4");
  const [noise, setNoise] = useState("moderate");
  return (
    <div className="space-y-6" data-testid="charts-tab">
      <div className="card p-4 flex flex-wrap gap-3">
        <Select id="chart-instance-select" label="Instance" value={instance} onChange={(v) => setInstance(v || "ghz_4")} options={core} allLabel={null} />
        <Select id="chart-noise-select" label="Noise level" value={noise} onChange={(v) => setNoise(v || "moderate")} options={["low", "moderate", "high"]} allLabel={null} />
      </div>
      <div className="grid lg:grid-cols-2 gap-6">
        <ShotsChart instance={instance} noise={noise} comparison="A" />
        <ShotsChart instance={instance} noise={noise} comparison="B" />
      </div>
      <ParetoChart instance={instance} noise={noise} />
    </div>
  );
}
