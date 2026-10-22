/* Rafiq front end — vanilla JS, no build step. */
const S = { role: "employee", user: null, lang: "en", personas: null, journey: null, caseFilter: "OPEN", selectedCase: null };

const T = {
  en: {
    tagline: "Employee journey companion", role_employee: "Employee", role_manager: "Manager", role_hrbp: "HR partner",
    role_owner: "Service owner", role_insights: "Insights", viewing_as: "Viewing as",
    banner: "<strong>Prototype.</strong> Synthetic data only. Today: {asof}.",
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
    banner: "<strong>نموذج أولي.</strong> بيانات افتراضية فقط. اليوم: {asof}.",
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
  // never leave the page waiting forever (e.g. a dropped connection during a redeploy)
  const ctl = new AbortController(); const timer = setTimeout(() => ctl.abort(), opts.timeoutMs || 30000);
  let r;
  try { r = await fetch(path, { credentials: "same-origin", headers: headers(), signal: ctl.signal, ...opts }); }
  catch (e) {
    throw new Error(e.name === "AbortError"
      ? (S.lang === "ar" ? "يستغرق الأمر وقتاً أطول من المعتاد. يرجى المحاولة مرة أخرى." : "This is taking longer than usual. Please try again.")
      : (S.lang === "ar" ? "تعذّر الاتصال. يرجى المحاولة مرة أخرى." : "Couldn't connect. Please try again."));
  } finally { clearTimeout(timer); }
  if (r.status === 401 && !path.startsWith("/api/login")) { S.me = null; showLogin(); throw new Error("Please sign in."); }
  if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || `Request failed (${r.status})`); }
  return r.json();
}
function toast(msg) { const el = $("#toast"); el.textContent = msg; el.classList.remove("hidden"); clearTimeout(toast._t); toast._t = setTimeout(() => el.classList.add("hidden"), 4200); }
function fmtDate(iso) { if (!iso) return ""; const d = new Date(iso.slice(0, 10) + "T12:00:00"); return d.toLocaleDateString(S.lang === "ar" ? "ar-AE" : "en-GB", { day: "numeric", month: "short" }); }
function md(text) {
  text = text.replace(/🔴\s?/g, "\u0001R").replace(/⚠️\s?/g, "\u0001A").replace(/(🗓️|📅|👍|🎉)\s?/g, "");
  return text.split(/\n\n+/).map((para) => {
    let h = esc(para).replace(/\u0001R/g, '<span class="mk mk-r" aria-label="late"></span>').replace(/\u0001A/g, '<span class="mk mk-a" aria-label="at risk"></span>')
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|\s)_(.+?)_(?=\s|$|[.,])/g, "$1<em>$2</em>")
      .replace(/\[([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)* §[\d.]+)\]/g, (m, c) => `<button class="cite" data-cite="${c}">${c}</button>`)
      .replace(/\(نص السياسة بالإنجليزية\)/g, '<span class="muted small">(نص السياسة بالإنجليزية)</span>');
    const isPol = /^• /.test(para);
    if (isPol) h = h.replace(/^• /, "").replace(/^(.*?)(\s*<button class="cite")/, '<bdi dir="auto">$1</bdi>$2');
    return `<p class="${isPol ? "pol" : ""}">${h.replace(/\n/g, "<br>")}</p>`;
  }).join("");
}
// Citations the interface shows are named by their synthetic-pack reference; the server maps them to the loaded pack
function citeBtn(ref) {
  const c = S.citeMap && ref in S.citeMap ? S.citeMap[ref] : ref;
  return c ? `<button class="cite" data-cite="${esc(c)}">${esc(c)}</button>` : "";
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
  S.homeStyle = params.get("home") === "full" ? "full" : "window";  // Home shows a five-step window of the route
  setLang(params.get("lang") === "ar" ? "ar" : "en");
  $("#langBtn").addEventListener("click", () => { setLang(S.lang === "en" ? "ar" : "en", true); renderBanner(); if (S.chatEl) { S.chatEl.remove(); S.chatEl = null; } S.me ? (renderChrome(), render()) : showLogin(); });
  $("#logoutBtn").addEventListener("click", async () => { await api("/api/logout", { method: "POST" }).catch(() => {}); S.me = null; S.chatEl = null; showLogin(); });
  document.addEventListener("click", (e) => { const c = e.target.closest(".cite"); if (c) showCite(c.dataset.cite); });
  renderBanner();
  const me = await fetch("/api/me", { credentials: "same-origin" });
  if (me.ok) { signedIn(await me.json()); } else { showLogin(); }
}
function renderBanner() {
  $("#banner").innerHTML = `<span>${t("banner", { asof: S.health.as_of })}</span>`;
}
const ROLE_LABEL = { employee: ["Employee", "موظف"], manager: ["Manager", "مدير"], hrbp: ["HR partner", "شريك الموارد البشرية"], owner: ["Service owner", "مالك الخدمة"], admin: ["Admin", "المسؤول"] };
const ICON = {
  home: '<path d="M3.5 10.5 12 4l8.5 6.5V20a1 1 0 0 1-1 1H15v-6H9v6H4.5a1 1 0 0 1-1-1z"/>',
  chat: '<path d="M4 5.5A1.5 1.5 0 0 1 5.5 4h13A1.5 1.5 0 0 1 20 5.5v9a1.5 1.5 0 0 1-1.5 1.5H9l-5 4z"/><path d="M8 9h8M8 12h5"/>',
  route: '<circle cx="5.5" cy="18.5" r="2"/><circle cx="18.5" cy="5.5" r="2"/><path d="M7.5 18.5H14a3 3 0 0 0 0-6h-4a3 3 0 0 1 0-6h6.5"/>',
  requests: '<path d="M4 4h16v16H4z"/><path d="M4 13.5h4.5l1 2.5h5l1-2.5H20"/>',
  policies: '<path d="M5 4.5A1.5 1.5 0 0 1 6.5 3H19v15H6.5A1.5 1.5 0 0 0 5 19.5z"/><path d="M5 19.5A1.5 1.5 0 0 0 6.5 21H19v-3"/><path d="M9 7.5h6"/>',
  privacy: '<path d="M12 3 19.5 6v5.5c0 4.8-3.2 8.2-7.5 9.5-4.3-1.3-7.5-4.7-7.5-9.5V6z"/><path d="m9 12 2 2 4-4"/>',
  team: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><circle cx="17.5" cy="9" r="2.5"/><path d="M16.5 14.6a5 5 0 0 1 5 5.4"/>',
  cases: '<path d="M3.5 7.5h17v12h-17z"/><path d="M9 7.5V5h6v2.5M3.5 12.5h17"/>',
  insights: '<path d="M4 20V11M10 20V5M16 20v-6M2.5 20.5h19"/>',
  admin: '<path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/>',
  profile: '<circle cx="12" cy="8.5" r="3.8"/><path d="M4.5 20.5a7.5 7.5 0 0 1 15 0"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
};
const icon = (k, cls = "ico") => `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${ICON[k]}</svg>`;
// [page, icon, English, Arabic]; pages starting with "!" are actions (open a dialog), not pages
const NAV = {
  employee: [["home", "home", "Home", "الرئيسية"], ["chat", "chat", "Ask Rafiq", "اسأل رفيق"], ["journey", "route", "My journey", "رحلتي"],
             ["requests", "requests", "My requests", "طلباتي"], ["policies", "policies", "Policies", "السياسات"], ["profile", "profile", "My profile", "ملفي الشخصي"], ["!mydata", "privacy", "My data", "بياناتي"]],
  manager: [["home", "home", "Home", "الرئيسية"], ["team", "team", "My team", "فريقي"], ["policies", "policies", "Policies", "السياسات"]],
  hrbp: [["home", "home", "Home", "الرئيسية"], ["cases", "cases", "Cases", "الحالات"], ["insights", "insights", "Insights", "المؤشرات"], ["policies", "policies", "Policies", "السياسات"]],
  owner: [["home", "home", "Home", "الرئيسية"], ["cases", "cases", "My cases", "حالاتي"], ["insights", "insights", "Insights", "المؤشرات"], ["policies", "policies", "Policies", "السياسات"]],
  admin: [["admin", "admin", "Demo admin", "إدارة العرض"], ["insights", "insights", "Insights", "المؤشرات"], ["policies", "policies", "Policies", "السياسات"]],
};
const SIDE_NOTE = {
  employee: ["Rafiq works for you. Your manager sees step progress only.", "رفيق يعمل لأجلك. يرى مديرك تقدم الخطوات فقط."],
  manager: ["Step progress only. Never conversations or feedback.", "تقدم الخطوات فقط، دون المحادثات أو الملاحظات."],
  hrbp: ["Not for performance, probation or disciplinary decisions.", "لا يُستخدم في قرارات الأداء أو التجربة أو التأديب."],
  owner: ["Not for performance, probation or disciplinary decisions.", "لا يُستخدم في قرارات الأداء أو التجربة أو التأديب."],
  admin: ["Synthetic data only.", "بيانات افتراضية فقط."],
};
function signedIn(d) {
  S.me = d.user; S.suggestions = d.suggestions || []; S.citeMap = d.cite_map || null; S.user = d.user.id; S.role = d.user.role; S.selectedCase = null;
  S.page = S.role === "admin" ? "admin" : "home"; S.chatEl = null;
  if (S.role === "employee" && d.user.lang === "ar" && !S.langChosen) { setLang("ar"); renderBanner(); }
  renderChrome(); render();
}
function renderChrome() {
  const ar = S.lang === "ar"; const u = S.me;
  document.body.classList.add("signed-in");
  const side = $("#side"); side.classList.remove("hidden");
  side.innerHTML = `<div class="side-in"><nav class="side-nav" aria-label="${ar ? "القائمة" : "Main menu"}">${NAV[u.role].map(([k, ic, en, a]) =>
    `<button data-page="${k}" ${k === S.page ? 'aria-current="page"' : ""}>${icon(ic)}<span>${ar ? a : en}</span></button>`).join("")}</nav>
    <p class="side-note">${SIDE_NOTE[u.role][ar ? 1 : 0]}</p></div>`;
  side.querySelectorAll("button[data-page]").forEach((b) => b.onclick = () => {
    if (b.dataset.page === "!mydata") return openMyData();
    go(b.dataset.page);
  });
  $("#who").classList.remove("hidden");
  $("#who").innerHTML = `<span class="who-name">${u.role === "employee" ? `<button class="linkbtn who-link" id="whoLink">${esc(u.name)}</button>` : esc(u.name)}</span><span class="who-role">${(ROLE_LABEL[u.role] || [u.role])[ar ? 1 : 0]}${u.title ? ` · ${esc(u.title)}` : ""}</span>`;
  $("#logoutBtn").classList.remove("hidden"); $("#logoutBtn").textContent = ar ? "تسجيل الخروج" : "Sign out";
  $("#whoLink")?.addEventListener("click", () => go("profile"));
}
function go(page, opts = {}) {
  finishTyping();
  if (S.page === "chat" && S.chatEl) S.chatEl.remove();
  S.page = page; if (opts.caseId) S.selectedCase = opts.caseId; else if (page !== "cases") S.selectedCase = null;
  S.pendingAsk = opts.ask || null;
  renderChrome(); render(); window.scrollTo(0, 0);
}
function render() {
  const v = $("#view"); if (!(S.page === "chat" && S.chatEl)) v.innerHTML = '<p class="empty">…</p>';
  const home = { employee: renderEmployeeHome, manager: renderManagerHome, hrbp: renderCaseHome, owner: renderCaseHome, admin: renderAdmin }[S.role];
  const fn = { home, chat: renderChat, journey: renderJourney, requests: renderRequests, policies: renderPolicies,
    profile: renderProfile, team: renderManager, cases: renderInbox, insights: renderInsights, admin: renderAdmin }[S.page] || home;
  fn().catch((e) => { if (S.me) v.innerHTML = `<p class="empty">${esc(e.message)}</p>`; });
}

