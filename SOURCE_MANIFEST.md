# Source and provenance manifest

This manifest records the provenance of public claims in the interactive project page for *Multiple Recovery Paths in a Lesioned Transformer: Internal Rerouting and Readout Remapping*. It distinguishes the primary-run representation analysis from later multi-seed controls and records known manuscript inconsistencies rather than silently selecting values.

## Public metadata

| Displayed claim | Authority | Status |
|---|---|---|
| Title and authors: Lorenzo Cannata and Uri Hasson | BlackboxNLP 2026 accepted-papers page | Verified 2026-10-23 |
| Venue: BlackboxNLP 2026 Main Track, paper/poster #192 | BlackboxNLP 2026 program | Verified 2026-10-23 |
| Workshop: October 29, 2026, co-located with EMNLP 2026 in Budapest | BlackboxNLP 2026 program | Verified 2026-10-23 |
| Affiliations, DOI, proceedings PDF, public code URL | No authoritative public record located | Intentionally omitted |

Official source: <https://blackboxnlp.github.io/2026/accepted_papers/>

## Manuscript inspected

- Local source: `/Users/lars/coding/mech-interpretability/neurorecovery/references/192_Multiple_Recovery_Paths_in.pdf`
- SHA-256: `6938ef737b0d7c9e007822957e4198ea19b98fea43a529f4f7846119879f04b7`
- PDF creation date: 2026-07-18
- Status: anonymous submitted draft; it is not copied into the public site.
- Relevant locations: abstract and Figure 1 (pp. 1–2), methods and condition table (pp. 3–4), endpoints and geometry (pp. 5–8), lesion appendix and Table A1 (pp. 10–11).

## Primary experiment

| Field | Record |
|---|---|
| Experiment | `legacy_sequential/legacy_paper_seq_v2` |
| Seed | 42 |
| Code commit | `3074adce0c39d07cc294d4deb6b706210ae0ca9b` |
| Evaluation | UD English-EWT development split; 2,001 sentences; 25,147 syntactic word tokens |
| Backbone | `bert-base-uncased` |
| Task | Linear 17-way universal POS readout |
| Damage mode | `legacy_headwise_dense` |
| Selection threshold | strict Q/K/V head-group sparsity `< 0.5`; dense projection sparsity `< 0.5` |
| Permanent gate score | `-12.0`, with gradient blocking |

Local configuration: `configs/recovery_legacy_paper.yaml`  
SHA-256: `5cbc40c2ee6c8fa8b366f2959384fb02c4f76c021967d92e9a06ec9c3ea2e51c`

Primary endpoint table: `/Users/lars/Desktop/wd/mechint/representations/final_results/tables/endpoint_summary.csv`  
SHA-256: `01744f907a206dafd6d0def725e99908ae2ffbcd4927baf78f796d28d95b0d74`

Checkpoint metrics: `/Users/lars/Desktop/wd/mechint/representations/metrics.csv`  
SHA-256: `6bc038cad1418b2d6d4567baf290062321ab0477d7ed9738cc7a8485ddb652d5`

The public copy of the primary endpoint values is `assets/data/site-data.json`. The plotted checkpoint copy is `assets/data/checkpoint-trajectories.csv`.

## Primary-run endpoint values

All accuracies are held-out development-token accuracy percentages. CKA values use the same ordered development tokens and raw 768-dimensional final hidden states.

| Condition | Accuracy | CKA to core | CKA to damage | POS-centroid RDM to core | Readout RDM to core | Trainable after lesion |
|---|---:|---:|---:|---:|---:|---|
| Core | 94.985485 | 1.000000 | 0.433569 | 1.000000 | 1.000000 | Gates + readout during core learning |
| Damaged | 16.829045 | 0.433569 | 1.000000 | 0.325838 | 1.000000 | None |
| Gates only, no penalty | 56.527618 | 0.529046 | 0.845590 | 0.559458 | 1.000000 | Surviving gates |
| Gates only, sparse | 53.358253 | 0.509324 | 0.873131 | 0.521516 | 1.000000 | Surviving gates |
| Gates only, density-promoting | 69.741918 | 0.604650 | 0.764097 | 0.642498 | 1.000000 | Surviving gates |
| Readout only | 80.001591 | 0.433569 | 1.000000 | 0.325838 | 0.539025 | Linear POS readout |
| Gates + readout | 85.879031 | 0.514219 | 0.872295 | 0.528725 | 0.689791 | Surviving gates + readout |
| Encoder only | 92.317175 | 0.787886 | 0.305340 | 0.506665 | 1.000000 | Surviving encoder weights |

