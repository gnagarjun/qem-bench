import { useState } from "react";
import { Lock } from "lucide-react";
import { runsApi, setToken, apiError } from "@/lib/runs";

export default function RunLogin({ onLogin }) {
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      setToken(await runsApi.login(pw));
      onLogin();
    } catch (x) {
      setErr(apiError(x));
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={submit} className="card p-5 flex flex-col sm:flex-row sm:items-end gap-3" data-testid="run-login-form">
      <div className="flex-1">
        <div className="flex items-center gap-2 font-display text-lg font-semibold"><Lock size={16} className="text-sky-400" /> Owner sign-in</div>
        <p className="text-sm text-slate-400 mt-1">Anyone can browse saved runs. Starting a new simulation requires the owner password.</p>
      </div>
      <label className="flex flex-col gap-1">
        <span className="overline">Password</span>
        <input type="password" data-testid="run-login-password-input" className="qselect w-full sm:w-64" value={pw} onChange={(e) => setPw(e.target.value)} />
      </label>
      <button type="submit" data-testid="run-login-submit-button" className="btn btn-primary" disabled={busy || !pw}>{busy ? "Signing in…" : "Sign in"}</button>
      {err && <div data-testid="run-login-error" className="text-sm text-rose-400 sm:basis-full">{err}</div>}
    </form>
  );
}
