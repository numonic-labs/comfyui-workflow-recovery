# Numonic Workflow Recovery

**Save your ComfyUI generations straight into [Numonic](https://numonic.ai) — and
recover the workflow behind any ComfyUI image.**

A free, open-source ComfyUI custom node pack from [Numonic](https://numonic.ai).

- **Save to Numonic** — drop-in replacements for the stock *Save Image* / *Save
  Video*. When your graph runs, the generated asset itself (real bytes, with its
  ComfyUI workflow embedded) lands in your Numonic library, and the node hands you
  the gallery link.
- **Recover lineage** — prompts, models, LoRAs, seed, sampler and custom nodes,
  read straight out of a PNG ComfyUI already saved. Lost the `.json`? Recover it.

---

## Contents

1. [Install](#1-install)
2. [Connect your Numonic account](#2-connect-your-numonic-account) ← the one setup step
3. [Use the save nodes](#3-use-the-save-nodes)
4. [Recover a workflow from an image](#4-recover-a-workflow-from-an-image)
5. [Troubleshooting](#5-troubleshooting)
6. [Privacy model](#6-privacy-model)
7. [Configuration reference](#7-configuration-reference)

---

## 1. Install

**From ComfyUI-Manager** (recommended): search for *Numonic Workflow Recovery* →
**Install** → restart ComfyUI.

**Manually:**

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/numonic-labs/comfyui-workflow-recovery
# restart ComfyUI
```

**No dependencies to install** — the pack uses only the Python standard library and
modules ComfyUI already ships. After restarting, ComfyUI's log lists the pack under
*"Import times for custom nodes"* with no error.

You now have three nodes (under the **Numonic** category) and a sidebar tab:

| Node | Takes | Does |
| --- | --- | --- |
| **Save Image to Numonic** | `IMAGE` | Uploads the image (with lineage) → returns `gallery_url` |
| **Save Video to Numonic** | `VIDEO` | Uploads the video (with lineage) → returns `gallery_url` |
| **Extract Workflow Lineage** | an image file | Outputs the recovered prompts / models / LoRAs / custom nodes / JSON |

Recovery works immediately with no account and no network. Saving needs one setup
step — next.

---

## 2. Connect your Numonic account

The save nodes authenticate with a Numonic API key that they read **from the machine
running ComfyUI** — never from a node widget, because a widget value would be
serialized into your saved workflows *and* embedded into your output files, leaking
the key to anyone you share them with.

### 2.1 Get a key

In Numonic: **Settings → API Keys → New key**, using the **"ComfyUI node key"**
preset. Copy the `napi_…` value.

**Prefer the least-privilege scope.** The preset mints a **`comfy-ingest`** key,
which can add assets to your library and nothing else — if it ever leaked, the
blast radius is limited to that. A general `write` key also works, but it can do
considerably more, so only use one if you have a reason to. Keys are revocable at
any time from the same screen; revoke and re-issue rather than reusing a key you
are unsure about.

### 2.2 Give the key to ComfyUI — pick ONE of these

> **⚠️ The one thing that trips people up:** an environment variable you type in a
> terminal is only visible to programs launched **from that same terminal**. If you
> start ComfyUI by double-clicking a `.bat`, from a desktop shortcut, from **ComfyUI
> Desktop**, or as a background service, it will **not** see it — and the node will
> report "No Numonic API key found". If in doubt, use **Option A**, which works no
> matter how ComfyUI is started.

#### Option A — config file (recommended, works everywhere)

Create a file called `config.json` in a `.numonic` folder inside your home
directory, containing:

```json
{ "api_key": "napi_..." }
```

| Platform | Full path |
| --- | --- |
| **Windows** | `C:\Users\<your-name>\.numonic\config.json` |
| **macOS** | `/Users/<your-name>/.numonic/config.json` |
| **Linux** | `/home/<your-name>/.numonic/config.json` |

<details>
<summary>Create it from a terminal (copy-paste)</summary>

**Windows (PowerShell)** — the second command restricts the file to your account
(the Windows equivalent of `chmod 600`; your user profile is already
ACL-protected, so this mainly matters on a shared or managed machine):
```powershell
mkdir "$env:USERPROFILE\.numonic" -Force
'{ "api_key": "napi_..." }' | Out-File -Encoding utf8 "$env:USERPROFILE\.numonic\config.json"
icacls "$env:USERPROFILE\.numonic\config.json" /inheritance:r /grant:r "$($env:USERNAME):(R,W)"
```

**macOS / Linux** — files are created group/world-readable by default, so the
`chmod` is worth doing, not optional:
```bash
mkdir -p ~/.numonic
printf '{ "api_key": "napi_..." }\n' > ~/.numonic/config.json
chmod 600 ~/.numonic/config.json
```
</details>

#### About this file (please read once)

The key is stored in **plain text**, exactly as `~/.aws/credentials`, `~/.npmrc`,
`~/.docker/config.json` and most developer tooling store theirs. What protects it
is your **operating-system user account**, so:

- **Restrict the file** if anyone else uses, administers, or can log into this
  machine (the commands above). On macOS/Linux the node prints a warning at save
  time if the file is readable by other users.
- **It is never written into your workflows or your output files.** That is the
  whole reason the key is not a node widget — you can share a workflow `.json` or
  a generated PNG without leaking it.
- **Watch out for folder sync.** If your home directory is synced to a cloud
  drive or lives in a dotfiles repo, the key goes with it. Put it somewhere
  unsynced, or use the environment-variable option instead.
- **Revoke it** in Numonic → Settings → API Keys if the machine is shared,
  retired, or you suspect exposure. Using the least-privilege `comfy-ingest`
  scope (§2.1) keeps the impact small if that ever happens.

The environment-variable option below is *not* more secure — an `export` in
`~/.bashrc` is also a plaintext file, and Windows `setx` writes plain text to the
registry. Pick whichever fits how you launch ComfyUI.

#### Option B — environment variable

Best when you launch ComfyUI from a terminal or run it as a service.

**Windows — ComfyUI portable (`run_nvidia_gpu.bat`):** open the `.bat` in a text
editor and add this line *above* the line that starts `python`:

```bat
set NUMONIC_API_KEY=napi_...
```

**Windows — persistent, for any launcher:** run once, then **sign out and back in**
(`setx` does not affect already-running programs or the current window):

```bat
setx NUMONIC_API_KEY "napi_..."
```

**Windows — current PowerShell session only:**
```powershell
$env:NUMONIC_API_KEY = "napi_..."
```

**macOS / Linux — terminal launch:** export it, then start ComfyUI *from that same
terminal*:
```bash
export NUMONIC_API_KEY="napi_..."
python main.py
```
To make it permanent, add that `export` line to `~/.bashrc` / `~/.zshrc`.

<details>
<summary>Linux — ComfyUI running as a <code>systemd</code> service</summary>

A shell `export` will **not** reach a service. Give it the variable explicitly:

```bash
sudo mkdir -p /etc/systemd/system/comfyui.service.d
sudo tee /etc/systemd/system/comfyui.service.d/numonic.conf >/dev/null <<'CONF'
[Service]
Environment=NUMONIC_API_KEY=napi_...
CONF
sudo systemctl daemon-reload
sudo systemctl restart comfyui.service
```
(Replace `comfyui.service` with your unit name.)
</details>

### 2.3 Restart ComfyUI

The key is read by the ComfyUI process, so **restart it** after setting either
option. Then run a graph with a save node — success shows a `gallery_url`; any
problem is reported in plain language (see [Troubleshooting](#5-troubleshooting)).

---

## 3. Use the save nodes

**The save nodes are siblings of the stock save nodes, not successors.** They take
the same input the built-in *Save Image* / *Save Video* take, so wire them from the
same place — either **instead of** the stock node (Numonic-only) or **alongside it**
(ComfyUI fans one output into several inputs, so you get a local file *and* the
upload):

```
                      ┌─→ Save Image                (writes a file — terminal)
… → VAE Decode ─IMAGE─┤
                      └─→ Save Image to Numonic     (uploads — terminal)

                      ┌─→ Save Video                (writes a file — terminal)
Create Video ───VIDEO─┤
 (or Load Video)      └─→ Save Video to Numonic     (uploads — terminal)
```

- **Save Image to Numonic** takes an `IMAGE` — typically straight off **VAE Decode**.
- **Save Video to Numonic** takes a `VIDEO` — off **Create Video** (the usual
  generative case: a model produces `IMAGE` frames and *Create Video* turns them
  into a `VIDEO`) or off **Load Video** (to push an existing video file into Numonic).
- You **cannot** chain ours *after* a stock *Save Image* / *Save Video*: those are
  terminal nodes with no output socket. Put ours next to them, not behind them.

**Optional inputs:** `filename_prefix` (default `numonic`), and for video
`format` / `codec` (both default `auto` — ComfyUI picks). The `prompt` and
`workflow` are captured automatically; there is nothing to wire for lineage.

**Output:** a `gallery_url` string. Wire it into any "show text" node to see it on
the canvas, or just open your Numonic gallery — the asset is there, with its
workflow lineage (prompts, models, LoRAs, seed, sampler) already extracted.

> **Video needs a recent ComfyUI** — the one with the native `VIDEO` type (the same
> one that has *Create Video* / *Save Video*). On older builds the video node's input
> socket won't resolve, and the node fails with a clear "update ComfyUI" message.
> *Save Image to Numonic* has no such requirement.

---

## 4. Recover a workflow from an image

Two ways, both entirely local — nothing leaves your machine:

- **Sidebar tab** — open the *Workflow Recovery* tab and drop in any generated
  image to read its lineage instantly.
- **`Extract Workflow Lineage` node** — point it at an image in your input folder;
  it outputs positive/negative prompts, models, LoRAs, custom nodes and the raw
  workflow JSON as strings you can use elsewhere in a graph.

Reads ComfyUI's `workflow` / `prompt` PNG metadata, including compressed (`zTXt` /
`iTXt`) chunks that some tools miss.

---

## 5. Troubleshooting

| What you see | What it means | Fix |
| --- | --- | --- |
| `No Numonic API key found` | The ComfyUI **process** can't see your key — almost always an environment variable set in a terminal while ComfyUI was launched some other way | Use [Option A, the config file](#option-a--config-file-recommended-works-everywhere), then restart ComfyUI |
| `Numonic rejected the API key (HTTP 401/403)` | Key is wrong, revoked, or lacks scope | Mint a fresh key with `write` or `comfy-ingest` scope; check for stray spaces/quotes |
| `Your Numonic storage is full (HTTP 413)` | Tenant storage limit reached | Free up space or raise the limit, then re-run |
| `Numonic is rate-limiting uploads (HTTP 429)` | Too many uploads too fast | Wait a moment and re-run |
| `…has no native save_to() primitive` / video node won't connect | ComfyUI predates the native `VIDEO` type | Update ComfyUI, or use *Save Image to Numonic* |
| `Numonic is unreachable` | Network/DNS/proxy problem, or a wrong host override | Check connectivity; unset `NUMONIC_API_URL` unless you deliberately set it |
| `Warning: …config.json is readable by other users` | The config file's permissions let other accounts on this machine read your key (macOS/Linux only — Windows uses ACLs) | `chmod 600 ~/.numonic/config.json`. Harmless on a single-user machine, but worth fixing |

The nodes never fail silently: every problem surfaces as a readable error in the
ComfyUI UI and log.

---

## 6. Privacy model

Your prompts are yours. Recovery never phones home:

| Path | Network? | When |
| --- | --- | --- |
| **Local recovery** (sidebar + `Extract Workflow Lineage`) | ❌ None | Always. Parsed on your machine / in your browser. Nothing is sent anywhere. |
| **Save Image / Video to Numonic** (graph nodes) | ✅ To Numonic | Only if you add the node **and** configure a key. Uploads the asset to **your own** Numonic tenant. |
| **Save lineage** (sidebar button) | ✅ To Numonic | Only if you click Save and connect an account. Sends the recovered lineage — never the raw image. |

- This package contains **no secret, token, or key of its own.** The save nodes use
  the key *you* place on your machine; the sidebar save uses a token *you* paste,
  stored only in your browser. Neither is ever written into a workflow or an output
  file.
- With no key configured, everything stays 100% local.

---

## 7. Configuration reference

Only `NUMONIC_API_KEY` is needed. Everything else is optional and has a sensible
default.

| Variable | Purpose | Default |
| --- | --- | --- |
| `NUMONIC_API_KEY` | Your `napi_` key (or use `~/.numonic/config.json`) | — |
| `NUMONIC_APP_URL` | Numonic app host, used for the returned gallery link | `https://www.numonic.ai` |
| `NUMONIC_API_URL` | Numonic REST API host — only change this to target a self-hosted or staging instance | same as `NUMONIC_APP_URL` |
| `WORKFLOW_RECOVERY_HTTP_TIMEOUT` | Network timeout, seconds | `20` |
| `WORKFLOW_RECOVERY_SAVE_URL` | Endpoint for the sidebar's lineage-save button | Numonic public API |
| `WORKFLOW_RECOVERY_CONNECT_URL` | Account-connect page opened by the sidebar | Numonic app |

The config file accepts the same host overrides as keys: `api_key`, `app_url`,
`api_url`.

---

## How this differs from adjacent nodes

- **vs. ComfyUI_PNGInfo_Sidebar / Crystools metadata tools** — those show raw
  embedded metadata. This pack *normalizes* it into a structured lineage (models /
  LoRAs / custom nodes / prompts) and adds a first-class path to archive the asset
  itself into an asset manager. Local-first parsing is shared prior art; the
  normalization and the save nodes are what's new.
- **It does not sign anything.** This recovers existing metadata; it is not a
  C2PA/provenance *signer*. (The naming is deliberate — it does what it says.)
- **It does not use execution hooks.** Recovery reads saved-file metadata only, so
  it is unaffected by ComfyUI execution-model changes.

## License

MIT © 2026 Numonic Labs. See [LICENSE](./LICENSE).

## Contributing

Issues and PRs welcome — see [CONTRIBUTING.md](./CONTRIBUTING.md).
