/* Rafiq front end — vanilla JS, no build step. */
const S = { role: "employee", user: null, lang: "en", personas: null, journey: null, caseFilter: "OPEN", selectedCase: null };

const T = {
  en: {
    tagline: "Employee journey companion", role_employee: "Employee", role_manager: "Manager", role_hrbp: "HR partner",
    role_owner: "Service owner", role_insights: "Insights", viewing_as: "Viewing as",
    banner: "<strong>Prototype.</strong> Synthetic data only. Today is set to {asof}. AI writer: {llm}.",
    your_journey: "Your journey", requests: "Your requests", updates: "Updates", my_data: "My data",
    ask: "Ask Rafiq about your journey, a policy, or something that's stuck…", send: "Send", thinking: "Rafiq is checking your journey…",
    onboarding: "Onboarding", mobility: "Internal move", start: "Offer accepted", join: "Joining day", day30: "Day 30",
    req: "Move requested", eff: "Move effective", today: "Today", none_requests: "No open requests.", none_updates: "Nothing new.",
    sources: "Sources", confirm: "Confirm", cancel: "Cancel", close: "Close",
    share_title: "Hand this to {name}?", share_what: "This is what will be shared:",
    share_items: ["Your journey step status", "Your related service requests", "The policy sections that apply"],
    share_never: "Never shared: your conversations with Rafiq.",
    include_pulse: "Also share my recent check-in feedback (optional)", note: "Add a note in your own words (optional)",
    sent_case: "Handed to {name}. Case {id}.", sent_req: "Sent to {agent}. Request {id}.",
    all_steps: "All steps", status: { DONE: "Done", DONE_LATE: "Done late", AT_RISK: "Late", STALLED: "Stalled", DUE_TODAY: "Due today", UPCOMING: "Upcoming", WAITING: "Waiting" },
    overall: { GREEN: "On track", AMBER: "Needs attention", RED: "Off track" },
    owner: "Owner", due: "Target", open_days: "open {d} days",
  },
  ar: {
    tagline: "رفيق رحلة الموظف", role_employee: "الموظف", role_manager: "المدير", role_hrbp: "شريك الموارد البشرية",
    role_owner: "مالك الخدمة", role_insights: "المؤشرات", viewing_as: "العرض بصفة",
    banner: "<strong>نموذج أولي.</strong> بيانات افتراضية فقط. تاريخ اليوم مضبوط على {asof}. محرّك الصياغة: {llm}.",
    your_journey: "رحلتك", requests: "طلباتك", updates: "التحديثات", my_data: "بياناتي",
    ask: "اسأل رفيق عن رحلتك أو عن سياسة أو عن أمر متأخر…", send: "إرسال", thinking: "رفيق يراجع رحلتك…",
    onboarding: "الالتحاق", mobility: "الانتقال الداخلي", start: "قبول العرض", join: "يوم الالتحاق", day30: "اليوم 30",
    req: "طلب الانتقال", eff: "سريان الانتقال", today: "اليوم", none_requests: "لا توجد طلبات مفتوحة.", none_updates: "لا جديد.",
    sources: "المصادر", confirm: "تأكيد", cancel: "إلغاء", close: "إغلاق",
    share_title: "تحويل الأمر إلى {name}؟", share_what: "هذا ما ستتم مشاركته:",
    share_items: ["حالة خطوات رحلتك", "طلبات الخدمة المرتبطة", "أقسام السياسات المعنية"],
    share_never: "لا تتم مشاركة محادثاتك مع رفيق أبداً.",
    include_pulse: "مشاركة ملاحظاتي الأخيرة في الاستطلاع أيضاً (اختياري)", note: "أضف ملاحظة بكلماتك (اختياري)",
    sent_case: "تم التحويل إلى {name}. رقم الحالة {id}.", sent_req: "تم الإرسال إلى {agent}. رقم الطلب {id}.",
    all_steps: "كل الخطوات", status: { DONE: "مكتمل", DONE_LATE: "اكتمل متأخراً", AT_RISK: "متأخر", STALLED: "متوقف", DUE_TODAY: "مستحق اليوم", UPCOMING: "قادم", WAITING: "بانتظار" },
    overall: { GREEN: "يسير وفق الخطة", AMBER: "يحتاج متابعة", RED: "متأخر" },
    owner: "المسؤول", due: "الموعد", open_days: "مفتوح منذ {d} أيام",
  },
};
const t = (k, vars = {}) => { let s = (T[S.lang][k] ?? T.en[k] ?? k); if (typeof s === "string") for (const [a, b] of Object.entries(vars)) s = s.replaceAll(`{${a}}`, b); return s; };


/* ------------------------------------------------------------------ helpers */
const $ = (sel, el = document) => el.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
function headers() { return { "Content-Type": "application/json", "X-Rafiq-Request": "1" }; }
async function api(path, opts = {}) {
  const r = await fetch(path, { credentials: "same-origin", headers: headers(), ...opts });
  if (r.status === 401 && !path.startsWith("/api/login")) { S.me = null; showLogin(); throw new Error("Please sign in."); }
  if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || `Request failed (${r.status})`); }
  return r.json();
}
function toast(msg) { const el = $("#toast"); el.textContent = msg; el.classList.remove("hidden"); clearTimeout(toast._t); toast._t = setTimeout(() => el.classList.add("hidden"), 4200); }
function fmtDate(iso) { if (!iso) return ""; const d = new Date(iso.slice(0, 10) + "T12:00:00"); return d.toLocaleDateString(S.lang === "ar" ? "ar-AE" : "en-GB", { day: "numeric", month: "short" }); }
function md(text) {
  return text.split(/\n\n+/).map((para) => {
    let h = esc(para)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|\s)_(.+?)_(?=\s|$|[.,])/g, "$1<em>$2</em>")
      .replace(/\[(POL-[A-Z]{2,4}-\d{3} §[\d.]+)\]/g, (m, c) => `<button class="cite" data-cite="${c}">${c}</button>`)
      .replace(/\(نص السياسة بالإنجليزية\)/g, '<span class="muted small">(نص السياسة بالإنجليزية)</span>');
    const isPol = /^• /.test(para);
    if (isPol) h = h.replace(/^• /, "").replace(/^(.*?)(\s*<button class="cite")/, '<bdi dir="auto">$1</bdi>$2');
    return `<p class="${isPol ? "pol" : ""}">${h.replace(/\n/g, "<br>")}</p>`;
  }).join("");
}
function setLang(lang, user = false) {
  if (user) S.langChosen = true;
  S.lang = lang; document.documentElement.lang = lang; document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  $("#langBtn").textContent = lang === "ar" ? "English" : "العربية";
  document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
}

