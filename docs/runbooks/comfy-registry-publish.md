# Comfy Registry Publish Runbook — Numonic Workflow Recovery

Step-by-step process for cutting a new version of this ComfyUI node pack.
Follow in order. Every step here is safe to re-read before a release; nothing
in this file is a secret.

**First-ever release?** See `PUBLISH_CHECKLIST.md` first — it covers the
one-time setup (PublisherId registration, `REGISTRY_ACCESS_TOKEN`, first IP
disclosure review). This runbook assumes that setup is already done and
covers the **repeatable release loop**.

## 0. Before you start

- [ ] Working tree clean and `main` up to date with `origin/main`:
      `git status --short && git fetch && git log HEAD..origin/main --oneline`
      (both outputs should be empty)
- [ ] Decide the new version number (semver: `MAJOR.MINOR.PATCH`).
      **Registry versions are immutable once published** — you cannot
      re-publish the same version number even to fix a typo. If in doubt,
      bump higher rather than lower.
- [ ] Run the local test suite: `python3 -m unittest discover -s tests -p "test_*.py"`
      — must be green before proceeding.
- [ ] Run the OSS-cleanliness pre-scan: `python3 docs/check_cleanliness.py`
      — must pass. For any release that touches docs, README, or adds new
      public-facing text, also re-run a manual IP disclosure review pass
      (see `docs/oss-cleanliness-checklist.md` check 5) — the pre-scan is a
      heuristic aid, not a substitute.
- [ ] Run the official Registry validator (installs `comfy-cli` if needed):
      `comfy --skip-prompt node validate`
      — must report "All validation checks passed successfully". This is
      the same check the publish Action runs; catching it locally avoids a
      failed/Flagged release.

## 1. Bump the version

Registry versions are immutable, so the version string must be updated in
**all three places** before tagging — they must agree:

| File | Field |
| --- | --- |
| `pyproject.toml` | `[project] version = "X.Y.Z"` |
| `__init__.py` | `__version__ = "X.Y.Z"` |
| `CHANGELOG.md` | New `## [X.Y.Z] - YYYY-MM-DD` section at the top, listing what changed |

```bash
# example: bumping to 0.2.0
sed -i 's/^version = ".*"/version = "0.2.0"/' pyproject.toml
sed -i 's/^__version__ = ".*"/__version__ = "0.2.0"/' __init__.py
# then hand-edit CHANGELOG.md to add the new section
```

Re-run the checklist in step 0 after bumping (tests + cleanliness + `comfy
node validate`) — a version bump alone can't break anything, but it costs
nothing to confirm.

## 2. Commit and push the bump

```bash
git add pyproject.toml __init__.py CHANGELOG.md
git commit -m "chore: bump version to X.Y.Z"
git push origin main
```

## 3. Tag the release

Use an **annotated** tag (not lightweight) so the tag carries a message —
useful for anyone browsing tags later.

```bash
git tag -a vX.Y.Z -m "vX.Y.Z — <one-line summary of what changed>"
git push origin vX.Y.Z
```

Pushing the tag alone does **not** publish anything — the publish workflow
only fires on a GitHub **Release**, not a bare tag push. This step is safe
and fully reversible (a mistaken tag can be deleted with `git push --delete
origin vX.Y.Z` before a Release is cut from it).

## 4. Create the GitHub Release (the actual go-live step)

**This step is not reversible in the way steps 1–3 are.** Publishing a
Release immediately triggers `.github/workflows/publish.yml`, which runs
`Comfy-Org/publish-node-action` and attempts a **real, immutable publish to
the ComfyUI Registry** using the `REGISTRY_ACCESS_TOKEN` secret. Do this step
deliberately, not as part of an automated script.

1. Go to `https://github.com/numonic-labs/comfyui-workflow-recovery/releases/new`
2. **Choose a tag**: select the `vX.Y.Z` tag you just pushed (don't create a
   new one here)
3. **Release title**: `vX.Y.Z`
4. **Description**: paste the matching `## [X.Y.Z]` section from
   `CHANGELOG.md`
5. Leave **"Set as a pre-release"** unchecked for a normal release (check it
   only for an intentional pre-release/beta)
6. Click **"Publish release"**

## 5. Watch the publish Action

- `https://github.com/numonic-labs/comfyui-workflow-recovery/actions`
- The `Publish to Comfy Registry` workflow should go green within a couple
  of minutes.
- If it fails: the job log will show which `comfy node validate`-style check
  rejected the release (invalid metadata, missing `Repository` URL,
  malformed semver, etc.). Fix locally, re-run step 0's checks, and **bump to
  a new version** before trying again — you cannot reuse the failed version
  number.

## 6. Confirm the release is actually visible

**Publish ≠ visible.** The Registry's security scanner can leave a version
in a `Flagged` state even after a successful Action run, which **silently
rolls back the public "latest" pointer** — so a green Action does not
guarantee users see the new version.

- [ ] Check `https://registry.comfy.org/publishers/numonic` — confirm the
      new version shows as the current/latest, not `Flagged` or `Pending`.
- [ ] If possible, confirm the update appears in ComfyUI-Manager's node
      listing for "Numonic Workflow Recovery".
- [ ] If Flagged: review what the scanner objected to (usually something
      resembling arbitrary system calls, unexpected network calls, or a
      dependency it doesn't recognize — this pack intentionally ships zero
      third-party dependencies specifically to minimize this risk). Address
      the finding and cut a new version — you cannot un-flag or edit the
      flagged version in place.

## 7. Post-release

- [ ] Confirm the repo's `README.md` install instructions still match
      reality (no action usually needed, but check after a install-path
      change).
- [ ] If this release changes the inspect/save contract, update
      `docs/CONTRACT-v0.md` and coordinate with whoever owns the private
      hosted endpoint side.
- [ ] Close out any GitHub issues this release addresses.

## Rollback / mistakes

- **Wrong tag, Release not yet published**: delete the tag
  (`git push --delete origin vX.Y.Z`), fix, re-tag.
- **Release published, Action not yet run or still running**: you generally
  cannot stop it mid-flight; let it finish and assess the result.
- **Bad version published to the Registry**: versions are immutable — you
  cannot edit or replace one in place. Options are (a) `DELETE
  /publishers/{id}/nodes/{node}` version-unpublish via the Registry API (removes
  it from listings but does not free the version number for reuse), or (b)
  cut a new, higher version with the fix and let the old one age out of
  "latest". Prefer (b) for anything already installed by users.