`Readout only` and `Damaged` have identical encoder metrics by construction. The empirical readout panel uses 816 POS-balanced tokens from `activation_panels/token_projection_scores.csv`: one PCA basis fitted on the core final-layer states is applied to every condition, damaged and readout-only coordinates match exactly, and PC1-PC2 explain 23.32% of variance. Actual correctness rises from 49/816 under the original readout to 521/816 under the retrained readout. The visual deliberately shows no 2D boundary because the measured classifier is 17-way in 768 dimensions.

The interactive representation explorer uses those same 816 token identities for six actual final states: core, damaged, density-promoting gates-only, readout-only, gates+readout, and encoder-only. Its axes always use the core state’s PC1/PC2 range; the plot does not refit or rescale individual conditions. Full-development-set accuracy is shown separately from accuracy on the deliberately POS-balanced panel.

Empirical projection provenance:

- Cached source: `/Users/lars/Desktop/wd/mechint/activation_panels/token_projection_scores.csv` (SHA-256 `e1bcb41e83f82fc56eb785abdde6e0212ec1f730ac476eefac732dd6643890e8`).
- Public paired export: `assets/data/readout-empirical.csv` (SHA-256 `0f0db87a94237206d136d107a6783b80810d21e3398844550cccdead998581aa`).
- Interactive six-state export: `assets/data/representation-states.json` (SHA-256 `109ad094bbea378f8d06f1b5d368cbc50dbf82be8f103e0d8b2487317573142a`).
- Shared website/poster figure: `assets/plots/readout-remapping-empirical.svg` (SHA-256 `13d22a86e3c5e0928799464be4908f6e9be89aa37d1d6f45e73ae75bbead4909`).

## Lesion identity and granularity

The implementation uses input-feature gates broadcast across each linear projection's output rows. Q/K/V gate values are summarized in 64-coordinate, head-sized groups for lesion selection. These groups must not be described as conventional attention-head-output ablations.

- 74 selected Q/K/V head-sized groups: all 12 groups in layers 0–5 and two in layer 6.
- 18 selected dense projection-mask tensors: 5 attention-output, 9 FFN-intermediate, and 4 FFN-output.
- 37,248 clamped gate entries in the complete Q/K/V+dense lesion.
- The site schematic is deliberately labelled as a schematic; its flow marks are explanatory, not measured activations.

Implementation sources: `model/masked_linear.py`, `model/masked_bert.py`, and `damage.py`.  
Audit source: `reviewer_response_artifacts/reviewer_response_report.md` (SHA-256 `5dfb702adaa5058f0208e6e3683a7b3ab548a7ab133a6ef40d889a22af60685c`).

## Five-seed recovery control

Source bundle: `/Users/lars/Desktop/wd/mechint/reviewer-controls/seed-replicates/paper_seed_stability_n5.tar.gz`  
Bundle SHA-256: `cca8cbcdfa7697c14d9fb1aac93154737c31cff8a1fb55d152706b4f89cea80d`

Seeds 42–46 are displayed individually from `seed_endpoints_long.csv` inside the bundle. All five runs preserve this ordering:

`Core > Encoder only > Gates + readout > Readout only > Gates only (dense) > Gates only (no penalty) > Gates only (sparse) > Damaged`

The website reports individual points, observed ranges, and arithmetic means. It does not label two- or five-seed summaries as confidence intervals. Mask-only and damaged endpoints show materially larger across-seed ranges than core, encoder-only, readout-only, and joint recovery.

## Random-lesion controls

Source report: `reviewer_response_artifacts/reviewer_response_report.md`.

| Control | Learned/target | Random mean | Random range | Count relative to target |
|---|---:|---:|---:|---:|
| Q/K/V-only lesion | 84.84 | 88.02 | 86.03–89.78 | 0/100 as or more damaging |
| Full lesion, learned dense targets fixed | 16.83 | 20.57 | 16.65–25.16 | 5/100 as or more damaging |
| Full lesion, randomized Q/K/V + dense | 16.83 | 16.33 | 8.71–36.33 | 63/100 as or more damaging |
| Keep only selected Q/K/V+dense set | 29.57 | 10.27 | 8.13–23.70 | 0/100 as good or better |

