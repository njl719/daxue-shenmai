# -*- coding: utf-8 -*-
"""app.js 第二刀:新首页 + 经验贴页 + growth/intel 分发修正。"""
import io
import re

PATH = "app/static/app.js"
src = io.open(PATH, encoding="utf-8").read()

NEW_HOME = '''ROUTES.home = async () => {
  const [persona, plan, brief] = await Promise.all([
    api("/persona"), api("/plan/day/" + todayStr()), api("/radar/home")]);
  const daysLeft = persona.days_left;
  const doneToday = (plan.tasks || []).filter(t => t.status === "done").length;
  const pct = plan.tasks.length ? Math.round(100 * doneToday / plan.tasks.length) : 0;
  let html = `<section class="hero">
    <div class="hero-badge"><span class="dot"></span>${persona.exam_year || 2028} 考研 · 11408 方案
      ${daysLeft != null ? " · 距考约 <b>" + daysLeft + "</b> 天" : ""}</div>
    <h1>${pct >= 80 ? "今天的状态很好,继续保持" : "先把今日计划推进完"}</h1>
    <p class="hero-desc">计划完成率 <b>${pct}%</b>(${doneToday}/${plan.tasks.length})
      ${brief && brief.found ? " · 最新动态:<a href='#intel/hot'>" + esc(brief.found.title.slice(0, 24)) + "…</a>" : ""}</p>
    <div class="hero-actions">
      <a class="hero-cta" href="#decision">🎯 智能择校</a>
      <a class="hero-ghost" href="#exp">📰 经验贴</a>
      <a class="hero-ghost" href="#plan">今日计划</a>
      <a class="hero-ghost" href="#intel/schools">院校库</a>
    </div></section>
  <div class="stats-band stagger">
    <div class="stat-cell"><div class="stat-num">${pct}<span style="font-size:14px">%</span></div>
      <div class="stat-label">今日计划完成率</div></div>
    <div class="stat-cell"><div class="stat-num">${daysLeft != null ? daysLeft : "—"}</div>
      <div class="stat-label">距考天数(${persona.exam_year || 2028})</div></div>
    <div class="stat-cell"><div class="stat-num">${persona.directions ? persona.directions.length : 0}</div>
      <div class="stat-label">目标方向</div></div>
    <div class="stat-cell"><div class="stat-num">${(brief.top || {}).items ? brief.top.items.length : 0}</div>
      <div class="stat-label">近期情报条数</div></div></div>
  <section class="radar-zone" id="home-radar"><div class="section-label">RADAR · 今日考研雷达</div>
    <div class="muted" style="margin:8px 0 14px">重要提醒与近期动态,全部来自公开检索与官方公告;<a href="#intel/hot">进入考研热点 →</a></div>
    <div class="radar-grid" id="radar-cards"><div class="muted">雷达加载中…</div></div></section>`;
  $("#view").innerHTML = html;
  typeset($("#view"));
  renderHomeRadar();
};
'''