/* ------------------------------------------------------------------ boot */
async function boot() {
  S.health = await fetch("/api/health").then((r) => r.json());
  const params = new URLSearchParams(location.search);
  setLang(params.get("lang") === "ar" ? "ar" : "en");
  $("#langBtn").addEventListener("click", () => { setLang(S.lang === "en" ? "ar" : "en", true); renderBanner(); S.me ? (renderChrome(), render()) : showLogin(); });
  $("#logoutBtn").addEventListener("click", async () => { await api("/api/logout", { method: "POST" }).catch(() => {}); S.me = null; showLogin(); });
  document.addEventListener("click", (e) => { const c = e.target.closest(".cite"); if (c) showCite(c.dataset.cite); });
  renderBanner();
  const me = await fetch("/api/me", { credentials: "same-origin" });
  if (me.ok) { signedIn(await me.json()); } else { showLogin(); }
}
function renderBanner() {
  const l = S.health.llm; const ar = S.lang === "ar";
  const llm = l.provider === "offline" ? (ar ? "وضع حتمي بدون اتصال" : "offline deterministic mode") : `${l.provider} ${l.model}${l.configured ? "" : " (no key, using offline)"}`;
  $("#banner").innerHTML = `<span>${t("banner", { asof: S.health.as_of, llm: esc(llm) })}</span>`;
}
const ROLE_LABEL = { employee: ["Employee", "موظف"], manager: ["Manager", "مدير"], hrbp: ["HR partner", "شريك الموارد البشرية"], owner: ["Service owner", "مالك الخدمة"], admin: ["Admin", "المسؤول"] };
const NAV = {
  employee: [["journey", "My journey", "رحلتي"]],
  manager: [["team", "My team", "فريقي"]],
  hrbp: [["cases", "Cases", "الحالات"], ["insights", "Insights", "المؤشرات"]],
  owner: [["cases", "My cases", "حالاتي"], ["insights", "Insights", "المؤشرات"]],
  admin: [["admin", "Demo admin", "إدارة العرض"], ["insights", "Insights", "المؤشرات"]],
};
function signedIn(d) {
  S.me = d.user; S.suggestions = d.suggestions || []; S.page = d.home; S.user = d.user.id; S.role = d.user.role; S.selectedCase = null;
  if (S.role === "employee" && d.user.lang === "ar" && !S.langChosen) setLang("ar");
  renderChrome(); render();
}
function renderChrome() {
  const ar = S.lang === "ar"; const u = S.me;
  const nav = $("#nav"); nav.classList.remove("hidden");
  nav.innerHTML = NAV[u.role].map(([k, en, a]) => `<button data-page="${k}" aria-pressed="${S.page === k}">${ar ? a : en}</button>`).join("");
  nav.querySelectorAll("button").forEach((b) => b.onclick = () => { S.page = b.dataset.page; S.selectedCase = null; renderChrome(); render(); });
  $("#who").classList.remove("hidden");
  $("#who").innerHTML = `<span class="who-name">${esc(u.name)}</span><span class="who-role">${(ROLE_LABEL[u.role] || [u.role])[ar ? 1 : 0]}${u.title ? ` · ${esc(u.title)}` : ""}</span>`;
  $("#logoutBtn").classList.remove("hidden"); $("#logoutBtn").textContent = ar ? "تسجيل الخروج" : "Sign out";
}
function render() {
  const v = $("#view"); v.innerHTML = '<p class="empty">…</p>';
  const fn = { journey: renderEmployee, team: renderManager, cases: renderInbox, insights: renderInsights, admin: renderAdmin }[S.page];
  fn().catch((e) => { if (S.me) v.innerHTML = `<p class="empty">${esc(e.message)}</p>`; });
}

