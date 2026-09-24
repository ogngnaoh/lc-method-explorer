# Model comparison protocol — fixed before model fitting

Experiment: `mcmrt-v3-compound-v1`, September 24, 2026. Exact candidate parameters and windows are in `config/experiment.json`; execution records its hash.

## Retention-time evaluation

Use the existing saved compound groups, 20% group holdout, and five development folds. Compare three Random Forest and three XGBoost configurations, plus the method-median baseline. Predict RT in minutes using the previously declared molecular and method features. Fit column one-hot encoding inside each fold; numeric features are finite and need neither scaling nor learned imputation. Unknown column categories fail explicitly. Use four CPU workers per fit, sequential candidate/fold runs, and fixed seeds. No early stopping on the final holdout.

Choose one configuration per family by pooled development out-of-fold MAE; tie-break by candidate ID. Choose the overall model by the same metric, including the median baseline. Candidate selection makes development scores optimistic; report final held-out performance separately. Retain all candidate results. No further tuning after final holdout scoring.

Report MAE, RMSE, median and 90th-percentile absolute error, equal-group mean MAE, and per-method errors. Add a paired group-bootstrap interval for the selected model's MAE improvement over the median baseline (2,000 replicates). This describes variation among sampled held-out compound groups with a fixed fitted model, not training/model-selection uncertainty or generalization to new laboratories.

## Recommendation task

The illustrative, prespecified windows are 2–5, 5–10, 10–20, and 20–40 minutes. They cover different timing needs; they are not claimed to be scientist-approved or optimal windows. Their endpoints are inclusive. Rank the 30 existing methods by:

1. Predicted distance outside the window (zero inside).
2. Predicted distance from window center.
3. Total method run duration.
4. Method ID for deterministic ties.

Use raw predictions; retain and report values outside physical bounds rather than silently clipping them. Method selection may place a compound inside a window without optimizing total assay throughput.

Primary ranking evaluation uses compounds with measurements for all 30 methods. It evaluates every window for each compound, including cases with no measured method in the window. Exclude incomplete panels from this primary metric rather than treating absent measurements as failures; report the excluded counts and scope explicitly.

Report top-1 hit rate, top-3 any-hit rate, observed feasibility (any of the 30 methods in the window), top-1 hit rate conditional on feasibility, and mean excess window distance: the selected method's measured distance minus the smallest measured distance among candidates. This last metric is zero when the selected method is as good as the measured oracle by window distance. The oracle is only an evaluation reference, never an input to ranking. Summarize by window and overall; overall equally averages compound/window cases.

Compare the RT models and method-median baseline with a simple window-specific fixed-method ranking. Learn that ranking on each training fold's complete panels, sorting methods by measured window hit rate, then mean distance outside the window, then duration and ID. Refit it using development data only for the final holdout. Report top-1 and top-3 for this comparator too. It tests whether personalized predictions improve on recommending the same methods to everyone.

## Final evaluation and artifacts

Freeze development selection and hashes before evaluating holdout labels. Refit each family's selected configuration on all development observations, evaluate all selected models plus baselines in one final pass, and save predictions, scores, provenance, and model artifacts. The deployment/demo model remains the development-selected winner even if a different family scores better on the holdout. Do not retrain it on holdout compounds for the interview demonstration.

Preserve the scientific limits: 343 source compounds, known methods, one source dataset; no claim of arbitrary-method optimization, mixture resolution, laboratory validation, or independent causal condition effects. Track the ten identifier quality flags and the multicomponent Vitamin B12 representation already documented in `BASELINE.md`.
