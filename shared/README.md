# Shared utilities

> **Status:** stub
> **Owner:** unassigned
> **Last reviewed:** 2026-06-01

Cross-modality code used by more than one modality's processing pipeline.

## Planned contents

- [`lsl_bridges/`](lsl_bridges/README.md) — Custom Lab Streaming Layer
  outlets for devices without native LSL support (ZED frame markers, room
  mic, Tobii if needed; BioRadio deferred). See
  [`docs/time-sync.md`](../docs/time-sync.md) for the three-layer sync
  architecture these fit into.
- `time_sync/` — Layer 1 sync-marker detection across modalities, Layer 3
  drift modeling for record-then-download devices, per-session sync report.
- `identifiers/` — Filename parsing/composing against the
  [identifiers convention](../docs/identifiers.md).
- `qa/` — Generic QA report scaffolding.

## Languages

R and Python both supported. Keep functionally equivalent versions in parallel
subdirectories (`shared/R/...`, `shared/python/...`) when both are needed.

## TODOs for collaborators

<!-- TODO(unassigned): Decide migration vs. vendoring strategy for tpd's `1_funcs_generic.R` sync helpers — see project memory project_tpd_upstream -->

- [ ] Migrate canonical sync helpers from tpd (or treat tpd as upstream)
- [ ] Implement filename parser/composer against identifiers.md
- [ ] Generic QA report template