/* ------------------------------------------------------------------ sign-in */
async function showLogin() {
  const ar = S.lang === "ar"; const L = (en, a) => (ar ? a : en);
  $("#nav").classList.add("hidden"); $("#who").classList.add("hidden"); $("#logoutBtn").classList.add("hidden");
  if ($("#dlg").open) $("#dlg").close();
  $("#view").innerHTML = `
  <div class="login">
    <section class="login-card panel" aria-labelledby="signinTitle">
      <h1 id="signinTitle">${L("Sign in", "تسجيل الدخول")}</h1>
      <p class="login-sub">${L("Your onboarding and move, in one place.", "رحلة انضمامك وانتقالك في مكان واحد.")}</p>
      <form id="loginForm" autocomplete="on">
        <label for="lu">${L("Username", "اسم المستخدم")}</label>
        <input id="lu" name="username" autocomplete="username" autocapitalize="none" spellcheck="false" required>
        <label for="lp">${L("Password", "كلمة المرور")}</label>
        <input id="lp" name="password" type="password" autocomplete="current-password" required>
        <p class="login-err hidden" id="lerr" role="alert"></p>
        <button class="btn primary" type="submit">${L("Sign in", "تسجيل الدخول")}</button>
      </form>
      <button class="linkbtn demo-link" id="demoBtn" type="button" aria-haspopup="dialog">${L("Demo accounts", "حسابات العرض")}</button>
    </section>
    <p class="login-foot small muted">${L("Prototype with synthetic people and data only.", "نموذج أولي بأشخاص وبيانات افتراضية فقط.")}</p>
  </div>`;
  $("#demoBtn").onclick = openDemoAccounts;
  $("#loginForm").onsubmit = async (ev) => {
    ev.preventDefault(); const err = $("#lerr"); err.classList.add("hidden");
    const btn = ev.target.querySelector("button[type=submit]"); btn.disabled = true;
    try {
      const r = await fetch("/api/login", { method: "POST", credentials: "same-origin", headers: headers(), body: JSON.stringify({ username: $("#lu").value, password: $("#lp").value }) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.detail || L("Sign-in failed.", "تعذر تسجيل الدخول."));
      $("#lp").value = ""; signedIn(j);
    } catch (e) { err.textContent = e.message; err.classList.remove("hidden"); btn.disabled = false; $("#lp").select(); }
  };
  $("#lu").focus();
}

async function openDemoAccounts() {
  const ar = S.lang === "ar"; const L = (en, a) => (ar ? a : en);
  let d = S.demo;
  if (!d) { try { d = S.demo = await fetch("/api/demo-accounts").then((r) => r.json()); } catch { toast(L("Couldn't load the demo accounts.", "تعذر تحميل حسابات العرض.")); return; } }
  const groups = [
    [L("Employees", "الموظفون"), d.employees], [L("Managers", "المديرون"), d.managers],
    [L("HR partners", "شركاء الموارد البشرية"), d.hrbps], [L("Service owners", "مالكو الخدمات"), d.owners],
  ];
  const pw = d.password_mode === "per_user" ? L("Each account has its own password, listed in the credentials sheet you were given.", "لكل حساب كلمة مرور خاصة مذكورة في ورقة بيانات الدخول.")
    : L("All demo accounts use the password provided with the submission.", "تستخدم جميع حسابات العرض كلمة المرور المرفقة مع المشاركة.");
  $("#dlgInner").innerHTML = `
    <div class="dlg-h"><div><h2>${L("Demo accounts", "حسابات العرض")}</h2>
      <p class="small muted">${pw} ${L(`Every person has an account (${d.counts.employee} employees, ${d.counts.manager} managers, ${d.counts.hrbp} HR partners, ${d.counts.owner} service owners); these are the ones used in the test scenarios. Choose one to fill in the username.`, "اختر حساباً لتعبئة اسم المستخدم.")}</p></div></div>
    <div class="dlg-b">
      <input id="acctFilter" class="acct-filter" type="search" placeholder="${L("Filter by name", "تصفية بالاسم")}" aria-label="${L("Filter by name", "تصفية بالاسم")}">
      ${groups.map(([title, items]) => `<section class="acct-group"><h3>${title}</h3><div class="acct-list">${items.map((a) =>
        `<button class="acct" data-u="${esc(a.username)}" data-n="${esc((a.name + " " + a.username + " " + (a.title || "")).toLowerCase())}"><strong>${esc(a.name)}</strong>${a.title ? `<span>${esc(a.title)}</span>` : ""}<code>${esc(a.username)}</code></button>`).join("")}</div></section>`).join("")}
    </div>
    <div class="dlg-f"><button class="btn" id="acctClose">${t("close")}</button></div>`;
  const dlg = $("#dlg"); dlg.className = "wide"; dlg.showModal();
  $("#acctClose").onclick = () => dlg.close();
  $("#acctFilter").oninput = (e) => { const q = e.target.value.trim().toLowerCase(); document.querySelectorAll("#dlgInner .acct").forEach((b) => { b.hidden = q && !b.dataset.n.includes(q); }); };
  document.querySelectorAll("#dlgInner .acct").forEach((b) => b.onclick = () => { dlg.close(); $("#lu").value = b.dataset.u; $("#lp").focus(); });
  $("#acctFilter").focus();
}

/* ------------------------------------------------------------------ admin */
async function renderAdmin() {
  const ar = S.lang === "ar"; const L = (en, a) => (ar ? a : en);
  const d = S.demo || (S.demo = await fetch("/api/demo-accounts").then((r) => r.json()));
  $("#view").innerHTML = `<section class="panel"><div class="panel-h"><h2>${L("Demo administration", "إدارة العرض")}</h2></div><div class="panel-b">
    <p>${L(`Accounts: ${d.counts.employee} employees, ${d.counts.manager} managers, ${d.counts.hrbp} HR partners, ${d.counts.owner} service owners. Password mode: ${d.password_mode}.`, "الحسابات وأسلوب كلمات المرور.")}</p>
    <div class="acts"><button class="btn primary" id="resetBtn">${L("Reset demo to its starting state", "إعادة ضبط العرض")}</button>
    ${d.password_mode === "per_user" ? `<a class="btn" href="/api/admin/credentials">${L("Download credentials sheet", "تنزيل ورقة بيانات الدخول")}</a>` : ""}</div>
    <p class="small muted" style="margin-top:10px">${L("Reset clears requests, cases, consent changes and conversations created during the demo. Everyone using the link sees the same demo data.", "تمسح إعادة الضبط الطلبات والحالات وتغييرات الموافقة والمحادثات التي أُنشئت أثناء العرض.")}</p></div></section>`;
  $("#resetBtn").onclick = async () => {
    if (!confirm(L("Clear everything created during this demo?", "مسح كل ما أُنشئ أثناء العرض؟"))) return;
    await api("/api/admin/reset", { method: "POST" }); toast(L("Demo reset to its starting state.", "تمت إعادة ضبط العرض."));
  };
}

async function renderEmployee() {
  const id = S.user;
  const [j, brief, notes] = await Promise.all([api(`/api/employee/${id}/journey`), api(`/api/employee/${id}/brief?lang=${S.lang}`), api(`/api/employee/${id}/notifications`)]);
  S.journey = j;
  const e = j.employee; const ar = S.lang === "ar";
  const where = j.journey_type === "ONBOARDING"
    ? `${esc(e.role_title)}, ${esc(e.department)} · ${esc(e.location)}`
    : `${e.from_role_title === e.role_title ? esc(e.role_title) : `${esc(e.from_role_title)} → ${esc(e.role_title)}`} · ${e.from_location === e.location ? esc(e.location) : `${esc(e.from_location)} → ${esc(e.location)}`}`;
  const openReq = j.requests.filter((q) => !["RESOLVED", "CLOSED"].includes(q.status));
  const prompts = S.suggestions || [];
  const generic = ar ? ["ما هي خطواتي التالية؟", "من يمكنه رؤية بياناتي؟"] : ["What's next for me?", "Who can see my data?"];
  $("#view").innerHTML = `
  <section class="route" aria-label="${t("your_journey")}">
    <div class="route-head">
      <div><h1>${esc(e.first_name)} ${esc(e.last_name)}</h1><p class="where">${where}</p></div>
      <div style="text-align:end"><span class="state-pill st-${j.overall}">${t("overall")[j.overall]}</span>
        <p class="small muted" style="margin-top:4px">${j.journey_type === "ONBOARDING" ? t("onboarding") : t("mobility")} · ${esc(ar ? j.stage_label_ar : j.stage_label)} · ${j.progress.done}/${j.progress.total}</p></div>
    </div>
    ${ribbon(j)}
  </section>
  <div class="emp-grid">
    <section class="panel chat" aria-label="Chat">
      <div class="panel-h"><h2>Rafiq</h2><span class="small muted">${S.health.llm.provider === "offline" ? "" : esc(S.health.llm.provider)}</span></div>
      <div class="msgs" id="msgs" aria-live="polite"></div>
      <div class="suggest" id="suggest">${[...prompts, ...generic].map((p) => `<button>${esc(p)}</button>`).join("")}</div>
      <div class="typing hidden" id="typing">${t("thinking")}</div>
      <form class="composer" id="composer"><textarea id="input" rows="1" placeholder="${t("ask")}" aria-label="${t("ask")}"></textarea><button class="btn primary" type="submit">${t("send")}</button></form>
    </section>
    <div class="side-stack">
      <section class="panel"><div class="panel-h"><h2>${t("your_journey")}</h2><button class="linkbtn" id="mydataBtn">${t("my_data")}</button></div>
        <div class="panel-b"><ul class="steps">${j.steps.map(stepRow).join("")}</ul></div></section>
      <section class="panel"><div class="panel-h"><h2>${t("requests")}</h2></div><div class="panel-b">
        ${openReq.length ? `<ul class="list">${openReq.map((q) => `<li><div><strong>${esc(q.subject)}</strong></div><div class="small muted">${esc(q.request_id)} · ${esc(q.owner_name)}, ${esc(q.owner_team)} · ${t("open_days", { d: q.days_open })}${q.sla_state !== "OK" ? ` · <span style="color:var(--red)">${ar ? "تجاوز مستوى الخدمة" : "over service level"}</span>` : ""}</div></li>`).join("")}</ul>` : `<p class="muted small">${t("none_requests")}</p>`}
      </div></section>
      <section class="panel"><div class="panel-h"><h2>${t("updates")}</h2></div><div class="panel-b">
        ${notes.length ? `<ul class="list">${notes.slice(0, 6).map((n) => `<li class="small">${esc(ar ? n.text_ar : n.text)}</li>`).join("")}</ul>` : `<p class="muted small">${t("none_updates")}</p>`}
      </div></section>
    </div>
  </div>`;
  addBot(brief, false);
  $("#composer").addEventListener("submit", (ev) => { ev.preventDefault(); send(); });
  $("#input").addEventListener("keydown", (ev) => { if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); send(); } });
  $("#suggest").addEventListener("click", (ev) => { const b = ev.target.closest("button"); if (b) { $("#input").value = b.textContent; send(); } });
  $("#mydataBtn").addEventListener("click", openMyData);
  document.querySelectorAll(".wp").forEach((w) => w.addEventListener("click", () => { $("#input").value = (ar ? "ما وضع " : "What's the status of ") + w.dataset.label + "?"; $("#input").focus(); }));
}

