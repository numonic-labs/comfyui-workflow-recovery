# OSS-Cleanliness Release Gate

Adapted from Numonic's internal open-source governance template (the default
regime for a new public OSS artifact). **All 7 checks must pass before any
release tag is cut.** This is a 🔴 release blocker.

## The 7 checks

1. **No internal identifiers.** No Numonic-internal schema names, `tenant_id`s,
   CRM IDs, GitLab project paths, internal (non-public) URLs, capability codes
   (`Platform-Cap-*`, `S#`/`C#`/`P#`), colleague names, or monorepo file paths
   anywhere in the shipped package.
   - The public product name ("Numonic"), the public product API host, and the
     public app URL are **allowed** — the node's purpose is a funnel to the
     public product. Only *internal* identifiers are disallowed.

2. **Generic worked examples.** README / docs examples use generic ComfyUI
   scenarios, not internal Numonic workflows or data.

3. **LICENSE present and MIT** (`Copyright (c) 2026 Numonic Labs`).

4. **No required Numonic dependency.** The node runs fully (local recovery) with
   no Numonic account, no network, and no Numonic code. Enhanced recovery and
   save are strictly opt-in enrichments.

5. **IP disclosure review clean.** Run the mandatory pre-publish IP disclosure
   review; zero HIGH findings.

6. **README "How this differs from adjacent nodes" section** present
   (anti-confusion).

7. **No secrets.** No token, key, or credential in the repo. Grep clean for
   `token`, `secret`, `api_key`, `password`, `Bearer ` (literal values). The only
   token the code references is the *user-supplied* one relayed at runtime.

## Automated pre-scan

`docs/check_cleanliness.py` runs a fast heuristic pass of checks 1, 3, 6, 7. It
is a **belt-and-braces aid, not a replacement** for the mandatory human
`ip-disclosure-review` (check 5). Run:

```bash
python docs/check_cleanliness.py
```

## Sign-off

| Check | Owner | Status |
| --- | --- | --- |
| 1 No internal identifiers | release author | ☐ |
| 2 Generic examples | release author | ☐ |
| 3 LICENSE MIT | release author | ☐ |
| 4 No required Numonic dep | release author | ☐ |
| 5 `ip-disclosure-review` clean | **maintainer (mandatory gate)** | ☐ |
| 6 README diff section | release author | ☐ |
| 7 No secrets | release author + CI grep | ☐ |
