"use strict";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
const mean = values => values.reduce((sum, value) => sum + value, 0) / values.length;
// The manuscript tables truncate at the reported precision
// (for example, 94.985485 -> 94.98). Keep that convention in every label.
const format = (value, digits = 2) => {
  const scale = 10 ** digits;
  return (Math.floor((Number(value) + Number.EPSILON) * scale) / scale).toFixed(digits);
};

const app = {
  data: null,
  headBaseline: [],
  headDamage: [],
  denseBaseline: [],
  denseDamage: [],
  perTag: [],
  representations: null,
  stage: 0,
  condition: "mask_only_inverse_reg",
  layer: 0,
  timer: null,
  evidenceView: "qkv",
  evidenceOption: "damaged"
};

async function loadCsv(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Could not load ${path}`);
  const [header, ...rows] = (await response.text()).trim().split(/\r?\n/).map(row => row.split(","));
  return rows.map(row => Object.fromEntries(header.map((key, index) => [key, Number.isNaN(Number(row[index])) ? row[index] : Number(row[index])])));
}

async function loadData() {
  const paths = [
    fetch("./assets/data/site-data.json").then(response => response.json()),
    loadCsv("./assets/data/head-sparsity-baseline.csv"),
    loadCsv("./assets/data/head-sparsity-damaged.csv"),
    loadCsv("./assets/data/dense-sparsity-baseline.csv"),
    loadCsv("./assets/data/dense-sparsity-damaged.csv"),
    loadCsv("./assets/data/per-tag-accuracy.csv"),
    fetch("./assets/data/representation-states.json").then(response => response.json())
  ];
  [app.data, app.headBaseline, app.headDamage, app.denseBaseline, app.denseDamage, app.perTag, app.representations] = await Promise.all(paths);
}

function setStage(stage) {
  app.stage = Number(stage);
  $$("[data-stage]").forEach(button => button.setAttribute("aria-selected", String(Number(button.dataset.stage) === app.stage)));
  $("#stage-scrubber").value = app.stage;
  $("#stage-output").value = app.data.stages[app.stage].letter;
  renderExperiment();
}

function setCondition(condition, jumpToOutcome = false) {
  app.condition = condition;
  $$("[data-condition]").forEach(button => button.setAttribute("aria-selected", String(button.dataset.condition === condition)));
  if (jumpToOutcome) app.stage = 3;
  setStage(app.stage);
  selectResult(condition);
}

function componentRows(trainable, lesionVisible) {
  const rows = [
    ["Encoder weights", trainable.includes("encoder") ? "trainable-encoder" : "fixed", trainable.includes("encoder") ? "trainable" : "fixed", "△"],
    ["Projection gates", trainable.includes("gates") ? "trainable-gate" : "fixed", trainable.includes("gates") ? "trainable" : "fixed", "○"],
    ["Permanent lesion", "lesioned", lesionVisible ? "clamped" : "not applied", lesionVisible ? "×" : "—"],
    ["Linear readout", trainable.includes("readout") ? "trainable-readout" : "fixed", trainable.includes("readout") ? "trainable" : "fixed", "◆"]
  ];
  return rows.map(([label, type, status, icon]) => `<div class="component-row status-${type}"><span class="status-icon" aria-hidden="true">${icon}</span><span>${label}</span><b>${status}</b></div>`).join("");
}

function stageState() {
  const stage = app.data.stages[app.stage];
  const condition = app.data.conditions[app.condition];
  if (app.stage === 0) return { title: "Core learning", summary: stage.note, trainable: ["gates", "readout"], accuracy: 94.985485, cka: 1, lesion: false };
  if (app.stage === 1) return { title: "Damaged · no adaptation", summary: stage.note, trainable: [], accuracy: 16.829045, cka: .433569, lesion: true };
  if (app.stage === 2) return { title: condition.label, summary: condition.summary, trainable: condition.trainable, accuracy: 16.829045, cka: .433569, lesion: true };
  return { title: condition.label, summary: condition.summary, trainable: condition.trainable, accuracy: condition.accuracy, cka: condition.cka_core, lesion: true };
}

function renderExperiment() {
  const stage = app.data.stages[app.stage];
  const state = stageState();
  $("#stage-kicker").textContent = `Stage ${stage.letter}`;
  $("#stage-title").textContent = stage.title;
  $("#stage-score").textContent = `${format(state.accuracy)}%`;
  $("#condition-title").textContent = state.title;
  $("#condition-summary").textContent = state.summary;
  $("#condition-accuracy").textContent = `${format(state.accuracy)}%`;
  $("#condition-cka").textContent = format(state.cka);
  $("#component-status").innerHTML = componentRows(state.trainable, state.lesion);
  renderSchematic(state);
}

function renderSchematic(state) {
  const columns = ["Q", "K", "V", "Attn out", "FFN in", "FFN out"];
  const selected = state.trainable;
  const cells = [];
  for (let layer = 0; layer < 12; layer += 1) {
    const headSparsity = mean(Object.entries(app.headBaseline[layer]).filter(([key]) => key.startsWith("head_")).map(([, value]) => value));
    const dense = [app.denseBaseline[layer].module_0, app.denseBaseline[layer].module_1, app.denseBaseline[layer].module_2].map(value => value / 100);
    const values = [headSparsity, headSparsity, headSparsity, ...dense];
    values.forEach((sparsity, column) => {
      const x = 145 + column * 105;
      const y = 65 + layer * 29;
      const coreSelected = sparsity < .5;
      const lesioned = state.lesion && coreSelected;
      const gateActive = selected.includes("gates") && !lesioned;
      const opacity = clamp(1 - sparsity, .18, .92);
      cells.push(`<g class="schematic-cell" data-layer="${layer}">
        <rect x="${x}" y="${y}" width="62" height="16" rx="8" fill="${selected.includes("encoder") ? "var(--encoder)" : "var(--fixed)"}" opacity="${.1 + opacity * .18}"/>
        <circle cx="${x + 31}" cy="${y + 8}" r="6" fill="${coreSelected ? "var(--gate)" : "white"}" stroke="var(--gate)" stroke-width="2" opacity="${lesioned ? .2 : opacity}" class="${gateActive ? "trainable-gate" : ""}"/>
        ${lesioned ? `<path d="M${x+23} ${y} l16 16 M${x+39} ${y} l-16 16" stroke="var(--lesion)" stroke-width="3"/>` : ""}
      </g>`);
    });
  }
  const flow = app.stage === 0 ? "Learning selected routes" : app.stage === 1 ? "Original route interrupted" : app.stage === 2 ? "Trainable degrees of freedom selected" : "Recovered endpoint";
  const readoutColor = selected.includes("readout") ? "var(--readout)" : "var(--fixed)";
  $("#model-schematic").innerHTML = `<svg viewBox="0 0 900 460" aria-hidden="true">
    <defs><pattern id="hatch" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="7" stroke="var(--lesion)" stroke-width="2"/></pattern></defs>
    <text x="20" y="34" fill="var(--muted)" font-size="12">BERT layer</text>
    ${columns.map((label, index) => `<text x="${176 + index * 105}" y="34" text-anchor="middle" fill="var(--muted)" font-size="12">${label}</text>`).join("")}
    ${Array.from({length: 12}, (_, layer) => `<text x="76" y="${78 + layer * 29}" text-anchor="middle" fill="var(--muted)" font-size="12">${layer}</text><line x1="105" y1="${86 + layer * 29}" x2="800" y2="${86 + layer * 29}" stroke="#e5e2db"/>`).join("")}
    ${cells.join("")}
    <path d="M112 412 H805" stroke="${selected.includes("encoder") ? "var(--encoder)" : "var(--fixed)"}" stroke-width="7" stroke-linecap="round" opacity=".75"/>
    <path d="M805 412 h22" stroke="var(--ink)" stroke-width="2"/><path d="M827 412 l-8 -6 v12 z" fill="var(--ink)"/>
    <rect x="836" y="382" width="48" height="60" rx="5" fill="white" stroke="${readoutColor}" stroke-width="4"/>
    <text x="860" y="407" text-anchor="middle" fill="${readoutColor}" font-size="12" font-weight="700">POS</text><text x="860" y="424" text-anchor="middle" fill="var(--muted)" font-size="10">readout</text>
    <text x="112" y="447" fill="var(--muted)" font-size="12">${flow}</text>
  </svg>`;
}

function renderLayerInspector(layer = app.layer) {
  app.layer = layer;
  $$("#layer-buttons button").forEach(button => button.setAttribute("aria-pressed", String(Number(button.dataset.layer) === layer)));
  const headBase = mean(Object.entries(app.headBaseline[layer]).filter(([key]) => key.startsWith("head_")).map(([, value]) => value)) * 100;
  const headDamage = mean(Object.entries(app.headDamage[layer]).filter(([key]) => key.startsWith("head_")).map(([, value]) => value)) * 100;
  const denseBase = mean([app.denseBaseline[layer].module_0, app.denseBaseline[layer].module_1, app.denseBaseline[layer].module_2]);
  const denseDamage = mean([app.denseDamage[layer].module_0, app.denseDamage[layer].module_1, app.denseDamage[layer].module_2]);
  const bar = (label, value, damage = false) => `<div class="mini-bar ${damage ? "damage" : ""}"><span>${label}</span><span class="mini-bar-track"><i style="width:${value}%"></i></span><b>${format(value, 1)}%</b></div>`;
  $("#layer-detail").innerHTML = `<p class="kicker">Layer ${layer} · inactive gates</p><div class="mini-bars">${bar("Q/K/V core", headBase)}${bar("Q/K/V lesion", headDamage, true)}${bar("Dense core", denseBase)}${bar("Dense lesion", denseDamage, true)}</div>`;
}

function renderRepresentation(key = "core") {
  const state = app.representations.states[key];
  const condition = app.data.conditions[key];
  const { x: xb, y: yb } = app.representations.meta.bounds;
  const sx = value => 54 + (value - xb[0]) / (xb[1] - xb[0]) * 636;
  const sy = value => 445 - (value - yb[0]) / (yb[1] - yb[0]) * 405;
  $$("#representation-controls button").forEach(button => button.setAttribute("aria-selected", String(button.dataset.representation === key)));
  $("#representation-title").textContent = state.label;
  $("#representation-full-accuracy").textContent = `${format(condition.accuracy)}%`;
  $("#representation-sample-accuracy").textContent = `${state.sample_accuracy.toFixed(2)}%`;
  const marks = state.x.map((value, index) => {
    const x = clamp(sx(value), 54, 690), y = clamp(sy(state.y[index]), 40, 445);
    const label = `Token ${app.representations.tokens.id[index]}: ${app.representations.tokens.gold[index]} → ${state.pred[index]}`;
    return state.correct[index]
      ? `<circle class="correct" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3.5"><title>${label}</title></circle>`
      : `<path class="incorrect" d="M${(x-3).toFixed(1)} ${(y-3).toFixed(1)}l6 6m0-6l-6 6"><title>${label}</title></path>`;
  }).join("");
  $("#representation-map").innerHTML = `<title id="representation-map-title">${state.label}</title><desc id="representation-map-desc">The same 816 POS-balanced tokens in a PCA basis fitted once on the core representation.</desc>
    <path class="grid" d="M54 40V445H690M54 242H690M372 40V445" fill="none"/>
    <g>${marks}</g>
    <text class="axis-label" x="372" y="482" text-anchor="middle">PC1 · 14.50% variance</text>
    <text class="axis-label" x="16" y="242" text-anchor="middle" transform="rotate(-90 16 242)">PC2 · 8.82% variance</text>`;
}

