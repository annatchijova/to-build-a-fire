const MAX_PACKAGE_BYTES = 2_000_000;
const MAX_ROWS_PER_SECTION = 500;
const MAX_PATH_CHARS = 2048;
const SHA_PATTERN = /^(?:[a-f0-9]{40}|[a-f0-9]{64})$/;

const elements = {
  file: document.querySelector("#package-file"),
  demo: document.querySelector("#load-demo"),
  status: document.querySelector("#status"),
  empty: document.querySelector("#empty-state"),
  view: document.querySelector("#package-view"),
  exampleNotice: document.querySelector("#example-notice"),
  mapperNav: document.querySelector("#mapper-nav"),
  mapperSection: document.querySelector("#mapper-section"),
};

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined && text !== null) element.textContent = String(text);
  return element;
}

function setStatus(message, kind = "info") {
  elements.status.textContent = message;
  elements.status.dataset.kind = kind;
}

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function validatePackage(value) {
  if (!isObject(value) || value.schema_version !== "tbaf.review-package/v2") {
    throw new Error("This file is not a supported tbaf.review-package/v2 document.");
  }
  if (!isObject(value.change) || !SHA_PATTERN.test(value.change.head_sha || "")
      || !Array.isArray(value.change.paths) || !isObject(value.attention)
      || !Array.isArray(value.attention.tasks) || !Array.isArray(value.claims)
      || !Array.isArray(value.checks) || !Array.isArray(value.observations)
      || !isObject(value.policy) || !SHA_PATTERN.test(value.sha256 || "")) {
    throw new Error("The package is missing required change, policy, evidence, or routing fields.");
  }
  const collections = [value.change.paths, value.attention.tasks, value.claims, value.checks, value.observations];
  if (collections.some((rows) => rows.length > MAX_ROWS_PER_SECTION)) {
    throw new Error(`A package section exceeds the ${MAX_ROWS_PER_SECTION}-item display limit.`);
  }
  if (value.change.paths.some((path) => typeof path !== "string" || path.length > MAX_PATH_CHARS)) {
    throw new Error("The package contains a changed path that is invalid or too long to display.");
  }
  return value;
}

function humanize(value) {
  return String(value || "unknown").replaceAll("_", " ").toLowerCase();
}

function minutes(value) {
  return Number.isInteger(value) ? `${value} min` : "Unknown";
}

function renderList(target, rows, emptyText, renderRow) {
  target.replaceChildren();
  if (!rows.length) {
    target.append(node("p", "empty-list", emptyText));
    return;
  }
  for (const row of rows) target.append(renderRow(row));
}

function validateLinkedEnvelope(value) {
  if (!isObject(value) || value.schema_version !== "tbaf.review-package-link/v2"
      || !isObject(value.change_mapper) || !isObject(value.review_package)) {
    throw new Error("This is not a supported linked Review Package v2 document.");
  }
  const mapper = value.change_mapper;
  const coverage = mapper.diff_coverage;
  if (mapper.epistemic_status !== "CANDIDATE" || !Array.isArray(mapper.observations)
      || mapper.observations.length > MAX_ROWS_PER_SECTION || !isObject(coverage)
      || !["complete", "partial", "unknown"].includes(coverage.status)
      || !Array.isArray(coverage.paths) || coverage.paths.length > 2000
      || coverage.paths.some((path) => typeof path !== "string" || path.length > MAX_PATH_CHARS)
      || !Array.isArray(coverage.limitations) || coverage.limitations.length > 100
      || coverage.limitations.some((item) => typeof item !== "string" || item.length > 1000)
      || mapper.observations.some((item) => !isObject(item)
        || typeof item.text !== "string" || item.text.length > 20_000)) {
    throw new Error("The linked assessment is missing valid candidate or diff coverage metadata.");
  }
  return { packageData: validatePackage(value.review_package), mapper };
}

