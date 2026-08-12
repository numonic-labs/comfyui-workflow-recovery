# Changelog

All notable changes to this project are documented here. This project adheres to
[Semantic Versioning](https://semver.org/). Published Registry versions are
immutable.

## [0.3.0] - Unreleased

### Added

- **`Save Image to Numonic`** and **`Save Video to Numonic`** graph nodes —
  drop-in replacements for the stock *Save Image* / *Save Video* that ingest the
  generated asset (real bytes, with ComfyUI lineage) into your Numonic library
  and return the gallery link.
  - Type-agnostic three-phase upload core (`upload_client.py`) against Numonic's
    dedicated ComfyUI ingest endpoints: `POST /comfy-lineage/asset/signed-url` →
    direct-to-storage `PUT` → `POST /import/comfyui/confirm-upload` → gallery
    link (`url`) returned by the server. Auth with a `write` or `comfy-ingest`
    scoped key. Friendly surfacing of `401/403` (key), `413` (storage full),
    `429` (rate).
  - Host-configured credential (`credential.py`): `NUMONIC_API_KEY` env or
    `~/.numonic/config.json` — never a node widget (no key leakage into saved
    workflows or output files). `NUMONIC_APP_URL` / `NUMONIC_API_URL` overrides.
  - Image: self-encode PNG with `prompt` + `workflow` tEXt chunks (mirrors
    `SaveImage`). Video: reuse ComfyUI's own `VIDEO.save_to()` PyAV primitive
    (workflow embedded), upload, then delete the temp file. Metadata is written
    exactly as native `SaveVideo` (top-level `workflow` + `prompt`) so Numonic's
    video extractor recovers lineage; guarded by a `save_to` presence check with
    a clear "update ComfyUI" message on older builds.

### Removed

- **Enhanced recovery** (hosted image-inspect) — `inspect_client.py`, the
  `POST /recover` route, the `inspect_url` / `enhancedRecoveryAvailable` config,
  and the sidebar checkbox. Local recovery and the sidebar lineage-save funnel
  are unchanged.

### Notes

- Zero runtime dependencies preserved (stdlib + ComfyUI-provided PIL/PyAV only).

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
