"use strict";

const $ = (id) => document.getElementById(id);
const terminal = new Set(["completed", "failed", "cancelled"]);
const state = { config: null, mode: "url", job: null, rows: [], page: 0, timer: null, rendered: null, pollSerial: 0, connectionLost: false };
const number = new Intl.NumberFormat("fr-FR");
const show = (id, visible) => { $(id).hidden = !visible; };
const text = (id, value) => { $(id).textContent = value; };

async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { "X-Playlist-Token": state.config?.token || "", ...options.headers } });
  let data;
  try { data = await response.json(); } catch { throw new Error("Le serveur a renvoyé une réponse inattendue."); }
  if (!response.ok) {
    const error = new Error(data.error || "La requête a échoué.");
    error.status = response.status;
    throw error;
  }
  return data;
}

function notice(id, message, kind = "") {
  $(id).textContent = message;
  $(id).className = `message ${kind}`;
  show(id, Boolean(message));
}

function setMode(mode) {
  state.mode = mode;
  for (const tab of document.querySelectorAll("[data-mode]")) {
    const selected = tab.dataset.mode === mode;
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
    show(`source-${tab.dataset.mode}`, selected);
  }
  $("playlist-url").required = mode === "url";
  $("playlist-file").required = mode === "file";
}

function setBusy(busy) {
  $("form-fields").disabled = busy || !state.config;
  if (!busy && state.config) {
    for (const input of document.querySelectorAll('[name="validator"]')) {
      input.disabled = !state.config.tools[input.value];
    }
    $("start-button").disabled = !Object.values(state.config.tools).some(Boolean);
  }
  show("cancel-button", busy);
}

function readOptions() {
  return {
    validator: document.querySelector('[name="validator"]:checked').value,
    workers: Number($("workers").value), timeout: Number($("timeout").value),
    retries: Number($("retries").value), retry_delay: Number($("retry-delay").value),
    use_cache: $("use-cache").checked, cache_ttl: Number($("cache-ttl").value),
  };
}

function fileChanged() {
  const file = $("playlist-file").files[0];
  text("file-label", file?.name || "Choisir un fichier M3U");
  if (file && state.config && file.size > state.config.max_size) {
    notice("form-error", "Le fichier dépasse la limite de 50 Mo.", "error");
  } else { notice("form-error", ""); }
}

async function start(event) {
  event.preventDefault();
  if (!state.config) return;
  const form = new FormData();
  form.set("mode", state.mode);
  form.set("options", JSON.stringify(readOptions()));
  if (state.mode === "file") {
    const file = $("playlist-file").files[0];
    if (!file || file.size > state.config.max_size) {
      notice("form-error", "Choisissez un fichier M3U de 50 Mo maximum.", "error"); return;
    }
    form.set("file", file);
  } else if (state.mode === "url") { form.set("url", $("playlist-url").value.trim()); }
  else { form.set("preset", $("source-preset-select").value); }
  setBusy(true);
  $("cancel-button").disabled = true;
  clearTimeout(state.timer);
  state.pollSerial++;
  notice("form-error", "");
  try {
    const created = await api("/api/jobs", { method: "POST", body: form });
    stopPlayer();
    state.job = created.id;
    state.rendered = null;
    state.rows = [];
    state.page = 0;
    $("search").value = "";
    $("status-filter").value = "all";
    try { localStorage.setItem("playlist-cleaner-job", state.job); } catch { /* Optional resume. */ }
    show("empty-state", false);
    show("how-it-works", false);
    show("completed-state", false);
    notice("result-message", "");
    notice("result-warnings", "");
    $("cancel-button").disabled = false;
    $("results-title").scrollIntoView({ behavior: "smooth", block: "nearest" });
    await poll();
  } catch (error) {
    notice("form-error", error.message, "error");
    setBusy(false);
  }
}

