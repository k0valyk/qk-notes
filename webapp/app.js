/* PLANNER Mini App */
const tg = window.Telegram?.WebApp;
tg?.ready(); tg?.expand();

/* --- i18n ------------------------------------------------------------------ */
let LANG = "en";
let DICT = {};
const LOCALE_MAP = { en: "en-US", uk: "uk-UA", ru: "ru-RU", pl: "pl-PL", es: "es-ES" };
function tr(key, fallback){
  if (DICT[key] != null) return DICT[key];
  return fallback != null ? fallback : key;
}
function applyI18n(){
  document.querySelectorAll("[data-i18n]").forEach(el => {
    const v = DICT[el.dataset.i18n];
    if (v != null) el.textContent = v;
  });
  document.getElementById("remind-input").placeholder = tr("ph_reminder", "New reminder…");
  const qi = document.getElementById("quick-input");
  if (qi) qi.placeholder = tr(TABLES[current.table].phKey);
}
async function setLang(lang){
  LANG = lang;
  try {
    const res = await fetch(`/locales/${lang}.json`);
    DICT = res.ok ? await res.json() : {};
  } catch { DICT = {}; }
  applyI18n();
  applyLangUI();
  if (document.getElementById("screen-list").classList.contains("active")) renderTabs();
}

const TABLES = {
  plans:    { subs: ["in_progress", "done"], phKey: "ph_task",
              chip: { in_progress: "doing", done: "done" } },
  notes:    { subs: ["note", "idea"], phKey: "ph_record", chip: {} },
  meetings: { subs: ["upcoming", "past"], phKey: "ph_meeting", chip: {} },
  reminders:{ subs: [], phKey: "ph_reminder", chip: {} },
};
const SUB_KEYS = {
  in_progress: "sub_in_progress", done: "sub_done", note: "sub_note",
  idea: "sub_idea", upcoming: "sub_upcoming", past: "sub_past",
};
function subLabel(sub){ return tr(SUB_KEYS[sub] || sub, (sub || "").replace(/_/g, " ")); }
const TABLE_SCREEN = { plans: "list", notes: "list", meetings: "list", reminders: "reminders" };

let current = { table: "plans", sub: "in_progress" };
let editing = null; // {table, item}
let longPressTimer = null;
let me = null;

function escapeHtml(s){ return (s||"").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }

