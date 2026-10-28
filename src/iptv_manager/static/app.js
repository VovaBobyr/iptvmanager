const state = { page: 1, pageSize: 50, total: 0, groups: [], sourceId: null, scanTimer: null, activeJobId: null, resumableJobId: null, scanSample: null };

const $ = (selector) => document.querySelector(selector);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try { detail = (await response.json()).detail || detail; } catch (_) { /* no JSON body */ }
    throw new Error(detail);
  }
  return response.status === 204 ? null : response.json();
}

function setBusy(button, busy, text) {
  if (!button.dataset.label) button.dataset.label = button.textContent;
  button.disabled = busy;
  button.textContent = busy ? text : button.dataset.label;
}

async function loadSources() {
  const sources = await api("/api/sources");
  const preferred = sources.find((source) => source.url === $("#source-url").value) || sources[0];
  state.sourceId = preferred?.id || null;
}

async function importSource() {
  const button = $("#import-source");
  const message = $("#source-message");
  setBusy(button, true, "Importing…");
  message.textContent = "Downloading and parsing the playlist…";
  try {
    const url = $("#source-url").value.trim();
    const sources = await api("/api/sources");
    let source = sources.find((item) => item.url === url);
    if (!source) {
      source = await api("/api/sources", {
        method: "POST",
        body: JSON.stringify({ name: "iptv-org global", kind: "remote", url }),
      });
    }
    state.sourceId = source.id;
    const result = await api(`/api/sources/${source.id}/refresh`, { method: "POST" });
    message.textContent = result.unchanged_remote
      ? "Playlist is unchanged."
      : `Found ${result.found.toLocaleString()} channels; ${result.created.toLocaleString()} added.`;
    state.page = 1;
    await loadChannels();
    window.setTimeout(() => window.location.reload(), 900);
  } catch (error) {
    message.textContent = error.message;
  } finally {
    setBusy(button, false, "");
  }
}

async function loadGroups() {
  state.groups = await api("/api/favorite-groups");
  const select = $("#favorite-group");
  const selected = select.value;
  select.innerHTML = state.groups.length
    ? state.groups.map((group) => `<option value="${group.id}">${escapeHtml(group.name)} (${group.item_count})</option>`).join("")
    : '<option value="">No groups yet</option>';
  if (state.groups.some((group) => String(group.id) === selected)) select.value = selected;
  updatePlaylistUrl();
}

function updatePlaylistUrl() {
  const group = state.groups.find((item) => String(item.id) === $("#favorite-group").value);
  const configuredBase = document.body.dataset.publicBaseUrl.replace(/\/$/, "");
  const publicBase = configuredBase || window.location.origin;
  $("#playlist-url").value = group ? `${publicBase}/playlists/${group.slug}.m3u` : "";
}

async function createGroup() {
  const name = $("#group-name").value.trim();
  if (!name) return;
  try {
    const group = await api("/api/favorite-groups", {
      method: "POST",
      body: JSON.stringify({ name }),
    });
    $("#group-name").value = "";
    await loadGroups();
    $("#favorite-group").value = String(group.id);
    updatePlaylistUrl();
  } catch (error) { window.alert(error.message); }
}

async function addFavorite(channelId, button) {
  const groupId = $("#favorite-group").value;
  if (!groupId) { window.alert("Create a favorite group first."); return; }
  setBusy(button, true, "Adding…");
  try {
    await api(`/api/favorite-groups/${groupId}/items`, {
      method: "POST",
      body: JSON.stringify({ channel_id: channelId }),
    });
    button.textContent = "Added ✓";
    button.dataset.label = "Added ✓";
    await loadGroups();
  } catch (error) {
    if (error.message.includes("already")) button.textContent = "Already added";
    else window.alert(error.message);
  } finally { button.disabled = false; }
}

async function checkOne(channelId, button) {
  setBusy(button, true, "Checking…");
  try { await api(`/api/channels/${channelId}/check`, { method: "POST" }); await loadChannels(); }
  catch (error) { window.alert(error.message); }
  finally { setBusy(button, false, ""); }
}

function escapeHtml(value) {
  return String(value || "").replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  }[char]));
}