/* ------------------------------------------------------------------ sign-in */
async function showLogin() {
  const ar = S.lang === "ar"; const L = (en, a) => (ar ? a : en);
  document.body.classList.remove("signed-in"); $("#side").classList.add("hidden"); $("#who").classList.add("hidden"); $("#logoutBtn").classList.add("hidden");
  if ($("#dlg").open) $("#dlg").close();
  $("#view").innerHTML = `
  <div class="login">
    <section class="login-card panel" aria-labelledby="signinTitle">
      <div class="login-mark"><svg class="mark mark-lg" viewBox="0 0 120 120" aria-hidden="true" focusable="false"><circle class="mark-ring" cx="60" cy="60" r="54"/><circle class="mark-ring2" cx="60" cy="60" r="48.5"/><path class="mark-r" d="M35 0V10H56Q80 10 96.5 17.0Q113 24 121.5 39.0Q130 54 130 79V638Q130 662 121.5 676.5Q113 691 96.5 697.5Q80 704 56 704H35V714H319Q408 714 466.0 692.5Q524 671 552.5 629.5Q581 588 581 528Q581 471 558.0 433.5Q535 396 499.5 374.5Q464 353 425 341L557 129Q580 93 596.5 69.5Q613 46 626.0 33.0Q639 20 650.0 15.0Q661 10 673 10H676V0H656Q610 0 578.5 3.5Q547 7 525.5 16.5Q504 26 487.0 44.0Q470 62 452 91L305 333H246V79Q246 54 254.5 39.0Q263 24 280.0 17.0Q297 10 320 10H341V0ZM313 343Q365 343 396.5 361.0Q428 379 442.5 418.0Q457 457 457 521Q457 586 442.0 626.5Q427 667 395.0 685.5Q363 704 311 704H246V343Z" transform="translate(34.05 86.06) scale(0.073 -0.073)"/><circle class="mark-dot" cx="98.18" cy="21.82" r="5.2"/></svg></div>
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

/* ------------------------------------------------------------------ employee */
// Steps are numbered in the order they're due (target day), the same everywhere in the app
async function loadJourney(id) {
  const j = await api(`/api/employee/${id}/journey`);
  j.ordered = j.steps.map((s, i) => ({ s, i })).sort((a, b) => a.s.target_day - b.s.target_day || a.i - b.i).map((x, k) => ({ ...x.s, n: k + 1 }));
  j.no = Object.fromEntries(j.ordered.map((s) => [s.code, s.n]));
  j.current = j.ordered.find((s) => !["DONE", "DONE_LATE"].includes(s.status)) || null;
  j.steps = j.ordered;
  S.journey = j;
  return j;
}
const isOpenReq = (q) => !["RESOLVED", "CLOSED"].includes(q.status);
const ATTN = ["STALLED", "AT_RISK", "DUE_TODAY"];
function whereLine(j) {
  const e = j.employee;
  return j.journey_type === "ONBOARDING"
    ? `${esc(e.role_title)}, ${esc(e.department)} · ${esc(e.location)}`
    : `${e.from_role_title === e.role_title ? esc(e.role_title) : `${esc(e.from_role_title)} → ${esc(e.role_title)}`} · ${e.from_location === e.location ? esc(e.location) : `${esc(e.from_location)} → ${esc(e.location)}`}`;
}
function routeCard(j, eyebrow = "") {
  const ar = S.lang === "ar"; const e = j.employee;
  return `<section class="route" aria-label="${t("your_journey")}">
    <div class="route-head">
      <div>${eyebrow ? `<p class="eyebrow">${eyebrow}</p>` : ""}<h1>${esc(e.first_name)} ${esc(e.last_name)}</h1><p class="where">${whereLine(j)}</p></div>
      <div style="text-align:end"><span class="state-pill st-${j.overall}">${t("overall")[j.overall]}</span>
        <p class="small muted" style="margin-top:4px">${j.journey_type === "ONBOARDING" ? t("onboarding") : t("mobility")} · ${esc(ar ? j.stage_label_ar : j.stage_label)} · ${j.current ? (ar ? `الخطوة ${j.current.n} من ${j.ordered.length}` : `Step ${j.current.n} of ${j.ordered.length}`) : `${j.progress.done}/${j.progress.total}`}</p></div>
    </div>
    ${ribbon(j)}
  </section>`;
}
function bindRibbon() {
  const ar = S.lang === "ar";
  document.querySelectorAll(".wp").forEach((w) => w.addEventListener("click", () => go("chat", { ask: (ar ? "ما وضع " : "What's the status of ") + w.dataset.label + "?" })));
}
function kpi(label, value, sub = "", tone = "") { return `<div class="kpi ${tone}"><p class="kpi-l">${label}</p><p class="kpi-v">${value}</p>${sub ? `<p class="kpi-s">${sub}</p>` : ""}</div>`; }
function pageHead(title, sub = "") { return `<header class="page-head"><h1>${title}</h1>${sub ? `<p class="muted">${sub}</p>` : ""}</header>`; }
function reqList(reqs, empty) {
  const ar = S.lang === "ar";
  return reqs.length ? `<ul class="list">${reqs.map((q) => `<li><div class="li-row"><strong>${esc(q.subject)}</strong><span class="tag ${q.sla_state !== "OK" && isOpenReq(q) ? "STALLED" : isOpenReq(q) ? "WAITING" : "DONE"}">${esc(q.status.replaceAll("_", " ").toLowerCase())}</span></div>
    <div class="small muted">${esc(q.request_id)} · ${esc(q.owner_name)}, ${esc(q.owner_team)}${isOpenReq(q) ? ` · ${t("open_days", { d: q.days_open })}` : ""}${isOpenReq(q) && q.sla_state !== "OK" ? ` · <span style="color:var(--red)">${ar ? "تجاوز مستوى الخدمة" : "over service level"}</span>` : ""}${q.priority === "HIGH" ? ` · ${ar ? "أولوية عالية" : "high priority"}` : ""}</div></li>`).join("")}</ul>` : `<p class="muted small">${empty || t("none_requests")}</p>`;
}
function notesList(notes, n = 6) {
  const ar = S.lang === "ar";
  return notes.length ? `<ul class="list">${notes.slice(0, n).map((x) => `<li class="small"><span class="muted">${fmtDate(x.at)}</span> · ${esc(ar ? x.text_ar : x.text)}</li>`).join("")}</ul>` : `<p class="muted small">${t("none_updates")}</p>`;
}

function timeKpi(j) {
  const ar = S.lang === "ar"; const L = (en, a) => (ar ? a : en);
  const days = (iso) => Math.round((new Date(iso.slice(0, 10) + "T12:00:00") - new Date(S.health.as_of + "T12:00:00")) / 864e5);
  if (j.journey_type === "MOBILITY" && j.move_effective_date) {
    const d = days(j.move_effective_date);
    return d > 0 ? kpi(L("Days to your move", "أيام حتى انتقالك"), d, L(`Effective ${fmtDate(j.move_effective_date)}`, `يسري في ${fmtDate(j.move_effective_date)}`))
      : kpi(L("Days in your new role", "أيام في دورك الجديد"), -d, L(`Since ${fmtDate(j.move_effective_date)}`, `منذ ${fmtDate(j.move_effective_date)}`));
  }
  const d = j.journey_day; const joined = j.employee.journey_anchor_date;
  return d < 0 ? kpi(L("Days to joining", "أيام حتى التحاقك"), -d, L(`Joining ${fmtDate(joined)}`, `الالتحاق في ${fmtDate(joined)}`))
    : kpi(L("Days since joining", "أيام منذ التحاقك"), d, L(`Joined ${fmtDate(joined)}`, `التحقت في ${fmtDate(joined)}`));
}
function homeRoute(j) {
  const ar = S.lang === "ar"; const L = (en, a) => (ar ? a : en);
  const e = j.employee; const total = j.ordered.length; const done = j.progress.done; const cur = j.current;
  return `<section class="route jhead home-route">
    <div class="route-head">
      <div><p class="eyebrow">${L("Welcome back", "أهلاً بعودتك")}</p><h1>${esc(e.first_name)} ${esc(e.last_name)}</h1><p class="where">${whereLine(j)}</p></div>
      <div style="text-align:end"><span class="state-pill st-${j.overall}">${t("overall")[j.overall]}</span>
        <p class="small muted" style="margin-top:4px">${j.journey_type === "ONBOARDING" ? t("onboarding") : t("mobility")} · ${esc(ar ? j.stage_label_ar : j.stage_label)}</p></div>
    </div>
    <div class="jprog">
      <div class="jprog-big">${cur ? L(`Step <b>${cur.n}</b> of ${total}`, `الخطوة <b>${cur.n}</b> من ${total}`) : L(`All ${total} steps done`, `اكتملت جميع الخطوات`)}</div>
      <div class="jprog-meter"><span class="meter"><span style="width:${Math.round(done / total * 100)}%"></span></span>
        <span class="small muted">${L(`${done} done · ${total - done} to go`, `${done} مكتملة · ${total - done} متبقية`)}</span></div>
    </div>
    ${S.homeStyle === "window" ? `<div class="strip">
        <button class="strip-btn prev" id="stripPrev" aria-label="${L("Earlier steps", "الخطوات السابقة")}">‹</button>
        <div class="strip-scroll" id="stripScroll" tabindex="0" aria-label="${L("Your journey steps. Scroll to see earlier and later steps.", "خطوات رحلتك. مرّر لرؤية الخطوات السابقة واللاحقة.")}"><div class="snake strip-snake" id="homeSnake"></div></div>
        <button class="strip-btn next" id="stripNext" aria-label="${L("Later steps", "الخطوات اللاحقة")}">›</button>
      </div>` : `<div class="snake compact" id="homeSnake"></div>`}
  </section>`;
}
function drawHomeRoute(j) {
  if (S.homeStyle !== "window") return drawSnake(j, { box: "#homeSnake" });
  // One scrollable strip of every step, opened centred on "You are here"
  drawSnake(j, { box: "#homeSnake", steps: j.ordered, cols: j.ordered.length });
  const sc = $("#stripScroll"); const here = sc.querySelector(".sn.here") || sc.querySelector(".sn:last-child");
  if (here) sc.scrollLeft += (here.getBoundingClientRect().left + here.offsetWidth / 2) - (sc.getBoundingClientRect().left + sc.clientWidth / 2);
  const step = () => (sc.querySelector(".sn")?.offsetWidth || 180) * 2;
  const upd = () => {
    const max = sc.scrollWidth - sc.clientWidth; const x = Math.abs(sc.scrollLeft);
    $("#stripPrev").disabled = x <= 2;          // at the start (earliest steps) in either direction
    $("#stripNext").disabled = x >= max - 2;
    sc.classList.toggle("fade-l", !$("#stripPrev").disabled); sc.classList.toggle("fade-r", !$("#stripNext").disabled);
  };
  const dir = S.lang === "ar" ? -1 : 1;  // earlier steps sit on the right in Arabic
  $("#stripPrev").onclick = () => sc.scrollBy({ left: -step() * dir, behavior: "smooth" });
  $("#stripNext").onclick = () => sc.scrollBy({ left: step() * dir, behavior: "smooth" });
  sc.onscroll = upd; upd();
}

async function renderEmployeeHome() {
  const id = S.user; const ar = S.lang === "ar"; const L = (en, a) => (ar ? a : en);
  const [j, notes] = await Promise.all([loadJourney(id), api(`/api/employee/${id}/notifications`)]);
  S.journey = j;
  const label = (s) => esc(ar ? s.label_ar : s.label);
  const attn = j.steps.filter((s) => ATTN.includes(s.status));
  const stalled = attn.filter((s) => s.status === "STALLED").length;
  const next = j.steps.filter((s) => ["UPCOMING", "WAITING"].includes(s.status)).sort((a, b) => a.target_date.localeCompare(b.target_date));
  const openReq = j.requests.filter(isOpenReq); const overSla = openReq.filter((q) => q.sla_state !== "OK").length;
  const pct = Math.round((j.progress.done / j.progress.total) * 100);
  const qa = [
    ["chat", "chat", L("Ask Rafiq", "اسأل رفيق"), L("Policies, your next steps, anything stuck", "السياسات وخطواتك التالية وأي أمر متأخر")],
    ["journey", "route", L("My journey", "رحلتي"), L("Every step, owner and target date", "كل خطوة ومسؤولها وموعدها")],
    ["requests", "requests", L("My requests", "طلباتي"), L("Track what's been raised for you", "تابع الطلبات المرفوعة لك")],
    ["policies", "policies", L("Policies", "السياسات"), L("Read the source documents", "اطلع على المستندات الأصلية")],
    ["!mydata", "privacy", L("My data", "بياناتي"), L("Consent, what's shared and with whom", "الموافقة وما تمت مشاركته ومع من")],
    ["!hr", "team", L("Talk to my HR partner", "التحدث مع شريك الموارد البشرية"), esc(j.employee.hrbp_name || "")],
  ];
  $("#view").innerHTML = `
  ${S.homeStyle ? homeRoute(j) : routeCard(j, L("Welcome back", "أهلاً بعودتك"))}
  <div class="kpis">
    ${timeKpi(j)}
    ${kpi(L("Needs attention", "يحتاج متابعة"), attn.length, attn.length ? (stalled ? L(`${stalled} stalled`, `${stalled} متوقفة`) : L("due or late", "مستحقة أو متأخرة")) : L("Nothing late", "لا شيء متأخر"), attn.length ? (stalled ? "red" : "amber") : "green")}
    ${kpi(L("Open requests", "طلبات مفتوحة"), openReq.length, overSla ? L(`${overSla} over service level`, `${overSla} تجاوزت مستوى الخدمة`) : L("All within service level", "كلها ضمن مستوى الخدمة"), overSla ? "red" : "")}
    ${kpi(L("Next milestone", "المحطة التالية"), next[0] ? fmtDate(next[0].target_date) : "—", next[0] ? label(next[0]) : L("All steps complete", "اكتملت كل الخطوات"))}
  </div>
  <div class="dash-grid">
    <section class="panel"><div class="panel-h"><h2>${L("Needs your attention", "يحتاج انتباهك")}</h2></div><div class="panel-b">
      ${attn.length ? `<ul class="att">${attn.map((s) => `<li><span class="tag ${s.status}">${t("status")[s.status]}${s.days_late ? ` +${s.days_late}d` : ""}</span>
        <div class="att-t"><strong><span class="sno-in">${L("Step", "الخطوة")} ${s.n}</span>${label(s)}</strong><span class="small muted">${t("due")} ${fmtDate(s.target_date)} · ${esc(s.owner_team)}</span></div>
        <button class="btn" data-ask="${label(s)}">${L("Get help", "اطلب المساعدة")}</button></li>`).join("")}</ul>`
        : `<p class="empty-ok">${L("You're on track. Nothing needs you right now.", "رحلتك تسير وفق الخطة. لا شيء يحتاجك الآن.")}</p>`}
    </div></section>
    <section class="panel"><div class="panel-h"><h2>${L("Coming up", "القادم")}</h2><button class="linkbtn" data-go="journey">${L("All steps", "كل الخطوات")}</button></div><div class="panel-b">
      ${next.length ? `<ul class="list">${next.slice(0, 4).map((s) => `<li><div class="li-row"><strong><span class="sno-in">${L("Step", "الخطوة")} ${s.n}</span>${label(s)}</strong><span class="small muted">${fmtDate(s.target_date)}</span></div><div class="small muted">${esc(s.owner_team)}</div></li>`).join("")}</ul>` : `<p class="muted small">${L("Nothing scheduled.", "لا شيء مجدول.")}</p>`}
    </div></section>
  </div>
  <h2 class="sec-title">${L("What would you like to do?", "ماذا تريد أن تفعل؟")}</h2>
  <div class="qa">${qa.map(([k, ic, title, sub]) => `<button class="qa-card" data-qa="${k}">${icon(ic, "qa-ico")}<span class="qa-t">${title}</span><span class="qa-s">${sub}</span></button>`).join("")}</div>
  <div class="dash-grid">
    <section class="panel"><div class="panel-h"><h2>${L("Open requests", "الطلبات المفتوحة")}</h2><button class="linkbtn" data-go="requests">${L("View all", "عرض الكل")}</button></div><div class="panel-b">${reqList(openReq)}</div></section>
    <section class="panel"><div class="panel-h"><h2>${t("updates")}</h2></div><div class="panel-b">${notesList(notes, 5)}</div></section>
  </div>`;
  bindRibbon();
  if (S.homeStyle) drawHomeRoute(j);

  document.querySelectorAll("[data-go]").forEach((b) => b.onclick = () => go(b.dataset.go));
  document.querySelectorAll("[data-ask]").forEach((b) => b.onclick = () => go("chat", { ask: (ar ? "ما وضع " : "What's the status of ") + b.dataset.ask + "?" }));
  document.querySelectorAll("[data-qa]").forEach((b) => b.onclick = () => {
    const k = b.dataset.qa;
    if (k === "!mydata") return openMyData();
    if (k === "!hr") return go("chat", { ask: L("I'd like to speak with HR about my journey.", "أريد التحدث مع شريك الموارد البشرية بشأن رحلتي.") });
    go(k);
  });
}

async function renderChat() {
  const id = S.user; const ar = S.lang === "ar"; const L = (en, a) => (ar ? a : en);
  if (S.chatEl && S.chatKey === `${id}|${S.lang}`) {
    $("#view").innerHTML = ""; $("#view").appendChild(S.chatEl); refreshSide(); refreshActionState(); return askPending();
  }
  const j = S.journey = await loadJourney(id);
  const wrap = document.createElement("div"); wrap.className = "chat-page";
  wrap.innerHTML = `
  <div class="chat-col">
    ${pageHead(L("Ask Rafiq", "اسأل رفيق"), L("Answers from your policies and your journey, with the source. Rafiq never approves or decides; people do.", "إجابات من سياساتك ورحلتك، مع ذكر المصدر. ورفيق لا يقرر نيابة عن أحد."))}
    <div class="ctx" id="ctx"></div>
    <section class="panel chat" aria-label="Chat">
      <div class="msgs" id="msgs" aria-live="polite"></div>
      <div class="typing hidden" id="typing"><span></span><span></span><span></span> ${t("thinking")}</div>
      <div class="suggest" id="suggest"></div>
      <form class="composer" id="composer"><textarea id="input" rows="1" placeholder="${t("ask")}" aria-label="${t("ask")}"></textarea><button class="btn primary" type="submit">${t("send")}</button></form>
    </section>
  </div>`;
  $("#view").innerHTML = ""; $("#view").appendChild(wrap);
  S.chatEl = wrap; S.chatKey = `${id}|${S.lang}`;
  renderCtx(j);
  S.threadId = null;
  await loadConversation(j);
  $("#composer").addEventListener("submit", (ev) => { ev.preventDefault(); send(); });
  $("#input").addEventListener("keydown", (ev) => { if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); send(); } });
  $("#input").addEventListener("input", (ev) => { ev.target.style.height = "auto"; ev.target.style.height = Math.min(140, ev.target.scrollHeight) + "px"; });
  $("#suggest").addEventListener("click", (ev) => { const b = ev.target.closest("button"); if (b) { $("#input").value = b.textContent; send(); } });
  $("#ctx").addEventListener("click", (ev) => { if (ev.target.closest("[data-go]")) go(ev.target.closest("[data-go]").dataset.go); });
  askPending();
}

function startNew(j, hasHistory = false) {
  const ar = S.lang === "ar"; const L = (en, a) => (ar ? a : en);
  // Short greeting from the journey (the full picture is one question away, and on Home)
  const label = (s) => ar ? s.label_ar : s.label;
  const late = j.steps.filter((s) => ["STALLED", "AT_RISK"].includes(s.status));
  const today = j.steps.filter((s) => s.status === "DUE_TODAY");
  const first = j.employee.first_name; const stage = ar ? j.stage_label_ar : j.stage_label;
  let hello = L(`Hi ${first}. You're in **${stage}**, with ${j.progress.done} of ${j.progress.total} steps done.`,
                `مرحباً ${first}. أنت في مرحلة **${stage}**، واكتملت ${j.progress.done} من أصل ${j.progress.total} خطوة.`);
  hello += late.length || today.length
    ? "\n\n" + L(`${late.length ? `${late.length} ${late.length === 1 ? "step is" : "steps are"} behind` : ""}${late.length && today.length ? " and " : ""}${today.length ? `${today.length} ${today.length === 1 ? "is" : "are"} due today` : ""}. Ask me about any of them, or pick a question below.`,
                    `${late.length ? `هناك ${late.length} خطوات متأخرة` : ""}${late.length && today.length ? " و" : ""}${today.length ? `${today.length} مستحقة اليوم` : ""}. اسألني عن أي منها أو اختر سؤالاً أدناه.`)
    : "\n\n" + L("Everything due so far is on track. What would you like to know?", "كل ما هو مستحق حتى الآن يسير وفق الخطة. ماذا تود أن تعرف؟");
  addBot({ reply: hello, citations: [], actions: [], lang: S.lang, intent: "BRIEF", stream: true }, false);
  const prompts = [...(S.suggestions || [])];
  late.slice(0, 2).forEach((s) => { const q = (ar ? "ما وضع " : "What's happening with ") + label(s) + "?"; if (!prompts.some((p) => p.includes(label(s)))) prompts.push(q); });
  prompts.push(...(ar ? ["ما هي خطواتي التالية؟", "من يمكنه رؤية بياناتي؟"] : ["What's next for me?", "Who can see my data?"]));
  $("#suggest").innerHTML = [...new Set(prompts)].slice(0, 5).map((p) => `<button>${esc(p)}</button>`).join("");
  $("#suggest").classList.toggle("hidden", hasHistory);
}