async function poll() {
  clearTimeout(state.timer);
  if (!state.job) return;
  const iteration = ++state.pollSerial;
  const jobId = state.job;
  try {
    const job = await api(`/api/jobs/${jobId}`);
    if (iteration !== state.pollSerial || state.job !== jobId) return;
    if (state.connectionLost) {
      notice("result-message", "");
      state.connectionLost = false;
    }
    text("status-label", job.stage);
    show("empty-state", false);
    show("how-it-works", false);
    const busy = !terminal.has(job.state);
    setBusy(busy);
    show("running-state", busy);
    $("cancel-button").disabled = job.state === "cancelling";
    text("progress-caption", job.stage);
    text("progress-count", job.total ? `${number.format(job.completed)} / ${number.format(job.total)}` : "");
    if (job.total) {
      $("progress").value = 100 * job.completed / job.total;
      text("progress-detail", `${number.format(job.working)} flux valide${job.working === 1 ? "" : "s"} · ${number.format(job.completed - job.working)} invalide${job.completed - job.working === 1 ? "" : "s"}`);
    } else {
      $("progress").removeAttribute("value");
      text("progress-detail", "La durée dépend du nombre de flux et de leur disponibilité.");
    }
    notice("result-warnings", job.warnings.join(" "), "warning");
    if (job.state === "completed" && state.rendered !== job.id) {
      const report = await api(`/api/jobs/${job.id}/results`);
      if (iteration !== state.pollSerial || state.job !== jobId) return;
      state.rows = report.streams;
      renderCompleted(job);
      state.rendered = job.id;
    } else if (job.state === "failed") {
      notice("result-message", job.error || "L'analyse n'a pas abouti.", "error");
    } else if (job.state === "cancelled") {
      notice("result-message", "Analyse annulée. Vous pouvez choisir une autre source et recommencer.");
    }
    if (busy) state.timer = setTimeout(poll, 800);
  } catch (error) {
    if (iteration !== state.pollSerial || state.job !== jobId) return;
    if (error.status === 404) {
      state.job = null;
      try { localStorage.removeItem("playlist-cleaner-job"); } catch { /* Optional resume. */ }
      setBusy(false);
      show("running-state", false);
      notice("result-message", "Cette analyse n'est plus disponible. Vous pouvez en lancer une nouvelle.");
    } else {
      state.connectionLost = true;
      notice("result-message", "Connexion au serveur interrompue. Nouvelle tentative dans quelques secondes…", "warning");
      state.timer = setTimeout(poll, 2500);
    }
  }
}

function element(tag, className, content) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content !== undefined) node.textContent = content;
  return node;
}

const player = { hls: null, row: null, timer: null, generation: 0 };

function safeMediaUrl(value) {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) && !url.username && !url.password ? url.href : "";
  } catch { return ""; }
}

function channelLogo(row) {
  const box = element("span", "channel-logo");
  box.setAttribute("aria-hidden", "true");
  const fallback = element("span", "logo-initials", (row.name || "TV").slice(0, 2).toUpperCase());
  box.append(fallback);
  const url = safeMediaUrl(row.logo);
  if (url) {
    const img = document.createElement("img");
    img.alt = "";
    img.loading = "lazy";
    img.referrerPolicy = "no-referrer";
    img.addEventListener("load", () => { fallback.hidden = true; });
    img.addEventListener("error", () => { img.remove(); fallback.hidden = false; }, { once: true });
    img.src = url;
    box.append(img);
  }
  return box;
}

function stopPlayer() {
  player.generation++;
  clearTimeout(player.timer);
  const video = $("channel-video");
  video.onplaying = video.onerror = video.onwaiting = video.oncanplay = video.onpause = null;
  if (player.hls) { player.hls.destroy(); player.hls = null; }
  video.pause();
  video.removeAttribute("src");
  video.load();
  player.row = null;
  show("player-panel", false);
  updateCurrentCard();
}