function ribbon(j) {
  const ar = S.lang === "ar";
  const lo = j.journey_type === "ONBOARDING" ? -45 : 0;
  const hi = j.journey_type === "ONBOARDING" ? 30 : 60;
  const pos = (d) => Math.max(0, Math.min(100, ((d - lo) / (hi - lo)) * 100));
  const side = ar ? "right" : "left";
  const today = pos(j.journey_day);
  const wps = j.steps.map((s) => `<button class="wp ${s.status}" style="${side}:${pos(s.target_day)}%" data-label="${esc(ar ? s.label_ar : s.label)}" aria-label="${esc(ar ? s.label_ar : s.label)}: ${t("status")[s.status]}"><span class="tip">${esc(ar ? s.label_ar : s.label)} · ${t("status")[s.status]}</span></button>`).join("");
  const plane = `<svg class="plane" style="${side}:${today}%" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M21.5 13.4v-1.8L13.6 7V2.6a1.6 1.6 0 0 0-3.2 0V7L2.5 11.6v1.8l7.9-2.4v4.6l-2.2 1.6v1.4l3.8-1.1 3.8 1.1v-1.4l-2.2-1.6V11z" transform="rotate(90 12 12)"/></svg>`;
  const labels = j.journey_type === "ONBOARDING" ? [t("start"), t("join"), t("day30")] : [t("req"), t("eff"), "+30"];
  const mid = j.journey_type === "ONBOARDING" ? pos(0) : pos(30);
  return `<div class="ribbon" role="img" aria-label="${t("your_journey")}: ${j.progress.done}/${j.progress.total}">
    <div class="track"></div><div class="flown" style="width:${today}%"></div>
    <div class="today" style="${side}:${today}%">${t("today")}</div>
    ${wps}${plane}
    <div class="ends"><span>${labels[0]}</span><span style="position:absolute;${side}:${mid}%;transform:translateX(${ar ? "50%" : "-50%"})">${labels[1]}</span><span>${labels[2]}</span></div>
  </div>`;
}

function stepRow(s) {
  const ar = S.lang === "ar";
  const sub = s.completed_at ? fmtDate(s.completed_at) : `${t("due")} ${fmtDate(s.target_date)} · ${esc(s.owner_team)}`;
  return `<li class="${s.status}"><span class="dot"></span><div><div class="s-label">${esc(ar ? s.label_ar : s.label)}</div><div class="s-sub">${sub}</div></div><span class="tag ${s.status}">${t("status")[s.status]}${["STALLED", "AT_RISK"].includes(s.status) ? ` +${s.days_late}d` : ""}</span></li>`;
}

