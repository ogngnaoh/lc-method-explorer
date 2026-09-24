# Release verification

Verified September 24, 2026 on macOS / Apple M2 Pro. This records the scope of the checks, not independent laboratory validation.

| Check | Evidence |
|---|---|
| Frozen experiment | Original code, configuration, root lockfile and prepared-input provenance match the saved selection record. Model and selection hashes match the final evaluation. |
| Saved inference | All 2,047 holdout predictions per model reproduce within the declared numeric tolerance. Measured labels, group membership and MAE reconcile with the saved outputs. |
| Automated checks | Nine experiment tests and four demo tests pass, both in the working directory and in a clean copy with freshly installed locked environments. |
| Model installation | Original five-file archive installs into the clean copy and matches every committed checksum. Corrupt archives are rejected and changed local artifacts are preserved. |
| Static presentation | All three new diagrams/charts inspected as PNGs, with SVG equivalents. The 16-second GIF contains three captured app states and links to static fallbacks. |
| README | 508 words including alt text/link labels. GitHub-rendered Markdown reviewed at desktop and 390 px mobile widths; embedded images load and the text layout has no horizontal overflow. Images open at full resolution for detail. |
| Local app | Prediction, measurement reveal, method details and evidence views inspected. Updated chart shows all ten method labels. Browser warning/error log is empty. Mobile evidence layout checked. |
| Slides | Five-slide PowerPoint passes package, geometry, font, editable-table and editable-chart checks. Each rendered slide and each page of the static companion PDF inspected. No claim of native PowerPoint application testing. |
| Publication boundary | Explicit public file list reviewed. Personal planning/interview documents, application references and private presentation remain outside version control. Public slide notes reviewed. |

The visual direction uses teal, white space and dark neutral typography inspired by the [Merck research site](https://www.merck.com/research/). This project uses no Merck logo or proprietary typeface and has no employer affiliation.

These checks establish a same-machine clean-copy installation and frozen-artifact reproduction. They do not establish independent hardware/OS reproduction, a fresh laboratory study, calibrated prediction intervals or new-method generalization. The optional full model-refit procedure is documented separately from loading the original release artifacts.

## Public download check

The public GitHub repository was cloned into a new directory. Both locked environments installed successfully. The model bundle downloaded from the public release, all five file checksums matched, frozen-output verification passed, and all nine experiment plus four demo tests passed again.

This check exposed a missing CA configuration in the standalone Python installation. The v0.1.1 setup fix uses system curl with HTTPS certificate validation enabled, consistent with the dataset downloader. It changes no scientific code, model files or reported results. The original model bundle remains attached to v0.1.0 and referenced by the committed manifest. Use current main or v0.1.1 for the corrected setup script.

The public repository page and all embedded README images were checked on GitHub. The published commit and reviewed local Git tree match.