// One continuous conversation: reload it (with day separators), then a fresh status greeting
async function loadConversation(j) {
  const ar = S.lang === "ar";
  $("#msgs").innerHTML = "";
  await refreshActionState();
  let threads = [];
  try { threads = await api(`/api/employee/${S.user}/threads`); } catch { threads = []; }
  let had = false;
  if (threads.length) {
    const t = await api(`/api/employee/${S.user}/threads/${threads[0].id}`);
    S.threadId = threads[0].id; let day = "";
    for (const m of t.messages) {
      const d = (m.at || "").slice(0, 10);
      if (d && d !== day) { day = d; daySep(d); }
      if (m.role === "user") addMe(m.text);
      else addBot({ reply: m.text, citations: m.meta?.citations || [], actions: m.meta?.actions || [], lang: m.meta?.lang || S.lang,
                    intent: m.meta?.intent, mode: m.meta?.mode }, false);
      had = true;
    }
    // a divider before the fresh greeting only when the history ends on an earlier day
    if (had && day && day !== S.health.as_of) daySep(S.health.as_of);
    // the conversation already continued today: don't re-greet in the middle of it after a reload
    if (had && day === S.health.as_of) { $("#suggest").classList.add("hidden"); scrollMsgs(); return; }
  }
  startNew(j, had);
  scrollMsgs();
}
function daySep(iso, label) {
  const ar = S.lang === "ar";
  const txt = label || (iso === S.health.as_of ? (ar ? "اليوم" : "Today") : fmtDate(iso));
  const d = document.createElement("div"); d.className = "day-sep"; d.innerHTML = `<span>${esc(txt)}</span>`; $("#msgs").appendChild(d);
}
async function refreshActionState() {
  try { S.actState = await api(`/api/employee/${S.user}/action-state`); } catch { S.actState = { requests: [], cases: [] }; }
  // re-mark any buttons already on screen
  document.querySelectorAll("#msgs .acts .btn[data-i]").forEach((b) => {
    const a = b._action; if (!a) return; const done = actionDone(a); if (done) b.replaceWith(doneChip(a, done));
  });
}
function actionDone(a) {
  const st = S.actState || { requests: [], cases: [] };
  if (a.type === "RAISE_REQUEST") { const q = st.requests.find((x) => x.key === a.request_key); return q ? q.request_id : null; }
  if (a.type === "ESCALATE") { const c = st.cases.find((x) => x.owner === a.owner?.name); return c ? c.case_id : null; }
  return null;
}
function doneChip(a, ref) {
  const ar = S.lang === "ar"; const sp = document.createElement("span"); sp.className = "act-old done";
  const what = a.type === "ESCALATE" ? (ar ? `تم التحويل إلى ${a.owner.name}` : `Handed to ${a.owner.name}`) : a.label;
  sp.textContent = `✓ ${what} · ${ref}`; return sp;
}
function renderCtx(j) {
  const ar = S.lang === "ar"; const L = (en, a) => (ar ? a : en);
  const late = j.steps.filter((s) => ["STALLED", "AT_RISK"].includes(s.status)).length;
  const el = $("#ctx"); if (!el) return;
  el.innerHTML = `<span>${esc(ar ? j.stage_label_ar : j.stage_label)}</span><span>${j.progress.done}/${j.progress.total} ${L("steps", "خطوات")}</span>
    ${late ? `<span><span class="mk mk-r"></span>${late} ${L("behind", "متأخرة")}</span>` : `<span>${L("On track", "وفق الخطة")}</span>`}
    <button class="linkbtn" data-go="journey">${L("View journey", "عرض الرحلة")}</button>
    <button class="linkbtn ctx-clear" id="clearConv">${L("Clear conversation", "مسح المحادثة")}</button>`;
  $("#clearConv").onclick = async (e) => {
    const b = e.currentTarget;
    if (!b.classList.contains("sure")) { b.classList.add("sure"); b.textContent = L("Clear it? Click again", "تأكيد المسح؟ اضغط مجدداً"); setTimeout(() => { b.classList.remove("sure"); b.textContent = L("Clear conversation", "مسح المحادثة"); }, 3500); return; }
    await api(`/api/employee/${S.user}/conversations`, { method: "DELETE" });
    finishTyping(); S.threadId = null; $("#msgs").innerHTML = ""; startNew(S.journey); toast(L("Conversation cleared.", "تم مسح المحادثة."));
    b.classList.remove("sure"); b.textContent = L("Clear conversation", "مسح المحادثة");
  };
}
function askPending() { if (S.pendingAsk) { $("#input").value = S.pendingAsk; S.pendingAsk = null; send(); } else $("#input")?.focus(); }