function addMe(text) { const d = document.createElement("div"); d.className = "msg me"; d.textContent = text; $("#msgs").appendChild(d); scrollMsgs(); }
function scrollMsgs() { const m = $("#msgs"); m.scrollTop = m.scrollHeight; }
function addBot(r, scroll = true) {
  const d = document.createElement("div"); d.className = "msg bot";
  const extra = r.citations.filter((c) => !r.reply.includes(c.cite));
  d.innerHTML = `<div class="body" dir="${r.lang === "ar" ? "rtl" : "ltr"}">${md(r.reply)}</div>
    ${r.actions.length ? `<div class="acts">${r.actions.map((a, i) => `<button class="btn ${a.primary ? "primary" : ""}" data-i="${i}">${esc(a.label)}</button>`).join("")}</div>` : ""}
    ${extra.length ? `<div class="meta">${t("sources")}: ${extra.map((c) => `<button class="cite" data-cite="${c.cite}">${c.cite}</button>`).join("")}</div>` : ""}
    ${r.mode && r.mode !== "offline" && r.intent !== "BRIEF" ? `<div class="meta">${r.mode === "offline_fallback" ? (S.lang === "ar" ? "إجابة قياسية من الحقائق المؤكدة" : "Standard answer from verified facts") : (S.lang === "ar" ? "صاغها الذكاء الاصطناعي من الحقائق والمصادر المؤكدة فقط" : "Worded by AI from verified facts and the sources shown only")}</div>` : ""}`;
  d.querySelectorAll(".acts .btn").forEach((b) => b.addEventListener("click", () => doAction(r.actions[+b.dataset.i], b)));
  $("#msgs").appendChild(d); if (scroll) scrollMsgs();
}
async function send() {
  const inp = $("#input"); const text = inp.value.trim(); if (!text) return;
  inp.value = ""; addMe(text); $("#typing").classList.remove("hidden");
  try { addBot(await api(`/api/employee/${S.user}/chat`, { method: "POST", body: JSON.stringify({ message: text, lang: S.lang }) })); }
  catch (e) { addBot({ reply: e.message, citations: [], actions: [], lang: S.lang }); }
  finally { $("#typing").classList.add("hidden"); }
}

async function doAction(a, btn) {
  if (a.type === "OPEN_MY_DATA") return openMyData();
  if (a.type === "ESCALATE") return confirmEscalation(a, btn);
  btn.disabled = true;
  try {
    const r = await api(`/api/employee/${S.user}/actions`, { method: "POST", body: JSON.stringify({ action: a }) });
    const ar = S.lang === "ar";
    const req = r.request;
    addBot({ reply: `**${esc(r.agent)}** — ${ar ? r.agent_reply_ar : r.agent_reply}\n\n${t("sent_req", { agent: r.agent, id: req.request_id })}`, citations: [], actions: [], lang: S.lang });
    btn.textContent = "✓ " + btn.textContent; refreshSide();
  } catch (e) { toast(e.message); btn.disabled = false; }
}

function confirmEscalation(a, btn) {
  const consent = S.journey.consent_active && a.can_include_pulse;
  const ar = S.lang === "ar";
  $("#dlgInner").innerHTML = `
    <div class="dlg-h"><h2>${t("share_title", { name: esc(a.owner.name) })}</h2></div>
    <div class="dlg-b">
      <p class="muted">${esc(a.owner.role)}${S.journey.employee.hrbp_name && a.owner.role !== "HR Business Partner" ? ` · ${ar ? "مع إشعار" : "cc"} ${esc(S.journey.employee.hrbp_name)}` : ""}</p>
      <div class="share-box"><strong>${t("share_what")}</strong><ul>${t("share_items").map((x) => `<li>${x}</li>`).join("")}</ul>
        <p class="small muted" style="margin-top:8px">${t("share_never")}</p></div>
      ${consent ? `<label class="check"><input type="checkbox" id="incPulse"> <span>${t("include_pulse")}</span></label>` : ""}
      <label class="small" for="note" style="display:block;margin-top:12px">${t("note")}</label>
      <textarea id="note" maxlength="400"></textarea>
    </div>
    <div class="dlg-f"><button class="btn" id="cx">${t("cancel")}</button><button class="btn primary" id="ok">${t("confirm")}</button></div>`;
  const dlg = $("#dlg"); dlg.className = ""; dlg.showModal();
  $("#cx").onclick = () => dlg.close();
  $("#ok").onclick = async () => {
    $("#ok").disabled = true;
    try {
      const r = await api(`/api/employee/${S.user}/actions`, { method: "POST", body: JSON.stringify({ action: a, include_pulse: !!($("#incPulse") && $("#incPulse").checked), note: $("#note").value }) });
      dlg.close(); btn.disabled = true; btn.textContent = "✓ " + btn.textContent;
      const c = r.case;
      addBot({ reply: (ar ? `تم التحويل إلى **${c.owner.name}** (${c.owner.role}). رقم الحالة **${c.case_id}**. ستتلقى تحديثاً بحلول ${c.next_update_due}. تمت مشاركة: ${c.shared_items.join("، ")}.`
        : `Handed to **${c.owner.name}** (${c.owner.role}). Case **${c.case_id}**. You'll hear back by ${fmtDate(c.next_update_due)}. Shared: ${c.shared_items.join(", ")}.`), citations: [], actions: [], lang: S.lang });
      refreshSide();
    } catch (e) { toast(e.message); $("#ok").disabled = false; }
  };
}
async function refreshSide() {
  // keep chat, refresh journey + requests + updates panels by re-rendering side stack only
  const id = S.user;
  const [j, notes] = await Promise.all([api(`/api/employee/${id}/journey`), api(`/api/employee/${id}/notifications`)]);
  S.journey = j; const ar = S.lang === "ar";
  const panels = document.querySelectorAll(".side-stack .panel .panel-b");
  const openReq = j.requests.filter((q) => !["RESOLVED", "CLOSED"].includes(q.status));
  panels[1].innerHTML = openReq.length ? `<ul class="list">${openReq.map((q) => `<li><div><strong>${esc(q.subject)}</strong></div><div class="small muted">${esc(q.request_id)} · ${esc(q.owner_name)}, ${esc(q.owner_team)} · ${t("open_days", { d: q.days_open })}${q.priority === "HIGH" ? " · HIGH" : ""}</div></li>`).join("")}</ul>` : `<p class="muted small">${t("none_requests")}</p>`;
  panels[2].innerHTML = notes.length ? `<ul class="list">${notes.slice(0, 6).map((n) => `<li class="small">${esc(ar ? n.text_ar : n.text)}</li>`).join("")}</ul>` : `<p class="muted small">${t("none_updates")}</p>`;
}

