# Shared inspect contract v0 (node ⇄ hosted endpoint)

This node builds against **contract v0** owned by the private `comfy-inspect`
service, a separately-hosted Numonic endpoint. It is mirrored here so the
node's integration point is explicit. **The hosted service is the source of
truth**; if the two drift, the service wins and this node adapts at
integration.

## Enhanced-recovery request (opt-in only)

```
POST <inspect_url>                       # default: https://api.numonic.ai/v1/comfy-inspect
Content-Type: multipart/form-data
  image=<file>                           # the generated image
  include_raw=true|false                 # optional; include raw prompt JSON
```

The node also plans to support `{ "image_url": "..." }` JSON bodies if the
hosted service offers it; the MVP node sends multipart only.

## Response (200)

```jsonc
{
  "source": "comfyui",
  "recovered": true,
  "workflow_graph": { /* raw UI graph, or null */ },
  "prompts": { "positive": "…", "negative": "…", "raw": { /* optional */ } },
  "models": ["…"],
  "loras": ["…"],
  "custom_nodes": ["…"],
  "seed": 123456,          // optional
  "sampler": "euler",      // optional
  "warnings": ["…"]
}
```

The node normalizes any response into this shape via `lineage.coerce_contract`,
filling missing keys with safe defaults, and stamps `mode: "enhanced"`.

## Status codes the node handles

| Code | Meaning | Node behaviour |
| --- | --- | --- |
| 200 | Recovered (or `recovered:false` with warnings) | Render result |
| 415 | Unsupported media type | Friendly message; fall back to local |
| 422 | No recoverable metadata | Friendly message; fall back to local |
| 5xx / network error | Service down/unreachable | Fall back to local recovery |

## Local path parity

The **local** recovery path (`lineage.normalize_embedded_metadata`, and the
in-browser `normalizeLocal`) produces the **same shape** with `mode: "local"`,
parsed entirely on-device from the PNG `workflow` / `prompt` chunks. This is why
the UI is identical regardless of which path produced the result.

## Save contract (separate surface — not inspect)

```
POST <save_url>                          # default: https://api.numonic.ai/v1/comfy-lineage/save
Authorization: Bearer <user-supplied token>
Content-Type: application/json
  { "source": "comfyui", "source_filename": "…", "lineage": { <LineageResult> } }
```

- Authenticated with a **user-supplied** token (never bundled).
- Sends the recovered lineage only — **never the raw image bytes**.
- 401/403 → the node clears the stored token and shows the connect prompt.
