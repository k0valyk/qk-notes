/* PLANNER Mini App */
const tg = window.Telegram?.WebApp;
tg?.ready(); tg?.expand();

const TABLES = {
  plans:    { subs: ["in_progress", "done"], subNames: ["In progress", "Done"], ph: "New task…",
              chip: { in_progress: "doing", done: "done" } },
  notes:    { subs: ["note", "idea"], subNames: ["Records", "Ideas"], ph: "New record…",
              chip: {} },
  meetings: { subs: ["upcoming", "past"], subNames: ["Upcoming", "Past"], ph: "New meeting…",
              chip: {} },
  reminders:{ subs: [], subNames: [], ph: "New reminder…", chip: {} },
};
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
  document.getElementById("hero-day").textContent =
    d.toLocaleDateString("en-US", { weekday:"long" });
  document.getElementById("hero-date").textContent =
    d.toLocaleDateString("en-US", { month:"long", day:"numeric" });
  try {
    const [plans, notes, meetings] = await Promise.all([
      api("/api/plans"), api("/api/notes"), api("/api/meetings")]);
    const doing = plans.filter(p => p.subsection === "in_progress");
    const done = plans.filter(p => p.subsection === "done");
    document.getElementById("hero-greet").textContent =
      `${doing.length} task${doing.length === 1 ? "" : "s"} in progress` +
      (meetings.length ? `, ${meetings.length} upcoming meeting${meetings.length === 1 ? "" : "s"}.` : ".");
    const dp = document.getElementById("digest-plans");
    dp.innerHTML = doing.length
      ? doing.slice(0, 2).map(p => `<div>${escapeHtml(p.title || (p.text||"").slice(0,40))}</div>`).join("") +
        `<div class="dim">In progress</div>`
      : `<div class="dim">Nothing yet — add by voice</div>`;
    document.getElementById("digest-plans-badges").innerHTML =
      `<span class="badge doing">${doing.length} doing</span><span class="badge done">${done.length} done</span>`;
    const dr = document.getElementById("digest-records");
    dr.innerHTML = notes.length
      ? `<div>${escapeHtml(notes[0].title || (notes[0].text||"").slice(0,40))}</div>` +
        `<div class="dim">Records · ${notes.length} total</div>`
      : `<div class="dim">No records yet</div>`;
    const dm = document.getElementById("digest-meetings");
    dm.innerHTML = meetings.length
      ? meetings.slice(0, 3).map(m => `
          <div class="meet-row">
            <div class="time">${m.datetime ? fmtDate(m.datetime).split(", ")[1] || "—" : "—"}</div>
            <div><div class="what">${escapeHtml(m.title || (m.text||"").slice(0,40))}</div>
                 <div class="who">${m.datetime ? escapeHtml(fmtDate(m.datetime)) : ""}</div></div>
          </div>`).join("")
      : `<div class="meet-row"><div class="what" style="color:var(--muted)">No upcoming meetings</div></div>`;
  } catch { /* unauthorized or offline */ }
}

/* --- list sections ------------------------------------------------------ */
function openSection(table){
  current.table = table;
  current.sub = TABLES[table].subs[0] || null;
  const scr = TABLE_SCREEN[table];
  show(scr);
  if (scr === "list"){
    document.getElementById("quick-input").dataset.ph = TABLES[table].ph;
    renderTabs();
  }
  renderList();
}

