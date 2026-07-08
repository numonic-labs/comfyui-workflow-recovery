/*
 * Numonic Workflow Recovery — ComfyUI sidebar extension.
 *
 * Privacy model (mirrors the Python side):
 *   1. LOCAL by default — a dropped image is parsed entirely in the browser.
 *      Its embedded `workflow` / `prompt` chunks are read here; nothing leaves
 *      the machine.
 *   2. ENHANCED recovery is OPT-IN — only when the user ticks the box does the
 *      image get POSTed to this pack's `/recover` route (which forwards to the
 *      read-only hosted inspect service).
 *   3. SAVE is OPT-IN + authenticated — requires a user-owned token stored in
 *      this browser. No token → we open the connect page instead of sending.
 *
 * This file holds no secret. The token is the user's, stored in localStorage.
 */

import { app } from "../../scripts/app.js";

const EXT_NAME = "numonic.workflow-recovery";
const ROUTE = "/numonic/workflow-recovery";
const TOKEN_KEY = "numonic.workflow-recovery.token";

// ---------------------------------------------------------------------------
// Local PNG metadata reader (in-browser, no network).
// ---------------------------------------------------------------------------

const PNG_SIG = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];

function isPng(bytes) {
  return PNG_SIG.every((b, i) => bytes[i] === b);
}

async function inflate(bytes) {
  // Browser-native zlib inflate for zTXt / compressed iTXt chunks.
  if (typeof DecompressionStream === "undefined") return "";
  try {
    const stream = new Response(
      new Blob([bytes]).stream().pipeThrough(new DecompressionStream("deflate")),
    );
    return await stream.text();
  } catch (e) {
    return "";
  }
}

async function readPngTextChunks(buffer) {
  const bytes = new Uint8Array(buffer);
  if (!isPng(bytes)) throw new Error("not-a-png");
  const view = new DataView(buffer);
  const decoder = new TextDecoder("utf-8");
  const latin1 = new TextDecoder("latin1");
  const chunks = {};
  let pos = 8;

  while (pos + 8 <= bytes.length) {
    const length = view.getUint32(pos);
    const type = latin1.decode(bytes.subarray(pos + 4, pos + 8));
    const bodyStart = pos + 8;
    const bodyEnd = bodyStart + length;
    if (bodyEnd + 4 > bytes.length) break;
    const body = bytes.subarray(bodyStart, bodyEnd);

    if (type === "tEXt") {
      const nul = body.indexOf(0);
      if (nul >= 0) {
        const key = latin1.decode(body.subarray(0, nul));
        const text = decoder.decode(body.subarray(nul + 1));
        if (!(key in chunks)) chunks[key] = text;
      }
    } else if (type === "zTXt") {
      const nul = body.indexOf(0);
      if (nul >= 0) {
        const key = latin1.decode(body.subarray(0, nul));
        const text = await inflate(body.subarray(nul + 2)); // skip method byte
        if (!(key in chunks)) chunks[key] = text;
      }
    } else if (type === "iTXt") {
      const nul = body.indexOf(0);
      if (nul >= 0) {
        const key = latin1.decode(body.subarray(0, nul));
        const compFlag = body[nul + 1];
        let p = nul + 3; // skip compression flag + method
        p = body.indexOf(0, p) + 1; // skip language tag
        p = body.indexOf(0, p) + 1; // skip translated keyword
        const rest = body.subarray(p);
        const text = compFlag === 1 ? await inflate(rest) : decoder.decode(rest);
        if (!(key in chunks)) chunks[key] = text;
      }
    }
    if (type === "IEND") break;
    pos = bodyEnd + 4;
  }
  return chunks;
}

// ---------------------------------------------------------------------------
// Local normalization (mirrors lineage.py; best-effort, no network).
// ---------------------------------------------------------------------------

const CORE_NODES = new Set([
  "KSampler", "KSamplerAdvanced", "CheckpointLoaderSimple", "CheckpointLoader",
  "CLIPTextEncode", "CLIPSetLastLayer", "VAEDecode", "VAEEncode", "VAELoader",
  "EmptyLatentImage", "LatentUpscale", "LatentUpscaleBy", "LoraLoader",
  "LoraLoaderModelOnly", "ControlNetLoader", "ControlNetApply",
  "ControlNetApplyAdvanced", "SaveImage", "PreviewImage", "LoadImage",
  "ImageScale", "ImageUpscaleWithModel", "UpscaleModelLoader",
  "ConditioningCombine", "ConditioningConcat", "ConditioningSetArea",
  "CLIPLoader", "DualCLIPLoader", "UNETLoader", "ModelSamplingDiscrete",
  "RepeatLatentBatch", "PrimitiveNode", "Note", "Reroute",
]);
const MODEL_KEYS = ["ckpt_name", "unet_name", "model_name", "model"];