function renderResults() {
  const order = ["core", "encoder_only", "readout_and_mask_reg", "readout_only", "mask_only_inverse_reg", "mask_only_no_reg", "mask_only_reg", "damage"];
  $("#results-controls").innerHTML = order.map(key => `<button type="button" role="option" aria-selected="${key === app.condition}" data-result="${key}"><i aria-hidden="true"></i><span>${app.data.conditions[key].short}</span><small>${format(app.data.conditions[key].accuracy)}%</small></button>`).join("");
  const chart = $("#accuracy-cka-chart");
  const x = value => 85 + (value - .38) / (.64) * 600;
  const y = value => 420 - (value - 10) / 90 * 350;
  const xTicks = [.4,.5,.6,.7,.8,.9,1];
  const yTicks = [20,40,60,80,100];
  const labels = {core:[-42,-14], damage:[8,22], mask_only_no_reg:[8,-10], mask_only_reg:[8,20], mask_only_inverse_reg:[8,-12], readout_only:[8,-12], readout_and_mask_reg:[8,-12], encoder_only:[8,-12]};
  chart.innerHTML = `<g class="axis">${xTicks.map(t => `<line x1="${x(t)}" y1="70" x2="${x(t)}" y2="420" opacity=".18"/><text x="${x(t)}" y="448" text-anchor="middle">${t.toFixed(1)}</text>`).join("")}${yTicks.map(t => `<line x1="85" y1="${y(t)}" x2="685" y2="${y(t)}" opacity=".18"/><text x="70" y="${y(t)+4}" text-anchor="end">${t}</text>`).join("")}<text x="385" y="486" text-anchor="middle">Linear CKA to pre-lesion core</text><text transform="translate(22 250) rotate(-90)" text-anchor="middle">UD-EWT dev accuracy (%)</text></g>` + order.map(key => {
    const condition = app.data.conditions[key];
    const [dx,dy] = labels[key];
    return `<g class="point ${key === "readout_only" ? "readout-point" : ""}" role="button" tabindex="0" aria-label="${condition.label}: ${format(condition.accuracy)} percent accuracy, ${format(condition.cka_core)} CKA to core" aria-selected="${key === app.condition}" data-point="${key}" transform="translate(${x(condition.cka_core)} ${y(condition.accuracy)})"><circle r="10"/><text x="${dx}" y="${dy}">${condition.short}</text></g>`;
  }).join("");
  selectResult(app.condition);
  renderSeedChart(order);
}