The Q/K/V-only control is not used as a control for the severe Q/K/V+dense lesion. The complete randomized lesion weakens any claim that the exact full dense target set is uniquely causal.

## Figure mapping

| Public asset | Displayed data | Generation evidence |
|---|---|---|
| `assets/plots/checkpoint-trajectory.{png,pdf}` | Actual 20-epoch checkpoints: accuracy, CKA, effective rank, activation energy, POS-centroid RDM | `figures_updated/evidence/figure5_checkpoint_trajectory_long.csv`; source `metrics.csv` |
| `assets/plots/head-sparsity.{png,pdf}` | Baseline, damaged, and difference Q/K/V head-group sparsity | `figures_updated/evidence/figure2_head_sparsity_{baseline,damaged}.csv` |
| `assets/plots/layer-gate-usage.{png,pdf}` | Layer lesion effect and mean Q/K/V active fraction | `figures_updated/evidence/figure4_layer_importance_head_usage_long.csv` |
| `assets/plots/per-tag-recovery.{png,pdf}` | Per-tag accuracy as percent of each tag's core accuracy | `figures_updated/evidence/per_tag_accuracy_long.csv` |
| `assets/plots/random-lesion-controls.png` | Q/K/V-only and full-lesion random controls | reviewer control bundles summarized above |
| `assets/figures/recovery-paths-poster.{svg,pdf,png}` | A0 poster: five-seed accuracy summary, primary-seed CKA, fixed-representation readout comparison, and matched random-lesion controls | `assets/data/site-data.json`; `assets/data/readout-empirical.csv`; reviewer control report |
| `assets/figures/poster-recovery-performance.svg` | Five-seed endpoint means, individual runs, and observed ranges | `assets/data/site-data.json` |
| `assets/figures/poster-accuracy-cka.svg` | Primary-seed accuracy versus linear CKA to the pre-lesion core | `assets/data/site-data.json` |
| `assets/figures/poster-readout-remapping.svg` | Same 816 token coordinates with original versus retrained readout correctness | `assets/data/readout-empirical.csv` |

The plot evidence manifest is `figures_updated/evidence/manifest.json`. It records transformations, original server paths, evaluation counts, thresholds, and the experiment commit. Missing values were not mocked by the figure generator.

### A0 poster aggregation contract

- Recovery accuracy uses arithmetic means over full-pipeline seeds 42-46; circles are individual seeds and whiskers are observed ranges, not confidence intervals.
- Accuracy-versus-CKA uses the primary seed because the corresponding matched hidden states are available for that run.
- Readout remapping uses the fixed 816-token POS-balanced subset in a single core-fitted PCA basis; subset correctness is labelled separately from full-development accuracy.
- Random controls show the global QKV-only intervention and the fully randomized QKV+dense intervention as distinct experiments.
- The poster contains no QR code because no canonical public project URL is verified.

Final A0 artifact checksums (2026-10-23):

- PDF: `1db1f8e8f572696389afbd08375402e5c53d552928c045a220309755400f1d0a`
- SVG: `9aca27e52924a3ee7aec0c1927fefcbe4d0ed2d1de4c246384d90e645030f01d`
- PNG: `a831e2ab1c855307fc1efa80b793643f95f45918263cc4176dc6bb8944257425`

## Resolved manuscript discrepancies

| Conflict | Resolution |
|---|---|
| 94.5% in Results vs. 95.0% in abstract/Table A1 | Primary record is 94.985485%; display 94.98% or rounded 95.0%. The 94.5% sentence is stale. |
| 88% joint recovery in Figure 1 caption vs. 85.9% elsewhere | Primary record is 85.879031%; display 85.87% or rounded 85.9%. The 88% caption is stale. |
| “Attention-head lesion” shorthand | Use “Q/K/V head-sized input-feature groups plus dense projection-mask tensors.” These are not true head-output ablations. |

## Remaining unresolved public items

- Author affiliations.
- Final proceedings or camera-ready PDF URL.
- DOI or anthology identifier.
- Public repository URL (the configured Git remote could not be independently verified as public).
- Canonical GitHub Pages URL; therefore no final-looking QR code is included.

Update these only from an authoritative public record. After a canonical HTTPS URL exists, run `scripts/generate_qr.py`; it refuses placeholders and decodes the generated PNG before reporting success.