function tryParse(value) {
  if (value == null) return null;
  if (typeof value === "object") return value;
  try {
    return JSON.parse(value);
  } catch (e) {
    return null;
  }
}

function uniq(arr) {
  return [...new Set(arr.filter(Boolean))];
}

function normalizeLocal(workflowRaw, promptRaw) {
  const result = {
    source: "comfyui", recovered: false, mode: "local", workflow_graph: null,
    prompts: { positive: "", negative: "" }, models: [], loras: [],
    custom_nodes: [], seed: null, sampler: null, warnings: [],
  };
  const workflow = tryParse(workflowRaw);
  const prompt = tryParse(promptRaw);
  if (!workflow && !prompt) {
    result.warnings.push("No embedded ComfyUI metadata found in image.");
    return result;
  }
  if (workflow) result.workflow_graph = workflow;

  const models = [], loras = [], customNodes = [];
  const positive = [], negative = [], ambiguous = [];
  if (prompt && typeof prompt === "object") {
    for (const node of Object.values(prompt)) {
      if (!node || typeof node !== "object" || !node.class_type) continue;
      const ct = node.class_type;
      if (!CORE_NODES.has(ct)) customNodes.push(ct);
      const inputs = node.inputs || {};
      for (const k of MODEL_KEYS) if (typeof inputs[k] === "string") models.push(inputs[k]);
      if (typeof inputs.lora_name === "string") loras.push(inputs.lora_name);
      if (result.seed == null && typeof inputs.seed === "number") result.seed = inputs.seed;
      if (result.sampler == null && typeof inputs.sampler_name === "string") result.sampler = inputs.sampler_name;
      if (ct === "CLIPTextEncode" && typeof inputs.text === "string" && inputs.text.trim()) {
        const title = (node._meta?.title || "").toLowerCase();
        if (title.includes("neg")) negative.push(inputs.text);
        else if (title.includes("pos")) positive.push(inputs.text);
        else ambiguous.push(inputs.text);
      }
    }
  }
  if (!positive.length && ambiguous.length) positive.push(ambiguous.shift());
  negative.push(...ambiguous);

  result.models = uniq(models);
  result.loras = uniq(loras);
  result.custom_nodes = uniq(customNodes);
  if (positive.length) result.prompts.positive = positive.join("\n").trim();
  if (negative.length) result.prompts.negative = negative.join("\n").trim();
  result.recovered = !!(result.workflow_graph || result.models.length ||
    result.prompts.positive || result.prompts.negative);
  if (workflow && !prompt) {
    result.warnings.push("Only the UI workflow chunk was present; details are best-effort. Try enhanced recovery.");
  }
  return result;
}

// ---------------------------------------------------------------------------
// UI
// ---------------------------------------------------------------------------

function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") el.className = v;
    else if (k === "text") el.textContent = v;
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v);
  }
  for (const c of children) if (c) el.append(c);
  return el;
}

function section(title, body) {
  const wrap = h("div", { class: "nwr-section" });
  wrap.append(h("div", { class: "nwr-section-title", text: title }));
  const pre = h("pre", { class: "nwr-pre" });
  pre.textContent = body || "—";
  wrap.append(pre);
  return wrap;
}

function renderResult(container, result, sourceName) {
  container.replaceChildren();
  if (!result.recovered) {
    container.append(h("div", { class: "nwr-empty",
      text: (result.warnings[0] || "No lineage recovered.") }));
  }
  const badge = result.mode === "enhanced" ? "enhanced (via Numonic)" : "local only";
  container.append(h("div", { class: "nwr-meta", text: `${sourceName} · ${badge}` }));
  container.append(section("Positive prompt", result.prompts.positive));
  container.append(section("Negative prompt", result.prompts.negative));
  container.append(section("Models", (result.models || []).join("\n")));
  container.append(section("LoRAs", (result.loras || []).join("\n")));
  container.append(section("Custom nodes", (result.custom_nodes || []).join("\n")));
  const extra = [];
  if (result.seed != null) extra.push(`seed: ${result.seed}`);
  if (result.sampler) extra.push(`sampler: ${result.sampler}`);
  if (extra.length) container.append(section("Parameters", extra.join("\n")));
  if (result.warnings && result.warnings.length) {
    container.append(section("Notes", result.warnings.join("\n")));
  }
}