function selectResult(key) {
  if (!app.data?.conditions[key]) return;
  app.condition = key;
  $$('[data-result]').forEach(button => button.setAttribute("aria-selected", String(button.dataset.result === key)));
  $$('[data-point]').forEach(point => point.setAttribute("aria-selected", String(point.dataset.point === key)));
  const condition = app.data.conditions[key];
  $("#selected-result").innerHTML = `<strong>${condition.label}: ${format(condition.accuracy)}% accuracy · ${format(condition.cka_core)} CKA to core · ${format(condition.cka_damage)} CKA to damage</strong><p>${condition.implication}</p>`;
}

function renderSeedChart(order) {
  $("#seed-chart").innerHTML = order.map(key => {
    const values = app.data.seeds[key];
    const min = Math.min(...values), max = Math.max(...values), avg = mean(values);
    return `<div class="seed-row"><span>${app.data.conditions[key].short}</span><span class="seed-track"><i class="seed-range" style="left:${min}%;width:${max-min}%"></i>${values.map(value => `<i class="seed-dot" style="left:${value}%" title="${format(value)}%"></i>`).join("")}</span><b>${format(avg)}</b></div>`;
  }).join("");
}

// Renders one of three exported-data views; all coordinates are SVG display units.
function renderEvidence(view = app.evidenceView, option = app.evidenceOption) {
  app.evidenceView = view;
  const settings = {
    qkv: { kicker: "Projection-specific gates", title: "Inactive Q/K/V input groups", options: [["core", "Core"], ["damaged", "Damaged"], ["delta", "Increase"]] },
    dense: { kicker: "Dense projection gates", title: "Core and damaged sparsity by layer", options: [["module_0", "Attention out"], ["module_1", "FFN in"], ["module_2", "FFN out"]] },
    pos: { kicker: "Task behavior", title: "Per-tag accuracy relative to core", options: [...new Set(app.perTag.map(row => row.condition))].map(value => [value, value]) }
  }[view];
  if (!settings.options.some(([value]) => value === option)) option = settings.options[0][0];
  app.evidenceOption = option;
  $$("[data-evidence]").forEach(button => button.setAttribute("aria-selected", String(button.dataset.evidence === view)));
  $("#evidence-kicker").textContent = settings.kicker;
  $("#evidence-chart-title").textContent = settings.title;
  $("#evidence-options").innerHTML = settings.options.map(([value, label]) => `<button type="button" data-evidence-option="${value}" aria-pressed="${value === option}">${label}</button>`).join("");
  if (view === "qkv") renderQkvEvidence(option);
  if (view === "dense") renderDenseEvidence(option);
  if (view === "pos") renderPosEvidence(option);
}

