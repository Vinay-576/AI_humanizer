/* ============================================================
   app.js — HumanizeAI Frontend Logic
   Mirrors master_pipeline.py, db_builder.py, paraphraser.py
   ============================================================ */

// ==================== DB SEED DATA ====================
// Mirrors db_builder.py seed_data
const WORD_REPLACEMENTS = [
  { ai_word: "delve",             alternatives: ["look into", "dig into", "check out"],           register: "both" },
  { ai_word: "intricate",        alternatives: ["complex", "detailed", "tricky"],                 register: "both" },
  { ai_word: "utilize",          alternatives: ["use", "apply", "work with"],                     register: "both" },
  { ai_word: "furthermore",      alternatives: ["also", "plus", "and"],                           register: "informal" },
  { ai_word: "moreover",         alternatives: ["also", "on top of that", "plus"],                register: "informal" },
  { ai_word: "however",          alternatives: ["but", "still", "though"],                        register: "informal" },
  { ai_word: "thus",             alternatives: ["so", "therefore", "because of that"],            register: "both" },
  { ai_word: "hence",            alternatives: ["so", "that's why", "for that reason"],           register: "both" },
  { ai_word: "indeed",           alternatives: ["really", "actually", "in fact"],                 register: "informal" },
  { ai_word: "it is worth noting", alternatives: ["note that", "keep in mind", "remember"],      register: "both" },
  { ai_word: "in conclusion",    alternatives: ["to sum up", "in short", "basically"],            register: "informal" },
  { ai_word: "in addition",      alternatives: ["also", "plus", "on top of that"],                register: "informal" },
  { ai_word: "as a result",      alternatives: ["so", "because of this", "that's why"],           register: "both" },
  { ai_word: "on the other hand",alternatives: ["but", "at the same time", "still"],              register: "both" },
  { ai_word: "testament",        alternatives: ["proof", "evidence", "sign"],                     register: "formal" },
  { ai_word: "demonstrates",     alternatives: ["shows", "proves", "explains"],                   register: "both" },
  { ai_word: "facilitates",      alternatives: ["helps", "makes easier", "supports"],             register: "both" },
  { ai_word: "implements",       alternatives: ["builds", "creates", "sets up"],                  register: "both" },
  { ai_word: "leverages",        alternatives: ["uses", "takes advantage of", "works with"],      register: "both" },
  { ai_word: "robust",           alternatives: ["strong", "reliable", "solid"],                   register: "both" },
  { ai_word: "scalable",         alternatives: ["can grow", "handles more load", "expandable"],   register: "both" },
  { ai_word: "optimize",         alternatives: ["improve", "make better", "tune"],                register: "both" },
  { ai_word: "efficient",        alternatives: ["fast", "quick", "works well"],                   register: "informal" },
  { ai_word: "seamless",         alternatives: ["smooth", "easy", "without issues"],              register: "informal" },
  { ai_word: "significant",      alternatives: ["important", "big", "major"],                     register: "both" },
  { ai_word: "numerous",         alternatives: ["many", "a lot of", "plenty of"],                 register: "informal" },
  { ai_word: "approximately",    alternatives: ["about", "around", "roughly"],                    register: "both" },
  { ai_word: "subsequently",     alternatives: ["later", "after that", "then"],                   register: "informal" },
  { ai_word: "is utilized",      alternatives: ["is used", "gets used"],                          register: "both" },
  { ai_word: "is implemented",   alternatives: ["is built", "is created"],                        register: "both" },
  { ai_word: "has been developed", alternatives: ["was built", "we built"],                       register: "informal" },
  { ai_word: "was performed",    alternatives: ["was done", "we did"],                            register: "informal" },
  { ai_word: "in order to",      alternatives: ["to", "so we can"],                               register: "informal" },
  { ai_word: "due to the fact that", alternatives: ["because", "since"],                          register: "informal" },
  { ai_word: "a large number of",  alternatives: ["many", "a lot of"],                            register: "informal" },
  { ai_word: "at this point in time", alternatives: ["now", "right now"],                         register: "informal" },
];