async function renderJourney() {
  const id = S.user; const ar = S.lang === "ar"; const L = (en, a) => (ar ? a : en);
  const j = await loadJourney(id);
  const e = j.employee; const total = j.ordered.length; const done = j.progress.done;
  const cur = j.current;
  $("#view").innerHTML = `
  <section class="route jhead">
    <div class="route-head">
      <div><h1>${esc(e.first_name)} ${esc(e.last_name)}</h1><p class="where">${whereLine(j)}</p></div>
      <div style="text-align:end"><span class="state-pill st-${j.overall}">${t("overall")[j.overall]}</span>
        <p class="small muted" style="margin-top:4px">${j.journey_type === "ONBOARDING" ? t("onboarding") : t("mobility")} · ${esc(ar ? j.stage_label_ar : j.stage_label)}</p></div>
    </div>
    <div class="jprog">
      <div class="jprog-big">${cur ? L(`Step <b>${cur.n}</b> of ${total}`, `الخطوة <b>${cur.n}</b> من ${total}`) : L(`All ${total} steps done`, `اكتملت جميع الخطوات (${total})`)}</div>
      <div class="jprog-meter"><span class="meter"><span style="width:${Math.round(done / total * 100)}%"></span></span>
        <span class="small muted">${L(`${done} done · ${total - done} to go`, `${done} مكتملة · ${total - done} متبقية`)}</span></div>
    </div>
    <div class="snake" id="snake"></div>
    <div class="snake-key small muted">
      <span><i class="kd DONE"></i>${L("Done", "مكتمل")}</span><span><i class="kd STALLED"></i>${L("Late", "متأخر")}</span>
      <span><i class="kd DUE_TODAY"></i>${L("Due today", "مستحق اليوم")}</span><span><i class="kd UPCOMING"></i>${L("Coming up", "قادم")}</span>
      <span class="muted">${L("Select a step to ask Rafiq about it.", "اختر خطوة لتسأل رفيق عنها.")}</span>
    </div>
  </section>
  <section class="panel"><div class="panel-h"><div><h2>${t("all_steps")}</h2></div></div>
    <div class="panel-b"><ul class="steps steps-wide">${j.ordered.map((s) => stepRow(s, true)).join("")}</ul></div></section>`;
  drawSnake(j);
  if (!S._snakeResize) { S._snakeResize = true; window.addEventListener("resize", () => { if (S.page === "journey" && S.journey) drawSnake(S.journey); if (S.page === "home" && S.journey && $("#homeSnake")) drawHomeRoute(S.journey); }); }
  document.querySelectorAll("[data-ask]").forEach((b) => b.onclick = () => go("chat", { ask: (ar ? "ما وضع " : "What's the status of ") + b.dataset.ask + "?" }));
}