function renderQkvEvidence(option) {
  const values = app.headBaseline.map((row, layer) => Array.from({length: 12}, (_, head) => {
    const core = row[`head_${head}`], damaged = app.headDamage[layer][`head_${head}`];
    return option === "core" ? core : option === "damaged" ? damaged : damaged - core;
  }));
  const label = option === "core" ? "Core inactive fraction" : option === "damaged" ? "Damaged inactive fraction" : "Increase after lesion";
  const cells = values.flatMap((row, layer) => row.map((value, head) => `<rect x="${126 + head * 58}" y="${52 + layer * 31}" width="48" height="22" rx="3" fill="${option === "core" ? "var(--fixed)" : "var(--lesion)"}" fill-opacity="${.08 + .9 * clamp(value, 0, 1)}"><title>Layer ${layer}, group ${head}: ${format(value * 100, 1)}%</title></rect>`)).join("");
  const desc = `${label} for twelve 64-wide Q/K/V input-feature groups in each BERT layer.`;
  $("#evidence-chart").innerHTML = `<desc id="evidence-chart-desc">${desc}</desc><g class="evidence-axis">${Array.from({length: 12}, (_, i) => `<text x="${150 + i*58}" y="35" text-anchor="middle">${i}</text><text x="102" y="${68 + i*31}" text-anchor="end">L${i}</text>`).join("")}</g>${cells}<text class="evidence-label" x="474" y="462" text-anchor="middle">64-wide Q/K/V input group · darker means more inactive</text>`;
  $("#evidence-note").textContent = option === "core" ? "The learned core is sparse but retains routes across layers." : option === "damaged" ? "The structural lesion permanently disables selected groups; dark cells are not routes that later return." : "The increase view isolates how much inactivity the lesion adds to each group.";
}