function renderTabs(){
  const t = TABLES[current.table];
  const tabs = document.getElementById("tabs");
  let html = t.subs.map((s, i) =>
    `<div class="tab ${s === current.sub ? "active" : ""}" data-sub="${s}">${t.subNames[i]}</div>`).join("");
  if (current.table === "meetings")
    html += `<div class="tab" data-sub="__rem">Reminders</div>`;
  tabs.innerHTML = html;
  tabs.querySelectorAll(".tab").forEach(el => el.addEventListener("click", () => {
    if (el.dataset.sub === "__rem") { openSection("reminders"); return; }
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
      <div class="sub">Nothing here yet.<br>Add by voice or with + button.</div></div>`;
    return;
  }
  for (const item of items){
    const div = document.createElement("div");
    div.className = "item" + (item.subsection === "done" ? " done" : "");
    const chip = TABLES[table].chip[item.subsection]
      ? `<span class="chip ${TABLES[table].chip[item.subsection]}">${TABLES[table].subNames[TABLES[table].subs.indexOf(item.subsection)]}</span>`
      : "";
    const when = item.datetime ? fmtDate(item.datetime) :
      (item.created_at ? item.created_at.slice(0, 16).replace("T", " ") : "");
    div.innerHTML = `<div class="top"><div class="txt">${escapeHtml(item.text)}</div>${chip}</div>
      <div class="meta">${escapeHtml(when)}</div>`;
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
  document.getElementById("sheet-overlay").classList.remove("hidden");
  document.getElementById("sheet-text").textContent = item ? item.text : "";
  document.getElementById("sheet-datetime").value = item?.datetime || "";
  const chips = document.getElementById("sheet-chips");
  const label = document.getElementById("sheet-sub-label");
  if (t.subs.length){
    label.style.display = "block";
    chips.innerHTML = t.subs.map((s, i) =>
      `<span class="chip-opt ${item?.subsection === s ? "on" : ""}" data-sub="${s}">${t.subNames[i]}</span>`).join("");
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
  document.getElementById("sheet-text").focus();
}

function closeSheet(){ document.getElementById("sheet-overlay").classList.add("hidden"); editing = null; }

document.getElementById("sheet-save").addEventListener("click", async () => {
  if (!editing) return;
  const { table, item } = editing;
  const text = document.getElementById("sheet-text").textContent.trim();
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
  } catch (e) { tg?.showAlert?.("Save failed: " + e.message); }
});

document.getElementById("sheet-cancel").addEventListener("click", closeSheet);
document.getElementById("sheet-del").addEventListener("click", async () => {
  if (!editing?.item) return;
  try {
    await api(`/api/${editing.table}/${editing.item.id}`, { method: "DELETE" });
    closeSheet(); renderList(); loadDigest();
  } catch (e) { tg?.showAlert?.("Delete failed: " + e.message); }
});
document.getElementById("sheet-overlay").addEventListener("click", e => {
  if (e.target.id === "sheet-overlay") closeSheet();
});

/* --- quick add (inline field) + FAB + mic -------------------------------- */
document.getElementById("quick-input").addEventListener("keydown", async e => {
  if (e.key === "Enter"){
    e.preventDefault();
    const text = e.target.textContent.trim();
    if (!text) return;
    try {
      await api(`/api/${current.table}`, { method: "POST",
        body: JSON.stringify({ text, subsection: current.sub, datetime: null }) });
      e.target.textContent = "";
      renderList();
    } catch (err) { tg?.showAlert?.("Add failed: " + err.message); }
  }
});
document.getElementById("remind-input").addEventListener("keydown", async e => {
  if (e.key === "Enter"){
    e.preventDefault();
    const text = e.target.textContent.trim();
    if (!text) return;
    try {
      await api("/api/reminders", { method: "POST",
        body: JSON.stringify({ text, datetime: new Date(Date.now() + 3600000).toISOString().slice(0,19) }) });
      e.target.textContent = "";
      renderList();
    } catch (err) { tg?.showAlert?.("Add failed: " + err.message); }
  }
});
document.querySelector(".fab").addEventListener("click", () => {
  if (document.querySelector(".screen.active").id === "screen-digest") openSection("plans");
  else openSheet(current.table, null);
});
document.querySelector(".mic").addEventListener("click", () => {
  tg?.HapticFeedback?.notificationOccurred("warning");
  tg?.showAlert?.("Press and hold 🎙 in the chat with the bot to add by voice.\nOr set up the iOS Shortcut in Settings → Voice add via Shortcuts.");
});

/* --- settings ------------------------------------------------------------ */
function langName(l){ return { en:"English", uk:"Українська", ru:"Русский", pl:"Polski", es:"Español" }[l] || l; }
function applyTheme(mode){
  document.body.classList.toggle("light", mode === "light");
  if (tg?.setHeaderColor) tg.setHeaderColor(mode === "light" ? "#f5f5f7" : "#0a0a0c");
}
async function loadSettings(){
  try {
    me = await api("/api/settings");
    document.getElementById("uname").textContent = me.first_name || "User";
    document.getElementById("uhandle").textContent = me.username ? "@" + me.username : "";
    document.getElementById("avatar").textContent = (me.first_name || "U")[0].toUpperCase();
    document.querySelectorAll(".lang").forEach(l => l.classList.toggle("active", l.dataset.l === me.language));
    document.getElementById("lang-val").textContent = langName(me.language) + " ›";
    document.querySelectorAll(".theme-opt").forEach(t => t.classList.toggle("on", t.dataset.t === (me.theme || "dark")));
    applyTheme(me.theme || "dark");
    document.getElementById("admin-block").style.display = me.is_admin ? "block" : "none";
  } catch { /* ignore */ }
}
document.getElementById("row-language").addEventListener("click", () =>
  document.getElementById("lang-pills").classList.toggle("hidden"));
document.querySelectorAll(".lang").forEach(l => l.addEventListener("click", async () => {
  await api("/api/settings", { method: "PUT", body: JSON.stringify({ language: l.dataset.l }) }).catch(()=>{});
  loadSettings();
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
    try {
      const qa = await api("/api/quick-action/token");
      document.getElementById("qa-url").textContent = qa.url;
      block.classList.remove("hidden");
      tog.classList.remove("off");
    } catch { tg?.showAlert?.("Not authorized"); }
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
  } catch { tg?.showAlert?.("Admin access denied"); }
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
    tg?.showAlert?.(`Sent: ${res.sent}, failed: ${res.failed}`);
  } catch (e) { tg?.showAlert?.("Broadcast failed: " + e.message); }
});
document.getElementById("row-admin").addEventListener("click", () => { loadAdmin(); show("admin"); });

/* --- init ------------------------------------------------------------------ */
applyTheme("dark");
loadDigest();
loadSettings();






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
  document.getElementById("back-btn").textContent = name === "digest" ? "Close" : "‹ Back";
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
document.getElementById("back-btn").addEventListener("click", () => show("digest"));
document.getElementById("dots-btn").addEventListener("click", () => show("settings"));
document.querySelectorAll(".card[data-open], .wide-card[data-open]").forEach(el =>
  el.addEventListener("click", () => openSection(el.dataset.open)));