async function loadChannels() {
  const params = new URLSearchParams({ page: state.page, page_size: state.pageSize });
  const query = $("#channel-search").value.trim();
  const health = $("#health-filter").value;
  if (query) params.set("q", query);
  if (health) params.set("health", health);
  const data = await api(`/api/channels?${params}`);
  state.total = data.total;
  const list = $("#channel-list");
  list.innerHTML = data.items.length ? data.items.map((channel) => `
    <article class="channel">
      <div class="logo-wrap">${channel.tvg_logo ? `<img src="${escapeHtml(channel.tvg_logo)}" alt="" loading="lazy">` : "<span>TV</span>"}</div>
      <div class="channel-copy">
        <h3>${escapeHtml(channel.name)}</h3>
        <p>${escapeHtml(channel.country || "—")} · ${escapeHtml(channel.group_title || "Uncategorized")}</p>
      </div>
      <span class="status status-${channel.health_status}">${channel.health_status === "working" ? "live" : escapeHtml(channel.health_status)}</span>
      <div class="channel-actions">
        <button class="button small check-one" data-id="${channel.id}" type="button">Check</button>
        <button class="button small favorite-one" data-id="${channel.id}" type="button">+ Favorite</button>
      </div>
    </article>`).join("") : '<div class="empty"><p>No channels match these filters.</p></div>';
  $("#page-message").textContent = `Page ${data.page} · ${data.total.toLocaleString()} channels`;
  $("#previous-page").disabled = state.page <= 1;
  $("#next-page").disabled = state.page * state.pageSize >= data.total;
  document.querySelectorAll(".favorite-one").forEach((button) => button.addEventListener("click", () => addFavorite(Number(button.dataset.id), button)));
  document.querySelectorAll(".check-one").forEach((button) => button.addEventListener("click", () => checkOne(Number(button.dataset.id), button)));
}

async function startScan(favoritesOnly, button) {
  setBusy(button, true, "Starting…");
  try {
    const job = await api("/api/health-scans", {
      method: "POST",
      body: JSON.stringify({ source_id: favoritesOnly ? null : state.sourceId, favorites_only: favoritesOnly }),
    });
    state.activeJobId = job.id;
    state.resumableJobId = null;
    state.scanSample = null;
    pollScan(job.id);
  } catch (error) { window.alert(error.message); }
  finally { setBusy(button, false, ""); }
}

function formatDuration(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return "Calculating remaining time…";
  if (seconds < 60) return `About ${Math.max(1, Math.round(seconds))} sec remaining`;
  if (seconds < 3600) return `About ${Math.ceil(seconds / 60)} min remaining`;
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.ceil((seconds % 3600) / 60);
  return `About ${hours} hr ${minutes} min remaining`;
}

function parseServerTime(value) {
  if (!value) return Date.now();
  const hasTimezone = /(?:z|[+-]\d{2}:?\d{2})$/i.test(value);
  return new Date(hasTimezone ? value : `${value}Z`).getTime();
}

function setScanControls(active) {
  $("#scan-all").disabled = active;
  $("#scan-favorites").disabled = active;
  $("#cancel-scan").disabled = !active;
}

function isResumable(job) {
  return ["interrupted", "cancelled", "failed"].includes(job.status)
    && job.total > 0
    && job.completed < job.total;
}

async function resumeScan() {
  if (!state.resumableJobId) return;
  const button = $("#resume-scan");
  setBusy(button, true, "Resuming…");
  try {
    const job = await api(`/api/health-scans/${state.resumableJobId}/resume`, { method: "POST" });
    state.activeJobId = job.id;
    state.resumableJobId = null;
    state.scanSample = { jobId: job.id, completed: job.completed, time: Date.now() };
    button.classList.add("hidden");
    $("#cancel-scan").classList.remove("hidden");
    pollScan(job.id);
  } catch (error) { window.alert(error.message); }
  finally { setBusy(button, false, ""); }
}