function renderMapper(mapper) {
  elements.mapperSection.hidden = !mapper;
  elements.mapperNav.hidden = !mapper;
  if (!mapper) return;

  const coverage = mapper.diff_coverage;
  const pill = document.querySelector("#mapper-coverage");
  pill.textContent = coverage.assertion_source === "reported_by_agent_not_independently_verified"
    ? `reported ${coverage.status}`
    : "unknown · legacy";
  pill.className = `state-pill coverage-${coverage.status}`;
  document.querySelector("#mapper-assurance").textContent =
    coverage.assertion_source === "reported_by_agent_not_independently_verified"
      ? "The agent reports this coverage state. The linker binds it to the exact MR head, but does not verify the claim. It never changes the deterministic route."
      : "This legacy assessment has no structured coverage field. Coverage is unknown; absence of a warning is not evidence of a complete diff.";

  const limitations = document.querySelector("#mapper-limitations");
  limitations.replaceChildren();
  const rows = [
    ...coverage.limitations.map((item) => `Limitation: ${item}`),
    ...coverage.paths.map((path) => `Affected path: ${path}`),
  ];
  if (!rows.length) rows.push("No coverage limitations reported by the mapper.");
  for (const row of rows) limitations.append(node("p", "item-meta coverage-detail", row));

  renderList(document.querySelector("#mapper-observations"), mapper.observations,
    "No candidate observations were supplied.", (observation) => {
      const card = node("section", "item-card");
      const top = node("div", "item-topline");
      top.append(node("h3", "item-title", observation.id || "Candidate"));
      top.append(node("span", "candidate-pill", "CANDIDATE"));
      card.append(top, node("p", "item-text", observation.text || "No observation text supplied."));
      const locations = Array.isArray(observation.locations) ? observation.locations : [];
      if (locations.length) {
        card.append(node("p", "item-meta", locations.map((location) =>
          `${location.path}:${location.start_line}-${location.end_line}`).join(" · ")));
      }
      return card;
    });
}

function renderPackage(packageData, isExample, mapper = null) {
  const change = packageData.change;
  const attention = packageData.attention;
  const route = attention.route;

  document.querySelector("#change-title").textContent = `Merge request !${change.mr_iid}`;
  document.querySelector("#change-project").textContent = change.project;
  document.querySelector("#change-iid").textContent = `!${change.mr_iid}`;
  document.querySelector("#change-sha").textContent = change.head_sha;
  document.querySelector("#change-path-count").textContent = String(change.paths.length);
  document.querySelector("#policy-name").textContent = `${packageData.policy.id} · v${packageData.policy.version}`;

  const paths = document.querySelector("#changed-paths");
  paths.replaceChildren();
  for (const path of change.paths) paths.append(node("li", "path-item", path));

  const routeTitle = document.querySelector("#route-title");
  routeTitle.textContent = humanize(route);
  routeTitle.className = `route-title route-${String(route).toLowerCase()}`;
  document.querySelector("#route-glyph").textContent = route === "COVERED_BY_EVIDENCE" ? "✓" : "!";
  document.querySelector("#route-description").textContent = {
    COVERED_BY_EVIDENCE: "The declared claims have the evidence required by policy. This is not a safety verdict or merge approval.",
    TARGETED_REVIEW: "Specific consequential claims remain unresolved and need focused human review.",
    DEEP_REVIEW: "The change has broad or unmapped uncertainty that needs a fuller human review.",
  }[route] || "The package contains an unrecognized route. Inspect its source and policy before acting.";

  renderList(document.querySelector("#route-reasons"), attention.reasons || [], "No route reasons recorded.",
    (reason) => node("li", "reason-item", humanize(reason)));
  document.querySelector("#capacity-value").textContent = minutes(attention.capacity_minutes);
  document.querySelector("#demand-value").textContent = minutes(attention.known_demand_minutes);
  document.querySelector("#uncovered-value").textContent = minutes(attention.uncovered_known_minutes);
  document.querySelector("#schedule-state").textContent = `Schedule state: ${humanize(attention.schedule_state)}`;

  document.querySelector("#claim-count").textContent = String(packageData.claims.length);
  renderList(document.querySelector("#claims-list"), packageData.claims, "No policy claims in this package.", (claim) => {
    const card = node("section", "item-card");
    const top = node("div", "item-topline");
    top.append(node("h3", "item-title", claim.claim_id));
    top.append(node("span", `state-pill state-${humanize(claim.evidence_state).replaceAll(" ", "-")}`, humanize(claim.evidence_state)));
    card.append(top, node("p", "item-text", claim.statement || "No claim statement supplied."));
    const reasons = Array.isArray(claim.reasons) ? claim.reasons : [];
    if (reasons.length) card.append(node("p", "item-meta", `Open reasons: ${reasons.map(humanize).join(" · ")}`));
    return card;
  });

  document.querySelector("#check-count").textContent = String(packageData.checks.length);
  renderList(document.querySelector("#checks-list"), packageData.checks, "No checks were recorded.", (check) => {
    const card = node("section", "item-card");
    const top = node("div", "item-topline");
    top.append(node("h3", "item-title", check.id));
    top.append(node("span", `state-pill state-${humanize(check.status).replaceAll(" ", "-")}`, humanize(check.status)));
    card.append(top, node("p", "item-meta", `${check.source?.name || "Unknown source"} ${check.source?.version || ""} · ${humanize(check.scope)}`));
    if (check.details) card.append(node("p", "item-text", check.details));
    return card;
  });

  document.querySelector("#task-count").textContent = String(attention.tasks.length);
  renderList(document.querySelector("#tasks-list"), attention.tasks, "No human review tasks were generated.", (task) => {
    const card = node("section", "item-card task-item");
    const top = node("div", "item-topline");
    top.append(node("h3", "item-title", task.claim_id || task.task_id));
    top.append(node("span", "task-minutes", minutes(task.required_minutes)));
    card.append(top, node("p", "item-meta", `${humanize(task.route)} · ${humanize(task.consequence)} consequence`));
    const reasons = Array.isArray(task.reason_codes) ? task.reason_codes : [];
    if (reasons.length) card.append(node("p", "item-text", reasons.map(humanize).join(" · ")));
    return card;
  });

  document.querySelector("#observation-count").textContent = String(packageData.observations.length);
  renderList(document.querySelector("#observations-list"), packageData.observations, "No candidate observations were supplied.", (observation) => {
    const card = node("section", "item-card");
    const top = node("div", "item-topline");
    top.append(node("h3", "item-title", observation.id));
    top.append(node("span", "candidate-pill", "CANDIDATE"));
    card.append(top, node("p", "item-text", observation.text));
    card.append(node("p", "item-meta", `${observation.source?.agent || "Unknown source"} ${observation.source?.version || ""} · ${humanize(observation.kind)} · ${humanize(observation.impact)}`));
    if (Array.isArray(observation.locations) && observation.locations.length) {
      card.append(node("p", "item-meta", observation.locations.map((location) => `${location.path}:${location.start_line}-${location.end_line}`).join(" · ")));
    }
    return card;
  });

  document.querySelector("#package-digest").textContent = packageData.sha256;
  renderMapper(mapper);
  elements.exampleNotice.hidden = !isExample;
  elements.empty.hidden = true;
  elements.view.hidden = false;
  setStatus(isExample ? "Example package loaded. It is illustrative data." : "Package loaded locally. The file was not sent to a server.", "success");
}

