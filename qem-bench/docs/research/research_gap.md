# Research Gap and Positioning

## 1. Established in the existing literature (we do not claim these)
- ZNE (Richardson, linear, exponential) and PEC can reduce noise-induced bias. Their sampling cost (variance amplification) is the price
  (Temme et al. 2017; Endo et al. 2018; Cai et al. 2023).
- Digital unitary folding is a practical way to scale noise (Giurgica-Tiron et al. 2020).
- Inverting an assignment matrix removes readout bias for uncorrelated readout noise. Scalable variants exist
  (Maciejewski et al. 2020; Bravyi et al. 2021; Nation et al. 2021).
- Any mitigation protocol has a sampling cost that grows exponentially with depth or size in the worst case (Takagi et al. 2022; Quek et al. 2024).
- Resource-normalised comparison of QEM methods has been done before, notably the improvement factor μ of Russo et al. (2023).
- Shot allocation and node choice for Richardson extrapolation can be optimised (Krebsbach et al. 2022).

## 2. Gaps supported by the literature reviewed
- **Accounting conventions are rarely made explicit.** In the works reviewed, papers often differ (or say little) on
  whether calibration shots, noise-scaled executions and measurement settings count towards the budget. Russo et al.
  normalise by total shots but leave combined techniques for future work.
- **Combining readout mitigation with ZNE** under a fixed total budget is discussed qualitatively (Endo et al. 2018; Cai et al. 2023).
  We found no controlled study in our review that paired the tests and corrected for multiple comparisons.
- **Statistical reporting.** Many demonstrations report single runs or error bars without paired tests, effect sizes or
  multiple-comparison control.
- **Validation of noise scaling.** Folding is often assumed to scale noise by λ. Few studies report the realised scaling.

*Caveat:* this review is focused, not exhaustive or systematic. The gaps above describe the papers reviewed,
not the whole field.

## 3. Questions QEM-Bench investigates
RQ1–RQ6 (see `hypotheses.md`): accuracy, variance, overhead and cost of baseline, REM, ZNE (linear and Richardson) and
REM+ZNE, measured under two explicitly defined accounting rules. Comparison A gives equal primary shots. Comparison B gives an equal total budget,
including calibration. The study covers Bell, GHZ (3–8 qubits) and small QAOA circuits under phenomenological Aer noise.

## 4. Possible contributions (not yet proven; they depend on review)
1. An open, reproducible harness whose resource ledger counts **every** shot, with a dataset validator that
   enforces the accounting rules.
2. Empirical evidence, within the simulated regime, of when mitigation does and does not pay off under equal budgets.
3. A dimensionless efficiency metric η, positioned against μ (Russo et al.) and work-normalised MSE.
4. A documented pitfall: unweighted partial folding mis-scales noise on small circuits, and extrapolating on the measured scale corrects for it.

None of these is claimed as a "first". Each needs to be checked against a systematic literature search before submission.

## 5. Outstanding literature tasks before submission
- Check by hand every [K] entry in `literature_review.md` (DOI, pages).
- Run a systematic search (2023–2026) for QEM benchmarking suites (e.g. application-oriented benchmarks and
  QEM benchmark collections) and update this gap statement.