// ==================== LOGGER ====================
const Logger = {
  box: null,
  init() { this.box = document.getElementById("consoleBox"); },
  log(msg, type = "info") {
    if (!this.box) return;
    const line = document.createElement("div");
    line.className = `console-line console-${type}`;
    const ts = new Date().toLocaleTimeString();
    line.textContent = `[${ts}] ${msg}`;
    this.box.appendChild(line);
    this.box.scrollTop = this.box.scrollHeight;
  },
  clear() {
    if (!this.box) return;
    this.box.innerHTML = '<div class="console-line console-info">[System] Console cleared.</div>';
  }
};

// ==================== SCORE ENGINE ====================
// Mirrors MasterHumanizer.calculate_score()
const ScoreEngine = {
  AI_TRIGGERS: [
    "delve","utilize","leverage","robust","scalable","seamless","efficient",
    "significant","numerous","intricate","crucial","essential","furthermore",
    "moreover","thus","hence","additionally","in conclusion","in summary",
    "as a result","this demonstrates","plays a vital role",
    "in order to","due to the fact that"
  ],

  countWords(text) {
    return text.trim().split(/\s+/).filter(Boolean);
  },

  vocabDiversity(tokens) {
    if (!tokens.length) return 0;
    return (new Set(tokens).size / tokens.length) * 100;
  },

  burstiness(text) {
    const sentences = text.match(/[^.!?]+[.!?]+/g) || [text];
    const lengths = sentences.map(s => s.trim().split(/\s+/).length);
    if (lengths.length <= 1) return 50;
    const mean = lengths.reduce((a, b) => a + b, 0) / lengths.length;
    const variance = lengths.reduce((s, x) => s + (x - mean) ** 2, 0) / lengths.length;
    return Math.min((variance / 30) * 100, 100);
  },

  patternScore(text) {
    const lower = text.toLowerCase();
    const hits = this.AI_TRIGGERS.filter(t => new RegExp(`\\b${t}\\b`).test(lower)).length;
    return Math.max(100 - hits * 10, 0);
  },

  calculate(text) {
    const tokens = this.countWords(text).map(w => w.toLowerCase().replace(/[^a-z]/g, "")).filter(Boolean);
    const vocab  = this.vocabDiversity(tokens);
    const burst  = this.burstiness(text);
    const pat    = this.patternScore(text);
    const perp   = 80; // simulated

    const total  = (0.35 * perp) + (0.25 * burst) + (0.20 * vocab) + (0.20 * pat);
    return {
      total: Math.round(total * 100) / 100,
      perplexity: perp,
      burstiness: Math.round(burst * 100) / 100,
      vocabDiversity: Math.round(vocab * 100) / 100,
      patternScore: Math.round(pat * 100) / 100,
    };
  }
};

// ==================== TEXT TRANSFORMERS ====================
// Mirrors MasterHumanizer pipeline steps