async function showCite(cite) {
  const pid = cite.split(" §")[0];
  const sec = (window._citeCache ||= {})[pid];
  $("#dlgInner").innerHTML = `<div class="dlg-h"><h2>${esc(cite)}</h2></div><div class="dlg-b" id="citeBody"><p class="muted">…</p></div><div class="dlg-f"><button class="btn" onclick="document.getElementById('dlg').close()">${t("close")}</button></div>`;
  const dlg = $("#dlg"); dlg.className = ""; dlg.showModal();
  const data = sec || await fetch(`/api/policies/${encodeURIComponent(pid)}`).then((x) => x.json());
  window._citeCache[pid] = data;
  const no = cite.split("§")[1];
  $("#citeBody").innerHTML = `<p class="muted small">${esc(data.title)} · v${esc(data.version)} · ${esc(data.owner)}</p>` +
    data.sections.map((s) => `<p style="margin-top:8px;${s.cite === cite ? "background:var(--amber-bg);padding:6px 8px;border-radius:6px" : ""}"><strong>§${esc(s.cite.split("§")[1])}</strong> ${esc(s.text)}</p>`).join("");
  const hit = [...$("#citeBody").querySelectorAll("p")].find((p) => p.textContent.startsWith("§" + no + " "));
  hit?.scrollIntoView({ block: "center" });
}

async function openMyData() {
  const d = await api(`/api/employee/${S.user}/mydata`); const ar = S.lang === "ar";
  const L = (en, a) => (ar ? a : en);
  $("#dlgInner").innerHTML = `
  <div class="dlg-h"><div><h2>${t("my_data")}</h2><p class="small muted">${L("Everything Rafiq holds about you, and who it has been shared with.", "كل ما يحتفظ به رفيق عنك، ومع من تمت مشاركته.")} [POL-PRV-001 §4.1]</p></div></div>
  <div class="dlg-b">
    <div class="md-sec"><h3>${L("Check-in feedback consent", "الموافقة على ملاحظات الاستطلاع")}</h3>
      <div class="switch"><span class="state-pill ${d.consent.pulse_active ? "st-GREEN" : "st-AMBER"}">${d.consent.pulse_active ? L("Opted in", "موافق") : L("Not opted in", "غير موافق")}</span>
      <button class="btn" id="consentBtn">${d.consent.pulse_active ? L("Withdraw consent", "سحب الموافقة") : L("Opt in", "الموافقة")}</button></div>
      <p class="small muted" style="margin-top:6px">${L("If you withdraw, your responses stop being used immediately and are deleted within 30 days. It has no effect on the help you get.", "عند السحب يتوقف استخدام ردودك فوراً وتُحذف خلال 30 يوماً، دون أي أثر على الخدمة التي تتلقاها.")}</p></div>
    <div class="md-sec"><h3>${L("Your check-in responses", "ردودك في الاستطلاع")}</h3>
      ${d.pulse.length ? `<table><tr><th>${L("Date", "التاريخ")}</th><th>${L("Score", "التقييم")}</th><th>${L("Comment", "التعليق")}</th><th>${L("Used by Rafiq", "يستخدمه رفيق")}</th></tr>${d.pulse.map((p) => `<tr><td>${fmtDate(p.submitted_at)}</td><td>${p.score}/5</td><td>${esc(p.comment)}</td><td>${p.used_by_companion ? L("Yes", "نعم") : `${L("No, withdrawn", "لا، مسحوبة")}${p.deletion_due ? ` · ${L("deleted by", "تُحذف قبل")} ${fmtDate(p.deletion_due)}` : ""}`}</td></tr>`).join("")}</table>` : `<p class="muted small">${L("None.", "لا يوجد.")}</p>`}</div>
    <div class="md-sec"><h3>${L("Signals Rafiq has flagged about you", "التنبيهات المسجلة عنك")}</h3>
      ${d.signals_about_me.length ? d.signals_about_me.map((s) => `<div class="sig ${s.level}">${esc(ar ? s.message_ar : s.message)}${s.sensitive ? ` <span class="small muted">(${L("only you see this", "تراه أنت فقط")})</span>` : ""}</div>`).join("") : `<p class="muted small">${L("None — you're on track.", "لا يوجد — رحلتك تسير وفق الخطة.")}</p>`}</div>
    <div class="md-sec"><h3>${L("Shared with others", "ما تمت مشاركته مع الآخرين")}</h3>
      ${d.shared_with_others.length ? `<table><tr><th>${L("Case", "الحالة")}</th><th>${L("With", "مع")}</th><th>${L("What was shared", "ما تمت مشاركته")}</th></tr>${d.shared_with_others.map((c) => `<tr><td>${esc(c.case_id)}<br><span class="small muted">${esc(c.type.replace("_", " ").toLowerCase())}</span></td><td>${esc(c.owner.name)} (${esc(c.owner.role)})<br><span class="small muted">cc ${esc(c.hrbp)}</span></td><td>${c.shared_items.map(esc).join(", ")}</td></tr>`).join("")}</table>` : `<p class="muted small">${L("Nothing has been shared.", "لم تتم مشاركة أي شيء.")}</p>`}
      <p class="small muted" style="margin-top:6px">${L("Your manager sees journey step progress only.", "يرى مديرك تقدم خطوات الرحلة فقط.")} [POL-PRV-001 §5.1]</p></div>
    <div class="md-sec"><h3>${L("Your profile", "ملفك")}</h3><dl class="kv">${Object.entries(d.profile).filter(([, v]) => v).map(([k, v]) => `<dt>${esc(k.replaceAll("_", " "))}</dt><dd>${esc(v)}</dd>`).join("")}</dl></div>
    <div class="md-sec"><h3>${L("Conversation history", "سجل المحادثات")}</h3><p class="small">${d.conversation_messages} ${L("messages stored.", "رسالة محفوظة.")} ${esc(d.retention)}</p>
      <button class="btn danger" id="forgetBtn" style="margin-top:6px">${L("Delete my conversation history", "حذف سجل محادثاتي")}</button></div>
    <div class="md-sec"><h3>${L("Access log", "سجل الوصول")}</h3>${d.access_log.length ? `<table>${d.access_log.map((a) => `<tr><td class="small">${esc(a.at.slice(0, 16).replace("T", " "))}</td><td class="small">${esc(a.actor)}</td><td class="small">${esc(a.detail)}</td></tr>`).join("")}</table>` : `<p class="muted small">—</p>`}</div>
  </div>
  <div class="dlg-f"><button class="btn" onclick="document.getElementById('dlg').close()">${t("close")}</button></div>`;
  const dlg = $("#dlg"); dlg.className = "wide"; if (!dlg.open) dlg.showModal();
  $("#dlgInner").innerHTML = $("#dlgInner").innerHTML.replace(/\[(POL-[A-Z]{2,4}-\d{3} §[\d.]+)\]/g, (m, c) => `<button class="cite" data-cite="${c}">${c}</button>`);
  $("#consentBtn").onclick = async () => { await api(`/api/employee/${S.user}/consent`, { method: "POST", body: JSON.stringify({ active: !d.consent.pulse_active }) }); toast(d.consent.pulse_active ? L("Consent withdrawn.", "تم سحب الموافقة.") : L("Thanks — you've opted in.", "شكراً — تمت الموافقة.")); openMyData(); };
  $("#forgetBtn").onclick = async () => { await api(`/api/employee/${S.user}/conversations`, { method: "DELETE" }); toast(L("Conversation history deleted.", "تم حذف سجل المحادثات.")); openMyData(); };
}

