# Reproducible baseline — September 24, 2026

This report preserves the phase-2 milestone. Subsequent tree-model and final holdout results are in [MODEL_RESULTS.md](MODEL_RESULTS.md).

## What was completed

The local pipeline verifies the original files, validates structures, extracts molecular descriptors and method settings, fixes compound-grouped splits, and evaluates a simple reference predictor using development data only.

All 343 supplied SMILES parse in RDKit. There are 341 conservative grouping keys: source IDs 162/163 and 167/168 share groups. Groups derive from RDKit ChargeParent, removal of stereochemistry/isotope/atom-map labels, and HetAtomTautomerv2 hashing. This is a leakage-control convention, not proof of identical chromatographic behavior or a simulation of ionization at a given pH. Descriptors retain the supplied molecular representation.

## Data quality findings and resolutions

- Three source InChIs (68, 273, 319) contain leading nonbreaking spaces. Trimming resolves their initial parse failures. Original values remain preserved.
- An initial attempt to compare canonicalized tautomers encountered enumeration limits on large molecules. The final grouping uses deterministic tautomer hashing instead. Initial diagnostics were not experimental performance results.
- All 343 supplied/generated InChIKeys agree on their first connectivity block. Ten differ in secondary layers: IDs 28, 50, 61, 79, 93, 149, 162, 248, 293, 334. These are retained as quality flags with both keys, not silently corrected. The selected 2D descriptors do not encode stereochemistry; the MVP does not resolve these stereochemical ambiguities.
- Vitamin B12 (341) has a disconnected multicomponent representation. Retain its supplied structure for descriptors; the grouping key uses its charge parent. No observations were excluded.
- Source formulas match RDKit formula strings for all compounds.

## Features

21 molecular features include molecular weight, logP, polar surface area, hydrogen-bond donors/acceptors, ring counts, flexibility, topology, and formal charge. The explicit list is in `chromrt/chemistry.py`.

61 numeric method fields plus column product category capture dimensions, temperatures, solvent/additive compositions, run duration, and seven ordered gradient knots. Each knot includes time, flow, %B, and actual solvent fractions. Six-knot methods repeat their last knot; a separate count records how many are real. This preserves schedules for known methods; it is not a validated representation for arbitrary unseen programs.

Measured retention factor, measured dead time, and RSD are excluded from predictors. Method ID is used only to define the method-median baseline, not as a planned feature of the condition-aware models. Feature names are explicitly enumerated in `data/processed/feature_schema.json`.

## Fixed evaluation protocol

- Random seed: 20260924.
- Holdout: 69 of 341 groups (70 source compounds; 2,047 observations).
- Development: 272 groups (273 source compounds; 8,026 observations).
- Five shuffled group folds within development data. All methods and variants in a group stay together.
- Splits are saved and reruns refuse to replace changed assignments or changed prepared inputs. At this phase-2 milestone, holdout labels were present in source data, but final holdout evaluation had not been performed. The later completed evaluation is documented in MODEL_RESULTS.md.
- No target-derived feature or learned preprocessing has been fitted across folds.

## Actual development result

For each validation compound, the baseline predicts the median retention time of training compounds measured under that method. It uses no chemical information.

| Metric | Five-fold development out-of-fold result |
|---|---:|
| Mean absolute error | 4.8531 min |
| Root mean squared error | 7.1418 min |
| Median absolute error | 3.2900 min |
| 90th-percentile absolute error | 10.8950 min |
| Mean of within-group MAEs | 4.8245 min |

Method-specific MAE ranges from 1.3615 min (M01) to 16.2542 min (M16), illustrating why a single pooled number is insufficient across methods with different run durations. This is a baseline reference, not evidence that a chemical model works. At this milestone, tree models and final evaluation were still pending; MODEL_RESULTS.md records their subsequent completion.

Machine-readable results, all development predictions, and per-method errors are under `reports/baseline/`. The metrics record includes package versions, source-code hashes, lockfile hash, split hash, timestamp, and measured runtime. This median calculation is very fast; its runtime does not estimate tree-model training time.

## Checks

Focused tests cover grouping of salts/stereoisomers/tautomers, malformed input, dimension order, premixed solvent fractions, variable flow, group separation, deterministic splits, and validation-label independence of baseline predictions. The integration check reconciles all prepared records and verifies finite features and the input/target boundary.

## Technical references

- RDKit standardization: https://www.rdkit.org/docs/source/rdkit.Chem.MolStandardize.rdMolStandardize.html
- RDKit molecular hashing: https://www.rdkit.org/docs/source/rdkit.Chem.rdMolHash.html
- Grouped validation: https://scikit-learn.org/stable/modules/cross_validation.html