function buildPanel(el) {
  el.classList.add("nwr-root");
  el.replaceChildren();

  const drop = h("div", { class: "nwr-drop", text: "Drop a generated image here, or click to choose" });
  const fileInput = h("input", { type: "file", accept: "image/*", class: "nwr-file" });
  const enhanced = h("input", { type: "checkbox", class: "nwr-enh" });
  const enhancedLabel = h("label", { class: "nwr-enh-label" }, enhanced,
    h("span", { text: " Enhanced recovery (sends image to Numonic to parse — read-only, not stored)" }));
  const results = h("div", { class: "nwr-results" });
  const status = h("div", { class: "nwr-status" });

  const saveBtn = h("button", { class: "nwr-btn nwr-save", text: "Save to Numonic" });
  const actions = h("div", { class: "nwr-actions" }, saveBtn);

  let lastResult = null;
  let lastName = "";

  async function handleFile(file) {
    if (!file) return;
    lastName = file.name;
    status.textContent = "Reading locally…";
    results.replaceChildren();
    const buffer = await file.arrayBuffer();

    if (enhanced.checked) {
      status.textContent = "Enhanced recovery…";
      try {
        const form = new FormData();
        form.append("image", new Blob([buffer]), file.name);
        const resp = await fetch(ROUTE + "/recover", { method: "POST", body: form });
        if (!resp.ok) throw new Error((await resp.json().catch(() => ({}))).error || resp.statusText);
        lastResult = await resp.json();
        status.textContent = "";
        renderResult(results, lastResult, file.name);
        return;
      } catch (e) {
        status.textContent = "Enhanced recovery failed; showing local result. (" + e.message + ")";
      }
    }

    try {
      const chunks = await readPngTextChunks(buffer);
      lastResult = normalizeLocal(chunks.workflow, chunks.prompt);
      if (!enhanced.checked) status.textContent = "";
      renderResult(results, lastResult, file.name);
    } catch (e) {
      lastResult = null;
      status.textContent = e.message === "not-a-png"
        ? "Local recovery reads PNG metadata. For other formats, enable enhanced recovery."
        : "Could not read this file.";
    }
  }

  async function handleSave() {
    if (!lastResult || !lastResult.recovered) {
      status.textContent = "Recover a lineage first.";
      return;
    }
    let token = localStorage.getItem(TOKEN_KEY) || "";
    if (!token) {
      // No token: open the connect page rather than sending anything.
      try {
        const cfg = await (await fetch(ROUTE + "/status")).json();
        window.open(cfg.connectUrl, "_blank", "noopener");
      } catch (e) { /* ignore */ }
      const entered = window.prompt(
        "Paste your Numonic account token to connect (stored only in this browser):");
      if (!entered) { status.textContent = "Save cancelled — nothing was sent."; return; }
      token = entered.trim();
      localStorage.setItem(TOKEN_KEY, token);
    }
    status.textContent = "Saving to Numonic…";
    try {
      const resp = await fetch(ROUTE + "/save", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + token },
        body: JSON.stringify({ lineage: lastResult, source_filename: lastName }),
      });
      const data = await resp.json().catch(() => ({}));
      if (resp.status === 401) {
        localStorage.removeItem(TOKEN_KEY);
        status.textContent = data.error || "Account not connected.";
        if (data.connect_url) window.open(data.connect_url, "_blank", "noopener");
        return;
      }
      if (!resp.ok) throw new Error(data.error || resp.statusText);
      status.textContent = "Saved to Numonic ✓";
    } catch (e) {
      status.textContent = "Save failed: " + e.message;
    }
  }

  drop.addEventListener("click", () => fileInput.click());
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("nwr-dragover"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("nwr-dragover"));
  drop.addEventListener("drop", (e) => {
    e.preventDefault();
    drop.classList.remove("nwr-dragover");
    handleFile(e.dataTransfer.files?.[0]);
  });
  fileInput.addEventListener("change", () => handleFile(fileInput.files?.[0]));
  saveBtn.addEventListener("click", handleSave);

  el.append(drop, fileInput, enhancedLabel, status, results, actions);
}

app.registerExtension({
  name: EXT_NAME,
  async setup() {
    const mgr = app.extensionManager;
    if (mgr && typeof mgr.registerSidebarTab === "function") {
      mgr.registerSidebarTab({
        id: "numonic-workflow-recovery",
        icon: "pi pi-history",
        title: "Workflow Recovery",
        tooltip: "Recover a ComfyUI workflow lineage from a generated image",
        type: "custom",
        render: (el) => buildPanel(el),
      });
    } else {
      console.warn("[Numonic Workflow Recovery] sidebar API unavailable on this ComfyUI frontend.");
    }
  },
});
