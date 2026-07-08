# Changelog

All notable changes to this project are documented here. This project adheres to
[Semantic Versioning](https://semver.org/). Published Registry versions are
immutable.

## [Unreleased]

### Added

- Initial node pack (staging build):
  - `Extract Workflow Lineage` graph node (local-first; opt-in enhanced recovery).
  - Sidebar tab: drop an image → recovered prompts / models / LoRAs / custom
    nodes / seed / sampler.
  - Three server routes under `/numonic/workflow-recovery`: `status`,
    opt-in `recover` (enhanced), opt-in authenticated `save`.
  - Local, zero-dependency PNG metadata reader (`tEXt` / `zTXt` / `iTXt`).
  - GitHub Actions: CI (`comfy node validate` + unit tests) and Registry
    publish on release.
  - MIT license, contribution model, OSS-cleanliness release gate.

_This 0.1.0 is a review-ready staging build. It has not been published to the
ComfyUI Registry — see `PUBLISH_CHECKLIST.md` for the gated go-live steps._
