# simcenter-sensing

Unobtrusive measurement methods for simulation-center research: hardware setup,
data collection protocols, troubleshooting, storage, and processing pipelines
across multiple sensor modalities.

## Status

This repository is in **Phase 0 — scaffolding**. Structure and conventions are
being established; content is being drafted modality by modality. See
[docs/scope.md](docs/scope.md) for what does and doesn't belong here, and the
phased plan below.

## Modalities

| Modality          | Status      | Priority | Notes                                         |
|-------------------|-------------|----------|-----------------------------------------------|
| Computer vision   | drafted     | high     | Current platform: ZedBox. Intel cameras archived. |
| Physiology        | stub        | high     | Empatica E4, EmotiBit. BioRadio deferred.     |
| Eye tracking      | drafted     | medium   | Tobii Pro Glasses 3.                          |
| Communication     | drafted (planning) | low | Phase 4. Stack planned; awaiting pilot.       |

Status legend: `not started` → `stub` → `drafted` → `reviewed` → `complete` (or `archived`).

## Repository layout

```
docs/                  Cross-cutting conventions (IDs, time sync, storage, governance)
modalities/
  _template/           Copy this when starting a new modality or section
  computer-vision/     ZedBox-based CV; legacy Intel-camera work under _archive/
  physiology/          E4, EmotiBit (devices/ subdir per device); BioRadio deferred
  eye-tracking/        Tobii (placeholder)
  communication/       Audio + transcript-based analysis (placeholder)
shared/                Cross-modality code (LSL bridges, time sync, QA)
tools/                 Dev/ops utilities (LSL test outlets, .xdf checker)
examples/              End-to-end worked sessions (against synthetic data)
STAGING/               Private workspace; gitignored except for README
```

## For collaborators

See [CONTRIBUTING.md](CONTRIBUTING.md) for:

- The **PHI/PII checklist** (mandatory before every push)
- The **section status** convention
- How to claim a `TODO(@you)` marker
- The modality scaffolding template

## Data

**No subject data lives in this repository.** Raw and derived data are stored
outside the repo per study; see [docs/storage.md](docs/storage.md) and
[docs/data-governance.md](docs/data-governance.md).

## Phased plan

- **Phase 0** — Scaffolding, conventions, templates. _(current)_
- **Phase 1** — CV and physiology: first drafts of docs from existing fragments.
- **Phase 2** — Processing code migration for CV and physiology.
- **Phase 3** — Eye tracking (Tobii).
- **Phase 4** — Communication analysis.

## License

MIT — see [LICENSE](LICENSE).
