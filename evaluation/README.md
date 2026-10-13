# Evidence support evaluation

The installed implementation and immutable dataset live in `src/researchflow/evaluation/`. Each split has twelve independent original SciFact claim/document pairs, with four SUPPORT, four CONTRADICT and four not-enough-information labels. Claims and documents do not cross splits. Six or more contradiction probes retain original numeric/condition errors; no model-authored gold is added.

Original release: https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz
Original schema and licenses: https://github.com/allenai/scifact/blob/master/doc/data.md and https://github.com/allenai/scifact/blob/master/LICENSE.md
Citation: Wadden et al. (2020), Fact or Fiction: Verifying Scientific Claims. https://aclanthology.org/2020.emnlp-main.609/
Claims/annotations: CC BY4.0. Abstracts: ODC-By1.0. The original archive and selected row/document hashes are recorded in the manifest.

`uv run researchflow evaluate --split development --mode contract --output artifacts/eval-contract`

Contract mode uses seeded labels to exercise the actual verifier and metric code. It always reports `quality_measured=false`; its numbers are not model quality. Live mode uses the configured provider with the full abstract; neither the gold label nor gold rationale is placed in the prompt. This measures verification on supplied abstracts, not end-to-end RAG retrieval.

`uv run researchflow evaluate --split holdout --mode live --output artifacts/eval-holdout`

Missing credentials produce `not_run` and exit2, never a passing score. Failed and inconclusive predictions remain in the fixed denominator. Precision is null when nothing is predicted supported. Every false support is listed in errors.json, along with all other errors. A supported precision of0.90 is a target; it has not been measured without a live provider.

Only development cases may guide strategy changes. Freeze the strategy before opening/running holdout. A changed strategy creates a new experiment; repeated use of holdout must be disclosed and is no longer an untouched generalization estimate.

Rebuild the exact dataset from the frozen archive with `uv run python -m researchflow.evaluation.prepare_scifact PATH_TO_DATA_TAR_GZ`. Any unexpected archive hash is rejected. Extraction reads selected JSONL members, never extracts arbitrary filesystem paths.
