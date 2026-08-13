"use strict";

const byId = (id) => document.getElementById(id);
let predictionSchema = null;

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {"Content-Type": "application/json", ...(options.headers || {})},
  });
  let payload;
  try { payload = await response.json(); }
  catch { payload = {message: "The local service returned an unreadable response."}; }
  if (!response.ok) throw new Error(payload.message || `Request failed (${response.status}).`);
  return payload;
}

function setError(id, error) {
  const target = byId(id);
  target.textContent = error instanceof Error ? error.message : String(error);
  target.classList.remove("hidden");
}

function clearError(id) { byId(id).classList.add("hidden"); }

function evidenceLabel(item, index) {
  return item.citation_marker || item.marker || `[S${index + 1}]`;
}

function renderEvidence(answer, retrieved) {
  const citations = Array.isArray(answer.citations) ? answer.citations : [];
  const candidates = citations.length ? citations : (retrieved.results || []);
  const list = byId("evidence-list");
  list.replaceChildren();
  for (const [index, item] of candidates.entries()) {
    const article = document.createElement("article");
    article.className = "evidence-item";
    const title = document.createElement("strong");
    title.textContent = `${evidenceLabel(item, index)} ${item.source_title || item.title || item.chunk_id || "Governed source"}`;
    const meta = document.createElement("span");
    meta.textContent = [item.classification, item.locator].filter(Boolean).join(" · ") || "Provenance preserved by API";
    article.append(title, meta);
    list.append(article);
  }
  if (!candidates.length) {
    const empty = document.createElement("p");
    empty.className = "boundary";
    empty.textContent = "No citation was emitted. Review the answer status and evidence boundary.";
    list.append(empty);
  }
  byId("evidence-count").textContent = `${candidates.length} item${candidates.length === 1 ? "" : "s"}`;
}

async function submitKnowledge(event) {
  event.preventDefault();
  clearError("knowledge-error");
  byId("answer-result").classList.add("hidden");
  const query = byId("knowledge-query").value.trim();
  const topK = Number(byId("top-k").value);
  try {
    const [answer, retrieved] = await Promise.all([
      api("/api/v1/answer", {method: "POST", body: JSON.stringify({query})}),
      api("/api/v1/retrieve", {method: "POST", body: JSON.stringify({query, top_k: topK})}),
    ]);
    byId("answer-status").textContent = answer.status.replaceAll("_", " ");
    byId("answer-text").textContent = answer.answer;
    byId("answer-boundary").textContent = `Reason: ${answer.reason_code} · Intent: ${answer.intent} · Request: ${answer.request_id}`;
    renderEvidence(answer, retrieved);
    byId("answer-result").classList.remove("hidden");
  } catch (error) { setError("knowledge-error", error); }
}

async function loadSchema() {
  predictionSchema = await api("/api/v1/prediction/schema");
  byId("model-badge").textContent = `${predictionSchema.feature_count} features · threshold ${predictionSchema.threshold.toFixed(6)}`;
}

function zeroTemplate() {
  if (!predictionSchema) return;
  byId("feature-json").value = JSON.stringify(Object.fromEntries(predictionSchema.feature_names.map((name) => [name, 0.0])), null, 2);
}

async function copySchema() {
  if (!predictionSchema) return;
  await navigator.clipboard.writeText(predictionSchema.feature_names.join("\n"));
  byId("copy-schema").textContent = "Copied";
  window.setTimeout(() => { byId("copy-schema").textContent = "Copy feature names"; }, 1200);
}

async function submitPrediction(event) {
  event.preventDefault();
  clearError("prediction-error");
  byId("prediction-result").classList.add("hidden");
  try {
    const features = JSON.parse(byId("feature-json").value);
    const result = await api("/api/v1/predict", {method: "POST", body: JSON.stringify({features})});
    byId("alarm-result").textContent = result.alarm ? "Review alarm" : "No threshold alarm";
    byId("score-result").textContent = result.unusualness_score.toFixed(6);
    byId("threshold-result").textContent = result.threshold.toFixed(6);
    byId("prediction-interpretation").textContent = `${result.interpretation} Request: ${result.request_id}`;
    byId("prediction-result").classList.remove("hidden");
  } catch (error) { setError("prediction-error", error); }
}

async function refreshOperations() {
  try {
    const [ready, metrics, reviews] = await Promise.all([
      api("/health/ready"), api("/api/v1/metrics"), api("/api/v1/evaluations?limit=1"),
    ]);
    const isReady = ready.status === "ready";
    byId("readiness-value").textContent = ready.status.replaceAll("_", " ");
    byId("interaction-count").textContent = metrics.persistence.records;
    byId("review-count").textContent = metrics.persistence.evaluations;
    byId("system-status").textContent = isReady ? "Governed services ready" : "Governed dependency unavailable";
    byId("status-dot").className = `status-dot ${isReady ? "ready" : "not-ready"}`;
    return reviews;
  } catch {
    byId("system-status").textContent = "Local service unavailable";
    byId("status-dot").className = "status-dot not-ready";
  }
}

for (const tab of document.querySelectorAll(".tab")) {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab, .panel").forEach((item) => item.classList.remove("active"));
    tab.classList.add("active");
    byId(tab.dataset.panel).classList.add("active");
  });
}

byId("knowledge-form").addEventListener("submit", submitKnowledge);
byId("prediction-form").addEventListener("submit", submitPrediction);
byId("load-template").addEventListener("click", zeroTemplate);
byId("copy-schema").addEventListener("click", copySchema);
byId("refresh-operations").addEventListener("click", refreshOperations);

loadSchema().catch((error) => setError("prediction-error", error));
refreshOperations();