async function restoreBackup(file) {
  const button = $("#restore-backup");
  const message = $("#backup-message");
  if (!file || !window.confirm("Replace the current IPTV database with this backup? A safety copy of the current database will be retained.")) return;
  setBusy(button, true, "Restoring…");
  message.textContent = "Validating and restoring the database…";
  try {
    const response = await fetch("/api/backups/database", {
      method: "PUT",
      headers: { "Content-Type": "application/vnd.sqlite3" },
      body: file,
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || `Restore failed (${response.status})`);
    message.textContent = `${result.message} Safety copy: ${result.safety_backup}`;
    window.setTimeout(() => window.location.reload(), 1200);
  } catch (error) {
    message.textContent = error.message;
  } finally {
    setBusy(button, false, "");
    $("#restore-file").value = "";
  }
}

async function cancelScan() {
  if (!state.activeJobId || !window.confirm("Stop the current health scan? Saved results will be kept.")) return;
  try {
    await api(`/api/health-scans/${state.activeJobId}`, { method: "DELETE" });
    $("#scan-state").textContent = "Stopping…";
    $("#scan-eta").textContent = "Finishing the current batch";
  } catch (error) { window.alert(error.message); }
}

async function pollScan(jobId) {
  window.clearTimeout(state.scanTimer);
  const box = $("#scan-progress");
  box.classList.remove("hidden");
  try {
    const job = await api(`/api/health-scans/${jobId}`);
    state.activeJobId = job.id;
    const percent = job.total ? Math.round((job.completed / job.total) * 100) : 0;
    $("#scan-progress-bar").style.width = `${percent}%`;
    $("#scan-percent").textContent = `${percent}%`;
    $("#scan-state").textContent = job.status === "running" ? "Running" : job.status.charAt(0).toUpperCase() + job.status.slice(1);
    $("#scan-checked").textContent = `${job.completed.toLocaleString()} / ${job.total.toLocaleString()}`;
    $("#scan-live").textContent = job.working.toLocaleString();
    $("#scan-failed").textContent = job.failed.toLocaleString();
    $("#scan-uncertain").textContent = job.uncertain.toLocaleString();
    $("#scan-message").textContent = `${job.status}: ${job.completed.toLocaleString()} of ${job.total.toLocaleString()}`;
    const active = ["queued", "running"].includes(job.status);
    const resumable = isResumable(job);
    $("#scan-state-dot").classList.toggle("inactive", !active);
    $("#resume-scan").classList.toggle("hidden", !resumable);
    $("#cancel-scan").classList.toggle("hidden", !active);
    state.resumableJobId = resumable ? job.id : null;
    setScanControls(active);
    if (active) {
      const now = Date.now();
      const previous = state.scanSample?.jobId === job.id ? state.scanSample : null;
      const sampleSeconds = previous ? Math.max(1, (now - previous.time) / 1000) : 0;
      const sampleCompleted = previous ? job.completed - previous.completed : 0;
      const started = parseServerTime(job.started_at);
      const elapsedSeconds = Math.max(1, (now - started) / 1000);
      const channelsPerSecond = sampleCompleted > 0
        ? sampleCompleted / sampleSeconds
        : job.completed / elapsedSeconds;
      const remainingSeconds = channelsPerSecond > 0 ? (job.total - job.completed) / channelsPerSecond : Number.NaN;
      $("#scan-eta").textContent = `${formatDuration(remainingSeconds)} · ${channelsPerSecond.toFixed(1)} channels/sec`;
      state.scanSample = { jobId: job.id, completed: job.completed, time: now };
      state.scanTimer = window.setTimeout(() => pollScan(jobId), 2000);
    } else {
      state.activeJobId = null;
      state.scanSample = null;
      $("#scan-eta").textContent = resumable
        ? `${(job.total - job.completed).toLocaleString()} channels remaining. Completed results are saved.`
        : job.error || `Finished with ${job.working.toLocaleString()} live channels`;
      await loadChannels();
    }
  } catch (error) { $("#scan-message").textContent = error.message; }
}

let searchTimer;
$("#import-source").addEventListener("click", importSource);
$("#create-group").addEventListener("click", createGroup);
$("#favorite-group").addEventListener("change", updatePlaylistUrl);
$("#copy-playlist").addEventListener("click", async () => {
  if ($("#playlist-url").value) await navigator.clipboard.writeText($("#playlist-url").value);
});
$("#scan-all").addEventListener("click", (event) => startScan(false, event.currentTarget));
$("#scan-favorites").addEventListener("click", (event) => startScan(true, event.currentTarget));
$("#cancel-scan").addEventListener("click", cancelScan);
$("#resume-scan").addEventListener("click", resumeScan);
$("#restore-backup").addEventListener("click", () => $("#restore-file").click());
$("#restore-file").addEventListener("change", (event) => restoreBackup(event.target.files[0]));
$("#channel-search").addEventListener("input", () => { window.clearTimeout(searchTimer); searchTimer = window.setTimeout(() => { state.page = 1; loadChannels(); }, 300); });
$("#health-filter").addEventListener("change", () => { state.page = 1; loadChannels(); });
$("#previous-page").addEventListener("click", () => { state.page -= 1; loadChannels(); });
$("#next-page").addEventListener("click", () => { state.page += 1; loadChannels(); });

Promise.all([loadSources(), loadGroups(), loadChannels()]).catch((error) => console.error(error));
api("/api/health-scans").then((jobs) => {
  const active = jobs.find((job) => ["queued", "running"].includes(job.status));
  const resumable = jobs.find((job) => isResumable(job));
  if (active) pollScan(active.id);
  else if (resumable) pollScan(resumable.id);
});
