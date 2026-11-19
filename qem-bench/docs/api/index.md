# API reference

Generated with `mkdocstrings` (install the `docs` extra). Key entry points:

- `qem_bench.config.load_config(profile, config_dir)` → `ExperimentConfig`
- `qem_bench.circuits.build_instance(InstanceSpec)` → `BenchmarkCircuit`
- `qem_bench.execution.runner.compile_instance(...)`, `ConditionRunner.run_rep(shots, rep, labels)`
- `qem_bench.execution.simulator.NoisySimulator(spec, mode)`
- `qem_bench.mitigation.readout.ReadoutCorrector`, `qem_bench.mitigation.zne.{fold_global, fold_local, extrapolate}`
- `qem_bench.experiments.runner.run_experiment(cfg, out_root, resume=None)`, `experiments.validation.validate_run`
- `qem_bench.analysis.{aggregation.aggregate, comparisons.paired_comparisons, pareto.pareto_table, hypotheses.evaluate_all}`
- `qem_bench.metrics.efficiency.{resource_efficiency, improvement_factor, work_normalized_mse_ratio}`

::: qem_bench.metrics.efficiency