function drawSnake(j, opt = {}) {
  const box = $(opt.box || "#snake"); if (!box) return;
  const ar = S.lang === "ar"; const L = (en, a) => (ar ? a : en);
  const w = box.clientWidth;
  const cols = opt.cols || (w > 1050 ? 5 : w > 760 ? 4 : w > 520 ? 3 : 2);
  const steps = opt.steps || j.ordered; const isDone = (s) => s && ["DONE", "DONE_LATE"].includes(s.status);
  const rows = []; for (let i = 0; i < steps.length; i += cols) rows.push(steps.slice(i, i + cols));
  box.style.setProperty("--cols", cols);
  box.innerHTML = rows.map((row, r) => {
    const last = r === rows.length - 1;
    const nextRowFirst = rows[r + 1]?.[0];
    const turnDone = isDone(row[row.length - 1]) && isDone(nextRowFirst);
    return `<div class="snake-row ${r % 2 ? "rev" : ""} ${last ? "" : "turn"} ${turnDone ? "seg-done" : ""}">${row.map((s, k) => {
      const nxt = row[k + 1];
      const lbl = esc(ar ? s.label_ar : s.label);
      const here = j.current && j.current.code === s.code;
      const sub = isDone(s) ? fmtDate(s.completed_at) : `${t("due")} ${fmtDate(s.target_date)}`;
      const cls = [s.status, nxt ? "has-next" : "", nxt && isDone(s) && isDone(nxt) ? "seg-done" : "",
        !nxt && !last ? "to-turn" : "", k === 0 && r > 0 ? "from-turn" : "", k === 0 && r > 0 && isDone(s) && isDone(rows[r - 1].slice(-1)[0]) ? "in-done" : "",
        here ? "here" : ""].join(" ");
      return `<button class="sn ${cls}" data-label="${lbl}" title="${lbl}: ${t("status")[s.status]}">
        ${here ? `<span class="sn-here">${L("You are here", "أنت هنا")}</span>` : ""}
        <span class="sn-node">${isDone(s) ? "✓" : s.n}</span>
        <span class="sn-n">${L("Step", "الخطوة")} ${s.n}</span>
        <span class="sn-l">${lbl}</span>
        <span class="sn-d">${sub}${["STALLED", "AT_RISK"].includes(s.status) ? ` · <b>${t("status")[s.status]} +${s.days_late}d</b>` : s.status === "DUE_TODAY" ? ` · <b>${t("status").DUE_TODAY}</b>` : ""}</span>
      </button>`;
    }).join("")}</div>`;
  }).join("");
  box.querySelectorAll(".sn").forEach((b) => b.onclick = () => go("chat", { ask: (ar ? "ما وضع " : "What's the status of ") + b.dataset.label + "?" }));
}

async function renderProfile() {
  const ar = S.lang === "ar"; const L = (en, a) => (ar ? a : en);
  const p = await api(`/api/employee/${S.user}/profile`);
  const yes = (v) => v === "true" ? L("Yes", "نعم") : L("No", "لا");
  const date = (iso) => iso ? new Date(iso.slice(0, 10) + "T12:00:00").toLocaleDateString(ar ? "ar-AE" : "en-GB", { day: "numeric", month: "long", year: "numeric" }) : "—";
  const MOVE = { ROLE_CHANGE: L("Role change", "تغيير الدور"), TEAM_CHANGE: L("Team change", "تغيير الفريق"), LOCATION_DOMESTIC: L("Move within the UAE", "انتقال داخل الدولة"), LOCATION_INTERNATIONAL: L("International move", "انتقال دولي") };
  const mob = p.journey_type === "MOBILITY";
  const row = (k, v) => v ? `<dt>${k}</dt><dd>${v}</dd>` : "";
  const initials = (p.first_name[0] || "") + (p.last_name[0] || "");
  $("#view").innerHTML = `${pageHead(L("My profile", "ملفي الشخصي"), L("Your details as held in the HR system. Only you can open this page.", "بياناتك كما هي مسجلة في نظام الموارد البشرية. لا يمكن لغيرك فتح هذه الصفحة."))}
  <section class="panel profile-hero"><div class="avatar" aria-hidden="true">${esc(initials)}</div>
    <div><h2 class="profile-name">${esc(p.first_name)} ${esc(p.last_name)}</h2>
      <p>${esc(p.role_title)}${p.department ? ` · ${esc(p.department)}` : ""}</p>
      <p class="small muted">${esc(p.location)} · ${esc(p.employee_id)}</p></div>
    <span class="state-pill ${mob ? "st-AMBER" : "st-GREEN"} profile-pill">${mob ? t("mobility") : t("onboarding")}</span></section>
  <div class="dash-grid">
    <section class="panel"><div class="panel-h"><h2>${L("Role", "الوظيفة")}</h2></div><div class="panel-b"><dl class="kv">
      ${row(L("Designation", "المسمى الوظيفي"), esc(p.role_title))}
      ${row(L("Team", "الفريق"), esc(p.department))}
      ${row(L("Grade", "الدرجة"), esc(p.grade))}
      ${row(L("Location", "الموقع"), esc(p.location))}
      ${row(L("Employee ID", "الرقم الوظيفي"), esc(p.employee_id))}
      ${row(L("Username", "اسم المستخدم"), esc(p.username))}
    </dl></div></section>
    <section class="panel"><div class="panel-h"><h2>${L("Reporting line", "التسلسل الإداري")}</h2></div><div class="panel-b"><dl class="kv">
      ${row(L("Reporting manager", "المدير المباشر"), esc(p.manager_name))}
      ${row(L("HR Business Partner", "شريك الموارد البشرية"), esc(p.hrbp_name))}
      ${mob && p.releasing_manager_name ? row(L("Previous manager", "المدير السابق"), esc(p.releasing_manager_name)) : ""}
    </dl>
    <div class="acts"><button class="btn" id="askHr">${L("Contact my HR partner", "التواصل مع شريك الموارد البشرية")}</button></div></div></section>
    <section class="panel"><div class="panel-h"><h2>${mob ? L("Your move", "انتقالك") : L("Joining", "الالتحاق")}</h2></div><div class="panel-b"><dl class="kv">
      ${mob ? `${row(L("Move", "نوع الانتقال"), MOVE[p.move_type] || esc(p.move_type))}
        ${row(L("From", "من"), [esc(p.from_role_title), esc(p.from_department), esc(p.from_location)].filter(Boolean).join(" · "))}
        ${row(L("To", "إلى"), [esc(p.role_title), esc(p.department), esc(p.location)].filter(Boolean).join(" · "))}
        ${row(L("Requested", "تاريخ الطلب"), date(p.journey_anchor_date))}
        ${row(L("Effective", "تاريخ السريان"), date(p.move_effective_date))}`
        : `${row(L("Joining date", "تاريخ الالتحاق"), date(p.journey_anchor_date))}
        ${row(L("Relocating from abroad", "قادم من الخارج"), yes(p.relocating_from_abroad))}
        ${row(L("Employment visa through the company", "تأشيرة عمل عبر الشركة"), yes(p.visa_required))}
        ${row(L("Company accommodation", "سكن الشركة"), yes(p.accommodation_eligible))}`}
    </dl></div></section>
    <section class="panel"><div class="panel-h"><h2>${L("Preferences", "التفضيلات")}</h2></div><div class="panel-b"><dl class="kv">
      ${row(L("Preferred language", "اللغة المفضلة"), p.preferred_language === "ar" ? "العربية" : "English")}
      ${row(L("Family status (for entitlements)", "الحالة العائلية (لأغراض الاستحقاقات)"), p.family_status === "FAMILY" ? L("With family", "مع العائلة") : p.family_status === "SINGLE" ? L("Without dependants", "بدون مُعالين") : "")}
    </dl>
    <p class="small muted" style="margin-top:10px">${L("Something not right? HR Operations can correct your record.", "هل هناك خطأ؟ يمكن لعمليات الموارد البشرية تصحيح سجلك.")}</p>
    <div class="acts"><button class="btn" id="fixRec">${L("Ask HR Operations to correct it", "طلب التصحيح من عمليات الموارد البشرية")}</button>
      <button class="btn" id="myData">${t("my_data")}</button></div></div></section>
  </div>`;
  $("#askHr").onclick = () => go("chat", { ask: L("I'd like to speak with HR about my journey.", "أريد التحدث مع شريك الموارد البشرية بشأن رحلتي.") });
  $("#fixRec").onclick = () => go("chat", { ask: L("Some of my profile details are wrong. Can HR Operations correct my record?", "بعض بيانات ملفي غير صحيحة. هل يمكن لعمليات الموارد البشرية تصحيح سجلي؟") });
  $("#myData").onclick = openMyData;
}

