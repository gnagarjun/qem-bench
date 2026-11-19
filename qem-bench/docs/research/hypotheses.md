# Research Questions, Hypotheses and Pre-specified Decision Rules

The decision rules were written (and coded in `src/qem_bench/analysis/hypotheses.py`) **before** the reported
standard run was analysed. They are applied mechanically. Verdicts: SUPPORTED / PARTIALLY SUPPORTED /
NOT SUPPORTED. "Significant" means a two-sided Wilcoxon signed-rank test on paired absolute errors with
Benjamini–Hochberg q < 0.05 across *all* tests in the study. "Practical" means |ΔRMSE/RMSE| ≥ 10 %.

| ID | Hypothesis | Decision rule |
|----|-----------|---------------|
| H1 | Readout mitigation reduces estimation bias when measurement errors dominate. | Readout sweep, comparison A, readout multiplier ≥ 1: the smaller of (fraction of conditions with REM significantly better) and (fraction with lower \|bias\|) ≥ 0.75 → SUPPORTED; ≥ 0.25 → PARTIAL. |
| H2 | ZNE improves estimates under moderate noise, but its effectiveness deteriorates under high noise or small budgets. | Core, A: ZNE significantly better in ≥ 50 % of moderate-noise conditions with N ≥ 4096, **and** this fraction drops by ≥ 0.2 at high noise *or* at the smallest N. The two parts are also reported separately. |
| H3 | Combined mitigation can improve accuracy but costs more. | Core, A: combined significantly better than **both** REM-only and the matching ZNE-only in ≥ 10 % of conditions, and always consumes more shots. |
| H4 | Greater depth makes accurate estimation harder. | Core, baseline, primary observable, largest N: Spearman ρ(two-qubit gate count, \|bias\|) > 0 with p < 0.05 at every noise level. |
| H5 | Under some conditions unmitigated execution is better after normalising for resources. | Core, comparison B: at least one condition in which no mitigation method is significantly better than baseline. |
| RQ6 | Ranking methods by a resource-aware criterion. | Mean RMSE rank per condition under A and B; distribution of η categories. |

Known weaknesses of these rules, acknowledged in advance:
- H4 pools different circuit families and observables whose bias scales differ (the QAOA cost is bounded in
  [0, 1] and tends to 0.5 under depolarizing noise). A within-family analysis is reported as **exploratory**.
- H5 uses "no method significantly better", which is weaker than "baseline significantly better". Both are reported.
