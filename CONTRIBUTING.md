# Contributing

Thanks for your interest in Numonic Workflow Recovery.

## Contribution model

This project is **internal-authored** by Numonic Labs at this stage:

- **Issues** — very welcome. Bug reports, reproduction cases, and feature ideas
  all help. Please include your ComfyUI version and, if relevant, a sample image
  (with any sensitive prompt text removed).
- **Pull requests** — accepted and reviewed by Numonic maintainers. There are no
  external commit rights or RFC process yet. If sustained external contribution
  materializes, we'll revisit with a heavier governance model.

## Development

The node has **zero third-party Python dependencies** and the test suite runs on
the standard library alone:

```bash
python -m unittest discover -s tests -v
```

Please keep it dependency-free — it's a supply-chain safety property and eases
the ComfyUI Registry security scan. If you believe a dependency is unavoidable,
raise it in an issue first.

## Coding conventions

- Python: standard library only; keep the ComfyUI-runtime imports (`server`,
  `folder_paths`) guarded so modules remain importable under unit test.
- Keep the three-tier privacy model intact: **local by default; enhanced recovery
  opt-in; save opt-in + authenticated with a user-supplied token.** No code path
  may send an image or prompt text off-machine without explicit user action.
- No secrets, tokens, or private endpoints in the repo — ever.

## Versioning

Semantic versioning (`MAJOR.MINOR.PATCH`). Published Registry versions are
immutable, so bump the version in both `pyproject.toml` and `__init__.py`
(`__version__`) for every release, and add a `CHANGELOG.md` entry.

## Releasing

Releases publish to the ComfyUI Registry automatically via GitHub Actions on a
GitHub Release. See [`PUBLISH_CHECKLIST.md`](./PUBLISH_CHECKLIST.md) and the
[OSS-cleanliness gate](./docs/oss-cleanliness-checklist.md), which must pass 7/7
before any tag is cut.