function headers(){
  return { "Content-Type": "application/json", "X-Telegram-Init-Data": tg?.initData || "" };
}
async function api(path, options = {}){
  const res = await fetch(path, { ...options, headers: headers() });
  if (res.status === 401) throw new Error("unauthorized");
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/* --- digest ------------------------------------------------------------ */
async function loadDigest(){
  const d = new Date();
  const loc = LOCALE_MAP[LANG] || "en-US";
  document.getElementById("hero-day").textContent =
    d.toLocaleDateString(loc, { weekday:"long" });
  document.getElementById("hero-date").textContent =
    d.toLocaleDateString(loc, { month:"long", day:"numeric" });
  try {
    const [plans, notes, meetings, reminders] = await Promise.all([
      api("/api/plans"), api("/api/notes"), api("/api/meetings"), api("/api/reminders")]);
    const doing = plans.filter(p => p.subsection === "in_progress");
    const done = plans.filter(p => p.subsection === "done");
    const upcoming = meetings.filter(m => m.subsection !== "past");
    document.getElementById("hero-greet").textContent =
      (!doing.length && !upcoming.length)
        ? tr("greet_empty", "Nothing planned yet — add by voice.")
        : tr("greet_summary", `${doing.length} task(s) in progress, ${upcoming.length} upcoming meeting(s).`)
            .replace("{t}", doing.length).replace("{m}", upcoming.length);
    const dp = document.getElementById("digest-plans");
    dp.innerHTML = doing.length
      ? doing.slice(0, 1).map(p => `<div>${escapeHtml(p.title || (p.text||"").slice(0,40))}</div>`).join("") +
        `<div class="dim">${subLabel("in_progress")}</div>`
      : `<div class="dim">${tr("greet_empty", "Nothing planned yet — add by voice.")}</div>`;
    document.getElementById("digest-plans-badges").innerHTML =
      `<span class="badge doing">${doing.length} · ${subLabel("in_progress")}</span><span class="badge done">${done.length} · ${subLabel("done")}</span>`;
    const dr = document.getElementById("digest-records");
    dr.innerHTML = notes.length
      ? `<div>${escapeHtml(notes[0].title || (notes[0].text||"").slice(0,40))}</div>` +
        `<div class="dim">${subLabel("note")} · ${notes.length}</div>`
      : `<div class="dim">${tr("no_records", "No records yet")}</div>`;
    const dm = document.getElementById("digest-meetings");
    dm.innerHTML = upcoming.length
      ? upcoming.slice(0, 3).map(m => `
          <div class="meet-row">
            <div class="time">${m.datetime ? fmtDate(m.datetime).split(", ")[1] || "—" : "—"}</div>
            <div><div class="what">${escapeHtml(m.title || (m.text||"").slice(0,40))}</div>
                 <div class="who">${m.datetime ? escapeHtml(fmtDate(m.datetime)) : ""}</div></div>
          </div>`).join("")
      : `<div class="meet-row"><div class="what" style="color:var(--muted)">${tr("no_meetings", "No upcoming meetings")}</div></div>`;
    const drm = document.getElementById("digest-reminders");
    const now = Date.now();
    const nearest = reminders
      .filter(r => r.datetime && new Date(r.datetime).getTime() >= now)
      .sort((a, b) => new Date(a.datetime) - new Date(b.datetime)).slice(0, 3);
    drm.innerHTML = nearest.length
      ? nearest.map(r => `
          <div class="meet-row">
            <div class="time">${fmtDate(r.datetime).split(", ")[1] || "—"}</div>
            <div><div class="what">${escapeHtml(r.title || (r.text||"").slice(0,40))}</div>
                 <div class="who">${escapeHtml(fmtDate(r.datetime))}</div></div>
          </div>`).join("")
      : `<div class="meet-row"><div class="what" style="color:var(--muted)">${tr("no_reminders", "No reminders yet")}</div></div>`;
  } catch { /* unauthorized or offline */ }
}

/* --- list sections ------------------------------------------------------ */
function openSection(table){
  current.table = table;
  current.sub = TABLES[table].subs[0] || null;
  const scr = TABLE_SCREEN[table];
  show(scr);
  if (scr === "list"){
    document.getElementById("quick-input").placeholder = tr(TABLES[table].phKey);
    renderTabs();
  }
  renderList();
}

function renderTabs(){
  const t = TABLES[current.table];
  const tabs = document.getElementById("tabs");
  const html = t.subs.map((s, i) =>
    `<div class="tab ${s === current.sub ? "active" : ""}" data-sub="${s}">${subLabel(s)}</div>`).join("");
  tabs.innerHTML = html;
  tabs.querySelectorAll(".tab").forEach(el => el.addEventListener("click", () => {
    current.sub = el.dataset.sub; renderTabs(); renderList();
  }));
}

async function renderList(){
  const table = current.table;
  const container = scrEl(table);
  container.innerHTML = "";
  let items = [];
  try { items = await api(`/api/${table}`); } catch { return; }
  if (table !== "reminders" && current.sub) items = items.filter(i => i.subsection === current.sub);
  if (!items.length){
    container.innerHTML = `<div class="empty"><div class="wm">PLANNER</div>
      <div class="sub">${tr("empty_hint", "Nothing here yet. Add by voice or with the + button.")}</div></div>`;
    return;
  }
  for (const item of items){
    const div = document.createElement("div");
    div.className = "item" + (item.subsection === "done" ? " done" : "");
    const chip = TABLES[table].chip[item.subsection]
      ? `<span class="chip ${TABLES[table].chip[item.subsection]}">${subLabel(item.subsection)}</span>`
      : "";
    const showWhen = table !== "notes" && (item.datetime || item.created_at);
    const when = showWhen ? (item.datetime ? fmtDate(item.datetime)
      : item.created_at.slice(0, 16).replace("T", " ")) : "";
    div.innerHTML = `<div class="top"><div class="txt">${escapeHtml(item.text)}</div>${chip}</div>` +
      (when ? `<div class="meta">${escapeHtml(when)}</div>` : "");
    bindLongPress(div, table, item);
    container.appendChild(div);
  }
}

function scrEl(table){ return table === "reminders" ? document.getElementById("remind-items") : document.getElementById("list-items"); }

function bindLongPress(el, table, item){
  el.addEventListener("contextmenu", e => { e.preventDefault(); openSheet(table, item); });
  el.addEventListener("touchstart", () => { longPressTimer = setTimeout(() => openSheet(table, item), 450); });
  el.addEventListener("touchend", () => clearTimeout(longPressTimer));
  el.addEventListener("touchmove", () => clearTimeout(longPressTimer));
  let down;
  el.addEventListener("mousedown", () => { down = setTimeout(() => openSheet(table, item), 450); });
  el.addEventListener("mouseup", () => clearTimeout(down));
}

function fmtDate(iso){
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleDateString(undefined, { month:"short", day:"numeric" }) + ", " +
         d.toLocaleTimeString(undefined, { hour:"2-digit", minute:"2-digit" });
}

/* --- add/edit bottom sheet ---------------------------------------------- */
function openSheet(table, item = null){
  editing = { table, item };
  const t = TABLES[table];
  document.querySelector(".fab").style.display = "none";
  document.querySelector(".mic").style.display = "none";
  document.getElementById("sheet-overlay").classList.remove("hidden");
  try { tg?.BackButton?.offClick(closeSheet); tg?.BackButton?.onClick(closeSheet); tg?.BackButton?.show?.(); } catch {}
  document.getElementById("sheet-text").value = item ? (item.text || "") : "";
  document.getElementById("sheet-datetime").value = item?.datetime || "";
  const chips = document.getElementById("sheet-chips");
  const label = document.getElementById("sheet-sub-label");
  if (t.subs.length){
    label.style.display = "block";
    chips.innerHTML = t.subs.map((s, i) =>
      `<span class="chip-opt ${item?.subsection === s ? "on" : ""}" data-sub="${s}">${subLabel(s)}</span>`).join("");
    if (!item?.subsection) chips.querySelector(".chip-opt")?.classList.add("on");
    chips.querySelectorAll(".chip-opt").forEach(c => c.addEventListener("click", () => {
      chips.querySelectorAll(".chip-opt").forEach(x => x.classList.remove("on"));
      c.classList.add("on");
    }));
  } else {
    label.style.display = "none";
    chips.innerHTML = "";
  }
  document.getElementById("sheet-del").style.visibility = item ? "visible" : "hidden";
  requestAnimationFrame(() => { try { document.getElementById("sheet-text").focus(); } catch {} });
}

function closeSheet(){
  document.getElementById("sheet-overlay").classList.add("hidden");
  editing = null;
  try { tg?.BackButton?.hide?.(); tg?.BackButton?.offClick(closeSheet); } catch {}
  const active = document.querySelector(".screen.active")?.id || "";
  const onList = ["screen-list","screen-reminders"].includes(active);
  document.querySelector(".fab").style.display = (onList || active === "screen-digest") ? "flex" : "none";
  document.querySelector(".mic").style.display = active === "screen-digest" ? "flex" : "none";
}

document.getElementById("sheet-save").addEventListener("click", async () => {
  if (!editing) return;
  const { table, item } = editing;
  const text = document.getElementById("sheet-text").value.trim();
  if (!text) { closeSheet(); return; }
  const sub = document.querySelector("#sheet-chips .chip-opt.on")?.dataset.sub || null;
  const dt = document.getElementById("sheet-datetime").value || null;
  const body = JSON.stringify({ text, title: item?.title || null, subsection: sub, datetime: dt });
  try {
    if (item) await api(`/api/${table}/${item.id}`, { method: "PUT", body });
    else await api(`/api/${table}`, { method: "POST", body });
    tg?.HapticFeedback?.notificationOccurred("success");
    closeSheet();
    if (["list","reminders"].includes(TABLE_SCREEN[table] || "list") &&
        document.querySelector(".screen.active").id === `screen-${TABLE_SCREEN[table]}`) renderList();
    loadDigest();
  } catch (e) { tg?.showAlert?.(tr("err_save", "Save failed") + ": " + e.message); }
});

document.getElementById("sheet-cancel").addEventListener("click", closeSheet);
document.getElementById("sheet-del").addEventListener("click", async () => {
  if (!editing?.item) return;
  try {
    await api(`/api/${editing.table}/${editing.item.id}`, { method: "DELETE" });
    closeSheet(); renderList(); loadDigest();
  } catch (e) { tg?.showAlert?.(tr("err_delete", "Delete failed")); }
});
document.getElementById("sheet-overlay").addEventListener("click", e => {
  if (!e.target.closest(".sheet")) closeSheet();
});
document.querySelector(".sheet").addEventListener("pointerdown", e => {
  if (e.target.closest(".chip-row") || e.target.closest(".actions") || e.target.closest("input, textarea")) return;
  try { document.getElementById("sheet-text").focus({ preventScroll: true }); } catch {}
});

/* --- quick add (inline field) + FAB + mic -------------------------------- */
document.getElementById("quick-input").addEventListener("keydown", async e => {
  if (e.key === "Enter"){
    e.preventDefault();
    const text = e.target.value.trim();
    if (!text) return;
    try {
      await api(`/api/${current.table}`, { method: "POST",
        body: JSON.stringify({ text, subsection: current.sub, datetime: null }) });
      e.target.value = "";
      renderList();
    } catch (err) { tg?.showAlert?.(tr("err_add", "Add failed")); }
  }
});
document.getElementById("remind-input").addEventListener("keydown", async e => {
  if (e.key === "Enter"){
    e.preventDefault();
    const text = e.target.value.trim();
    if (!text) return;
    try {
      await api("/api/reminders", { method: "POST",
        body: JSON.stringify({ text, datetime: new Date(Date.now() + 3600000).toISOString().slice(0,19) }) });
      e.target.value = "";
      renderList();
    } catch (err) { tg?.showAlert?.(tr("err_add", "Add failed")); }
  }
});
document.querySelector(".fab").addEventListener("click", () => {
  if (document.querySelector(".screen.active").id === "screen-digest") openSection("plans");
  else openSheet(current.table, null);
});
document.querySelector(".mic").addEventListener("click", () => {
  tg?.HapticFeedback?.notificationOccurred("warning");
  tg?.showAlert?.(tr("mic_hint", "Press and hold 🎙 in the chat with the bot to add by voice."));
});

/* --- in-app voice recorder (press and hold the 🎙 button) ------------------ */
const TYPE_KEYS = { plan: "type_plan", note: "type_note", meeting: "type_meeting", reminder: "type_reminder" };
let recorder = null, recorderStream = null, micChunks = [], micHeld = false, micHoldTimer = null;

function showMicOverlay(on, status, sub){
  const ov = document.getElementById("mic-overlay");
  if (!ov) return;
  if (on){
    ov.classList.remove("hidden");
    document.getElementById("mic-status").textContent = status;
    document.getElementById("mic-sub").textContent = sub || "";
  } else ov.classList.add("hidden");
}
function hideFabMic(){
  document.querySelector(".fab").style.display = "none";
  document.querySelector(".mic").style.display = "none";
}
function restoreFabMic(){
  const active = document.querySelector(".screen.active")?.id || "";
  const onList = ["screen-list","screen-reminders"].includes(active);
  document.querySelector(".fab").style.display = (onList || active === "screen-digest") ? "flex" : "none";
  document.querySelector(".mic").style.display = active === "screen-digest" ? "flex" : "none";
}
async function startRecording(){
  try {
    if (!navigator.mediaDevices || typeof navigator.mediaDevices.getUserMedia !== "function") throw new Error("noMic");
    recorderStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recorder = new MediaRecorder(recorderStream, { mimeType: "audio/webm" });
    micChunks = [];
    recorder.addEventListener("dataavailable", e => { if (e.data && e.data.size) micChunks.push(e.data); });
    recorder.addEventListener("stop", () => { sendRecordedAudio(); });
    recorder.start();
    hideFabMic();
    showMicOverlay(true, tr("recording", "Recording…"), tr("mic_release", "Release to send"));
    tg?.HapticFeedback?.notificationOccurred("success");
  } catch (e){
    showMicOverlay(false); restoreFabMic();
    tg?.showAlert?.(tr("mic_unavailable", "Recording isn't available here. Hold 🎙 in the chat with the bot instead."));
  }
}
function stopRecording(){
  clearTimeout(micHoldTimer);
  if (recorder){ try { recorder.stop(); } catch(e){ showMicOverlay(false); restoreFabMic(); } }
  else { showMicOverlay(false); restoreFabMic(); }
}
async function sendRecordedAudio(){
  showMicOverlay(true, tr("analyzing", "Analyzing…"), "");
  const blob = new Blob(micChunks, { type: "audio/webm" });
  micChunks = [];
  recorder = null;
  if (recorderStream){ try { recorderStream.getTracks().forEach(tr => tr.stop()); } catch {} recorderStream = null; }
  try {
    const fd = new FormData();
    fd.append("audio", blob, "voice.webm");
    const res = await fetch("/api/voice", { method: "POST", headers: { "X-Telegram-Init-Data": tg?.initData || "" }, body: fd });
    if (!res.ok) throw new Error("err");
    const j = await res.json();
    showMicOverlay(false); restoreFabMic();
    if (j.saved){
      const typeName = tr(TYPE_KEYS[j.record_type] || j.record_type, j.record_type);
      tg?.showAlert?.(tr("mic_saved", "Saved {type} #{id}").replace("{type}", typeName).replace("{id}", String(j.record_id)));
    } else {
      tg?.showAlert?.(tr("no_speech", "Couldn't recognize any speech. Try again."));
    }
    loadDigest();
  } catch (e){
    showMicOverlay(false); restoreFabMic();
    tg?.showAlert?.(tr("err_add", "Add failed"));
  }
}
const micBtn = document.querySelector(".mic");
micBtn.addEventListener("pointerdown", e => {
  e.preventDefault();
  micHeld = true;
  micHoldTimer = setTimeout(() => { if (micHeld) startRecording(); }, 200);
});
micBtn.addEventListener("pointerup", () => { micHeld = false; stopRecording(); });
micBtn.addEventListener("pointercancel", () => { micHeld = false; stopRecording(); });
micBtn.addEventListener("contextmenu", e => { e.preventDefault(); });

/* --- settings ------------------------------------------------------------ */
function langName(l){ return { en:"English", uk:"Українська", ru:"Русский", pl:"Polski", es:"Español" }[l] || l; }
function applyLangUI(){
  document.querySelectorAll(".lang").forEach(x => x.classList.toggle("active", x.dataset.l === LANG));
  const el = document.getElementById("lang-val");
  if (el) el.textContent = langName(LANG) + " ›";
}
function applyTheme(mode){
  document.body.classList.toggle("light", mode === "light");
  if (tg?.setHeaderColor) tg.setHeaderColor(mode === "light" ? "#f5f5f7" : "#0a0a0c");
}
async function loadSettings(){
  try {
    me = await api("/api/settings");
    if (me.language && me.language !== LANG) await setLang(me.language);
    document.getElementById("uname").textContent = me.first_name || "User";
    document.getElementById("uhandle").textContent = me.username ? "@" + me.username : "";
    document.getElementById("avatar").textContent = (me.first_name || "U")[0].toUpperCase();
    applyLangUI();
    try {
      const qa = await api("/api/quick-action/token");
      document.getElementById("qa-url").textContent = qa.url;
      document.getElementById("qa-block").classList.remove("hidden");
      document.getElementById("qa-toggle").classList.remove("off");
    } catch {}
    document.querySelectorAll(".theme-opt").forEach(t => t.classList.toggle("on", t.dataset.t === (me.theme || "dark")));
    applyTheme(me.theme || "dark");
    document.getElementById("admin-block").style.display = me.is_admin ? "block" : "none";
  } catch { /* ignore */ }
}
document.getElementById("row-language").addEventListener("click", () =>
  document.getElementById("lang-pills").classList.toggle("hidden"));
document.querySelectorAll(".lang").forEach(l => l.addEventListener("click", async () => {
  await api("/api/settings", { method: "PUT", body: JSON.stringify({ language: l.dataset.l }) }).catch(()=>{});
  await setLang(l.dataset.l);
  applyLangUI();
  loadDigest();
}));
document.querySelectorAll(".theme-opt").forEach(t => t.addEventListener("click", async () => {
  await api("/api/settings", { method: "PUT", body: JSON.stringify({ theme: t.dataset.t }) }).catch(()=>{});
  applyTheme(t.dataset.t);
  document.querySelectorAll(".theme-opt").forEach(x => x.classList.toggle("on", x === t));
}));
document.getElementById("qa-toggle").addEventListener("click", async () => {
  const block = document.getElementById("qa-block");
  const tog = document.getElementById("qa-toggle");
  if (block.classList.contains("hidden")){
    block.classList.remove("hidden");
    tog.classList.remove("off");
    try {
      const qa = await api("/api/quick-action/token");
      document.getElementById("qa-url").textContent = qa.url;
    } catch { document.getElementById("qa-url").textContent = ""; }
  } else { block.classList.add("hidden"); tog.classList.add("off"); }
});
document.getElementById("qa-copy").addEventListener("click", () => {
  const url = document.getElementById("qa-url").textContent;
  if (navigator.clipboard) navigator.clipboard.writeText(url);
  tg?.HapticFeedback?.notificationOccurred("success");
});
document.getElementById("qa-refresh").addEventListener("click", async () => {
  try {
    const qa = await api("/api/quick-action/token");
    document.getElementById("qa-url").textContent = qa.url;
  } catch { /* ignore */ }
});
document.getElementById("qa-open").addEventListener("click", () => {
  window.location.href = "shortcuts://create-shortcut";
});

/* --- admin ---------------------------------------------------------------- */
async function loadAdmin(){
  try {
    const stats = await api("/api/admin/stats");
    document.getElementById("admin-stats").innerHTML = Object.entries(stats)
      .map(([k, v]) => `<div class="row"><span>${k.replace(/_/g, " ")}</span><b>${v}</b></div>`).join("");
    const users = await api("/api/admin/users");
    document.getElementById("admin-users").innerHTML = users.map(u => `
      <div class="row" data-uid="${u.user_id}" style="cursor:pointer;">
        <span>${u.is_blocked ? "🚫 " : ""}${escapeHtml(u.first_name || "")} ${u.username ? "@" + escapeHtml(u.username) : ""}</span>
        <span class="dim">${u.language} · ${u.is_blocked ? "tap to unblock" : "tap to block"}</span>
      </div>`).join("") || "<div class='dim'>No users</div>";
    document.querySelectorAll("#admin-users .row").forEach(r => r.addEventListener("click", () => toggleBlock(+r.dataset.uid)));
    const logs = await api("/api/admin/logs");
    document.getElementById("admin-logs").innerHTML = logs.map(l =>
      `<div class="row"><span>${escapeHtml(l.event_type)} · ${escapeHtml(l.status)}</span>
       <span class="dim">${escapeHtml(l.timestamp || "")}</span></div>`).join("") || "<div class='dim'>No logs</div>";
  } catch { tg?.showAlert?.(tr("admin_denied", "Admin access denied")); }
}
async function toggleBlock(uid){
  try {
    const users = await api("/api/admin/users");
    const u = users.find(x => x.user_id === uid);
    if (!u) return;
    await api(`/api/admin/users/${uid}/${u.is_blocked ? "unblock" : "block"}`, { method: "POST" });
    loadAdmin();
  } catch { /* ignore */ }
}
document.getElementById("broadcast-send").addEventListener("click", async () => {
  const text = document.getElementById("broadcast-text").value.trim();
  if (!text) return;
  try {
    const res = await api("/api/admin/broadcast", { method: "POST", body: JSON.stringify({ message: text }) });
    tg?.showAlert?.(tr("sent_msg", "Sent: {s}, failed: {f}").replace("{s}", res.sent).replace("{f}", res.failed));
  } catch (e) { tg?.showAlert?.(tr("err_broadcast", "Broadcast failed")); }
});
document.getElementById("row-admin").addEventListener("click", () => { loadAdmin(); show("admin"); });

/* --- init ------------------------------------------------------------------ */
applyTheme("dark");
setLang("en");
loadDigest();
loadSettings();

/* hide floating buttons while scrolling */
let floatTimer = null;
function onPageScroll(){
  const fab = document.querySelector(".fab"), mic = document.querySelector(".mic");
  if (fab) fab.classList.add("float-hide");
  if (mic) mic.classList.add("float-hide");
  clearTimeout(floatTimer);
  floatTimer = setTimeout(() => {
    if (fab) fab.classList.remove("float-hide");
    if (mic) mic.classList.remove("float-hide");
  }, 700);
}
window.addEventListener("scroll", onPageScroll, { passive: true });
document.addEventListener("scroll", onPageScroll, { passive: true });
document.querySelectorAll(".screen").forEach(scr =>
  scr.addEventListener("scroll", onPageScroll, { passive: true }));

/* quick-action setup guides */
function guideText(key, fallback){ return tr(key, fallback).replace(/\\n/g, "\n"); }
document.getElementById("qa-guide-ab").addEventListener("click", () => {
  const t = document.getElementById("qa-guide-ab-text");
  if (!t.textContent) t.textContent = guideText("actionbutton_guide",
    "Action Button setup (iPhone 15+):\n1. Open Settings → Action Button.\n2. Choose the \"Shortcut\" action.\n3. Pick the QK NOTES shortcut.\n4. Now pressing the Action Button starts voice capture and sends it to the bot.");
  t.classList.toggle("hidden");
});
document.getElementById("qa-guide-bt").addEventListener("click", () => {
  const t = document.getElementById("qa-guide-bt-text");
  if (!t.textContent) t.textContent = guideText("backtap_guide",
    "Back Tap setup (iPhone):\n1. Open Settings → Accessibility → Touch → Back Tap.\n2. Choose Double Tap or Triple Tap.\n3. Pick the QK NOTES shortcut.\n4. Now double/triple tapping the back of your phone starts voice capture and sends it to the bot.");
  t.classList.toggle("hidden");
});






/* --- screens ---------------------------------------------------------- */
function show(name){
  document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
  document.getElementById(`screen-${name}`).classList.add("active");
  document.querySelectorAll(".navitem").forEach(n =>
    n.classList.toggle("active", n.dataset.nav === name ||
      (name === "reminders" && n.dataset.nav === "reminders") ||
      (name === "list" && n.dataset.nav === (current.table === "notes" ? "records" : current.table === "meetings" ? "meetings" : current.table === "reminders" ? "reminders" : "plans"))));
  const onList = ["list","reminders"].includes(name);
  document.querySelector(".fab").style.display = onList ? "flex" : (name === "digest" ? "flex" : "none");
  document.querySelector(".mic").style.display = name === "digest" ? "flex" : "none";
  document.getElementById("back-btn").textContent = name === "digest" ? tr("btn_close", "Close") : tr("btn_back", "‹ Back");
  if (name === "digest") loadDigest();
}

document.querySelectorAll(".navitem").forEach(n =>
  n.addEventListener("click", () => {
    const nav = n.dataset.nav;
    if (nav === "records") openSection("notes");
    else if (nav === "plans") openSection("plans");
    else if (nav === "meetings") openSection("meetings");
    else if (nav === "reminders") openSection("reminders");
    else show(nav);
  }));
function closeApp(){
  try { if (tg && typeof tg.close === "function") { tg.close(); return; } } catch {}
  try { window.close(); } catch {}
}
document.getElementById("back-btn").addEventListener("click", () => {
  if (document.querySelector(".screen.active").id === "screen-digest") closeApp();
  else show("digest");
});
document.getElementById("dots-btn").addEventListener("click", () => show("settings"));
document.querySelectorAll(".card[data-open], .wide-card[data-open]").forEach(el =>
  el.addEventListener("click", () => openSection(el.dataset.open)));