function renderDenseEvidence(module) {
  const names = {module_0: "attention-output", module_1: "FFN-intermediate", module_2: "FFN-output"};
  const bars = app.denseBaseline.map((row, layer) => {
    const core = row[module], damaged = app.denseDamage[layer][module], y = 54 + layer * 32;
    return `<text class="evidence-tick" x="92" y="${y+8}" text-anchor="end">L${layer}</text><rect x="115" y="${y}" width="${core*6.5}" height="8" fill="var(--fixed)"><title>Core: ${format(core,1)}%</title></rect><rect x="115" y="${y+11}" width="${damaged*6.5}" height="8" fill="var(--lesion)"><title>Damaged: ${format(damaged,1)}%</title></rect>`;
  }).join("");
  const desc = `Core and damaged inactive-gate percentages for the ${names[module]} projection in each layer.`;
  $("#evidence-chart").innerHTML = `<desc id="evidence-chart-desc">${desc}</desc><g class="evidence-axis">${[0,25,50,75,100].map(value => `<line x1="${115+value*6.5}" y1="42" x2="${115+value*6.5}" y2="438"/><text x="${115+value*6.5}" y="465" text-anchor="middle">${value}%</text>`).join("")}</g>${bars}<g class="evidence-legend"><rect x="590" y="12" width="14" height="8" fill="var(--fixed)"/><text x="612" y="20">Core</text><rect x="674" y="12" width="14" height="8" fill="var(--lesion)"/><text x="696" y="20">Damaged</text></g>`;
  $("#evidence-note").textContent = `Paired bars show the same ${names[module]} projection before and immediately after the fixed structural lesion.`;
}

