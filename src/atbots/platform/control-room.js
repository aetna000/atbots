"use strict";
// Credentials stay in this page's memory, never in URLs sent to the server.
const token = new URLSearchParams(location.hash.slice(1)).get("token") || "";
const $ = id => document.getElementById(id);
let selected = null;
let agents = [];
let refreshing = false;
let editing = false;
let editingRevision = null;
let connectionList = [];
const conversations = new Map();
const drafts = new Map();
let viewRevision = 0;
function node(tag, text, parent) {
  const item = document.createElement(tag);
  if (text !== undefined) item.textContent = text;
  if (parent) parent.append(item);
  return item;
}
function button(parent, label, action) {
  const item = node("button", label, parent);
  item.type = "button";
  item.onclick = async () => {
    item.disabled = true;
    try { await action(); } catch (error) { message(error.message); }
    finally { item.disabled = false; }
  };
  return item;
}
async function api(path, data) {
  const response = await fetch(path, {
    method: data === undefined ? "GET" : "POST",
    headers: {Authorization: `Bearer ${token}`, ...(data === undefined ? {} : {"Content-Type": "application/json"})},
    ...(data === undefined ? {} : {body: JSON.stringify(data)})
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Request failed. Check recorded state before retrying.");
  return result;
}
function message(text) {
  const item = node("div", text, $("conversation"));
  item.className = "message";
  item.scrollIntoView({block: "nearest"});
  viewRevision++;
  return item;
}
function messageFor(scope, text) {
  if (scope === selected) return message(text);
  const item = node("div", text); item.className = "message";
  const rows = conversations.get(scope) || []; rows.push(item); conversations.set(scope, rows);
  return item;
}
function details(parent, value, label = "Technical receipt") {
  const box = node("details", undefined, parent);
  node("summary", label, box);
  node("pre", JSON.stringify(value, null, 2), box);
}
function proposalSummary(plan) {
  const labels = {create: "Create agent", configure: "Update settings", memory_remember: "Save private memory", memory_correct: "Correct private memory", memory_forget: "Forget private memory", supervise: "Start supervised work", schedule_create: "Create schedule", retire: "Archive agent", restore: "Restore agent"};
  const lines = [`${labels[plan.action] || plan.action.replaceAll("_", " ")}${plan.name ? ` · ${plan.name}` : ""}`];
  if (plan.binding) lines.push(`Model: ${plan.binding.kind} / ${plan.binding.model}`);
  if (plan.changes) lines.push(`Settings changed: ${Object.keys(plan.changes).join(", ")}`);
  if (plan.objective) lines.push(`Task: ${plan.objective}`);
  if (plan.text) lines.push(`Memory: ${plan.text}`);
  if (plan.state) lines.push(`State: ${plan.state}`);
  lines.push("Nothing has been applied. Expand the details to check permissions and the exact operation.");
  return lines.join("\n");
}
function present(result, scope = selected) {
  let text = result.answer || result.question;
  if (!text && result.applied && result.applied.name) text = `Saved ${result.applied.name}`;
  if (!text && result.agents) text = result.agents.map(a => `${a.name} · ${a.state}`).join("\n");
  if (!text && result.approval_required) text = "Changes proposed. Review the approval below; nothing has been applied yet.";
  if (!text && result.rejected) text = "Proposal rejected.";
  if (!text && result.configured) text = `Saved supervision settings for ${result.agent}. No task has started. Ask the agent to use AtSys, then approve its proposed objective.`;
  if (!text && result.delegation) text = `AtSys accepted task ${result.delegation.upstream_id} for ${result.delegation.agent}. Follow its recorded progress under Supervised work.`;
  if (!text && result.schedule) text = `Schedule saved for ${result.schedule.agent}. Next occurrence: ${result.schedule.next || "see recorded schedule"}. The local app and PC must be running.`;
  if (!text && result.memory_result) text = `Memory operation recorded: ${result.memory_result.decision || (result.memory_result.deleted ? "forgotten" : "see receipt")}.`;
  if (!text && result.memories) text = result.memories.length
    ? result.memories.map(row => `${row.status} · ${row.content}`).join("\n\n")
    : "No memories recorded for this agent.";
  if (!text && result.checks) text = `${result.ready ? "Setup checks passed" : "Setup needs attention"}\n` + result.checks.map(row => `${row.check}: ${row.state} — ${row.detail}`).join("\n");
  const item = messageFor(scope, text || "Recorded result. Expand the receipt for details.");
  details(item, result);
}
async function operation(plan) {
  present(await api("/api/operation", plan));
  await refresh();
}
function choose(name) {
  const needsHistory = !conversations.has(name);
  conversations.set(selected, Array.from($("conversation").childNodes));
  drafts.set(selected, $("message").value);
  selected = name;
  viewRevision++;
  $("message").value = drafts.get(name) || "";
  $("conversation").replaceChildren(...(conversations.get(name) || []));
  $("heading").textContent = name || "Control room";
  $("target").textContent = name ? "Talk directly to this agent. Settings and memory remain scoped to it." : "Coordinate work and inspect recorded status.";
  for (const id of ["settings", "memory", "files", "environment", "supervision-settings", "schedule-settings", "tracing-settings"]) $(id).disabled = !name;
  refresh();
  if (needsHistory) loadConversation(name);
}
async function loadConversation(scope) {
  const revision = viewRevision;
  try {
    const value = await api(`/api/conversation?agent=${encodeURIComponent(scope || "control-room")}`);
    if (selected !== scope || viewRevision !== revision || !value.messages.length) return;
    $("conversation").replaceChildren();
    if (value.earlier_messages) message(`Showing the latest 200 messages. ${value.earlier_messages} earlier messages remain in this agent's stored history.`);
    for (const row of value.messages) message(`${row.speaker}: ${row.text}`);
  } catch (error) { if (selected === scope) message(error.message); }
}
async function refresh() {
  if (refreshing) return;
  refreshing = true;
  const scope = selected;
  try {
    const state = await api(scope ? `/api/state?agent=${encodeURIComponent(scope)}` : "/api/state");
    if (scope !== selected) return;
    agents = state.agents;
    let runner = {not_started: "not started", starting: "starting", ready: "ready", recovering: "recovering", blocked: "needs attention", maintenance: "maintenance"}[state.desktop.scheduler] || "unknown";
    if (state.desktop.scheduler === "ready" && Date.now() - Date.parse(state.desktop.updated) > 15000) runner = "stalled — check setup";
    $("connection").textContent = `Connected · runner ${runner} · ${new Date(state.at).toLocaleTimeString()}`;
    $("agents").replaceChildren();
    for (const agent of agents) {
      if (agent.name === "control-room" || (agent.state === "retired" && !$("show-archived").checked)) continue;
      const item = button($("agents"), `${agent.name} · ${agent.state}`, () => choose(agent.name));
      item.className = "agent";
      item.setAttribute("aria-current", String(agent.name === selected));
    }
    $("approvals").replaceChildren();
    for (const approval of state.approvals) {
      const card = node("article", undefined, $("approvals"));
      card.className = "approval";
      node("h3", approval.state === "executing" ? "Outcome uncertain — inspect receipts before retrying" : "Review proposed change", card);
      node("p", proposalSummary(approval.proposal), card);
      details(card, approval, "Proposed operation and authority scope");
      if (!approval.expired && approval.state !== "executing") {
        button(card, "Approve", async () => { present(await api("/api/approve", {id: approval.id})); await refresh(); });
        button(card, "Reject", async () => { present(await api("/api/reject", {id: approval.id})); await refresh(); });
      } else node("p", approval.expired ? "Expired. Request a fresh proposal." : "No automatic replay.", card);
    }
    $("jobs").replaceChildren();
    if (!state.jobs.length) node("p", "No recorded jobs yet.", $("jobs"));
    for (const job of state.jobs) {
      const card = node("article", undefined, $("jobs"));
      card.className = "card";
      node("h3", `${job.agent} · ${job.status}`, card);
      if (job.objective) node("p", job.objective, card);
      node("p", `Last recorded update: ${job.updated}. A reply is not independently verified completion.`, card);
      button(card, "Inspect outcome", () => operation({action: "job_status", name: job.agent, job_id: job.id}));
      for (const action of ["pause", "resume", "cancel"]) button(card, action, () => operation({action: `job_${action}`, name: job.agent, job_id: job.id}));
    }
    $("schedules").replaceChildren();
    if (!state.schedules.length) node("p", "No schedules yet.", $("schedules"));
    for (const entry of state.schedules) {
      const card = node("article", `${entry.agent} · ${entry.enabled ? "enabled" : "paused"} · next ${entry.next}`, $("schedules"));
      details(card, entry);
      for (const action of [entry.enabled ? "pause" : "resume", "delete"]) button(card, action, () => operation({action: `schedule_${action}`, name: entry.agent, schedule_id: entry.id}));
    }
    $("delegations").replaceChildren();
    if (!state.delegations.length) node("p", "No delegated objectives yet.", $("delegations"));
    for (const entry of state.delegations) {
      const card = node("article", `${entry.agent} · delegated work`, $("delegations"));
      details(card, entry, "Last recorded supervision state");
      for (const action of ["status", "report", "pause", "resume", "stop"]) button(card, action, () => operation({action: `supervision_${action}`, name: entry.agent, delegation_id: entry.id}));
    }
  } catch (error) { $("connection").textContent = error.message; }
  finally { refreshing = false; if (scope !== selected) refresh(); }
}
$("room").onclick = () => choose(null);
$("show-archived").onchange = refresh;
$("doctor").onclick = async () => { try { present(await api("/api/doctor")); } catch (error) { message(error.message); } };
$("chat").onsubmit = async event => {
  event.preventDefault();
  const text = $("message").value.trim();
  if (!text) return;
  const name = selected;
  message(`You → ${name || "control room"}: ${text}`);
  $("send").disabled = true;
  try {
    const result = await api(name ? "/api/agent" : "/api/chat", name ? {name, message: text} : {message: text});
    present(result, name);
    if (selected === name && $("message").value.trim() === text) $("message").value = "";
    if (drafts.get(name)?.trim() === text) drafts.set(name, "");
    await refresh();
  } catch (error) { messageFor(name, error.message); }
  finally { $("send").disabled = false; }
};
$("memory").onclick = async () => {
  const name = selected;
  try {
    const result = await api("/api/agent-memory", {action: "inspect", name});
    if (name !== selected) return;
    present(result);
    const controls = message(`${name} · own-memory controls`);
    const form = node("form", undefined, controls);
    const label = node("label", "Search or propose a fact to remember", form);
    const input = node("input", undefined, label); input.required = true; input.maxLength = 2000;
    const search = button(form, "Search own memory", async () => { const value = await api("/api/agent-memory", {name, action: "search", text: input.value}); if (name === selected) present(value); });
    search.disabled = false;
    button(form, "Propose remember", async () => { const value = await api("/api/agent-memory", {name, action: "remember", text: input.value}); if (name === selected) present(value); await refresh(); });
    form.onsubmit = event => { event.preventDefault(); search.click(); };
    for (const record of result.memories) {
      const row = node("article", `${record.status} · ${record.content}`, controls);
      const change = node("input", undefined, row); change.value = record.content; change.setAttribute("aria-label", "Correct memory text");
      for (const action of ["correct", "forget"]) button(row, `Propose ${action}`, async () => { const value = await api("/api/agent-memory", {name, action, record_id: record.id, ...(action === "correct" ? {text: change.value} : {})}); if (name === selected) present(value); await refresh(); });
    }
  }
  catch (error) { message(error.message); }
};
$("files").onclick = async () => {
  const name = selected;
  try {
    const result = await api(`/api/artifacts?agent=${encodeURIComponent(name)}`);
    if (name !== selected) return;
    const item = message(`${name} workspace files`);
    for (const file of result.files) {
      const path = typeof file === "string" ? file : file.path;
      button(item, `View ${path}`, async () => {
        const response = await fetch(`/api/artifact?agent=${encodeURIComponent(name)}&path=${encodeURIComponent(path)}`, {headers: {Authorization: `Bearer ${token}`}});
        if (!response.ok) throw new Error("File could not be read in this scope.");
        const text = await response.text(); if (name === selected) message(text);
      });
    }
    if (!result.files.length) node("p", "No files yet.", item);
  } catch (error) { message(error.message); }
};
async function editAgent(isNew, target = selected) {
  editing = !isNew;
  const agent = isNew ? null : agents.find(a => a.name === target);
  if (!isNew && !agent) return;
  editingRevision = agent?.revision || null;
  $("agent-form").reset();
  $("dialog-title").textContent = isNew ? "New agent" : `Settings · ${agent.name}`;
  $("agent-name").value = agent?.name || "";
  $("agent-name").readOnly = !isNew;
  $("provider").value = agent?.binding.kind || "ollama";
  $("endpoint").value = agent?.binding.endpoint || "http://127.0.0.1:11434";
  $("key-env").value = agent?.binding.api_key_env || "";
  $("instructions").value = agent?.instructions || "";
  $("agent-state").value = agent?.state || "active";
  $("remote").checked = agent?.remote_allowed || false;
  const caps = agent?.capabilities || {};
  $("file-read").checked = isNew ? true : caps.file_read || false;
  $("file-create").checked = isNew ? true : caps.file_create || false;
  $("domains").value = (caps.browser_domains || []).join(", ");
  $("browser-actions").value = (caps.browser_actions || []).join(", ");
  $("browser-transport").value = caps.browser_transport || "native";
  $("vision").checked = caps.vision || false;
  $("skill-names").value = (caps.skills || []).join(", ");
  $("form-error").textContent = "";
  $("agent-dialog").showModal();
  $("agent-connection").replaceChildren();
  try {
    connectionList = (await api("/api/connections")).connections;
    for (const connection of connectionList) {
      const option = node("option", connection.label, $("agent-connection"));
      option.value = connection.id;
    }
    const match = agent && connectionList.find(c => c.kind === agent.binding.kind && c.auth_profile === agent.binding.auth_profile && c.endpoint === agent.binding.endpoint);
    if (match) $("agent-connection").value = match.id;
    else if (agent) {
      const option = node("option", "Current connection (not registered in Setup)", $("agent-connection"));
      option.value = "current";
      $("agent-connection").value = "current";
    }
    await loadModels(agent?.binding.model);
  } catch (error) { $("catalog-status").textContent = error.message; }
}
async function loadModels(currentModel) {
  const identity = $("agent-connection").value;
  $("model").replaceChildren();
  $("catalog-status").textContent = "Discovering models from this connection…";
  if (identity === "current") {
    const option = node("option", currentModel, $("model")); option.value = currentModel;
    $("catalog-status").textContent = "Keeping the existing binding. Register a connection in Setup to discover other models.";
    return;
  }
  const connection = connectionList.find(c => c.id === identity);
  if (!connection) return;
  if (!currentModel) $("remote").checked = false;
  $("provider").value = connection.kind;
  $("endpoint").value = connection.endpoint;
  $("key-env").value = "";
  try {
    const catalog = await api(`/api/connection-models?id=${encodeURIComponent(identity)}`);
    for (const id of catalog.models) { const option = node("option", id, $("model")); option.value = id; }
    if (currentModel) {
      if (!catalog.models.includes(currentModel)) { const option = node("option", `${currentModel} (current; not advertised by catalog)`, $("model")); option.value = currentModel; }
      $("model").value = currentModel;
    }
    $("catalog-status").textContent = catalog.models.length ? "Models discovered. Remote inference requires your explicit permission below; catalog access is not an inference test." : "No models returned. Connect another provider in Setup, or install a local model in Ollama.";
  } catch (error) {
    if (currentModel) { const option = node("option", currentModel, $("model")); option.value = currentModel; }
    $("catalog-status").textContent = error.message + " Open Setup & connections to recover. Existing model bindings can be retained.";
  }
}
$("agent-connection").onchange = () => loadModels();
$("new-agent").onclick = () => { editAgent(true); };
$("settings").onclick = () => { editAgent(false); };
$("control-model").onclick = () => { editAgent(false, "control-room"); };
$("dialog-cancel").onclick = () => $("agent-dialog").close();
$("agent-form").onsubmit = async event => {
  event.preventDefault();
  const submit = event.submitter;
  submit.disabled = true;
  $("form-error").textContent = "Preparing your approval proposal…";
  const split = id => $(id).value.split(",").map(s => s.trim()).filter(Boolean);
  const remote = $("remote").checked;
  const original = agents.find(a => a.name === $("agent-name").value);
  const plan = {
    action: editing ? "configure" : "create", name: $("agent-name").value,
    binding: {...(editing ? original.binding : {}), kind: $("provider").value, model: $("model").value,
      endpoint: $("endpoint").value, api_key_env: $("key-env").value || null, egress_class: remote ? "remote" : "local"},
    instructions: $("instructions").value, remote_allowed: remote,
    capabilities: {...(editing ? original.capabilities : {}), file_read: $("file-read").checked, file_create: $("file-create").checked,
      browser_domains: split("domains"), browser_actions: split("browser-actions"), browser_transport: $("browser-transport").value,
      vision: $("vision").checked, skills: split("skill-names")}
  };
  if (editing) plan.state = $("agent-state").value;
  try {
    if ($("agent-connection").value === "current") await operation(plan);
    else {
      const result = await api("/api/setup/agent", {name: plan.name, action: plan.action, ...(editing ? {expected_revision: editingRevision} : {}), connection: $("agent-connection").value, model: $("model").value,
        remote_allowed: remote, capabilities: plan.capabilities, ...(editing ? {state: plan.state} : {}), instructions: plan.instructions});
      present(result); await refresh();
    }
    $("agent-dialog").close();
  }
  catch (error) { $("form-error").textContent = error.message; }
  finally { submit.disabled = false; }
};
$("environment").onclick = async () => {
  const name = selected;
  try {
    const value = await api("/api/environment", {name});
    if (name !== selected) return;
    const item = message(`${value.agent}\nWorkspace: ${value.workspace}\nMemory: ${value.memory.backend} · ${value.memory.scope}\nFiles: read ${value.file_permissions.read ? "allowed" : "off"}, create ${value.file_permissions.create ? "allowed" : "off"}\nAtSys: ${value.atsys.configuration ? "configured, health not checked" : "configure in Supervision"}\nAtFlows: ${value.atflows.status}`);
    details(item, value);
  } catch (error) { message(error.message); }
};
async function renderConnections() {
  $("saved-connections").replaceChildren();
  const value = await api("/api/connections");
  for (const connection of value.connections) {
    const card = node("article", connection.label, $("saved-connections"));
    card.className = "card";
    button(card, "Check available models", async () => {
      const catalog = await api(`/api/connection-models?id=${encodeURIComponent(connection.id)}`);
      node("p", catalog.models.join(", ") || "No available models", card);
    });
  }
}
$("setup").onclick = async () => { $("setup-dialog").showModal(); try { await renderConnections(); } catch (error) { $("setup-status").textContent = error.message; } };
$("setup-close").onclick = () => $("setup-dialog").close();
function providerHelp() {
  const kind = $("connect-provider").value;
  $("api-key-label").hidden = !["anthropic", "openai-compatible"].includes(kind);
  $("copilot-help").hidden = kind !== "github-copilot";
  $("connect-submit").textContent = kind === "chatgpt" ? "Continue with ChatGPT" : kind === "github-copilot" ? "Sign in with GitHub" : "Save API connection";
  $("provider-help").textContent = kind === "chatgpt" ? "Authorize ChatGPT plan usage in your browser. No Codex token files are read. Model access depends on your account." : kind === "anthropic" ? "Use an Anthropic API key. Claude subscription OAuth is not supported. The key is saved in your OS keychain, never in agent memory or configuration." : kind === "github-copilot" ? "Complete GitHub device sign-in. Each new agent reuses the saved AtBots profile." : "Use your own OpenAI API key. It is saved in your OS keychain and can be reused by all your agents.";
}
$("connect-provider").onchange = providerHelp;
$("connection-form").onsubmit = async event => {
  event.preventDefault();
  $("connect-submit").disabled = true;
  const kind = $("connect-provider").value;
  try {
    if (["anthropic", "openai-compatible"].includes(kind)) {
      const key = $("connect-key").value; $("connect-key").value = "";
      await api("/api/setup/key", {provider: kind, label: kind === "anthropic" ? "Anthropic API" : "OpenAI API", api_key: key});
      $("setup-status").textContent = "Connection saved in the OS keychain. Use it in Control room model or New agent.";
    } else {
      let job = await api("/api/setup/login", {provider: kind, client_id: $("connect-client-id").value || null});
      while (job.state === "waiting") {
        $("setup-status").textContent = job.message;
        await new Promise(resolve => setTimeout(resolve, 1500));
        job = await api(`/api/sign-in?id=${encodeURIComponent(job.id)}`);
      }
      $("setup-status").textContent = job.message;
    }
    await renderConnections();
  } catch (error) { $("setup-status").textContent = error.message; }
  finally { $("connect-submit").disabled = false; $("connect-key").value = ""; }
};
let supervisionAgent = null;
$("supervision-settings").onclick = async () => {
  supervisionAgent = selected; $("supervision-agent").textContent = selected; $("supervision-form").reset(); $("supervision-error").textContent = ""; $("supervision-dialog").showModal();
  try {
    const value = await api("/api/environment", {name: supervisionAgent});
    const profile = value.atsys.configuration;
    if (profile) {
      $("atsys-endpoint").value = profile.endpoint; $("atsys-worker").value = profile.worker; $("atsys-supervisor").value = profile.supervisor_provider;
      $("atsys-worker-model").value = profile.model; $("atsys-supervisor-model").value = profile.supervisor_model;
      $("atsys-validator").value = profile.validation_argv.map(x => /\s/.test(x) ? '"' + x.replaceAll('"', '\\"') + '"' : x).join(" ");
      $("atsys-criteria").value = profile.success_criteria.join("\n"); $("atsys-trusted").checked = profile.trusted_local_execution;
    }
  } catch (error) { $("supervision-error").textContent = error.message; }
};
$("supervision-close").onclick = () => $("supervision-dialog").close();
$("atsys-start-private").onclick = async () => {
  $("atsys-start-private").disabled = true;
  $("supervision-error").textContent = "Starting this agent's private AtSys; existing shared services are left alone…";
  try { const value = await api("/api/setup/atsys", {name: supervisionAgent, confirmed: true, initialize_git: $("atsys-init-git").checked}); $("atsys-endpoint").value = value.endpoint; $("supervision-error").textContent = value.next; }
  catch (error) { $("supervision-error").textContent = error.message; }
  finally { $("atsys-start-private").disabled = false; }
};
$("atsys-stop-private").onclick = async () => {
  $("atsys-stop-private").disabled = true;
  try { const value = await api("/api/setup/atsys-stop", {name: supervisionAgent, confirmed: true}); $("supervision-error").textContent = `Private AtSys ${value.status}. Task reports and data are retained.`; }
  catch (error) { $("supervision-error").textContent = error.message; }
  finally { $("atsys-stop-private").disabled = false; }
};
$("supervision-form").onsubmit = async event => {
  event.preventDefault();
  try {
    const value = await api("/api/setup/supervision", {name: supervisionAgent, endpoint: $("atsys-endpoint").value, worker: $("atsys-worker").value,
      supervisor: $("atsys-supervisor").value, worker_model: $("atsys-worker-model").value, supervisor_model: $("atsys-supervisor-model").value, validation_command: $("atsys-validator").value, success_criteria: $("atsys-criteria").value.split("\n").map(x => x.trim()).filter(Boolean), trusted_local_execution: $("atsys-trusted").checked});
    present(value); $("supervision-dialog").close();
  } catch (error) { $("supervision-error").textContent = error.message; }
};
async function renderComponents(latest = false) {
  const value = await api("/api/components" + (latest ? "?latest=1" : ""));
  $("component-list").replaceChildren();
  for (const row of value.components) node("p", `${row.package}: ${row.installed || "not installed"}${row.latest ? ` · available ${row.latest}` : ""}`, $("component-list"));
  $("component-status").textContent = `${value.maintenance.status}${value.maintenance.message ? ` · ${value.maintenance.message}` : ""}${value.maintenance.restart_required ? " · Restart required. Do not resume agents yet. Use Start private AtSys again before supervised work." : ""}`;
}
$("components").onclick = async () => { $("components-dialog").showModal(); try { await renderComponents(); } catch (error) { $("component-status").textContent = error.message; } };
$("component-close").onclick = () => $("components-dialog").close();
$("component-latest").onclick = async () => { try { await renderComponents(true); } catch (error) { $("component-status").textContent = error.message; } };
$("component-restart").onclick = async () => { try { const value = await api("/api/desktop/restart", {confirmed: true}); $("component-status").textContent = value.answer; } catch (error) { $("component-status").textContent = error.message; } };
$("upgrade-form").onsubmit = async event => {
  event.preventDefault();
  try { await api("/api/components/upgrade", {package: $("upgrade-package").value, target: $("upgrade-version").value, confirmed: $("upgrade-confirm").checked}); await renderComponents(); }
  catch (error) { $("component-status").textContent = error.message; }
};
let scheduleAgent = null;
$("schedule-settings").onclick = () => { scheduleAgent = selected; $("schedule-agent").textContent = selected; $("schedule-form").reset(); $("schedule-error").textContent = ""; $("schedule-dialog").showModal(); };
$("schedule-close").onclick = () => $("schedule-dialog").close();
$("schedule-form").onsubmit = async event => {
  event.preventDefault();
  try { await operation({action: "schedule_create", name: scheduleAgent, message: $("schedule-objective").value, at: new Date($("schedule-at").value).toISOString(), timezone: Intl.DateTimeFormat().resolvedOptions().timeZone, missed: "skip", overlap: "skip"}); $("schedule-dialog").close(); }
  catch (error) { $("schedule-error").textContent = error.message; }
};
let tracingAgent = null;
$("tracing-settings").onclick = () => { tracingAgent = selected; $("tracing-agent").textContent = selected; $("tracing-form").reset(); $("tracing-error").textContent = ""; $("tracing-dialog").showModal(); };
$("tracing-close").onclick = () => $("tracing-dialog").close();
$("tracing-form").onsubmit = async event => {
  event.preventDefault();
  try { await operation({action: "atflows_connect", name: tracingAgent, message: $("tracing-endpoint").value}); $("tracing-dialog").close(); }
  catch (error) { $("tracing-error").textContent = error.message; }
};
providerHelp();
choose(null);
refresh();
setInterval(refresh, 5000);
setInterval(() => { if ($("components-dialog").open) renderComponents().catch(() => {}); }, 5000);
