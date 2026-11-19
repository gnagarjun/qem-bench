# Literature Review

Scope: quantum error mitigation (QEM), readout mitigation, zero-noise extrapolation (ZNE), probabilistic
error cancellation (PEC), Richardson extrapolation, noise scaling/gate folding, sampling overhead and
resource-aware evaluation. Bibliographic data are in `paper/references.bib`.

**Verification status.** Entries marked **[V]** had venue, volume and DOI checked against the publisher
or index records (via web search) while this review was written (June 2026). Entries marked **[K]** are
canonical references whose details come from the author's knowledge of the standard record; their DOIs
still need checking by hand before submission (listed in `docs/research/research_gap.md`, section 5).
The summaries describe each paper's main contribution. They are **not** a replacement for reading the
papers, and the "Limitations" notes give the author's critical reading.

---

## 1. Foundational error mitigation

### Temme, Bravyi & Gambetta (2017). *Error Mitigation for Short-Depth Quantum Circuits.* PRL 119, 180509. doi:10.1103/PhysRevLett.119.180509 [K]
- **Problem:** estimating expectation values on noisy short-depth circuits without error correction.
- **Technique:** (i) Richardson extrapolation of expectation values measured at amplified noise strengths
  (by stretching gate duration); (ii) probabilistic error cancellation through quasi-probability
  decompositions of inverse noise channels.
- **Setup:** theoretical analysis with numerical examples (no hardware experiment in this paper).
- **Metrics:** estimator bias and the sampling cost of quasi-probability sampling (the variance grows with the 1-norm γ²).
- **Findings:** both methods can remove the leading-order noise bias. PEC is unbiased given an exact noise model, but its sampling cost grows exponentially with circuit size.
- **Limitations:** assumes the noise can be amplified in a controlled way (Richardson) or is known exactly (PEC).
- **Relation to QEM-Bench:** our ZNE is the Richardson/linear-extrapolation idea, implemented with *digital* folding. We make
  the variance amplification Σγᵢ² explicit and charge it against the shot budget (comparison B).

### Li & Benjamin (2017). *Efficient Variational Quantum Simulator Incorporating Active Error Minimization.* PRX 7, 021050. doi:10.1103/PhysRevX.7.021050 [K]
- **Problem:** running a variational quantum simulator on noisy hardware.
- **Technique:** a variational simulation algorithm with error extrapolation: the noise is deliberately raised and the result extrapolated to zero noise.
- **Setup:** numerical simulation with realistic noise models.
- **Findings:** extrapolation substantially reduces the error at modest cost.
- **Limitations:** simulated noise only; the extrapolation model is assumed.
- **Relation:** an early statement of the extrapolation principle that we benchmark.

### Endo, Benjamin & Li (2018). *Practical Quantum Error Mitigation for Near-Future Applications.* PRX 8, 031027. doi:10.1103/PhysRevX.8.031027 [K]
- **Problem:** making PEC and extrapolation practical when the noise is not known a priori.
- **Technique:** PEC using noise characterised by gate set tomography; exponential extrapolation; combining mitigation with measurement-error handling.
- **Setup:** numerical simulations.
- **Metrics:** estimation error and the sampling overhead (cost factor).
- **Findings:** under realistic noise, exponential extrapolation can outperform polynomial extrapolation. Mitigation methods can be combined.
- **Limitations:** simulation only; tomography is costly.
- **Relation:** motivates our RQ3 (combining methods) and our note that the depolarizing-induced
  decay is close to exponential, which leaves a residual bias in linear and Richardson fits (observed in our data).

### Kandala et al. (2019). *Error Mitigation Extends the Computational Reach of a Noisy Quantum Processor.* Nature 567, 491–495. doi:10.1038/s41586-019-1040-7 [K]
- **Problem:** showing ZNE on hardware.
- **Technique:** Richardson extrapolation with noise amplified by stretching pulses, used for VQE on molecular Hamiltonians and for quantum magnetism.
- **Setup:** superconducting transmon processor (IBM).
- **Findings:** energy estimates improved markedly over unmitigated runs.
- **Limitations:** pulse-level control is needed. Shot and resource accounting was not the focus.
- **Relation:** our study is simulation-only and uses digital folding. Hardware results like this one are not reproduced here.

## 2. Digital noise scaling and software frameworks