NEW_EXP = '''/* ================= 经验贴(V2.0 核心模块) ================= */
const EXP_TABS = [
  ["all", "全部"], ["985", "985上岸"], ["211", "211上岸"], ["regular", "普通本科逆袭"],
  ["cs", "计算机考研"], ["plan11408", "11408备考"], ["math1", "数学一"], ["e408", "408"],
  ["english1", "英语一"], ["choose", "择校与专业"], ["retest", "复试与调剂"],
  ["fail", "失败复盘避坑"], ["habit", "长期备考自律"],
];
function expMatch(item, tab) {
  const t = (item.title || "") + " " + (item.summary || "");
  if (tab === "all") return true;
  if (tab === "985") return /985|清华|北大|复旦|上海交通|浙江大学|南京大学|中科大|哈工大|华中科技/.test(t);
  if (tab === "211") return /211|北邮|西电|华东理工|南京理工|华中师范|苏州大学/.test(t);
  if (tab === "regular") return /普通本科|双非|二本|三本|逆袭/.test(t);
  if (tab === "cs") return /计算机|408|cs|编程|软件工程/.test(t) || item.subject === "cs408";
  if (tab === "plan11408") return /11408|数学一.{0,6}英语一|数一.{0,6}408/.test(t);
  if (tab === "math1") return /数学一|数一|高数|考研数学/.test(t) || item.subject === "math";
  if (tab === "e408") return item.subject === "cs408" || /408/.test(t);
  if (tab === "english1") return /英语一|阅读|作文模板|长难句/.test(t) || item.subject === "english";
  if (tab === "choose") return item.category === "choose" || /择校|选学校|报录比/.test(t);
  if (tab === "retest") return /复试|调剂|面试/.test(t);
  if (tab === "fail") return item.category === "fail" || /失败|没考上|落榜|后悔|避坑/.test(t);
  if (tab === "habit") return /自律|长期|坚持|习惯|作息/.test(t);
  return true;
}
let expTab = "all", expBucket = "30", expQ = "";

ROUTES.exp = async () => {
  let html = `<div class="page-head"><div>
    <div class="section-label">EXPERIENCE · 经验贴</div><h1>经验贴</h1></div></div>
  <div class="infobox">全部条目来自公开检索的真实帖子(带原文链接与可信度标记);
    AI/规则拆解仅基于摘要,不编造作者与结果。抖音/小红书无合规公开接口,走搜索引擎站点索引,来源不可用时如实显示。</div>
  <div class="toolbar" style="flex-wrap:wrap;gap:8px">
    <input id="exp-q" placeholder="搜索标题/摘要" value="${esc(expQ)}" style="flex:1;min-width:180px">
    <select id="exp-bucket">${[["7", "最近 7 天"], ["30", "最近 30 天"], ["90", "最近 90 天"], ["annual", "一年内"], ["all", "全部时间"]].map(([v, n]) =>
      `<option value="${v}" ${expBucket === v ? "selected" : ""}>${n}</option>`).join("")}</select>
    <button class="primary" id="exp-refresh">⟳ 更新</button>
    <span class="muted" id="exp-status"></span></div>
  <div class="tabs" id="exp-tabs">${EXP_TABS.map(([k, n]) =>
    `<button data-t="${k}" ${expTab === k ? 'class="on"' : ""}>${n}</button>`).join("")}</div>
  <div id="exp-quote"></div>
  <div id="exp-list"><div class="muted">加载中…</div></div>`;
  $("#view").innerHTML = html;
  typeset($("#view"));
  api("/motivation/daily").then(d => {
    const el = $("#exp-quote");
    if (el && d.quote) el.innerHTML = `<div class="card" style="border-left:3px solid var(--gold);margin-bottom:12px">
      <b>今日一句</b> <span class="tag gray">${esc(d.quote.author || "")}</span>
      <span class="tag ${/待核验/.test(d.quote.license || d.quote.source || "") ? "amber" : "green"}">${esc(d.quote.license || d.quote.source || "")}</span>
      <div style="margin-top:6px;font-size:15px">${esc(d.quote.text)}</div></div>`;
  }).catch(() => {});
  const load = async () => {
    const p = new URLSearchParams();
    if (expBucket !== "all") p.set("bucket", expBucket);
    if (expQ) p.set("q", expQ);
    const d = await api("/radar?" + p.toString());
    radarCats = d.categories || {}; radarLevs = d.levels || {};
    $("#exp-status").textContent = d.status.last_success
      ? "上次更新 " + d.status.last_success.replace("T", " ").slice(0, 16)
      : "尚未检索过";
    const items = d.items.filter(i => !i.ctype || !["expired"].includes(i.ctype)).filter(i => expMatch(i, expTab));
    $("#exp-list").innerHTML = items.length ? items.map(i => {
      const lv = radarLevs[i.source_level] || "来源未定";
      return `<div class="card" style="margin-bottom:12px">
      <div style="display:flex;justify-content:space-between;gap:10px">
        <b><a href="${esc(i.url)}" target="_blank" rel="noopener" style="color:var(--text);text-decoration:none">${esc(i.title)}</a></b>
        <span class="score-pill" title="可信度等级">${esc(radarLevs[i.source_level] || "来源未定")}</span></div>
      <div class="muted" style="font-size:13px;margin:6px 0">${esc(i.summary || "(无摘要)")}</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px">
        <span class="tag gray">${esc(i.platform)}</span>
        ${i.author ? `<span class="tag gray">${esc(i.author)}</span>` : ""}
        <span class="tag ${i.published_at ? "gray" : "amber"}">${i.published_at ? "发布 " + esc(i.published_at) : "日期未核验"}</span>
        <span class="tag gray">抓取 ${esc((i.fetched_at || "").slice(0, 10))}</span>
        ${i.category && radarCats[i.category] ? `<span class="tag blue">${esc(radarCats[i.category])}</span>` : ""}</div>
      <div class="hot-actions">
        <button data-a="open" data-u="${esc(i.url)}" class="btn">原文 ↗</button>
        <button data-a="ai" data-id="${i.id}" class="btn">🧠 拆解</button>
        <button data-a="favorite" data-id="${i.id}" class="btn">${i.favorite ? "★ 已藏" : "☆ 收藏"}</button>
        <button data-a="hide" data-id="${i.id}" class="btn">🚫 不感兴趣</button></div>
      <div class="exp-detail" id="ed-${i.id}"></div></div>`;
    }).join("") : `<div class="card"><div class="muted" style="padding:18px;text-align:center">该筛选下暂无内容 —— 点「⟳ 更新」检索,或换个分类。来源不可用时系统如实显示,不用虚构内容填充。</div></div>`;
    $$("#exp-list button[data-a]").forEach(b => b.onclick = async () => {
      const a = b.dataset.a, id = b.dataset.id;
      if (a === "open") return window.open(b.dataset.u, "_blank");
      if (a === "ai") {
        b.disabled = true; b.textContent = "拆解中…";
        try {
          const d = await api("/radar/analyze/" + id);
          const gen = d.generator === "ai" ? `<span class="tag blue">AI 拆解(${esc(d.model)})</span>` : '<span class="tag gray">规则提炼(AI 未配置)</span>';
          $("#ed-" + id).innerHTML = `<div class="infobox" style="margin-top:8px">
            <div><b>方法:</b>${esc(d.method)}</div>
            <div><b>背景:</b>${esc(d.background)}</div>
            <div><b>适用:</b>${esc(d.audience)}</div>
            <div><b>局限:</b>${esc(d.limits)}</div>
            <div style="margin-top:4px">${gen} <a href="${esc(d.url)}" target="_blank" rel="noopener">查看原文 →</a></div></div>`;
          b.textContent = "拆解"; b.disabled = false;
        } catch (e) { toast(e.message, "err"); b.disabled = false; b.textContent = "拆解"; }
        return;
      }
      try {
        await api("/radar/feedback", { method: "POST", body: JSON.stringify({ id, action: a }) });
        toast(a === "favorite" ? "已收藏" : "已记录"); load();
      } catch (e) { toast(e.message, "err"); }
    });
  };
  $("#exp-refresh").onclick = async () => {
    const b = $("#exp-refresh");
    b.disabled = true; b.textContent = "检索中…";
    try { const r = await api("/radar/refresh", { method: "POST" });
      toast(r.ok ? `新增 ${r.stats.added} 条` : "检索失败:" + (r.failure_reason || "网络不可用"), r.ok ? "ok" : "err");
    } catch (e) { toast(e.message, "err"); }
    b.disabled = false; b.textContent = "⟳ 更新";
    load();
  };
  $("#exp-bucket").onchange = e => { expBucket = e.target.value; load(); };
  $("#exp-q").onchange = e => { expQ = e.target.value.trim(); load(); };
  $$("#exp-tabs button").forEach(b => b.onclick = () => {
    expTab = b.dataset.t;
    $$("#exp-tabs button").forEach(x => x.classList.toggle("on", x === b));
    load();
  });
  await load();
};
'''

# 1) 替换旧 home 块
a = src.index("ROUTES.home = async () => {")
b = src.index("const KIND_NAME")
src = src[:a] + NEW_HOME + "\n" + src[b:]

# 2) growth: motivation 页签改为跳转经验贴
src = src.replace(
    'else if (growthTab === "motivation") await renderMotivation(body);',
    'if (growthTab === "motivation") { location.hash = "#exp"; return; }')

# 3) intel 页签精简:去掉 搜索/经验与方法
src = src.replace(
    'const names = { hot: "热点雷达", search: "搜索", sources: "来源清单", schools: "梦校与目标", exp: "经验与方法", quality: "数据质量" };',
    'const names = { hot: "考研热点", sources: "来源与数据源", schools: "院校库", quality: "数据质量" };')
src = src.replace('  if (intelTab === "search") await renderSearch(body);\n', "")
src = src.replace('  else if (intelTab === "exp") await renderExperience(body);\n', "")

# 4) 插入经验贴页(放在 intel 路由后)
anchor = "/* ================= 热点雷达(V3.1) ================= */"
src = src.replace(anchor, NEW_EXP + "\n" + anchor)

io.open(PATH, "w", encoding="utf-8", newline="\n").write(src)
print("完成")