function playChannel(row) {
  stopPlayer();
  const generation = player.generation;
  player.row = row;
  updateCurrentCard();
  const video = $("channel-video");
  const title = element("h3", "", row.name);
  title.id = "player-title";
  $("player-identity").replaceChildren(channelLogo(row), title);
  $("player-vlc").href = `/api/jobs/${state.job}/streams/${row.index}/playlist`;
  show("player-panel", true);
  show("channel-video", true);
  $("player-panel").scrollIntoView({ behavior: "smooth", block: "nearest" });
  const url = safeMediaUrl(row.playback_url);
  const fail = (message) => {
    if (generation !== player.generation) return;
    clearTimeout(player.timer);
    if (player.hls) { player.hls.destroy(); player.hls = null; }
    video.oncanplay = video.onplaying = video.onwaiting = video.onerror = video.onpause = null;
    video.pause(); video.removeAttribute("src"); video.load();
    show("channel-video", false);
    text("player-status", message);
  };
  if (row.needs_headers) {
    show("channel-video", false);
    text("player-status", "Ce flux nécessite des en-têtes spécifiques. Téléchargez le M3U pour le lire dans VLC en conservant ses réglages.");
    return;
  }
  if (!url) { fail("Ce format d’adresse ne peut pas être lu dans le navigateur. Essayez avec VLC."); return; }
  text("player-status", "Connexion au flux…");
  player.timer = setTimeout(() => fail("Le flux ne répond pas. Réessayez ou ouvrez-le dans VLC."), 25000);
  video.onplaying = () => { clearTimeout(player.timer); text("player-status", "Lecture en cours"); };
  video.onwaiting = () => {
    text("player-status", "Mise en mémoire tampon…");
    clearTimeout(player.timer);
    player.timer = setTimeout(() => fail("La lecture reste bloquée. Réessayez ou ouvrez le flux dans VLC."), 25000);
  };
  video.onpause = () => {
    clearTimeout(player.timer);
    text("player-status", video.ended ? "Lecture terminée" : "En pause");
  };
  video.onerror = () => fail("Lecture impossible : format non pris en charge, flux indisponible ou accès refusé par le diffuseur. Essayez avec VLC.");
  const begin = () => {
    if (generation !== player.generation) return;
    video.play().catch((error) => {
      if (generation !== player.generation || error.name === "AbortError") return;
      if (error.name === "NotAllowedError") {
        clearTimeout(player.timer);
        text("player-status", "Appuyez sur Lecture dans la vidéo pour démarrer.");
      } else { fail("Ce flux ne peut pas être lu ici. Essayez avec VLC."); }
    });
  };
  const isFile = /\.(mp4|m4v|webm|ogv|mp3|m4a|ogg)(?:$|[?#])/i.test(url);
  if (!isFile && !video.canPlayType("application/vnd.apple.mpegurl") && window.Hls?.isSupported()) {
    const hls = new Hls({ maxBufferLength: 20, backBufferLength: 30 });
    player.hls = hls;
    hls.on(Hls.Events.ERROR, (_, data) => {
      if (data.fatal) fail("Lecture HLS impossible : flux indisponible, format incompatible ou accès refusé (CORS). Essayez avec VLC.");
    });
    hls.on(Hls.Events.MANIFEST_PARSED, begin);
    hls.loadSource(url);
    hls.attachMedia(video);
  } else {
    video.src = url;
    begin();
  }
}

$("close-player").addEventListener("click", () => {
  const current = document.querySelector('.channel-card[aria-current="true"]');
  stopPlayer();
  (current || $("search")).focus();
});
$("retry-player").addEventListener("click", () => { if (player.row) playChannel(player.row); });
window.addEventListener("pagehide", stopPlayer);

function renderCompleted(job) {
  show("completed-state", true);
  notice("result-message", job.summary.selected === 0 ? "Aucun flux valide trouvé. Les rapports restent disponibles pour comprendre les échecs." : "");
  $("summary-strip").replaceChildren();
  for (const [key, label] of [["selected", "Flux conservés"], ["invalid", "Flux invalides"], ["discarded", "Flux écartés"]]) {
    const item = element("div", "summary-item");
    item.append(element("strong", "", number.format(job.summary[key])), element("span", "", label));
    $("summary-strip").append(item);
  }
  text("status-label", `${number.format(job.summary.total)} flux analysé${job.summary.total === 1 ? "" : "s"} · ${number.format(job.summary.cached)} depuis le cache`);
  $("downloads").replaceChildren();
  for (const [key, label] of [["playlist", "Télécharger la playlist"], ["json", "Rapport JSON"], ["csv", "Rapport CSV"]]) {
    if (!job.downloads[key]) continue;
    const link = element("a", `secondary ${key === "playlist" ? "download-main" : ""}`, label);
    link.href = job.downloads[key];
    link.setAttribute("download", "");
    $("downloads").append(link);
  }
  renderChannels();
}

function updateCurrentCard() {
  for (const card of document.querySelectorAll(".channel-card")) {
    const selected = Boolean(player.row && card.dataset.streamIndex === String(player.row.index));
    card.classList.toggle("is-current", selected);
    if (selected) card.setAttribute("aria-current", "true");
    else card.removeAttribute("aria-current");
    card.querySelector(".card-action").textContent = card.disabled ? "Indisponible" : selected ? "Dans le lecteur" : "▶ Lire";
  }
}

function renderChannels() {
  const search = $("search").value.trim().toLocaleLowerCase("fr");
  const status = $("status-filter").value;
  const rows = state.rows.filter((row) => (status === "all" || row.status === status) && String(row.name).toLocaleLowerCase("fr").includes(search));
  const pageSize = 24;
  const pages = Math.max(1, Math.ceil(rows.length / pageSize));
  state.page = Math.min(state.page, pages - 1);
  const fragment = document.createDocumentFragment();
  for (const row of rows.slice(state.page * pageSize, (state.page + 1) * pageSize)) {
    const item = element("li");
    const card = element("button", "channel-card");
    card.type = "button";
    card.dataset.streamIndex = row.index;
    card.disabled = row.status === "invalid";
    card.setAttribute("aria-label", `${card.disabled ? "Indisponible :" : "Lire"} ${row.name}`);
    const badges = element("span", "channel-badges");
    badges.append(element("span", `status ${row.status}`, {selected:"Conservé",invalid:"Invalide",discarded:"Écarté"}[row.status] || row.status));
    if (row.quality && !["unknown", "failed", "timeout"].includes(row.quality)) {
      badges.append(element("span", "channel-quality", row.quality));
    }
    const description = row.error || (row.reason === "duplicate" ? "Flux en double" : row.reason === "lower_quality" ? "Une meilleure version a été conservée" : "");
    card.title = [row.name, description].filter(Boolean).join(" — ");
    card.append(badges, channelLogo(row), element("span", "channel-name", row.name));
    if (description) card.append(element("span", "channel-detail", description));
    card.append(element("span", "card-action", card.disabled ? "Indisponible" : "▶ Lire"));
    card.addEventListener("click", () => playChannel(row));
    item.append(card);
    fragment.append(item);
  }
  $("channel-grid").replaceChildren(fragment);
  updateCurrentCard();
  show("no-matches", rows.length === 0);
  text("page-label", `${number.format(rows.length)} flux · page ${state.page + 1}/${pages}`);
  $("previous-page").disabled = state.page === 0;
  $("next-page").disabled = state.page >= pages - 1;
}

document.querySelectorAll("[data-mode]").forEach((tab, index, tabs) => {
  tab.addEventListener("click", () => setMode(tab.dataset.mode));
  tab.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
    tabs[next].focus(); setMode(tabs[next].dataset.mode);
  });
});
$("cleaner-form").addEventListener("submit", start);
$("france-source").addEventListener("click", () => { $("playlist-url").value = state.config.default_url; });
$("playlist-file").addEventListener("change", fileChanged);
$("source-preset-select").addEventListener("change", () => {
  const preset = state.config.presets.find((item) => item.id === $("source-preset-select").value);
  text("preset-hint", `${preset.count} source${preset.count > 1 ? "s" : ""}`);
});
$("cache-ttl").addEventListener("input", () => {
  const seconds = Number($("cache-ttl").value);
  text("cache-hint", seconds === 3600 ? "Cache valable 1 heure" : `Cache valable ${number.format(seconds)} secondes`);
});
$("cancel-button").addEventListener("click", async () => {
  $("cancel-button").disabled = true;
  try { await api(`/api/jobs/${state.job}/cancel`, {method:"POST"}); await poll(); }
  catch (error) { notice("result-message", error.message, "error"); $("cancel-button").disabled = false; }
});
for (const id of ["search", "status-filter"]) $(id).addEventListener(id === "search" ? "input" : "change", () => { state.page = 0; renderChannels(); });
$("previous-page").addEventListener("click", () => { state.page--; renderChannels(); });
$("next-page").addEventListener("click", () => { state.page++; renderChannels(); });
for (const name of ["dragenter", "dragover"]) $("dropzone").addEventListener(name, (event) => { event.preventDefault(); $("dropzone").classList.add("dragging"); });
for (const name of ["dragleave", "drop"]) $("dropzone").addEventListener(name, (event) => { event.preventDefault(); $("dropzone").classList.remove("dragging"); });
$("dropzone").addEventListener("drop", (event) => {
  if (!$("form-fields").disabled && event.dataTransfer.files.length) { $("playlist-file").files = event.dataTransfer.files; fileChanged(); }
});

(async function init() {
  try {
    state.config = await api("/api/config");
    $("source-preset-select").replaceChildren(...state.config.presets.map((preset) => {
      const option = element("option", "", preset.name); option.value = preset.id; return option;
    }));
    if (!state.config.tools.ffprobe && state.config.tools.curl) document.querySelector('[name="validator"][value="curl"]').checked = true;
    const missing = Object.keys(state.config.tools).filter((name) => !state.config.tools[name]);
    if (missing.length) {
      text("tool-warning", `${missing.join(" et ")} introuvable${missing.length > 1 ? "s" : ""}. Installez ${missing.includes("ffprobe") ? "FFmpeg" : "curl"} puis rechargez la page.`);
      show("tool-warning", true);
    }
    setBusy(false);
    try { state.job = localStorage.getItem("playlist-cleaner-job"); } catch { /* Optional resume. */ }
    if (state.job) await poll();
  } catch (error) { notice("form-error", `Impossible de joindre le serveur. ${error.message}`, "error"); }
})();
