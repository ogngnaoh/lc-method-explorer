# Model and demo card

## Intended use

A local research demonstration of retention-time prediction and ranking among 30 fixed MCMRT V3 methods. Audience: a reader inspecting the scientific evidence and implementation. It supports single-molecule target-window exploration, not validated laboratory decisions.

## Data and evaluation

10,073 observations, 343 source compounds, 341 conservative structure groups, 30 methods. Source: MCMRT V3, DOI 10.57760/sciencedb.15823; the dataset record specifies CC0. See DATA_AUDIT.md for method coverage and preparation.json for chemical identifier caveats. The supplied structure generates 21 molecular descriptors; method features cover the column, temperature, solvents, additives, and gradient knots. Missing compound/method measurements are not imputed as labels.

All methods for a compound group stay in one partition. Development: 273 compounds/272 groups/8,026 rows; five grouped folds. Final holdout: 70 compounds/69 groups/2,047 rows. Grouping removes stereo/isotope distinctions and uses parent/tautomer equivalence; this is not scaffold separation. The fitted artifacts use development compounds only.

Six tree-model candidates were compared. XGBoost depth 5 was selected by development MAE and remains the interface default. Holdout MAE: 2.16 min for XGBoost, 1.89 for Random Forest, 4.84 for the method-median baseline. No model was selected using these holdout results. Full results and uncertainty definition: MODEL_RESULTS.md. The holdout has been evaluated and cannot be reused as an untouched test.

## Recommendation behavior

The interface builds candidates for all 30 known methods, predicts raw retention times, and sorts by distance to the target window, distance to its center, run duration, and method ID. It joins measured truth only after ranking. Missing measurements stay empty. The illustrative 5–10 min initial window and Pirimicarb example are interface defaults, not new evaluation results. The four prespecified evaluation windows and 67 complete panels remain fixed in the Evidence tab.

New SMILES get descriptors under the same pinned RDKit version. The interface detects overlap with existing structure groups and labels it. It never attaches measured truth to a new SMILES input by approximate grouping. There is no applicability-domain score or calibrated individual prediction interval.

XGBoost made 14 negative holdout predictions. The demo preserves these values, labels them invalid, and warns users; it does not clip or silently rerank them. Values after the run end are also flagged. Changing this behavior would be a separately evaluated policy change.

## Limitations

Only unseen compound groups under familiar measured methods have been tested. Unseen methods, different instruments/labs, novel scaffolds, mixtures, resolution, peak shape, sensitivity, and optimization of arbitrary continuous settings are not validated. A selected-model ranking hit rate of 64.2% versus the fixed rule's 63.1% is a modest descriptive improvement, not evidence of laboratory time savings. Runtime efficiency is measured on this M2 Pro/16 GB machine, not a general benchmark.

## Local operation

The interface reads prepared tables and trusted locally fitted models. At startup it checks model, code, configuration, and prepared-input hashes against the frozen experiment. Its separate demo/uv.lock preserves root experiment provenance. No training runs in the interface; no cloud inference service is used. Start from demo/ to apply its loopback-only and telemetry-off configuration. Do not expose this research demo as a public service without a separate deployment review. See README.md for setup and artifact recovery.
