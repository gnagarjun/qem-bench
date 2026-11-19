import { useEffect, useState } from "react";
import { Toaster } from "sonner";
import { useQuery } from "@tanstack/react-query";
import "@/App.css";
import { get } from "@/lib/qem";
import OverviewTab from "@/components/qem/OverviewTab";
import ExplorerTab from "@/components/qem/ExplorerTab";
import ChartsTab from "@/components/qem/ChartsTab";
import StatsTab from "@/components/qem/StatsTab";
import FiguresTab from "@/components/qem/FiguresTab";
import ReproTab from "@/components/qem/ReproTab";

const TABS = [
  ["overview", "Overview & Hypotheses", OverviewTab],
  ["condition-explorer", "Condition Explorer", ExplorerTab],
  ["interactive-charts", "Scaling & Pareto", ChartsTab],
  ["statistical-tests", "Statistical Tests", StatsTab],
  ["figures-gallery", "Publication Figures", FiguresTab],
  ["reproducibility", "Reproducibility", ReproTab],
];

export default function App() {
  const [tab, setTab] = useState("overview");
  const overview = useQuery({ queryKey: ["overview"], queryFn: () => get("/overview") });
  const filters = useQuery({ queryKey: ["filters"], queryFn: () => get("/filters") });
  useEffect(() => { document.documentElement.classList.add("dark"); }, []);
  const Active = TABS.find((t) => t[0] === tab)[2];
  return (
    <div className="min-h-screen relative">
      <div className="grid-bg absolute inset-x-0 top-0 h-80 pointer-events-none" />
      <header className="sticky top-0 z-40 border-b border-white/10 bg-[#0b0e14]/90 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex flex-col gap-3">
          <div className="flex items-baseline gap-3">
            <h1 data-testid="header-brand-title" className="font-display text-2xl font-bold tracking-tight whitespace-nowrap">QEM-Bench</h1>
            <span className="overline hidden md:inline whitespace-nowrap">Resource-aware QEM results · simulated (Qiskit Aer)</span>
          </div>
          <nav className="flex gap-1 overflow-x-auto -mx-1 px-1" data-testid="main-tabs">
            {TABS.map(([id, label]) => (
              <button key={id} data-testid={`tab-${id}`} data-active={tab === id} className="tabbtn" onClick={() => setTab(id)}>{label}</button>
            ))}
          </nav>
        </div>
      </header>
      <main className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {overview.isError && <div data-testid="api-error" className="card p-5 text-rose-300">Could not load results from the API.</div>}
        {overview.isLoading || filters.isLoading ? (
          <div data-testid="loading-indicator" className="overline animate-pulse">Loading saved results…</div>
        ) : overview.data && filters.data ? (
          <Active overview={overview.data} filters={filters.data} />
        ) : null}
      </main>
      <footer className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-10 overline">
        All values are read from saved experiment outputs. Simulation results only; not quantum-hardware measurements.
      </footer>
      <Toaster theme="dark" position="bottom-right" />
    </div>
  );
}