async function renderRequests() {
  const id = S.user; const ar = S.lang === "ar"; const L = (en, a) => (ar ? a : en);
  const j = S.journey = await loadJourney(id);
  const open = j.requests.filter(isOpenReq); const done = j.requests.filter((q) => !isOpenReq(q));
  $("#view").innerHTML = `${pageHead(L("My requests", "طلباتي"), L("Requests raised for you by Rafiq's service agents or by the teams helping you.", "الطلبات التي رفعها لك وكلاء الخدمة في رفيق أو الفرق التي تساعدك."))}
  <div class="dash-grid">
    <section class="panel"><div class="panel-h"><h2>${L("Open", "مفتوحة")} <span class="muted small">${open.length}</span></h2><button class="btn primary" id="newReq">${L("Ask Rafiq to help", "اطلب من رفيق المساعدة")}</button></div><div class="panel-b">${reqList(open)}</div></section>
    <section class="panel"><div class="panel-h"><h2>${L("Completed", "مكتملة")} <span class="muted small">${done.length}</span></h2></div><div class="panel-b">${reqList(done, L("No completed requests yet.", "لا توجد طلبات مكتملة بعد."))}</div></section>
  </div>`;
  $("#newReq").onclick = () => go("chat");
}

async function renderPolicies() {
  const ar = S.lang === "ar"; const L = (en, a) => (ar ? a : en);
  const list = S.policyList || (S.policyList = await api("/api/policies"));
  const sorted = [...list].sort((a, b) => a.title.localeCompare(b.title));
  $("#view").innerHTML = `${pageHead(L("Policies", "السياسات"), L("The source documents Rafiq answers from. Every answer cites the section it used.", "المستندات التي يجيب منها رفيق. كل إجابة تذكر القسم الذي استندت إليه.") + (ar ? " (نص السياسات بالإنجليزية)" : ""))}
  <input id="polFilter" class="acct-filter pol-filter" type="search" placeholder="${L("Filter policies", "تصفية السياسات")}" aria-label="${L("Filter policies", "تصفية السياسات")}">
  <div class="pol-grid">${sorted.map((p) => `<button class="pol-card" data-pid="${esc(p.policy_id)}" data-n="${esc((p.title + " " + p.policy_id + " " + p.owner).toLowerCase())}">${icon("policies", "qa-ico")}<span class="qa-t">${esc(p.title)}</span><span class="qa-s">${esc(p.policy_id)} · v${esc(p.version)} · ${esc(p.owner)}</span></button>`).join("")}</div>`;
  $("#polFilter").oninput = (e) => { const q = e.target.value.trim().toLowerCase(); document.querySelectorAll(".pol-card").forEach((b) => { b.hidden = q && !b.dataset.n.includes(q); }); };
  document.querySelectorAll(".pol-card").forEach((b) => b.onclick = () => showPolicy(b.dataset.pid));
}
async function showPolicy(pid) {
  $("#dlgInner").innerHTML = `<div class="dlg-h"><h2>${esc(pid)}</h2></div><div class="dlg-b" id="citeBody"><p class="muted">…</p></div><div class="dlg-f"><button class="btn" onclick="document.getElementById('dlg').close()">${t("close")}</button></div>`;
  const dlg = $("#dlg"); dlg.className = "wide"; dlg.showModal();
  const data = (window._citeCache ||= {})[pid] || await api(`/api/policies/${encodeURIComponent(pid)}`);
  window._citeCache[pid] = data;
  $("#dlgInner .dlg-h").innerHTML = `<div><h2>${esc(data.title)}</h2><p class="small muted">${esc(pid)} · v${esc(data.version)} · ${esc(data.owner)}</p></div>`;
  $("#citeBody").innerHTML = data.sections.map((s) => `<p style="margin-top:8px"><strong>§${esc(s.cite.split("§")[1])}</strong> ${esc(s.text)}</p>`).join("");
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

function stepRow(s, help = false) {
  const ar = S.lang === "ar";
  const sub = s.completed_at ? fmtDate(s.completed_at) : `${t("due")} ${fmtDate(s.target_date)} · ${esc(s.owner_team)}`;
  const lbl = esc(ar ? s.label_ar : s.label);
  const n = s.n || (S.journey?.no || {})[s.code] || "";
  return `<li class="${s.status}"><span class="sno">${n}</span><div><div class="s-label">${lbl}</div><div class="s-sub">${sub}</div></div><span class="tag ${s.status}">${t("status")[s.status]}${["STALLED", "AT_RISK"].includes(s.status) ? ` +${s.days_late}d` : ""}</span>${help ? (ATTN.includes(s.status) ? `<button class="btn btn-s" data-ask="${lbl}">${ar ? "اطلب المساعدة" : "Get help"}</button>` : "<span></span>") : ""}</li>`;
}

function addMe(text) { const d = document.createElement("div"); d.className = "msg me"; d.textContent = text; $("#msgs").appendChild(d); scrollMsgs(); }
function scrollMsgs() { const m = $("#msgs"); m.scrollTop = m.scrollHeight; }
function addBot(r, scroll = true) {
  const d = document.createElement("div"); d.className = "msg bot" + (r.stream ? " streaming" : "");
  const extra = r.citations.filter((c) => !r.reply.includes(c.cite));
  d.innerHTML = `<span class="bot-av" aria-hidden="true">R</span><div class="bot-main"><div class="body" dir="${r.lang === "ar" ? "rtl" : "ltr"}">${md(r.reply)}</div>
    ${r.actions.length ? `<div class="acts">${r.actions.map((a, i) => `<button class="btn ${a.primary ? "primary" : ""}" data-i="${i}">${esc(a.label)}</button>`).join("")}</div>` : ""}
    ${extra.length ? `<div class="meta">${t("sources")}: ${extra.map((c) => `<button class="cite" data-cite="${c.cite}">${c.cite}</button>`).join("")}</div>` : ""}
    ${r.mode && r.mode !== "offline" && r.intent !== "BRIEF" ? `<div class="meta">${r.mode === "offline_fallback" ? (S.lang === "ar" ? "إجابة قياسية من الحقائق المؤكدة" : "Standard answer from verified facts") : (S.lang === "ar" ? "صاغها الذكاء الاصطناعي من الحقائق والمصادر المؤكدة فقط" : "Worded by AI from verified facts and the sources shown only")}</div>` : ""}</div>`;
  d.querySelectorAll(".acts .btn").forEach((b) => {
    const a = r.actions[+b.dataset.i]; b._action = a;
    const done = actionDone(a);
    if (done) b.replaceWith(doneChip(a, done)); else b.addEventListener("click", () => doAction(a, b));
  });
  $("#msgs").appendChild(d); if (scroll) scrollMsgs();
  if (r.stream) typeOut(d, r);
}

// Reveal an answer word by word (the answer is already checked; this is presentation only)
function typeOut(d, r) {
  finishTyping();
  const body = d.querySelector(".body"); const full = r.reply;
  const reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce || full.length < 40) { d.classList.remove("streaming"); return; }
  const msgs = $("#msgs"); let i = 0; let raf; let follow = true;   // follow the text unless the reader scrolls up
  const perFrame = Math.max(2, Math.ceil(full.length / 150));  // about 2.5 seconds for any length
  const partial = (n) => {
    let t = full.slice(0, n);
    const lb = t.lastIndexOf("["); if (lb > t.lastIndexOf("]")) t = t.slice(0, lb);   // never show half a citation
    if ((t.match(/\*\*/g) || []).length % 2) t += "**";                                // close bold while it's being typed
    return t;
  };
  const done = () => { cancelAnimationFrame(raf); body.innerHTML = md(full); d.classList.remove("streaming"); S._typing = null;
    if (follow) scrollMsgs(); };
  const tick = () => {
    follow = msgs.scrollHeight - msgs.scrollTop - msgs.clientHeight < 80;
    i = Math.min(full.length, i + perFrame);
    while (i < full.length && !/\s/.test(full[i])) i++;   // whole words
    body.innerHTML = md(partial(i)).replace(/<\/p>$/, '<span class="caret"></span></p>');
    if (follow) msgs.scrollTop = msgs.scrollHeight;
    if (i >= full.length) return done();
    raf = requestAnimationFrame(tick);
  };
  S._typing = done; body.innerHTML = '<span class="caret"></span>'; raf = requestAnimationFrame(tick);
  d.addEventListener("click", (e) => { if (S._typing === done && !e.target.closest(".cite")) done(); }, { once: true });
}
function finishTyping() { if (S._typing) S._typing(); }
async function send() {
  const inp = $("#input"); const text = inp.value.trim(); if (!text) return;
  finishTyping();
  inp.value = ""; inp.style.height = "auto"; addMe(text); $("#typing").classList.remove("hidden");
  $("#suggest")?.classList.add("hidden");  // suggestions help you start; once you're talking they step aside
  try {
    const r = await api(`/api/employee/${S.user}/chat`, { method: "POST", body: JSON.stringify({ message: text, lang: S.lang, thread_id: S.threadId || null }) });
    if (r.redacted_message) {  // the server removed bank or card details: show the stored version, not what was typed
      const mine = document.querySelectorAll("#msgs .msg.me"); const last = mine[mine.length - 1];
      if (last) last.textContent = r.redacted_message;
    }
    addBot({ ...r, stream: true });
    S.threadId = r.thread_id;
  }
  catch (e) { addBot({ reply: e.message, citations: [], actions: [], lang: S.lang }); }
  finally { $("#typing").classList.add("hidden"); }
}

async function doAction(a, btn) {
  if (a.type === "OPEN_MY_DATA") return openMyData();
  if (a.type === "ESCALATE") return confirmEscalation(a, btn);
  if (a.type === "RAISE_REQUEST") return confirmRequest(a, btn);
  btn.disabled = true;
  try {
    const r = await api(`/api/employee/${S.user}/actions`, { method: "POST", body: JSON.stringify({ action: a }) });
    const ar = S.lang === "ar";
    const req = r.request;
    addBot({ reply: r.duplicate ? `${ar ? r.agent_reply_ar : r.agent_reply}` : `**${esc(r.agent)}** — ${ar ? r.agent_reply_ar : r.agent_reply}\n\n${ar ? `رقم الطلب ${req.request_id}.` : `Request ${req.request_id} raised.`}`, citations: [], actions: [], lang: S.lang });
    await refreshActionState(); refreshSide();
  } catch (e) { toast(e.message); btn.disabled = false; }
}

// Requests: show the pre-filled request (exactly what the team receives) before anything is raised
const REQ_LABEL_AR = { "Employee": "الموظف", "Role": "الوظيفة", "Location": "الموقع", "Line manager": "المدير المباشر",
  "Journey": "الرحلة", "Move effective": "سريان الانتقال", "Reason": "السبب", "Related requests": "طلبات مرتبطة",
  "Policy": "السياسة", "Service level": "مستوى الخدمة" };
