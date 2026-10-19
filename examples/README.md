# Examples

> **Status:** stub
> **Owner:** unassigned
> **Last reviewed:** 2026-06-01

End-to-end worked sessions running against **synthetic** data. These examples
exercise the pipelines documented under `modalities/*/processing.md` so new
collaborators have a runnable reference.

## Constraints

- **Synthetic data only.** No real subject data, ever. See
  [docs/data-governance.md](../docs/data-governance.md).
- Examples must run end-to-end without external configuration beyond what is
  documented inline.

## Planned examples

- `cv_zedbox_single_subject/` — one synthetic CV session through pose extraction
- `physio_multi_device/` — one synthetic session with E4 + EmotiBit, time-aligned

## TODOs for collaborators

- [ ] Generate synthetic data fixtures for each modality
- [ ] First worked example for CV (Phase 2)
- [ ] First worked example for physio (Phase 2)