function renderPosEvidence(condition) {
  const rows = app.perTag.filter(row => row.condition === condition).sort((a, b) => b.dev_tag_probability - a.dev_tag_probability);
  const bars = rows.map((row, index) => {
    const y = 28 + index * 25, width = Math.min(row.accuracy_percent_of_baseline, 120) * 5.25;
    return `<text class="evidence-tick" x="145" y="${y+10}" text-anchor="end">${row.tag}</text><rect x="160" y="${y}" width="${width}" height="14" fill="var(--readout)" fill-opacity=".82"><title>${row.tag}: ${format(row.accuracy_percent_of_baseline,1)}% of core</title></rect><text class="evidence-value" x="${170+width}" y="${y+11}">${format(row.accuracy_percent_of_baseline,0)}%</text>`;
  }).join("");
  const desc = `${condition} accuracy for each POS tag as a percentage of the core baseline.`;
  $("#evidence-chart").innerHTML = `<desc id="evidence-chart-desc">${desc}</desc><line class="baseline-line" x1="685" y1="18" x2="685" y2="456"/><text class="evidence-label" x="685" y="478" text-anchor="middle">100% of core</text>${bars}`;
  $("#evidence-note").textContent = `${condition}: tags are ordered by their frequency in the development set; values above 100% exceed the core tag-level accuracy.`;
}

function bindEvents() {
  $$("[data-stage]").forEach(button => button.addEventListener("click", () => setStage(button.dataset.stage)));
  $("#stage-scrubber").addEventListener("input", event => setStage(event.target.value));
  $$("[data-condition]").forEach(button => button.addEventListener("click", () => setCondition(button.dataset.condition, true)));
  $("#play-stage").addEventListener("click", () => {
    if (app.timer) { clearInterval(app.timer); app.timer = null; $("#play-stage").innerHTML = "<span aria-hidden='true'>▶</span> Play"; return; }
    if (app.stage === 3) setStage(0);
    $("#play-stage").innerHTML = "<span aria-hidden='true'>Ⅱ</span> Pause";
    app.timer = setInterval(() => { if (app.stage === 3) { clearInterval(app.timer); app.timer = null; $("#play-stage").innerHTML = "<span aria-hidden='true'>▶</span> Play"; } else setStage(app.stage + 1); }, 1800);
  });
  $("#layer-buttons").addEventListener("click", event => { const button = event.target.closest("button"); if (button) renderLayerInspector(Number(button.dataset.layer)); });
  $("#representation-controls").addEventListener("click", event => { const button = event.target.closest("button"); if (button) renderRepresentation(button.dataset.representation); });
  $("#results-controls").addEventListener("click", event => { const button = event.target.closest("button"); if (button) selectResult(button.dataset.result); });
  $("#accuracy-cka-chart").addEventListener("click", event => { const point = event.target.closest("[data-point]"); if (point) selectResult(point.dataset.point); });
  $("#accuracy-cka-chart").addEventListener("keydown", event => { if ((event.key === "Enter" || event.key === " ") && event.target.dataset.point) { event.preventDefault(); selectResult(event.target.dataset.point); } });
  $("#evidence-tabs").addEventListener("click", event => { const button = event.target.closest("[data-evidence]"); if (button) renderEvidence(button.dataset.evidence); });
  $("#evidence-options").addEventListener("click", event => { const button = event.target.closest("[data-evidence-option]"); if (button) renderEvidence(app.evidenceView, button.dataset.evidenceOption); });
}

async function init() {
  try {
    await loadData();
    $("#layer-buttons").innerHTML = Array.from({length:12}, (_, layer) => `<button type="button" data-layer="${layer}" aria-pressed="${layer === 0}" aria-label="Inspect layer ${layer}">${layer}</button>`).join("");
    const representationOrder = ["core", "damage", "mask_only_inverse_reg", "readout_only", "readout_and_mask_reg", "encoder_only"];
    $("#representation-controls").innerHTML = representationOrder.map(key => `<button type="button" role="tab" data-representation="${key}" aria-selected="${key === "core"}">${app.data.conditions[key].short}</button>`).join("");
    renderRepresentation();
    renderLayerInspector();
    renderResults();
    renderEvidence();
    bindEvents();
    setStage(0);
  } catch (error) {
    console.error(error);
    $("#model-schematic").innerHTML = `<p role="alert">Interactive data could not be loaded. Reload the page to retry.</p>`;
  }
}

init();