async function confirmRequest(a, btn) {
  const ar = S.lang === "ar";
  let p;
  try {
    p = (await api(`/api/employee/${S.user}/actions`, { method: "POST", body: JSON.stringify({ action: a, preview: true }) })).preview;
  } catch (e) { toast(e.message); return; }
  $("#dlgInner").innerHTML = `
    <div class="dlg-h"><h2>${ar ? `إرسال هذا الطلب إلى ${esc(p.to)}؟` : `Send this request to ${esc(p.to)}?`}</h2></div>
    <div class="dlg-b">
      <p class="muted">${esc(ar ? p.subject_ar : p.subject)}</p>
      <div class="share-box"><strong>${ar ? "هذا ما سيستلمه الفريق:" : "This is what the team will receive:"}</strong>
        <ul>${p.details.map((d) => `<li><strong>${esc(ar ? (REQ_LABEL_AR[d.label] || d.label) : d.label)}:</strong> ${esc(d.value)}</li>`).join("")}</ul>
        <p class="small muted" style="margin-top:8px">${t("share_never")}</p></div>
      <label class="small" for="note" style="display:block;margin-top:12px">${t("note")}</label>
      <textarea id="note" maxlength="400"></textarea>
    </div>
    <div class="dlg-f"><button class="btn" id="cx">${t("cancel")}</button><button class="btn primary" id="ok">${ar ? "إرسال الطلب" : "Send request"}</button></div>`;
  const dlg = $("#dlg"); dlg.className = ""; dlg.showModal();
  $("#cx").onclick = () => dlg.close();
  $("#ok").onclick = async () => {
    $("#ok").disabled = true; btn.disabled = true;
    try {
      const r = await api(`/api/employee/${S.user}/actions`, { method: "POST", body: JSON.stringify({ action: a, note: $("#note").value }) });
      dlg.close();
      const req = r.request;
      addBot({ reply: r.duplicate ? `${ar ? r.agent_reply_ar : r.agent_reply}` : `**${esc(r.agent)}** — ${ar ? r.agent_reply_ar : r.agent_reply}\n\n${ar ? `رقم الطلب ${req.request_id}.` : `Request ${req.request_id} raised.`}`, citations: [], actions: [], lang: S.lang });
      await refreshActionState(); refreshSide();
    } catch (e) { toast(e.message); $("#ok").disabled = false; btn.disabled = false; }
  };
}