### Giurgica-Tiron, Hindy, LaRose, Mari & Zeng (2020). *Digital Zero Noise Extrapolation for Quantum Error Mitigation.* IEEE QCE 2020, pp. 306–316. doi:10.1109/QCE49297.2020.00045 [V]
- **Technique:** unitary folding (global and local, G → G G† G) and parameter noise scaling, with comparisons of extrapolation methods.
- **Setup:** simulators and IBM hardware.
- **Findings:** digital folding allows ZNE using only gate-level access.
- **Limitations:** the noise really scales by λ only if the folded gates carry noise proportional to their count. That fails for virtual gates and for coherent or time-dependent noise.
- **Relation:** QEM-Bench implements global and local folding. It **checks** that folding preserves the
  unitary and **measures** the effective error-mass scale λ_eff. We found that unweighted gate-count partial folding mis-scales noise
  badly on tiny circuits (λ_eff = 1.18 or 2.93 for nominal λ = 2). We therefore use error-weighted gate selection and extrapolate on λ_eff (see methodology).

### LaRose et al. (2022). *Mitiq: A Software Package for Error Mitigation on Noisy Quantum Computers.* Quantum 6, 774. doi:10.22331/q-2022-08-11-774 [K]
- **Contribution:** an open-source framework (ZNE, PEC, later CDR and others), with benchmarks.
- **Relation:** QEM-Bench is **not** a replacement for Mitiq. It is an evaluation harness focused on resource accounting.
  We implemented folding and extrapolation ourselves so that every executed shot is visible to the resource ledger.

## 3. Readout (measurement) error mitigation

### Maciejewski, Zimborás & Oszmaniec (2020). *Mitigation of readout noise in near-term quantum devices by classical post-processing based on detector tomography.* Quantum 4, 257. doi:10.22331/q-2020-04-24-257 [V]
- **Technique:** characterise the detectors by tomography, then invert the classical noise in post-processing. Includes an analysis of the statistical error caused by the inversion.
- **Relation:** the basis for our assignment-matrix inversion. Their error analysis motivates our separate reporting of variance inflation (the empirical/predicted variance ratio).

### Bravyi, Sheldon, Kandala, McKay & Gambetta (2021). *Mitigating measurement errors in multiqubit experiments.* PRA 103, 042605. doi:10.1103/PhysRevA.103.042605 [V]
- **Technique:** scalable readout-mitigation models (tensor-product and continuous-time Markov process) that avoid full 2ⁿ calibration.
- **Relation:** our "tensored" calibration (2 circuits) is the uncorrelated special case. It is exact for our
  noise model, which is itself uncorrelated. That is a **favourable assumption** and a threat to validity.

### Nation, Kang, Sundaresan & Gambetta (2021). *Scalable Mitigation of Measurement Errors on Quantum Computers.* PRX Quantum 2, 040326. doi:10.1103/PRXQuantum.2.040326 [V]
- **Technique:** M3, a matrix-free correction restricted to the observed-bitstring subspace and solved iteratively.
- **Relation:** a scalable alternative not implemented here (our largest system has 8 qubits). It is recorded as future work.

### Smolin, Gambetta & Smith (2012). *Efficient method for computing the maximum-likelihood quantum state from measurements with additive Gaussian noise.* PRL 108, 070502. doi:10.1103/PhysRevLett.108.070502 [K]
- **Relation:** the standard reference for projecting non-physical estimates to the nearest physical one. We offer a
  Euclidean simplex projection (Duchi et al., 2008) as an *option*. We default to unconstrained quasi-probabilities because
  projection is nonlinear and biases linear estimators.

## 4. Probabilistic error cancellation, learning-based and large-scale mitigation

### van den Berg, Minev, Kandala & Temme (2023). *Probabilistic error cancellation with sparse Pauli–Lindblad models on noisy quantum processors.* Nature Physics 19, 1116–1121. doi:10.1038/s41567-023-02042-2 [V]
- Learns sparse Pauli–Lindblad noise models that make PEC scalable on hardware. **Relation:** PEC is outside
  our scope; the `MethodSpec` registry is designed so that it can be added.

### Kim et al. (2023). *Evidence for the utility of quantum computing before fault tolerance.* Nature 618, 500–505. doi:10.1038/s41586-023-06096-3 [V]
- ZNE with noise amplified probabilistically through learned Pauli–Lindblad models on a 127-qubit processor.
  **Relation:** shows that the choice of noise-scaling method matters at scale. Our folding results apply only to small simulated circuits.