/* ------------------------------------------------------------------ manager */
async function renderManager() {
  const d = await api(`/api/manager/${S.user}/team`); const ar = S.lang === "ar";
  const L = (en, a) => (ar ? a : en);
  $("#view").innerHTML = `
    <section class="panel"><div class="panel-h"><div><h2>${L("Your team's journeys", "رحلات فريقك")}</h2>
      <p class="small muted">${L("You see step progress only — never conversations, check-in feedback or sentiment.", "ترى تقدم الخطوات فقط — وليس المحادثات أو ملاحظات الاستطلاع أو المشاعر.")} <button class="cite" data-cite="POL-PRV-001 §5.1">POL-PRV-001 §5.1</button></p></div></div>
    <div class="panel-b" style="overflow-x:auto"><table>
      <tr><th>${L("Person", "الموظف")}</th><th>${L("Journey", "الرحلة")}</th><th>${L("Steps", "الخطوات")}</th><th>${L("Overdue steps", "خطوات متأخرة")}</th></tr>
      ${d.team.map((m) => `<tr><td><strong>${esc(m.name)}</strong><br><span class="small muted">${esc(m.role_title)}</span></td>
        <td>${m.journey_type === "ONBOARDING" ? t("onboarding") : t("mobility")}<br><span class="small muted">${esc(m.stage_label)}, ${L("day", "اليوم")} ${m.journey_day}</span></td>
        <td><div class="dots">${m.steps.map((s) => `<i class="${s.status}" title="${esc(s.label)}: ${t("status")[s.status]}"></i>`).join("")}</div><span class="small muted">${m.progress.done}/${m.progress.total}</span></td>
        <td class="small">${m.overdue_steps.length ? m.overdue_steps.map(esc).join("<br>") : "—"}</td></tr>`).join("")}
    </table>
    <div class="guard">${L("Want to know how someone is feeling? Ask them. Rafiq is the employee's companion, not a monitoring tool.", "تريد معرفة شعور أحد أعضاء فريقك؟ اسأله مباشرة. رفيق مساعد للموظف وليس أداة مراقبة.")} <button class="cite" data-cite="POL-PRV-001 §1.2">POL-PRV-001 §1.2</button></div></div></section>`;
}