async function confirmEscalation(a, btn) {
  const consent = S.journey.consent_active && a.can_include_pulse;
  const ar = S.lang === "ar";
  let p = null;  // exactly what the owner will receive (falls back to the generic list if the preview fails)
  try { p = (await api(`/api/employee/${S.user}/actions`, { method: "POST", body: JSON.stringify({ action: a, preview: true }) })).preview; } catch (e) { p = null; }
  const shareBox = p ? `<div class="share-box"><strong>${ar ? `هذا ما سيستلمه ${esc(a.owner.name)}:` : `This is what ${esc(a.owner.name)} will receive:`}</strong>
        <p style="margin:8px 0 4px"><strong>${esc(p.title)}</strong></p><p style="margin:0 0 8px">${esc(p.summary)}</p>
        ${p.policy.length ? `<p class="small muted">${ar ? "السياسات" : "Policy"}: ${p.policy.map((c) => esc(c.cite || c)).join(", ")}</p>` : ""}
        <p class="small muted">${ar ? "تحديث متوقع بحلول" : "Next update due"}: ${fmtDate(p.next_update_due)}</p>
        <p class="small muted" style="margin-top:8px">${ar ? "لن تتم مشاركة: محادثاتك مع رفيق" + (consent ? "" : "، وإجاباتك على استبيان المتابعة") : "Not shared: " + p.not_shared.join(", ").replace("Your check", "your check")}.</p>
        ${p.existing_case ? `<p class="small" style="margin-top:8px">${ar ? `هذا الأمر لديه بالفعل (${esc(p.existing_case)}).` : `This is already with them (${esc(p.existing_case)}); nothing new will be sent.`}</p>` : ""}</div>`
    : `<div class="share-box"><strong>${t("share_what")}</strong><ul>${t("share_items").map((x) => `<li>${x}</li>`).join("")}</ul>
        <p class="small muted" style="margin-top:8px">${t("share_never")}</p></div>`;
  $("#dlgInner").innerHTML = `
    <div class="dlg-h"><h2>${t("share_title", { name: esc(a.owner.name) })}</h2></div>
    <div class="dlg-b">
      <p class="muted">${esc(a.owner.role)}${S.journey.employee.hrbp_name && a.owner.role !== "HR Business Partner" ? ` · ${ar ? "مع إشعار" : "cc"} ${esc(S.journey.employee.hrbp_name)}` : ""}</p>
      ${shareBox}
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
      dlg.close();
      const c = r.case;
      if (c.duplicate) {
        addBot({ reply: ar ? `هذا الأمر لدى **${c.owner.name}** بالفعل (الحالة **${c.case_id}**). لم يتم إرسال أي شيء جديد.`
          : `This is already with **${c.owner.name}** (case **${c.case_id}**). Nothing new was sent.`, citations: [], actions: [], lang: S.lang });
        await refreshActionState(); return;
      }
      addBot({ reply: (ar ? `تم التحويل إلى **${c.owner.name}** (${c.owner.role}). رقم الحالة **${c.case_id}**. ستتلقى تحديثاً بحلول ${c.next_update_due}. تمت مشاركة: ${c.shared_items.join("، ")}.`
        : `Handed to **${c.owner.name}** (${c.owner.role}). Case **${c.case_id}**. You'll hear back by ${fmtDate(c.next_update_due)}. Shared: ${c.shared_items.join(", ")}.`), citations: [], actions: [], lang: S.lang });
      await refreshActionState(); refreshSide();
    } catch (e) { toast(e.message); $("#ok").disabled = false; }
  };
}
async function refreshSide() {
  const id = S.user;
  const [j, notes] = await Promise.all([loadJourney(id), api(`/api/employee/${id}/notifications`)]);
  S.journey = j;
  if ($("#sideSteps")) $("#sideSteps").innerHTML = j.steps.map((s) => stepRow(s)).join("");
  if ($("#sideProg")) $("#sideProg").textContent = `${j.progress.done}/${j.progress.total}`;
  if ($("#sideUpdates")) $("#sideUpdates").innerHTML = notesList(notes);
  renderCtx(j);
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
  <div class="dlg-h"><div><h2>${t("my_data")}</h2><p class="small muted">${L("Everything Rafiq holds about you, and who it has been shared with.", "كل ما يحتفظ به رفيق عنك، ومع من تمت مشاركته.")} ${citeBtn("POL-PRV-001 §4.1")}</p></div></div>
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
      <p class="small muted" style="margin-top:6px">${L("Your manager sees journey step progress only.", "يرى مديرك تقدم خطوات الرحلة فقط.")} ${citeBtn("POL-PRV-001 §5.1")}</p></div>
    <div class="md-sec"><h3>${L("Your profile", "ملفك")}</h3><dl class="kv">${Object.entries(d.profile).filter(([, v]) => v).map(([k, v]) => `<dt>${esc(k.replaceAll("_", " "))}</dt><dd>${esc(v)}</dd>`).join("")}</dl></div>
    <div class="md-sec"><h3>${L("Conversation history", "سجل المحادثات")}</h3><p class="small">${d.conversation_messages} ${L("messages stored.", "رسالة محفوظة.")} ${esc(d.retention)}</p>
      <button class="btn danger" id="forgetBtn" style="margin-top:6px">${L("Delete my conversation history", "حذف سجل محادثاتي")}</button></div>
    <div class="md-sec"><h3>${L("Access log", "سجل الوصول")}</h3>${d.access_log.length ? `<table>${d.access_log.map((a) => `<tr><td class="small">${esc(a.at.slice(0, 16).replace("T", " "))}</td><td class="small">${esc(a.actor)}</td><td class="small">${esc(a.detail)}</td></tr>`).join("")}</table>` : `<p class="muted small">—</p>`}</div>
  </div>
  <div class="dlg-f"><button class="btn" onclick="document.getElementById('dlg').close()">${t("close")}</button></div>`;
  const dlg = $("#dlg"); dlg.className = "wide"; if (!dlg.open) dlg.showModal();
  $("#dlgInner").innerHTML = $("#dlgInner").innerHTML.replace(/\[([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)* §[\d.]+)\]/g, (m, c) => `<button class="cite" data-cite="${c}">${c}</button>`);
  $("#consentBtn").onclick = async () => { await api(`/api/employee/${S.user}/consent`, { method: "POST", body: JSON.stringify({ active: !d.consent.pulse_active }) }); toast(d.consent.pulse_active ? L("Consent withdrawn.", "تم سحب الموافقة.") : L("Thanks — you've opted in.", "شكراً — تمت الموافقة.")); openMyData(); };
  $("#forgetBtn").onclick = async () => { await api(`/api/employee/${S.user}/conversations`, { method: "DELETE" }); toast(L("Conversation history deleted.", "تم حذف سجل المحادثات.")); if (S.chatEl) { S.chatEl.remove(); S.chatEl = null; S.threadId = null; } openMyData(); };
}

/* ------------------------------------------------------------------ manager home */
async function renderManagerHome() {
  const d = await api(`/api/manager/${S.user}/team`); const ar = S.lang === "ar"; const L = (en, a) => (ar ? a : en);
  const team = d.team; const needs = team.filter((m) => m.overdue_steps.length);
  const overdue = needs.reduce((n, m) => n + m.overdue_steps.length, 0);
  const soon = team.filter((m) => m.journey_day < 0).sort((a, b) => b.journey_day - a.journey_day);
  const first = (S.me.name || "").split(" ")[0];
  $("#view").innerHTML = `${pageHead(L(`Welcome back, ${esc(first)}`, `أهلاً بعودتك، ${esc(first)}`), L("How your team's onboarding and moves are progressing.", "كيف تسير رحلات الالتحاق والانتقال في فريقك."))}
  <div class="kpis">
    ${kpi(L("People on a journey", "في رحلة"), team.length, L("onboarding or moving", "التحاق أو انتقال"))}
    ${kpi(L("On track", "وفق الخطة"), team.length - needs.length, "", "green")}
    ${kpi(L("Need support", "يحتاجون دعماً"), needs.length, L("have an overdue step", "لديهم خطوة متأخرة"), needs.length ? "amber" : "green")}
    ${kpi(L("Overdue steps", "خطوات متأخرة"), overdue, L("across your team", "في فريقك"), overdue ? "red" : "")}
  </div>
  <div class="dash-grid">
    <section class="panel"><div class="panel-h"><h2>${L("Who may need your support", "من قد يحتاج دعمك")}</h2><button class="linkbtn" data-go="team">${L("Whole team", "كل الفريق")}</button></div><div class="panel-b">
      ${needs.length ? `<ul class="list">${needs.map((m) => `<li><div class="li-row"><strong>${esc(m.name)}</strong><span class="small muted">${esc(m.stage_label)}, ${L("day", "اليوم")} ${m.journey_day}</span></div><div class="small muted">${esc(m.role_title)}</div><div class="small" style="margin-top:4px">${m.overdue_steps.map((s) => `<span class="tag AT_RISK">${esc(s)}</span>`).join(" ")}</div></li>`).join("")}</ul>` : `<p class="empty-ok">${L("Everyone is on track.", "الجميع وفق الخطة.")}</p>`}
    </div></section>
    <section class="panel"><div class="panel-h"><h2>${L("Joining or moving soon", "ينضمون أو ينتقلون قريباً")}</h2></div><div class="panel-b">
      ${soon.length ? `<ul class="list">${soon.map((m) => `<li><div class="li-row"><strong>${esc(m.name)}</strong><span class="small muted">${L(`in ${-m.journey_day} days`, `بعد ${-m.journey_day} أيام`)}</span></div><div class="small muted">${esc(m.role_title)} · ${m.journey_type === "ONBOARDING" ? t("onboarding") : t("mobility")}</div></li>`).join("")}</ul>` : `<p class="muted small">${L("No one starting in the coming weeks.", "لا أحد يبدأ في الأسابيع القادمة.")}</p>`}
    </div></section>
  </div>
  <div class="guard">${L("You see step progress only — never conversations, check-in feedback or sentiment. Want to know how someone is feeling? Ask them.", "ترى تقدم الخطوات فقط — وليس المحادثات أو ملاحظات الاستطلاع أو المشاعر. تريد معرفة شعور أحدهم؟ اسأله.")} ${citeBtn("POL-PRV-001 §5.1")}</div>`;
  document.querySelectorAll("[data-go]").forEach((b) => b.onclick = () => go(b.dataset.go));
}

/* ------------------------------------------------------------------ HR partner / owner home */
async function renderCaseHome() {
  const ar = S.lang === "ar"; const L = (en, a) => (ar ? a : en);
  const [cases, ins] = await Promise.all([api("/api/cases"), api("/api/insights/stalls?group=location")]);
  const open = cases.filter((c) => c.status === "OPEN"); const ack = cases.filter((c) => c.status === "ACKNOWLEDGED");
  const ew = open.filter((c) => c.type === "EARLY_WARNING").length; const ho = open.filter((c) => c.type === "EMPLOYEE_HANDOFF").length;
  const kinds = { EARLY_WARNING: L("Early warning", "إنذار مبكر"), EMPLOYEE_HANDOFF: L("Employee handoff", "تحويل من الموظف"), POLICY_QUESTION: L("Policy question", "سؤال سياسة") };
  const today = S.health.as_of; const dueNow = [...open, ...ack].filter((c) => c.next_update_due <= today).length;
  const first = (S.me.name || "").split(" ")[0];
  const recent = [...open, ...ack].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 5);
  $("#view").innerHTML = `${pageHead(L(`Welcome back, ${esc(first)}`, `أهلاً بعودتك، ${esc(first)}`), S.role === "hrbp" ? L("Cases for the employees you support, and where journeys are stalling.", "حالات الموظفين الذين تدعمهم، وأين تتعثر الرحلات.") : L("Cases where you are the named owner.", "الحالات التي أنت مسؤول عنها بالاسم."))}
  <div class="kpis">
    ${kpi(L("Open cases", "حالات مفتوحة"), open.length, L("waiting for an owner to act", "بانتظار تحرك المسؤول"), open.length ? "amber" : "green")}
    ${kpi(L("Early warnings", "إنذارات مبكرة"), ew, L("raised from journey data", "من بيانات الرحلة"), ew ? "red" : "")}
    ${kpi(L("Employee handoffs", "تحويلات الموظفين"), ho, L("asked for a person", "طلبوا التحدث مع شخص"))}
    ${kpi(L("Update due", "تحديث مستحق"), dueNow, L("today or overdue", "اليوم أو متأخر"), dueNow ? "red" : "")}
  </div>
  <div class="dash-grid">
    <section class="panel"><div class="panel-h"><h2>${L("Latest cases", "أحدث الحالات")}</h2><button class="linkbtn" data-go="cases">${L("Open inbox", "فتح صندوق الحالات")}</button></div><div class="panel-b">
      ${recent.length ? `<ul class="list">${recent.map((c) => `<li><button class="row-link" data-case="${c.case_id}"><div class="li-row"><strong>${esc(c.employee_name)}</strong><span class="kind ${c.type}">${kinds[c.type]}</span></div><div class="small">${esc(c.title)}</div><div class="small muted">${esc(c.case_id)} · ${esc(c.owner.name)} · ${L("update by", "تحديث قبل")} ${fmtDate(c.next_update_due)}</div></button></li>`).join("")}</ul>` : `<p class="empty-ok">${L("No open cases.", "لا توجد حالات مفتوحة.")}</p>`}
    </div></section>
    <section class="panel"><div class="panel-h"><h2>${L("Where journeys stall", "أين تتعثر الرحلات")}</h2><button class="linkbtn" data-go="insights">${L("Full view", "العرض الكامل")}</button></div><div class="panel-b">
      <ul class="list">${ins.rows.slice(0, 6).map((r) => `<li><div class="li-row"><strong>${esc(r.label)}</strong><span class="small">${Math.round(r.rate * 100)}%</span></div><div class="bar"><span style="width:${Math.round(r.rate * 100)}%"></span></div><div class="small muted">${r.open_issue} ${L("open now", "مفتوحة الآن")} · ${L("avg", "متوسط")} ${r.avg_days_late} ${L("days late", "أيام تأخير")}</div></li>`).join("")}</ul>
      <p class="small muted" style="margin-top:8px">${L("Groups under 10 people are hidden.", "تُخفى المجموعات التي تقل عن 10 أشخاص.")}</p>
    </div></section>
  </div>
  <div class="guard">${L("Not for use in performance, probation or disciplinary decisions. Conversations are never shared; check-in feedback only when the employee chooses.", "لا يُستخدم في قرارات الأداء أو التجربة أو التأديب. لا تتم مشاركة المحادثات أبداً، وملاحظات الاستطلاع فقط باختيار الموظف.")} ${citeBtn("POL-PRV-001 §6.2")}</div>`;
  document.querySelectorAll("[data-go]").forEach((b) => b.onclick = () => go(b.dataset.go));
  document.querySelectorAll("[data-case]").forEach((b) => b.onclick = () => { S.caseFilter = "ALL"; go("cases", { caseId: b.dataset.case }); });
}

/* ------------------------------------------------------------------ manager */
async function renderManager() {
  const d = await api(`/api/manager/${S.user}/team`); const ar = S.lang === "ar";
  const L = (en, a) => (ar ? a : en);
  $("#view").innerHTML = `
    <section class="panel"><div class="panel-h"><div><h2>${L("Your team's journeys", "رحلات فريقك")}</h2>
      <p class="small muted">${L("You see step progress only — never conversations, check-in feedback or sentiment.", "ترى تقدم الخطوات فقط — وليس المحادثات أو ملاحظات الاستطلاع أو المشاعر.")} ${citeBtn("POL-PRV-001 §5.1")}</p></div></div>
    <div class="panel-b" style="overflow-x:auto"><table>
      <tr><th>${L("Person", "الموظف")}</th><th>${L("Journey", "الرحلة")}</th><th>${L("Steps", "الخطوات")}</th><th>${L("Overdue steps", "خطوات متأخرة")}</th></tr>
      ${d.team.map((m) => `<tr><td><strong>${esc(m.name)}</strong><br><span class="small muted">${esc(m.role_title)}</span></td>
        <td>${m.journey_type === "ONBOARDING" ? t("onboarding") : t("mobility")}<br><span class="small muted">${esc(m.stage_label)}, ${L("day", "اليوم")} ${m.journey_day}</span></td>
        <td><div class="dots">${m.steps.map((s) => `<i class="${s.status}" title="${esc(s.label)}: ${t("status")[s.status]}"></i>`).join("")}</div><span class="small muted">${m.progress.done}/${m.progress.total}</span></td>
        <td class="small">${m.overdue_steps.length ? m.overdue_steps.map(esc).join("<br>") : "—"}</td></tr>`).join("")}
    </table>
    <div class="guard">${L("Want to know how someone is feeling? Ask them. Rafiq is the employee's companion, not a monitoring tool.", "تريد معرفة شعور أحد أعضاء فريقك؟ اسأله مباشرة. رفيق مساعد للموظف وليس أداة مراقبة.")} ${citeBtn("POL-PRV-001 §1.2")}</div></div></section>`;
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
      ${L("Conversations are never shared. Check-in feedback appears only if the employee chose to include it. Not for use in performance, probation or disciplinary decisions.", "لا تتم مشاركة المحادثات أبداً. تظهر ملاحظات الاستطلاع فقط إذا اختار الموظف ذلك. لا يجوز استخدامها في قرارات الأداء أو التجربة أو التأديب.")} ${citeBtn("POL-PRV-001 §6.2")}</div>
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
