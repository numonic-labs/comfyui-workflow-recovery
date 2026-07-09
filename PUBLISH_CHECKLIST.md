# Publish checklist — what the maintainer must do to go live

This staging build is **review-ready but not published**. Publishing is gated on
four decisions/actions that only the maintainer can take. Nothing here has
touched GitHub, the Comfy Registry, or any secret.

## The 4 gates

### 1. Confirm the public product name

Confirm the **public product name** is **"Numonic Workflow Recovery"** (used in
`DisplayName`, README, sidebar). This is the one naming decision to sign off. It
deliberately does **not** say "Provenance-Sign" — this is a read-only recovery
tool, not a signing/provenance tool.

### 2. Create the GitHub repo + go-public decision

- ✅ Created and pushed: `github.com/numonic-labs/comfyui-workflow-recovery`
  (public, company-owned).
- The `Repository`, `Icon`, and `Banner` URLs in `pyproject.toml` point at that
  repo path.
- ✅ `assets/icon.png` (256×256) and `assets/banner.png` (1280×640) added,
  derived from the production brand assets. Once pushed, confirm the raw
  GitHub URLs in `pyproject.toml` resolve.

### 3. Run the mandatory IP disclosure review

- Run a full IP disclosure review over the whole repo before the first public
  push.
- Fast pre-scan available now: `python docs/check_cleanliness.py` (passes the
  heuristic checks; **does not replace** the human review).
- Must be **zero HIGH findings** (OSS-cleanliness gate check 5).

### 4. Register the PublisherId + add the Registry secret

- Register a **Comfy Registry publisher** (instant namespace). The PublisherId is
  **globally unique and immutable**.
- Replace `PublisherId = "REPLACE_WITH_REGISTERED_PUBLISHER_ID"` in
  `pyproject.toml`.
- Add the repo secret **`REGISTRY_ACCESS_TOKEN`** (the Registry *publisher*
  token — **not** a Comfy account key). Never commit it.

## Then: publishing a release

All 4 gates above are closed (repo live, IP review clean, PublisherId +
secret set). For the actual release steps — version bump, tag, GitHub
Release, watching the publish Action, and confirming Registry visibility —
see **`docs/runbooks/comfy-registry-publish.md`**, the repeatable step-by-step process for
every release, first or subsequent.

"Verified" author status is automatic once GitHub repo ownership is
confirmed (Claim-My-Node) — no separate action needed.

## Integration dependency (not a gate, but sequence-sensitive)

- The **enhanced-recovery** and **save** endpoints are owned by a private,
  separately-hosted service (`/v1/comfy-inspect`; save reuses an authenticated
  ingest route). The node ships against **contract v0**
  (`docs/CONTRACT-v0.md`). Confirm the final URLs and set them via
  `WORKFLOW_RECOVERY_INSPECT_URL` / `WORKFLOW_RECOVERY_SAVE_URL` (or update the
  defaults in `config.py`) once that endpoint is live.
- **Local recovery works today with no endpoint** — the node is useful and
  demoable before the hosted endpoint lands. Enhanced/save simply stay dormant
  until the URLs resolve.

## Governance (decided 2026-07-08)

This repo follows Numonic's existing lightweight OSS-governance pattern (MIT
license, internal-first `CONTRIBUTING.md`, semver, the 7-point cleanliness gate
in `docs/oss-cleanliness-checklist.md`) rather than a bespoke regime — kept
deliberately reversible if a dedicated governance document for distributed
ComfyUI/plugin artifacts becomes worth writing once more code repos exist.
