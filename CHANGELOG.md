# Changelog

All notable changes to this project are documented here. This project adheres to
[Semantic Versioning](https://semver.org/). Published Registry versions are
immutable.

## [0.1.0] - 2026-07-08

### Added

- Initial node pack:
  - `Extract Workflow Lineage` graph node (local-first; opt-in enhanced recovery).
  - Sidebar tab: drop an image → recovered prompts / models / LoRAs / custom
    nodes / seed / sampler.
  - Three server routes under `/numonic/workflow-recovery`: `status`,
    opt-in `recover` (enhanced), opt-in authenticated `save`.
  - Local, zero-dependency PNG metadata reader (`tEXt` / `zTXt` / `iTXt`).
  - GitHub Actions: CI (`comfy node validate` + unit tests) and Registry
    publish on release.
  - MIT license, contribution model, OSS-cleanliness release gate.
  - Icon and banner assets.
