# Numonic Workflow Recovery

**Drop in a generated image → recover its full ComfyUI workflow lineage.**

Prompts, models, LoRAs, seed, sampler, and the custom nodes that made it — read
straight out of the image your ComfyUI already saved. Lost the `.json`? Handed a
PNG with no recipe? Recover the workflow behind any ComfyUI image.

A free, open-source ComfyUI custom node from [Numonic](https://numonic.ai).

---

## What it does

ComfyUI embeds the full workflow into every PNG it saves (the `workflow` and
`prompt` metadata chunks). This node reads that metadata back out:

- **Positive / negative prompts**
- **Checkpoints & models** used
- **LoRAs** applied
- **Seed & sampler**
- **Custom nodes** the workflow depends on
- The **raw workflow graph** as JSON

Two ways to use it:

- **Sidebar tab** — drag any generated image in and read its lineage instantly.
- **Graph node** — `Extract Workflow Lineage` outputs the recovered fields for
  use in a workflow (great for archiving/organizing pipelines).

## Privacy model (read this)

Your prompts are yours. This node is built so recovery never phones home:

| Path | Network? | When |
| --- | --- | --- |
| **Local recovery** (default) | ❌ None | Always. The image is parsed **in your browser / on your machine**. Nothing is sent anywhere. |
| **Enhanced recovery** | ✅ To Numonic | **Only if you tick the box.** Sends the image to a **read-only** service for a richer parse. It is **not stored**. |
| **Save to Numonic** | ✅ To Numonic | **Only if you click Save** and connect your own account. Sends the recovered lineage (not the raw image). |

- This package contains **no secret, token, or key**. "Save to Numonic" uses a
  token **you** provide, stored only in your browser.
- With no account connected, everything stays 100% local.

## Install

**From ComfyUI-Manager** (recommended): search for *Numonic Workflow Recovery*
and click Install.

**Manually:**

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/numonic-labs/comfyui-workflow-recovery
# restart ComfyUI
```

No dependencies to install — the node uses only the Python standard library and
modules ComfyUI already ships.

## Configuration (optional)

All optional; sensible defaults ship out of the box. Set as environment
variables before starting ComfyUI:

| Variable | Purpose | Default |
| --- | --- | --- |
| `WORKFLOW_RECOVERY_INSPECT_URL` | Enhanced-recovery endpoint | Numonic public API |
| `WORKFLOW_RECOVERY_SAVE_URL` | Save endpoint | Numonic public API |
| `WORKFLOW_RECOVERY_CONNECT_URL` | Account-connect page | Numonic app |
| `WORKFLOW_RECOVERY_HTTP_TIMEOUT` | Network timeout (seconds) | `20` |

To run fully offline, simply don't tick enhanced recovery and don't connect an
account. Local recovery needs no configuration and no network.

## How this differs from adjacent nodes

- **vs. ComfyUI_PNGInfo_Sidebar / Crystools metadata tools** — those show raw
  embedded metadata. This node *normalizes* it into a structured lineage
  (models / LoRAs / custom-node list / prompts) and adds an optional path to
  archive it to an asset manager. Local-first parsing is shared prior art; the
  normalization + opt-in save funnel is what's new here.
- **It does not sign anything.** This recovers existing metadata; it is not a
  C2PA/provenance *signer*. (Naming is deliberate — it does what it says.)
- **It does not use execution hooks.** Recovery reads saved-image metadata only,
  so it is unaffected by ComfyUI execution-model changes.

## License

MIT © 2026 Numonic Labs. See [LICENSE](./LICENSE).

## Contributing

Issues and PRs welcome — see [CONTRIBUTING.md](./CONTRIBUTING.md).
