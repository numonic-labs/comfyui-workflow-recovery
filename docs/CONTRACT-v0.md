# Integration contracts (node ⇄ Numonic)

The surfaces this node talks to. **The hosted service is the source of truth**; if
the two drift, the service wins and this node adapts.

Two network surfaces exist, both opt-in, plus a fully local path that needs no
network at all.

---

## 1. Asset save — the `Save Image/Video to Numonic` nodes

The primary integration. Three phases; the node holds no secret of its own and
authenticates with a `napi_` key read from the host (see the README, "Connect your
Numonic account"). The tenant is resolved **server-side from the key** — the node
never supplies a tenant.

An API key with `write` **or** `comfy-ingest` scope is accepted.

### Phase 1 — request a signed upload URL

```
POST <api_base>/api/v1/comfy-lineage/asset/signed-url
Authorization: Bearer napi_…
Content-Type: application/json
  { "filename": "numonic_00000.png", "contentType": "image/png" }

→ 200 { "signedUrl": "https://…", "token": "…", "path": "<tenant-scoped storage path>" }
```

### Phase 2 — upload the bytes straight to storage

```
PUT <signedUrl>
Content-Type: <the same mime type>
  <raw file bytes>
```

Bytes go **directly to storage**, never through the web tier — this is what keeps
large video uploads clear of request-body size limits. The presigned URL carries its
own authorization; the `napi_` key is deliberately **not** sent here.

### Phase 3 — confirm, extract lineage, create the asset

```
POST <api_base>/api/v1/import/comfyui/confirm-upload
Authorization: Bearer napi_…
Content-Type: application/json
  { "path": "<path from phase 1>", "filename": "…", "fileSize": 12345, "mimeType": "image/png" }

→ 200 {
    "success": true,
    "url": "https://www.numonic.ai/app/assets/<assetH>",   // gallery deep-link
    "asset": { "assetH": "…", "filename": "…", "fileSize": 123, "toolName": "ComfyUI", … },
    "metadata": { … },
    "warning": null
  }
```

The server downloads the file, extracts the ComfyUI workflow from the embedded
metadata, creates the asset, and returns the gallery link. The node surfaces
`url` as its `gallery_url` output (falling back to `<app_base>/app/assets/<assetH>`
if `url` is absent).

### Embedded metadata the server reads

The node's job is to make sure the lineage is *inside the file* before upload:

- **PNG** — `prompt` and `workflow` `tEXt` chunks, written exactly as core
  `SaveImage` writes them.
- **Video** — container metadata tags written by ComfyUI's own `VIDEO.save_to()`,
  with `workflow` and `prompt` as **top-level** keys (mirroring core `SaveVideo`:
  `metadata.update(extra_pnginfo)` then `metadata["prompt"] = prompt`). Nesting
  them would break server-side extraction.

### Status codes the node handles

| Code | Meaning | Node behaviour |
| --- | --- | --- |
| 200 | Asset created | Surface `gallery_url` |
| 401 / 403 | Key invalid, revoked, or lacking scope | "check your API key" message |
| 413 | Tenant storage limit reached | "storage full" message |
| 429 | Rate limited | "wait and re-run" message |
| other 4xx/5xx, network error | Failure at a named phase | Readable error naming the phase + code |

---

## 2. Lineage save — DORMANT, no live endpoint

> **Status: not available.** The sidebar's "Save to Numonic" button and its
> `save_client.py` / `POST /numonic/workflow-recovery/save` plumbing are still in
> the tree, but the hosted endpoint they target was never deployed — the default
> host `api.numonic.ai` does not resolve. Clicking the button therefore always
> fails with "Numonic is unreachable". It is **not** documented as a user-facing
> feature in the README, and it is slated for removal. Use the asset-save nodes
> (§1) instead; they supersede this path entirely, since they capture the lineage
> *and* the asset.

The shape it was built against, for whoever removes or revives it:

```
POST <save_url>                          # default (dead): https://api.numonic.ai/v1/comfy-lineage/save
Authorization: Bearer <user-supplied token>
Content-Type: application/json
  { "source": "comfyui", "source_filename": "…", "lineage": { <LineageResult> } }
```

---

## 3. Local recovery — no network

`lineage.normalize_embedded_metadata` (Python) and `normalizeLocal` (browser) parse
the PNG `workflow` / `prompt` chunks entirely on-device and produce the shared
`LineageResult` shape:

```jsonc
{
  "source": "comfyui",
  "recovered": true,
  "mode": "local",
  "workflow_graph": { /* raw UI graph, or null */ },
  "prompts": { "positive": "…", "negative": "…" },
  "models": ["…"],
  "loras": ["…"],
  "custom_nodes": ["…"],
  "seed": 123456,          // optional
  "sampler": "euler",      // optional
  "warnings": ["…"]
}
```

Both implementations produce the same shape, so the UI is identical regardless of
which one produced the result.

> **Removed in v0.3.0:** the opt-in hosted "enhanced recovery" (image-inspect)
> surface and its `mode: "enhanced"` responses. Recovery is now local-only.