const Transformers = {

  // replace_repetitions()
  fixRepetitions(text) {
    const map = {
      "\\bthe data\\b": "it",
      "\\bthe system\\b": "it",
      "\\bthe results\\b": "them",
      "\\bthe model\\b": "it",
    };
    for (const [pat, rep] of Object.entries(map)) {
      text = text.replace(new RegExp(pat, "gi"), rep);
    }
    return text;
  },

  // vary_sentence_structure()
  varySentenceStructure(text) {
    const starters = ["Honestly,", "So,", "Well,", "Basically,"];
    const sentences = text.match(/[^.!?]+[.!?]+/g) || [text];
    return sentences.map(sent => {
      const r = Math.random();
      if (r < 0.25) {
        const words = sent.trim().split(/\s+/);
        if (words.length > 10) {
          sent = words.slice(0, Math.floor(words.length / 2)).join(" ") + ".";
        }
      } else if (r < 0.5) {
        sent = starters[Math.floor(Math.random() * starters.length)] + " " + sent.trim();
      } else if (r < 0.7) {
        sent = sent.replace(/,/g, " and");
      }
      return sent.trim();
    }).join(" ");
  },

  // apply_contractions()
  applyContractions(text) {
    const map = {
      "do not": "don't", "cannot": "can't", "it is": "it's",
      "we are": "we're", "they are": "they're", "that is": "that's",
      "there is": "there's"
    };
    for (const [k, v] of Object.entries(map)) {
      text = text.replace(new RegExp(`\\b${k}\\b`, "gi"), v);
    }
    return text;
  },

  // apply_synonyms() using word_replacements table
  applySynonyms(text) {
    for (const row of WORD_REPLACEMENTS) {
      if (Math.random() < 0.7) continue; // 30% chance to apply each
      const alts = row.alternatives;
      const pick = alts[Math.floor(Math.random() * alts.length)];
      text = text.replace(
        new RegExp(`\\b${row.ai_word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "gi"),
        pick
      );
    }
    return text;
  },

  // ML Paraphraser simulation (client-side approximation)
  paraphrase(text) {
    // Structural rewrites for common AI patterns
    const rewrites = [
      [/Furthermore,?\s*/gi, "Also, "],
      [/\bIt is crucial to\b/gi, "You need to"],
      [/\bdelve into\b/gi, "look at"],
      [/\bIn order to\b/gi, "To"],
      [/\bdue to the fact that\b/gi, "because"],
      [/\bIn conclusion,?\b/gi, "To wrap up,"],
      [/\bIt is worth noting that\b/gi, "Note that"],
      [/\bAs a result,?\b/gi, "So,"],
      [/\bMoreover,?\b/gi, "On top of that,"],
      [/\bHowever,?\b/gi, "But"],
      [/\bThis demonstrates\b/gi, "This shows"],
      [/\bplays a vital role\b/gi, "matters a lot"],
      [/\butilizes?\b/gi, "uses"],
      [/\bleverages?\b/gi, "uses"],
      [/\brobust\b/gi, "solid"],
      [/\bseamless(ly)?\b/gi, "smooth"],
      [/\bsignificant\b/gi, "major"],
      [/\bnumerous\b/gi, "many"],
      [/\befficiently\b/gi, "well"],
    ];
    for (const [pat, rep] of rewrites) text = text.replace(pat, rep);
    return text;
  }
};

// ==================== PIPELINE RUNNER ====================
const Pipeline = {
  steps: [
    { id: "paraphraser",   label: "ML Paraphraser",     fn: t => Transformers.paraphrase(t) },
    { id: "repetitions",   label: "Fix Repetitions",     fn: t => Transformers.fixRepetitions(t) },
    { id: "variation",     label: "Sentence Variation",  fn: t => Transformers.varySentenceStructure(t) },
    { id: "contractions",  label: "Contractions",        fn: t => Transformers.applyContractions(t) },
    { id: "synonyms",      label: "Synonym Swap",        fn: t => Transformers.applySynonyms(t) },
  ],

  async run(text, { targetScore, maxIter, enabledSteps }) {
    const runBtn = document.getElementById("runBtn");
    runBtn.classList.add("loading");
    runBtn.querySelector(".btn-run-text").textContent = "Running...";

    showProgress(true);
    let current = text;

    Logger.log("🚀 STARTING HUMANIZATION PIPELINE", "step");
    Logger.log(`Target score: ${targetScore} | Max iterations: ${maxIter}`, "info");

    for (let i = 0; i <= maxIter; i++) {
      const result = ScoreEngine.calculate(current);
      Logger.log(`[Iteration ${i}] Score: ${result.total}/100`, "info");
      updateScore(result);

      if (result.total >= targetScore) {
        Logger.log("✅ Target score achieved!", "success");
        break;
      }

      if (i === maxIter) { Logger.log("⚠ Max iterations reached.", "warn"); break; }

      Logger.log(`❌ Score below target. Running transformations...`, "warn");

      const activeSteps = this.steps.filter(s => enabledSteps.has(s.id));
      for (let si = 0; si < activeSteps.length; si++) {
        const step = activeSteps[si];
        setProgressStep(step.id, "active", activeSteps);
        Logger.log(` -> ${step.label}...`, "step");
        await delay(180);
        current = step.fn(current);
        setProgressStep(step.id, "done", activeSteps);
        setProgressBar(((si + 1) / activeSteps.length) * 100 * ((i + 1) / maxIter));
      }
    }

    const finalScore = ScoreEngine.calculate(current);
    updateScore(finalScore);

    document.getElementById("outputBox").innerHTML = escapeHtml(current);
    Logger.log("FINAL TEXT generated.", "success");
    Logger.log(`Final score: ${finalScore.total}/100`, "success");

    runBtn.classList.remove("loading");
    runBtn.querySelector(".btn-run-text").textContent = "Run Pipeline";
    setProgressBar(100);
    setTimeout(() => showProgress(false), 1200);
  }
};

// ==================== HELPERS ====================
function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

function escapeHtml(str) {
  return str.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

function showToast(msg) {
  const t = document.createElement("div");
  t.className = "toast"; t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 2100);
}

function showProgress(show) {
  document.getElementById("progressStrip").style.display = show ? "block" : "none";
}

function setProgressBar(pct) {
  document.getElementById("progressBar").style.width = `${Math.min(pct, 100)}%`;
}

function setProgressStep(id, state, steps) {
  const container = document.getElementById("progressSteps");
  // Rebuild step UI
  container.innerHTML = "";
  steps.forEach(s => {
    const div = document.createElement("div");
    let cls = "progress-step";
    if (s.id === id && state === "active") cls += " active";
    else if (s.id === id && state === "done") cls += " done";
    div.className = cls;
    div.innerHTML = `<span class="progress-step-dot"></span><span>${s.label}</span>`;
    container.appendChild(div);
  });
}

function updateScore(result) {
  // Ring
  const circumference = 326.7;
  const offset = circumference - (result.total / 100) * circumference;
  document.getElementById("ringFg").style.strokeDashoffset = offset;
  document.getElementById("scoreNum").textContent = result.total;

  // Breakdown
  const vals = document.querySelectorAll(".breakdown-val");
  if (vals[0]) vals[0].textContent = result.perplexity;
  if (vals[1]) vals[1].textContent = result.burstiness;
  if (vals[2]) vals[2].textContent = result.vocabDiversity;
  if (vals[3]) vals[3].textContent = result.patternScore;
}

// ==================== DB TABLE RENDER ====================
function renderDbTable(data) {
  const tbody = document.getElementById("dbTableBody");
  tbody.innerHTML = "";
  data.forEach(row => {
    const tr = document.createElement("tr");
    const altsHtml = row.alternatives.map(a => `<span class="alt-tag">${escapeHtml(a)}</span>`).join("");
    const regClass = `reg-${row.register}`;
    tr.innerHTML = `
      <td><code style="color:var(--accent);font-size:0.78rem;">${escapeHtml(row.ai_word)}</code></td>
      <td><div class="alt-tags">${altsHtml}</div></td>
      <td><span class="reg-badge ${regClass}">${row.register}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

// ==================== PARAPHRASER TAB ====================
function runParaphraser() {
  const input = document.getElementById("paraInput").value.trim();
  if (!input) return showToast("Please enter some text first.");
  const words = input.split(/\s+/).length;
  if (words < 8) return showToast("Enter at least 8 words.");

  const results = document.getElementById("paraResults");
  results.innerHTML = "";

  // Generate N variations (mirrors num_return_sequences)
  const n = parseInt(document.getElementById("numSeqVal").textContent) || 3;
  const variations = [];
  for (let i = 0; i < n; i++) {
    let v = Transformers.paraphrase(input);
    v = Transformers.applyContractions(v);
    v = Transformers.applySynonyms(v);
    if (Math.random() > 0.5) v = Transformers.varySentenceStructure(v);
    variations.push(v);
  }

  variations.forEach((v, i) => {
    const div = document.createElement("div");
    div.className = "para-result-item";
    div.innerHTML = `<span class="para-result-label">variant ${i + 1}</span>${escapeHtml(v)}`;
    results.appendChild(div);
  });

  Logger.log(`Paraphraser: generated ${n} variants.`, "success");
}

// ==================== INIT ====================
document.addEventListener("DOMContentLoaded", () => {
  Logger.init();
  Logger.log("HumanizeAI Frontend initialized.", "info");

  // --- Tabs ---
  document.querySelectorAll(".nav-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
    });
  });

  // --- Word count ---
  const inputText = document.getElementById("inputText");
  inputText.addEventListener("input", () => {
    const w = inputText.value.trim().split(/\s+/).filter(Boolean).length;
    document.getElementById("inputWordCount").textContent = `${w} word${w !== 1 ? "s" : ""}`;
  });

  // --- Clear ---
  document.getElementById("clearBtn").addEventListener("click", () => {
    inputText.value = "";
    document.getElementById("inputWordCount").textContent = "0 words";
    document.getElementById("outputBox").innerHTML = '<span class="output-placeholder">Your humanized text will appear here after running the pipeline...</span>';
  });

  // --- Sliders ---
  const sliders = [
    ["targetScore", "targetScoreVal"],
    ["maxIter",     "maxIterVal"],
    ["tempSlider",  "tempVal"],
    ["topkSlider",  "topkVal"],
    ["toppSlider",  "toppVal"],
    ["numSeqSlider","numSeqVal"],
  ];
  sliders.forEach(([id, valId]) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener("input", () => {
      document.getElementById(valId).textContent = el.value;
    });
  });

  // --- Run Pipeline ---
  document.getElementById("runBtn").addEventListener("click", () => {
    const text = document.getElementById("inputText").value.trim();
    if (!text) return showToast("Please paste some text first.");

    const enabledSteps = new Set();
    document.querySelectorAll("[data-step]").forEach(cb => {
      if (cb.checked) enabledSteps.add(cb.dataset.step);
    });

    Pipeline.run(text, {
      targetScore: parseFloat(document.getElementById("targetScore").value),
      maxIter:     parseInt(document.getElementById("maxIter").value),
      enabledSteps,
    });
  });

  // --- Copy ---
  document.getElementById("copyBtn").addEventListener("click", () => {
    const out = document.getElementById("outputBox");
    const txt = out.innerText || out.textContent;
    if (!txt || out.querySelector(".output-placeholder")) return showToast("Nothing to copy yet.");
    navigator.clipboard.writeText(txt).then(() => showToast("Copied to clipboard!"));
  });

  // --- Score Output ---
  document.getElementById("scoreOutputBtn").addEventListener("click", () => {
    const out = document.getElementById("outputBox");
    const txt = out.innerText || out.textContent;
    if (!txt || out.querySelector(".output-placeholder")) return showToast("Run the pipeline first.");
    const result = ScoreEngine.calculate(txt);
    updateScore(result);
    showToast(`Score: ${result.total}/100`);
    Logger.log(`Scored output text: ${result.total}/100`, "success");
  });

  // --- DB Table ---
  renderDbTable(WORD_REPLACEMENTS);

  // --- DB Search + Filter ---
  function filterTable() {
    const q = document.getElementById("dbSearch").value.toLowerCase();
    const reg = document.getElementById("registerFilter").value;
    const filtered = WORD_REPLACEMENTS.filter(row => {
      const matchQ = !q || row.ai_word.includes(q) || row.alternatives.some(a => a.includes(q));
      const matchR = !reg || row.register === reg;
      return matchQ && matchR;
    });
    renderDbTable(filtered);
  }
  document.getElementById("dbSearch").addEventListener("input", filterTable);
  document.getElementById("registerFilter").addEventListener("change", filterTable);

  // --- Paraphraser ---
  document.getElementById("paraRunBtn").addEventListener("click", runParaphraser);

  // --- Logs ---
  document.getElementById("clearLogsBtn").addEventListener("click", () => Logger.clear());
  document.getElementById("exportLogsBtn").addEventListener("click", () => {
    const txt = document.getElementById("consoleBox").innerText;
    const blob = new Blob([txt], { type: "text/plain" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
    a.download = "pipeline_logs.txt"; a.click();
  });

  // --- Device tag ---
  const deviceTag = document.getElementById("deviceTag");
  if (deviceTag) {
    // Guess based on browser/platform hint
    const gl = document.createElement("canvas").getContext("webgl");
    const renderer = gl?.getExtension("WEBGL_debug_renderer_info");
    const gpu = renderer ? gl.getParameter(renderer.UNMASKED_RENDERER_WEBGL) : null;
    deviceTag.textContent = gpu ? `GPU: ${gpu.slice(0,30)}` : "CPU (no CUDA detected)";
  }

  Logger.log("All components ready.", "success");
});