/* ------------------------------------------------------------------ HRBP / owner inbox */
async function renderInbox() {
  const cases = await api("/api/cases"); const ar = S.lang === "ar"; const L = (en, a) => (ar ? a : en);
  const filtered = cases.filter((c) => S.caseFilter === "ALL" || c.status === S.caseFilter);
  if (!S.selectedCase || !filtered.some((c) => c.case_id === S.selectedCase)) S.selectedCase = filtered[0]?.case_id;
  const kinds = { EARLY_WARNING: L("Early warning", "إنذار مبكر"), EMPLOYEE_HANDOFF: L("Employee handoff", "تحويل من الموظف"), POLICY_QUESTION: L("Policy question", "سؤال سياسة") };
  const sel = cases.find((c) => c.case_id === S.selectedCase);
  $("#view").innerHTML = `
  <div class="inbox">
    <section class="panel"><div class="panel-h"><h2>${S.role === "hrbp" ? L("Cases for your employees", "حالات موظفيك") : L("Cases assigned to you", "الحالات المسندة إليك")}</h2><span class="small muted">${filtered.length}</span></div>
      <div class="filters">${["OPEN", "ACKNOWLEDGED", "RESOLVED", "ALL"].map((f) => `<button data-f="${f}" aria-pressed="${S.caseFilter === f}">${({ OPEN: L("Open", "مفتوحة"), ACKNOWLEDGED: L("Acknowledged", "مستلمة"), RESOLVED: L("Resolved", "مغلقة"), ALL: L("All", "الكل") })[f]}</button>`).join("")}</div>
      <div class="case-list">${filtered.length ? filtered.map((c) => `<button class="case-item" data-id="${c.case_id}" aria-current="${c.case_id === S.selectedCase}">
        <div style="display:flex;justify-content:space-between;gap:8px"><span class="t">${esc(c.employee_name)}</span><span class="kind ${c.type}">${kinds[c.type]}</span></div>
        <div class="small">${esc(c.title)}</div><div class="s">${esc(c.case_id)} · ${esc(c.owner.name)}</div></button>`).join("") : `<p class="empty">${L("No cases here.", "لا توجد حالات.")}</p>`}</div></section>
    <section class="panel" id="caseDetail">${sel ? caseDetail(sel, kinds) : `<p class="empty">${L("Select a case.", "اختر حالة.")}</p>`}</section>
  </div>`;
  document.querySelectorAll(".filters button").forEach((b) => b.onclick = () => { S.caseFilter = b.dataset.f; renderInbox(); });
  document.querySelectorAll(".case-item").forEach((b) => b.onclick = () => { S.selectedCase = b.dataset.id; renderInbox(); });
  document.querySelectorAll("[data-status]").forEach((b) => b.onclick = async () => {
    await api(`/api/cases/${S.selectedCase}`, { method: "POST", body: JSON.stringify({ status: b.dataset.status, note: $("#caseNote").value || null }) });
    toast(L("Case updated. The employee has been told.", "تم تحديث الحالة وإبلاغ الموظف.")); renderInbox();
  });
}
function caseDetail(c, kinds) {
  const ar = S.lang === "ar"; const L = (en, a) => (ar ? a : en);
  return `<div class="panel-h"><div><h2>${esc(c.title)}</h2><p class="small muted">${esc(c.case_id)} · ${kinds[c.type]} · ${esc(c.created_at.slice(0, 10))} · ${esc(c.status)}</p></div></div>
  <div class="panel-b">
    <dl class="kv"><dt>${L("Employee", "الموظف")}</dt><dd>${esc(c.employee_name)} (${esc(c.employee_id)})</dd>
      <dt>${L("Named owner", "المسؤول")}</dt><dd><strong>${esc(c.owner.name)}</strong>, ${esc(c.owner.role)}</dd>
      <dt>HRBP</dt><dd>${esc(c.hrbp.name)}</dd><dt>${L("Next update due", "موعد التحديث")}</dt><dd>${esc(c.next_update_due)}</dd>
      ${c.linked_request ? `<dt>${L("Linked request", "الطلب المرتبط")}</dt><dd>${esc(c.linked_request)}</dd>` : ""}</dl>
    <h3 style="margin-top:14px">${L("Summary", "الملخص")}</h3><p style="margin-top:4px">${esc(c.summary)}</p>
    ${c.signals.length ? `<h3 style="margin-top:14px">${L("Signals", "التنبيهات")}</h3>${c.signals.map((s) => `<div class="sig ${s.level}">${esc(s.message)}</div>`).join("")}` : ""}
    ${c.policy.length ? `<p style="margin-top:12px">${c.policy.map((p) => `<button class="cite" data-cite="${p}">${p}</button>`).join(" ")}</p>` : ""}
    <div class="guard"><strong>${L("Shared by the employee:", "ما شاركه الموظف:")}</strong> ${c.shared_items.map(esc).join(", ")}.<br>
      ${L("Conversations are never shared. Check-in feedback appears only if the employee chose to include it. Not for use in performance, probation or disciplinary decisions.", "لا تتم مشاركة المحادثات أبداً. تظهر ملاحظات الاستطلاع فقط إذا اختار الموظف ذلك. لا يجوز استخدامها في قرارات الأداء أو التجربة أو التأديب.")} <button class="cite" data-cite="POL-PRV-001 §6.2">POL-PRV-001 §6.2</button></div>
    ${c.notes.length ? `<h3 style="margin-top:14px">${L("Notes", "ملاحظات")}</h3><ul class="notes">${c.notes.map((n) => `<li>${esc(n.at.slice(0, 10))} · ${esc(n.by)}: ${esc(n.text)}</li>`).join("")}</ul>` : ""}
    <label class="small" for="caseNote" style="display:block;margin-top:14px">${L("Note to the employee (optional)", "ملاحظة للموظف (اختياري)")}</label>
    <textarea id="caseNote" style="width:100%;border:1px solid var(--line);border-radius:6px;padding:8px;min-height:60px"></textarea>
    <div class="acts">${c.status !== "ACKNOWLEDGED" && c.status !== "RESOLVED" ? `<button class="btn primary" data-status="ACKNOWLEDGED">${L("Acknowledge and take ownership", "الاستلام وتولي المسؤولية")}</button>` : ""}
      ${c.status !== "RESOLVED" ? `<button class="btn" data-status="RESOLVED">${L("Mark resolved", "إغلاق الحالة")}</button>` : `<button class="btn" data-status="OPEN">${L("Reopen", "إعادة فتح")}</button>`}</div>
  </div>`;
}

/* ------------------------------------------------------------------ insights */
async function renderInsights() {
  const group = S.insightGroup || "location";
  const d = await api(`/api/insights/stalls?group=${group}`); const ar = S.lang === "ar"; const L = (en, a) => (ar ? a : en);
  const heat = (r) => r == null ? "" : `background:rgba(200,55,45,${Math.min(0.85, 0.08 + r * 1.6).toFixed(2)});color:${r > 0.3 ? "#fff" : "var(--ink)"}`;
  $("#view").innerHTML = `<section class="panel"><div class="panel-h"><div><h2>${L("Where journeys stall", "أين تتعثر الرحلات")}</h2>
      <p class="small muted">${esc(d.note)}</p></div>
      <div class="filters" style="padding:0">${["location", "department"].map((g) => `<button data-g="${g}" aria-pressed="${group === g}">${g === "location" ? L("By site", "حسب الموقع") : L("By department", "حسب الإدارة")}</button>`).join("")}</div></div>
    <div class="panel-b" style="overflow-x:auto"><table class="heat">
      <tr><th>${L("Step", "الخطوة")}</th><th>${L("Late or stalled", "متأخر أو متوقف")}</th><th>${L("Avg days late", "متوسط أيام التأخير")}</th>${d.groups.map((g) => `<th class="small">${esc(g.replace("Dubai - ", ""))}</th>`).join("")}</tr>
      ${(S.showAllRows ? d.rows : d.rows.slice(0, 12)).map((r) => `<tr><td><strong>${esc(r.label)}</strong><br><span class="small muted">${r.journey === "ONBOARDING" ? t("onboarding") : t("mobility")} · ${r.open_issue} ${L("open now", "مفتوحة الآن")}, ${r.late_done} ${L("done late", "اكتملت متأخرة")} / ${r.applicable}</span></td>
        <td><div class="bar"><span style="width:${Math.round(r.rate * 100)}%"></span></div><span class="small">${Math.round(r.rate * 100)}%</span></td><td>${r.avg_days_late}</td>
        ${d.groups.map((g) => { const c = r.cells[g]; return c.suppressed ? `<td class="cell supp" title="${L("Fewer than 10 people", "أقل من 10 أشخاص")}">${c.n === 0 ? "—" : "&lt;10"}</td>` : `<td class="cell" style="${heat(c.rate)}">${Math.round(c.rate * 100)}%</td>`; }).join("")}</tr>`).join("")}
    </table>${d.rows.length > 12 ? `<p style="margin-top:10px"><button class="linkbtn" id="allRows">${S.showAllRows ? L("Show top 12", "عرض أعلى 12") : L(`Show all ${d.rows.length} steps`, `عرض كل الخطوات (${d.rows.length})`)}</button></p>` : ""}</div></section>`;
  $("#allRows")?.addEventListener("click", () => { S.showAllRows = !S.showAllRows; renderInsights(); });
  document.querySelectorAll("[data-g]").forEach((b) => b.onclick = () => { S.insightGroup = b.dataset.g; renderInsights(); });
}

boot();
