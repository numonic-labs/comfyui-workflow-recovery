# Numonic Workflow Recovery

**Recover a ComfyUI image's workflow — and save your generations straight into
Numonic.**

Two jobs in one pack:

1. **Recover lineage** — prompts, models, LoRAs, seed, sampler, and the custom
   nodes that made an image, read straight out of the PNG your ComfyUI already
   saved. Lost the `.json`? Recover the workflow behind any ComfyUI image.
2. **Save to Numonic** — drop-in replacements for the stock *Save Image* /
   *Save Video* that ingest the generated **asset itself** (real bytes, with its
   ComfyUI lineage) into your [Numonic](https://numonic.ai) library and return a
   gallery link.

A free, open-source ComfyUI custom node from [Numonic](https://numonic.ai).

---

## What it does

ComfyUI embeds the full workflow into every file it saves (the `workflow` and
`prompt` metadata). This pack reads that back out **and** can push your outputs
to Numonic:

- **Positive / negative prompts**, **checkpoints & models**, **LoRAs**,
  **seed & sampler**, **custom nodes**, and the **raw workflow graph** as JSON.

Three nodes + a sidebar tab:

- **`Extract Workflow Lineage`** (graph node) — outputs the recovered fields for
  use in a workflow (great for archiving/organizing pipelines).
- **`Save Image to Numonic`** (graph node) — wire it where you'd wire *Save
  Image*: the generated image is uploaded to your Numonic library with its
  lineage, and the node returns the gallery URL.
- **`Save Video to Numonic`** (graph node) — the same for a `VIDEO` output
  (needs a recent ComfyUI with the native `VIDEO` type).
- **Sidebar tab** — drag any generated image in and read its lineage instantly.

### Saving to Numonic (one-time setup)

The save nodes upload to your tenant using a Numonic API key read from the
**host** (never a node widget — a widget would serialize the key into your saved
workflows and output files). Set it once, then just run your graph:

```bash
# either an environment variable before starting ComfyUI …
export NUMONIC_API_KEY="napi_..."
# … or ~/.numonic/config.json:  { "api_key": "napi_..." }
```

Mint a **write**-scoped `napi_` key in Numonic → **Settings → API Keys** (there
is a "ComfyUI node key" preset). No key set? The save nodes fail with a clear
message telling you exactly what to do; the recovery features keep working with
no key and no network.

### Where to wire it

**The save nodes are siblings of the stock save nodes, not successors.** They take
the same input the built-in *Save Image* / *Save Video* take, so you wire them from
the same place — either **instead of** the stock node (Numonic-only) or **alongside
it** (ComfyUI happily fans one output into several inputs, so you get a local file
*and* the upload):

```
                      ┌─→ Save Image                (writes a file — terminal)
… → VAE Decode ─IMAGE─┤
                      └─→ Save Image to Numonic     (uploads — terminal)

                      ┌─→ Save Video                (writes a file — terminal)
CreateVideo ────VIDEO─┤
 (or Load Video)      └─→ Save Video to Numonic     (uploads — terminal)
```

- **`Save Image to Numonic`** takes an `IMAGE`, so it goes wherever *Save Image*
  goes — typically straight off **VAE Decode**.
- **`Save Video to Numonic`** takes a `VIDEO`, so it goes wherever *Save Video*
  goes — off **Create Video** (the usual generative case: a model produces `IMAGE`
  frames, `Create Video` turns them into a `VIDEO`) or off **Load Video** (to push
  an existing video file into Numonic with its embedded lineage).
- You **cannot** chain ours *after* a stock *Save Image* / *Save Video*: those are
  terminal output nodes with no output socket. Put ours next to them, not behind
  them.

## Privacy model (read this)

Your prompts are yours. This node is built so recovery never phones home:

| Path | Network? | When |
| --- | --- | --- |
| **Local recovery** (default) | ❌ None | Always. The image is parsed **in your browser / on your machine**. Nothing is sent anywhere. |
| **Save Image/Video to Numonic** (graph nodes) | ✅ To Numonic | **Only if you add the node** and set `NUMONIC_API_KEY`. Uploads the generated asset to your own Numonic tenant. |
| **Save lineage** (sidebar) | ✅ To Numonic | **Only if you click Save** and connect your own account. Sends the recovered lineage (not the raw image). |

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

Set as environment variables before starting ComfyUI. Only `NUMONIC_API_KEY` is
needed to save assets; everything else has a sensible default.

| Variable | Purpose | Default |
| --- | --- | --- |
| `NUMONIC_API_KEY` | `napi_` key for the *Save to Numonic* nodes (or put it in `~/.numonic/config.json`) | — |
| `NUMONIC_APP_URL` | Numonic app host (used to build the returned gallery link) | `https://www.numonic.ai` |
| `NUMONIC_API_URL` | Numonic REST API host | (same as `NUMONIC_APP_URL`) |
| `WORKFLOW_RECOVERY_SAVE_URL` | Sidebar lineage-save endpoint | Numonic public API |
| `WORKFLOW_RECOVERY_CONNECT_URL` | Account-connect page | Numonic app |
| `WORKFLOW_RECOVERY_HTTP_TIMEOUT` | Network timeout (seconds) | `20` |

To run fully offline, just don't use the save nodes and don't connect an
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
