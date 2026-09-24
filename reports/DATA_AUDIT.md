# MCMRT V3 data feasibility

## Decision

MCMRT supports an MVP predicting retention time for unseen compounds under known LC methods and ranking those methods for a target retention window. All required condition axes are represented. This is a data-feasibility conclusion, not evidence of predictive performance.

## Source and reuse

- Dataset DOI: https://doi.org/10.57760/sciencedb.15823
- Publisher record: https://www.scidb.cn/en/detail?dataSetId=7b1a8766e1e947e1884707f6a1016e4f
- Paper: https://www.nature.com/articles/s41597-024-03780-5
- Dataset license: CC0 1.0, recorded in both the publisher's structured dataset record and DOI metadata. The article's license is separate.
- All 30 original workbooks downloaded: 2,380,456 bytes. Every file matches the publisher's MD5. A SHA256 manifest records the exact local inputs and verification timestamp.
- Originals are under `data/raw/mcmrt/`; publisher metadata and manifest are under `data/source/`.

## Verified coverage

| Item | File-level finding |
|---|---|
| Methods | 30 |
| Numeric positive RT observations | 10,073 |
| Source compound IDs | 343; chemical canonicalization still pending |
| Compounds with all methods | 330 |
| Remaining coverage | Five compounds in 25 methods; eight in six methods |
| Missing compound–method pairs | 217 out of 10,290 possible pairs |
| Column products | Six within the reversed-phase C18 family |
| Mobile-phase A/B pairs | Six after whitespace normalization |
| Time/%B schedules | 15 distinct schedules, including re-equilibration |
| Column temperatures | 30, 40, 45 °C |
| Total run times | 10–100 minutes |
| Observed retention times | 0.59–74.09 minutes |

Every workbook contains RT and LC setups sheets. Checked: expected RT headers, unique compound IDs within each method, consistent stripped SMILES/InChI strings for each source ID, positive numeric RT, numeric gradient entries, increasing time, positive flow, and %B within 0–100. No failures in these checks. These checks do not establish molecular validity or correctness of the underlying experiments.

## Import and modeling decisions

1. Preserve originals. Normalize whitespace in derived tables; do not silently overwrite structures.
2. Parse column dimensions explicitly because their ordering varies. Retain original text beside normalized units.
3. Preserve full time/flow/%B schedules. Compute actual solvent fractions using phase A and B compositions rather than treating %B as organic percentage.
4. Missing pairs remain unobserved. Do not impute RT labels. Evaluate complete-panel ranking on held-out members of the 330-compound panel; report partial-panel coverage separately.
5. Retention factor and RSD are measurement-derived fields, excluded from predictor inputs. Audit their quality separately if used for diagnostics. Decide whether to use measured dead time only with an explicit calibration assumption; default to excluding it from the initial feature set.
6. Group standardized compound identities across all methods before splitting. Source IDs alone are an initial audit convenience.
7. Start with known-method recommendations. The design is not fully factorial, and only 30 methods are available. Do not infer causal condition effects or arbitrary-method generalization.

## Reproduction and remaining work

`python scripts/download_mcmrt.py` retrieves and verifies the pinned file list using Python standard libraries and curl. `python scripts/audit_mcmrt.py` verifies SHA256 hashes and regenerates `reports/data_audit.json`; it requires openpyxl. This audit used the available bundled openpyxl runtime without installing project dependencies. A project environment will be pinned in phase 2.

At completion of this initial audit, RDKit validation/canonicalization, structure-identity collision checks, normalized method tables, split protocol, and model evaluation were pending. Phase 2 has since completed chemical validation, normalized tables, fixed splits, and a development median baseline; see `BASELINE.md` for subsequent findings. Tree models and final evaluation remain pending.