async function loadText(text, isExample = false) {
  if (new Blob([text]).size > MAX_PACKAGE_BYTES) throw new Error("The package exceeds the 2 MB limit.");
  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error("The file is not valid JSON. Check that you selected the Review Package artifact.");
  }
  const documentData = parsed?.schema_version === "tbaf.review-package-link/v2"
    ? validateLinkedEnvelope(parsed)
    : { packageData: validatePackage(parsed), mapper: null };
  renderPackage(documentData.packageData, isExample, documentData.mapper);
}

elements.file.addEventListener("change", async () => {
  const file = elements.file.files?.[0];
  if (!file) return;
  setStatus("Reading the selected file on this device…");
  try {
    if (file.size > MAX_PACKAGE_BYTES) throw new Error("The selected file exceeds the 2 MB limit.");
    await loadText(await file.text());
  } catch (error) {
    const previousPackageVisible = !elements.view.hidden;
    setStatus(`${error.message || "Could not read this file."}${previousPackageVisible ? " The previously loaded package remains on screen." : ""}`, "error");
  }
});

elements.demo.addEventListener("click", async () => {
  setStatus("Loading the example package…");
  elements.demo.disabled = true;
  try {
    const response = await fetch("/demo-review-package.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`Example download failed (HTTP ${response.status}). Try opening a local JSON file.`);
    await loadText(await response.text(), true);
  } catch (error) {
    const previousPackageVisible = !elements.view.hidden;
    setStatus(`${error.message || "Could not load the example package."}${previousPackageVisible ? " The previously loaded package remains on screen." : ""}`, "error");
  } finally {
    elements.demo.disabled = false;
  }
});