### Czarnik, Arrasmith, Coles & Cincio (2021). *Error mitigation with Clifford quantum-circuit data.* Quantum 5, 592. doi:10.22331/q-2021-11-26-592 [V]
- Clifford data regression (CDR). **Relation:** future extension.

## 5. Limits, overhead and optimal extrapolation

### Takagi, Endo, Minagawa & Gu (2022). *Fundamental limits of quantum error mitigation.* npj Quantum Information 8, 114. doi:10.1038/s41534-022-00618-z [V]
- Lower bounds on the sampling cost of any mitigation protocol, based on state distinguishability. The cost grows exponentially with depth under local depolarizing noise.
- **Relation:** gives the theoretical reason why the trade-off between accuracy and resources studied here is unavoidable.

### Quek, Stilck França, Khatri, Meyer & Eisert (2024). *Exponentially tighter bounds on limitations of quantum error mitigation.* Nature Physics 20, 1648–1658. doi:10.1038/s41567-024-02536-7 [V]
- Shows that a superpolynomial number of samples is needed in the worst case, even at shallow depth. **Relation:** our small-circuit regime is far from these asymptotic limits.
  Our findings must not be extrapolated to large systems.

### Krebsbach, Trauzettel & Calzona (2022). *Optimization of Richardson extrapolation for quantum error mitigation.* PRA 106, 062436. doi:10.1103/PhysRevA.106.062436 [V]
- Analyses the bias–variance trade-off of Richardson extrapolation. Proposes node choices and allocating shots in proportion to |γⱼ|.
- **Relation:** our comparison B uses the |γ|-proportional allocation from this paper.

### Endo, Cai, Benjamin & Yuan (2021). *Hybrid quantum-classical algorithms and quantum error mitigation.* J. Phys. Soc. Jpn. 90, 032001. doi:10.7566/JPSJ.90.032001 [K]; Cai et al. (2023). *Quantum error mitigation.* Rev. Mod. Phys. 95, 045005. doi:10.1103/RevModPhys.95.045005 [V]
- Reviews. Cai et al. explicitly discuss sampling overhead, the bias–variance trade-off and combining techniques.
  **Relation:** these reviews already state the general trade-offs. Our contribution is a controlled empirical
  measurement, under explicit accounting rules, for a specific benchmark suite.

## 6. Resource-normalised benchmarking of QEM (closest prior work)

### Russo, Mari, Shammah, LaRose & Zeng (2023). *Testing platform-independent quantum error mitigation on noisy quantum computers.* IEEE Trans. Quantum Eng. 4. doi:10.1109/TQE.2023.3305232 [V]
- **Problem:** benchmarking ZNE and PEC across hardware platforms (IBM, IonQ, Rigetti) and simulators.
- **Metric:** an *improvement factor* μ normalised by the shot-cost factor √(N_QEM/N).
- **Findings:** QEM is generally beneficial even after the overhead is normalised, but the benefit depends on the platform and the technique (some ZNE variants did worse than no mitigation on some devices).
- **Limitations noted by the authors:** combining techniques and structured circuits were left for future work.
- **Relation:** this is the **closest prior work**. QEM-Bench reports μ alongside its own η metric. It adds (i) readout
  mitigation and REM+ZNE combinations, (ii) an explicit equal-total-budget comparison that includes calibration
  shots, (iii) paired statistical testing with FDR control, and (iv) Pareto analysis. These additions are differences in
  design, not claims of being first.

## 7. Algorithms and statistics used

- Farhi, Goldstone & Gutmann (2014), *A Quantum Approximate Optimization Algorithm*, arXiv:1411.4028 [K].
- Benjamini & Hochberg (1995), JRSS-B 57, 289–300, doi:10.1111/j.2517-6161.1995.tb02031.x [K]; Holm (1979), Scand. J. Stat. 6, 65–70 [K].
- Efron & Tibshirani (1993), *An Introduction to the Bootstrap*, Chapman & Hall [K].
- Duchi, Shalev-Shwartz, Singer & Chandra (2008), *Efficient projections onto the ℓ1-ball*, ICML, doi:10.1145/1390156.1390191 [K].
- Javadi-Abhari et al. (2024), *Quantum computing with Qiskit*, arXiv:2405.08810 [K].
