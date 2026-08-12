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

### Fixed

- **Seed recovery on modern Flux / custom-sampling workflows.** Local recovery
  read the seed only from the classic `KSampler.seed` input, so workflows using
  `RandomNoise` → `SamplerCustomAdvanced` (the dominant Flux pattern, incl.
  Flux 2) reported `seed: null` even though the seed was embedded in the image.
  `lineage.py` now also reads `RandomNoise.noise_seed`. Verified against a real
  Flux 2 dev generation. Classic `KSampler` recovery is
  unchanged. A `noise_seed` supplied via a *link* from another node still does
  not resolve (graph-link following remains out of scope).

- **Core ComfyUI nodes are no longer mis-reported as custom nodes.** The
  `custom_nodes` list was matched against a hand-maintained set of built-in
  `class_type` names that predated the Flux / custom-sampling era, so on the
  stock ComfyUI Flux 2 template *every* built-in — `RandomNoise`,
  `KSamplerSelect`, `SamplerCustomAdvanced`, `FluxGuidance`, `Flux2Scheduler`,
  `EmptyFlux2LatentImage`, the `Primitive*`/`ComfySwitchNode` helpers — was
  listed as third-party (10 out of 10 false positives). Classification now
  derives the built-in set from the image's own UI workflow graph, which stamps
  each node with `properties.cnr_id` (`"comfy-core"` for built-ins), walking
  subgraph definitions too. This cannot go stale as ComfyUI adds core nodes.
  Images carrying no workflow chunk fall back to the previous static list.

### Removed

- **Enhanced recovery** (hosted image-inspect) — `inspect_client.py`, the
  `POST /recover` route, and the `inspect_url` / `enhancedRecoveryAvailable`
  config. Local recovery is unchanged.
- **The browser sidebar panel**, in full. `web/` (the frontend extension and its
  CSS), `save_client.py`, `routes.py` (both the `GET /status` and
  `POST /save` routes), and the `WEB_DIRECTORY` registration are all gone; the
  pack now ships **graph nodes only** and registers no server route. Rationale:
  the panel duplicated `Extract Workflow Lineage` — it was a second, untested
  reimplementation of the parser in JavaScript that had to be kept in lockstep
  with `lineage.py` — and its one unique affordance, the lineage-save button,
  targeted an endpoint that was never deployed. Recovery is unchanged: point the
  node at an image and wire its outputs to a text-preview node, exactly as the
  save nodes' `gallery_url` is displayed. Config members that existed only for
  the panel (`save_url`, `connect_url`, `client_settings`, and their
  `WORKFLOW_RECOVERY_SAVE_URL` / `WORKFLOW_RECOVERY_CONNECT_URL` overrides) are
  removed; `WORKFLOW_RECOVERY_HTTP_TIMEOUT` remains.

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
