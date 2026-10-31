# -*- coding: utf-8 -*-
"""考研热点雷达:近期真实内容检索 → 筛选评分 → 入库 → 个性化展示。

数据通道(均为公开接口,不绕过任何登录/反爬):
  1. DuckDuckGo HTML 版公开搜索(POST,免 Key)——通用检索;
  2. 研招网(yz.chsi.com.cn)资讯/政策列表页——官方来源,直连;
  3. 用户手动提交的公开链接(抖音/小红书等无公开检索接口的平台只走此通道)。

诚信规则:
  - 抓不到原文页面时仅保留搜索摘要,verify_status=snippet_only,发布时间标"未核验";
  - 评分是筛选工具不是真理,每条保留 breakdown + rationale;
  - 检索失败保留上次成功数据,绝不编造"今日最新热点"。
"""
import datetime
import hashlib
import html as _html
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")

CTYPES = {
    "hot": "A·近期热点", "exp": "B·真实经验", "method": "C·学习方法",
    "policy": "D·招生政策", "mindset": "E·情绪压力", "ai": "F·AI原创",
    "warn": "G·警惕营销", "expired": "H·已过期",
}
CTYPES_REV = {v.split("·", 1)[1]: k for k, v in CTYPES.items()}

SUBJECTS = ("math", "cs408", "english", "politics", "general")

PLATFORMS = [
    ("chsi.com.cn", "研招网(官方)"), ("edu.cn", "高校官网(官方)"),
    ("github.com", "GitHub"),
    ("gov.cn", "政府网站(官方)"), ("eol.cn", "中国教育在线"),
    ("xdf.cn", "新东方考研"), ("zhuanlan.zhihu.com", "知乎专栏"),
    ("zhihu.com", "知乎"), ("bilibili.com", "哔哩哔哩"),
    ("toutiao.com", "今日头条"), ("mp.weixin.qq.com", "微信公众号"),
    ("sohu.com", "搜狐"), ("163.com", "网易"), ("csdn.net", "CSDN"),
    ("weibo.com", "微博"), ("douyin.com", "抖音"), ("xiaohongshu.com", "小红书"),
]
OFFICIAL_DOM = ("chsi.com.cn", "edu.cn", "gov.cn")

MARKETING_STRONG = ("保过", "不过退", "押题命中", "内部名额", "限时优惠", "秒杀价",
                    "直降", "名额不多", "再不报名就晚了", "错过等一年")
MARKETING_SOFT = ("全程班", "强化班", "冲刺班", "优惠券", "拼团", "免费领课",
                  "私信我", "加微信", "关注公众号领取", "课程安排")

ACTION_WORDS = ("方法", "复盘", "计划", "步骤", "清单", "技巧", "模板", "时间表",
                "正确率", "错题", "归纳", "总结", "安排", "规划", "攻略", "怎么做")

DOMESTIC_DOM = ("chsi.com.cn", "edu.cn", "gov.cn", "eol.cn")


# ---------------------------------------------------------------- HTTP 基础

def _strip_track(url):
    """去掉跟踪参数,生成去重用的规范 URL。"""
    p = urllib.parse.urlsplit(url.strip())
    qs = [(k, v) for k, v in urllib.parse.parse_qsl(p.query)
          if not k.lower().startswith(("utm_", "from", "fbw", "share", "spm"))]
    return urllib.parse.urlunsplit((
        "https", (p.netloc or "").lower().removeprefix("www."),
        p.path.rstrip("/"), urllib.parse.urlencode(qs), ""))


def dedup_hash(url, title=""):
    base = _strip_track(url)
    t = re.sub(r"[\s,。;:、()()【】\[\]?？,.\"'""''—_-]+", "", (title or "").lower())
    return hashlib.sha1((base + "|" + t[:80]).encode("utf-8")).hexdigest()[:20]


def _open(url, proxy, timeout=12, data=None, referer=None):
    """带 UA 的 GET/POST。国内域名直连优先,境外走代理,失败互换再试一次。"""
    domestic = any(d in urllib.parse.urlsplit(url).netloc for d in DOMESTIC_DOM)
    handlers = []
    if proxy:
        ph = urllib.request.ProxyHandler(
            {"http": proxy, "https": proxy})
        handlers.append([ph] if not domestic else [None, ph])
    else:
        handlers.append([None])
    last_err = None
    for seq in handlers:
        for h in seq:
            try:
                opener = urllib.request.build_opener(h) if h else urllib.request.build_opener()
                headers = {"User-Agent": UA}
                if referer:
                    headers["Referer"] = referer
                if data is not None:
                    headers["Content-Type"] = "application/x-www-form-urlencoded"
                req = urllib.request.Request(url, data=data, headers=headers)
                with opener.open(req, timeout=timeout) as r:
                    return r.read()
            except urllib.error.HTTPError as e:
                # 4xx 是反爬/不存在,换通道也没用,直接抛
                if 400 <= e.code < 500 and e.code not in (408, 429):
                    raise
                last_err = e
            except Exception as e:  # 超时/SSL/连接重置 → 换通道
                last_err = e
    raise last_err or RuntimeError("fetch failed")


def http_text(url, proxy, timeout=12, data=None, referer=None):
    raw = _open(url, proxy, timeout=timeout, data=data, referer=referer)
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


# ---------------------------------------------------------------- 检索通道

def search_ddg(query, proxy, timeout=15):
    """DuckDuckGo HTML 公开搜索(POST 表单,免 Key)。返回候选列表。"""
    data = urllib.parse.urlencode({"q": query}).encode("utf-8")
    raw = http_text("https://html.duckduckgo.com/html/", proxy,
                    timeout=timeout, data=data, referer="https://html.duckduckgo.com/")
    links = re.findall(
        r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', raw, re.S)
    snips = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', raw, re.S)
    out = []
    for i, (href, title) in enumerate(links):
        m = re.search(r"uddg=([^&]+)", href)
        url = urllib.parse.unquote(m.group(1)) if m else href
        if not url.startswith("http"):
            continue
        t = _html.unescape(re.sub(r"<[^>]+>", "", title)).strip()
        s = _html.unescape(re.sub(r"<[^>]+>", "", snips[i])).strip() if i < len(snips) else ""
        if t:
            out.append({"title": t[:120], "url": url, "snippet": s[:300], "via_query": query})
    return out


CHSI_PAGES = [
    ("https://yz.chsi.com.cn/kyzx/kydt/", "考研资讯"),
    ("https://yz.chsi.com.cn/kyzx/policy/", "政策公告"),
]

# GitHub 公开仓库检索(官方 API,直连无需代理;按天轮换避免重复)
GITHUB_QUERIES = ["考研 408", "考研数学", "考研英语 真题", "计算机考研 复试",
                  "考研政治", "考研 经验 贴", "考研 复习 资料"]


def search_github(query, timeout=12):
    """GitHub 官方 Search API(免 Key,10 次/分钟限速内使用)。
    返回候选;published_at 取仓库 pushed_at(真实日期,可直接进时间桶)。"""
    url = ("https://api.github.com/search/repositories?q=%s&sort=updated&per_page=6"
           % urllib.parse.quote(query))
    raw = _open(url, proxy=None, timeout=timeout)
    data = json.loads(raw.decode("utf-8", "replace"))
    out = []
    for it in data.get("items") or []:
        desc = (it.get("description") or "").strip()
        stars = it.get("stargazers_count") or 0
        license_ = ((it.get("license") or {}).get("spdx_id") or "未标许可")
        pushed = (it.get("pushed_at") or "")[:10] or None
        out.append({
            "title": ("%s:%s" % (it.get("full_name", ""), desc))[:120].strip(": "),
            "url": it.get("html_url", ""),
            "snippet": "GitHub 仓库 · ⭐%d · 许可 %s · 最近更新 %s · %s"
                       % (stars, license_, pushed or "未知", desc)[:300],
            "published_at": pushed,
            "official": False,
            "platform": "GitHub",
            "via_query": "github:" + query,
        })
    return out


def search_ddg_site(site, query, proxy, timeout=15):
    """站点限定检索:用公开搜索引擎的 site: 索引拿小红书/抖音公开帖子。
    不登录、不绕过任何访问控制;拿不到就失败(调用方如实记账)。"""
    return search_ddg("site:%s %s" % (site, query), proxy, timeout=timeout)


def fetch_chsi(proxy):
    """研招网官方列表页:标题 + 链接 + 官方发布日期。直连优先。"""
    out = []
    for page_url, page_name in CHSI_PAGES:
        try:
            raw = http_text(page_url, proxy, timeout=12)
        except Exception:
            continue
        for li in re.findall(r"<li>.*?</li>", raw, re.S):
            m_url = re.search(r'<a[^>]+href="(/kyzx/[^"]+\.html)"', li)
            if not m_url:
                continue
            m_date = re.search(r'<div class="time">(\d{4}-\d{2}-\d{2})</div>', li)
            texts = re.findall(r">([^<>]{6,80})</a>", li)
            title = _html.unescape((texts[-1] if texts else "")).strip()
            if not title:
                continue
            out.append({
                "title": title[:120],
                "url": "https://yz.chsi.com.cn" + m_url.group(1),
                "snippet": "研招网%s栏目官方发布。" % page_name,
                "published_at": (m_date.group(1) if m_date else None),
                "official": True, "via_query": "chsi:" + page_name,
            })
    return out


# ---------------------------------------------------------------- 页面核验

DATE_META = re.compile(
    r'<meta[^>]+(?:property|name)="(?:article:published_time|og:updated_time|'
    r'pubdate|publishdate|publish-date|release_date|date)"[^>]+content="([^"]+)"', re.I)
DATE_META2 = re.compile(
    r'content="([^"]+)"[^>]+(?:property|name)="(?:article:published_time|pubdate)"', re.I)
DATE_URL = re.compile(r"/(20\d{2})(\d{2})(\d{2})?/")


def extract_date(page, url):
    """从原文页提取发布时间:meta → time 标签 → URL 路径 → 正文前部日期。"""
    for pat in (DATE_META, DATE_META2):
        m = pat.search(page)
        if m:
            d = _norm_date(m.group(1))
            if d:
                return d
    m = re.search(r'<time[^>]+datetime="([^"]+)"', page, re.I)
    if m:
        d = _norm_date(m.group(1))
        if d:
            return d
    m = DATE_URL.search(url)
    if m:
        try:
            day = m.group(3) or "01"
            return "%s-%s-%s" % (m.group(1), m.group(2), day)
        except Exception:
            pass
    for m in re.finditer(r"(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})", page[:6000]):
        d = "%04d-%02d-%02d" % (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if "1900" < d[:4] and d <= datetime.date.today().isoformat():
            return d
    return None


def _norm_date(s):
    m = re.search(r"(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})", s or "")
    if m:
        try:
            return "%04d-%02d-%02d" % tuple(int(x) for x in m.groups())
        except Exception:
            return None
    return None


def extract_meta(page):
    desc = ""
    m = re.search(r'(?:property|name)="(?:og:description|description)"[^>]+content="([^"]{10,300})"', page, re.I) \
        or re.search(r'content="([^"]{10,300})"[^>]+(?:property|name)="(?:og:description|description)"', page, re.I)
    if m:
        desc = _html.unescape(m.group(1)).strip()
    author = ""
    m = re.search(r'(?:property|name)="(?:author|article:author)"[^>]+content="([^"]{2,40})"', page, re.I)
    if m:
        author = _html.unescape(m.group(1)).strip()
    return desc, author


def platform_of(url):
    host = urllib.parse.urlsplit(url).netloc.lower()
    for dom, name in PLATFORMS:
        if dom in host:
            return name
    return host.removeprefix("www.") or "未知来源"


# ---------------------------------------------------------------- 分类/过滤

def detect_subject(text):
    t = text.lower()
    if any(k in t for k in ("数学", "高数", "线代", "概率", "张宇", "李林", "武忠祥", "660", "880")):
        return "math"
    if any(k in t for k in ("408", "数据结构", "操作系统", "计组", "计算机网络", "王道")):
        return "cs408"
    if any(k in t for k in ("英语", "阅读", "完形", "翻译", "作文", "单词", "长难句")):
        return "english"
    if any(k in t for k in ("政治", "肖四", "肖八", "马原", "毛中特", "时政")):
        return "politics"
    return "general"


def classify(cand):
    """内容类型判定 A-H(营销内容判 G,其余按优先级)。"""
    t = cand.get("title", "") + " " + cand.get("snippet", "")
    strong = [k for k in MARKETING_STRONG if k in t]
    if strong or cand.get("official") is None and len([k for k in MARKETING_SOFT if k in t]) >= 2:
        return "warn", strong or [k for k in MARKETING_SOFT if k in t][:2]
    if cand.get("official") or any(k in t for k in (
            "招生简章", "招生政策", "考试大纲", "网上报名", "报名公告", "复试线",
            "调剂", "扩招", "考试时间", "考点安排")):
        return "policy", []
    if any(k in t for k in ("焦虑", "压力", "崩溃", "心态", "emo", "失眠", "放弃", "二战失败")):
        return "mindset", []
    if any(k in t for k in ("方法", "复盘", "技巧", "规划", "时间表", "怎么复习",
                            "正确率", "错题", "进度安排", "刷题")):
        return "method", []
    if any(k in t for k in ("上岸", "一战", "二战", "跨考", "经验贴", "备考记录", "心得")):
        return "exp", []
    return "hot", []


def stage_of(today=None):
    """按月份粗分备考阶段(27 考研视角):3-6 基础,7-10 强化,11-12 冲刺,1-2 复试。"""
    m = (today or datetime.date.today()).month
    if 3 <= m <= 6:
        return "基础"
    if 7 <= m <= 10:
        return "强化"
    return "冲刺"


# ---------------------------------------------------------------- 评分(规则版,保留依据)

def score_item(item, user_ctx, existing_titles):
    """五维评分(时效25/来源25/实用25/相关15/独特10)。返回 breakdown+rationale。"""
    why = {}
    pub = item.get("published_at")
    today = datetime.date.today()
    if pub:
        try:
            days = (today - datetime.date.fromisoformat(pub)).days
        except ValueError:
            days = None
    else:
        days = None
    if days is None:
        timeliness, why["时效"] = 6, "发布时间未核验"
    elif days <= 7:
        timeliness, why["时效"] = 25, "%d 天前发布" % days
    elif days <= 30:
        timeliness, why["时效"] = 20, "%d 天前发布" % days
    elif days <= 90:
        timeliness, why["时效"] = 14, "%d 天前发布" % days
    elif days <= 180:
        timeliness, why["时效"] = 8, "%d 天前发布(较旧)" % days
    else:
        timeliness, why["时效"] = 3, "%d 天前发布(仅作参考)" % days

    host = urllib.parse.urlsplit(item["url"]).netloc.lower()
    if item.get("official") or any(d in host for d in OFFICIAL_DOM):
        source, why["来源"] = 25, "官方来源"
    elif item.get("submitted_by") == "user":
        source, why["来源"] = 12, "用户提交,待核验"
    elif platform_of(item["url"]) in ("知乎", "知乎专栏", "哔哩哔哩", "今日头条", "微信公众号"):
        source, why["来源"] = 15, "公开社区/自媒体(个人观点)"
    else:
        source, why["来源"] = 10, "普通站点"

    text = item.get("title", "") + item.get("summary", "")
    hits = [k for k in ACTION_WORDS if k in text]
    utility = min(25, 6 + 3 * len(hits))
    if item["ctype"] == "policy":
        utility = max(utility, 20)
        why["实用"] = "官方关键节点信息"
    else:
        why["实用"] = "含可操作关键词:%s" % ",".join(hits[:3]) if hits else "描述性内容"

    relevance, why["相关"] = 6, "通用考研内容"
    subs = user_ctx.get("subjects") or SUBJECTS
    if item.get("subject") in subs and item.get("subject") != "general":
        relevance += 5
        why["相关"] = "匹配你在学的科目(%s)" % item["subject"]
    school = user_ctx.get("target_school") or ""
    if school and school in item.get("title", "") + item.get("summary", ""):
        relevance = min(15, relevance + 6)
        why["相关"] = "提到你的目标院校 %s" % school
    if item.get("stage") == user_ctx.get("stage"):
        relevance = min(15, relevance + 2)

    t_norm = re.sub(r"[\W_]+", "", item.get("title", "").lower())
    sim = sum(1 for x in existing_titles
              if _similar(t_norm, re.sub(r"[\W_]+", "", (x or "").lower())))
    uniqueness = 4 if sim else 10
    why["独特"] = "与库内 %d 条标题相近" % sim if sim else "库内无同题"

    w = user_ctx.get("ctype_weights") or {}
    bias = w.get(item["ctype"], 0)
    total = timeliness + source + utility + relevance + uniqueness + bias * 2
    return {"total": max(0, min(100, total)),
            "breakdown": {"时效": timeliness, "来源": source, "实用": utility,
                          "相关": relevance, "独特": uniqueness, "偏好修正": bias * 2},
            "rationale": ";".join("%s:%s" % kv for kv in why.items())}


def _similar(a, b):
    if not a or not b:
        return False
    if abs(len(a) - len(b)) > max(len(a), len(b)) * 0.4:
        return False
    common = sum(1 for x in set(a[:60]) if x in b[:60])
    return common >= min(len(set(a[:60])), len(set(b[:60]))) * 0.75


# ---------------------------------------------------------------- 关键词轮换

KEYWORD_POOL = [
    "{y}考研 数学 强化 错题复盘", "{y}考研 英语一 阅读正确率 提高",
    "{y}考研 408 复习进度 安排", "考研政治 大纲 变化 备考",
    "考研人 备考记录 真实 复盘", "考研 冲刺 时间管理 经验",
    "考研 焦虑 效率 调整 方法", "计算机考研 院校 招生信息 变化",
    "{y}考研 真题 使用方法", "{y}考研 政治 客观题 刷题",
    "{y}考研 英语 作文 模板 话题", "{y}考研 数学 模拟卷 推荐",
    "考研 二战 复盘 经验教训", "{y}考研 专业课 资料 收集",
    "考研 复试 准备 什么", "{y}考研 报名 流程 注意",
    "考研 图书馆 效率 方法", "{y}考研 660 880 刷题顺序",
    "考研 长难句 分析 技巧", "{y}考研 王道 408 笔记",
    "考研 碎片时间 利用 方法", "{y}考研 进度 落后 怎么办",
    "考研 睡眠 作息 安排", "{y}考研 跨考 计算机 经验",
    # V2.0 决策与情报定向词
    "{y}考研 择校 计算机", "27考研 复盘 上岸", "26考研 失败 复盘 教训",
    "{y}考研 数学一 经验", "{y}考研 408 上岸 经验", "考研 择校 报录比",
    "考研 后期 心态 崩了 怎么办", "考研 上岸故事 真实",
]

CATEGORY_NAMES = {
    "admit": "上岸经验", "fail": "失败复盘", "choose": "院校选择",
    "method": "学习方法", "plan": "备考规划", "material": "资料推荐",
    "mind": "心态调整", "story": "励志故事", "hot": "热点讨论",
    "avoid": "避坑建议",
}

_CAT_RULES = [
    ("avoid", ("避坑", "被坑", "套路", "警惕", "被骗", "劝退")),
    ("fail", ("失败", "没考上", "落榜", "二战失败", "后悔", "弃考", "滑档")),
    ("admit", ("上岸", "拟录取", "录取经验", "一战成硕", "400分", "高分经验")),
    ("choose", ("择校", "选学校", "院校推荐", "报录比", "院校选择", "招生人数")),
    ("material", ("资料", "网课", "讲义", "书推荐", "用什么书", "必买")),
    ("mind", ("焦虑", "心态", "崩溃", "失眠", "压力大", "emo", "疲惫")),
    ("plan", ("规划", "计划", "时间表", "进度", "安排", "冲刺阶段", "月计划")),
    ("method", ("方法", "技巧", "复盘", "错题", "刷题", "怎么复习", "正确率")),
    ("story", ("励志", "逆袭", "感动", "坚持")),
]


def classify_category(ctype, title, snippet=""):
    """内容归入 V2.0 十类(关键词规则,可解释;逐条保存在 category 字段)。"""
    text = (title or "") + " " + (snippet or "")
    if ctype == "policy":
        return "hot"  # 招生政策归入热点讨论(院校选择细节由用户在数据层看)
    if ctype == "mindset":
        return "mind"
    if ctype == "warn":
        return "avoid"
    for cat, kws in _CAT_RULES:
        if any(k in text for k in kws):
            return cat
    return "hot"


def pick_keywords(state, count=6):
    """按天轮换关键词:14 天内用过的不再用,池子轮空才重置。"""
    exam_year = datetime.date.today().year + (1 if datetime.date.today().month >= 6 else 0)
    pool = [k.format(y=str(exam_year)[-2:]) for k in KEYWORD_POOL]
    used = []
    for day, ks in sorted((state.get("keywords_used") or {}).items(), reverse=True):
        used.extend(ks)
    fresh = [k for k in pool if k not in used]
    if len(fresh) < count:
        fresh = pool  # 轮空重置(诚实:允许复用,但记录在案)
    # 稳定但可变的选取:按日期种子打散
    seed = int(datetime.date.today().strftime("%Y%m%d"))
    idx = list(range(len(fresh)))
    s = seed
    for i in range(len(idx) - 1, 0, -1):
        s = (s * 1103515245 + 12345) % (2 ** 31)
        j = s % (i + 1)
        idx[i], idx[j] = idx[j], idx[i]
    return [fresh[i] for i in idx[:count]]


# ---------------------------------------------------------------- 刷新主流程

def default_state():
    return {"last_attempt": None, "last_success": None, "last_stats": None,
            "failure_reason": None, "keywords_used": {},
            "ctype_weights": {}, "daily_card": None, "auto_refresh": False}


def refresh(store, settings, today=None, budget_s=90):
    """执行一轮检索→筛选→入库。返回统计。失败时保留旧数据并记录原因。"""
    today = today or datetime.date.today()
    t0 = time.time()
    cfg = dict((settings or {}).get("radar") or {})
    proxy = cfg.get("proxy", "http://127.0.0.1:7897") or None
    max_queries = int(cfg.get("max_queries", 6))
    state = store.load("radar_state") or default_state()
    if not state.get("keywords_used"):
        state.update(default_state())
    state["last_attempt"] = datetime.datetime.now().isoformat(timespec="seconds")

    stats = {"queries": [], "queried": 0, "candidates": 0, "fetched_pages": 0,
             "added": 0, "duplicates": 0, "rejected": 0, "failed": 0,
             "bucket_7d": 0, "bucket_30d": 0, "bucket_90d": 0, "older": 0, "unknown_date": 0}

    # 用户上下文(相关性评分用);persona 方向驱动关键词扩展
    goals = store.load("goals") or {}
    subs_conf = (settings or {}).get("subjects") or {}
    user_ctx = {
        "subjects": [s for s in ("math", "cs408", "english", "politics")
                     if (subs_conf.get(s) or {}).get("enabled", s != "politics")],
        "target_school": goals.get("institution") or "",
        "stage": stage_of(today), "ctype_weights": state.get("ctype_weights") or {},
    }
    persona = store.load("persona") or {}
    exam_year = persona.get("exam_year") or today.year + 1
    kws = pick_keywords(state, max_queries)
    if persona.get("directions"):
        dirs = " ".join(persona["directions"][:2])
        kws = list(kws)  # persona 驱动:方向词并入本轮检索
        kws[0] = "%s考研 %s" % (str(exam_year)[-2:], dirs)

    cands = []
    for kw in kws:
        if time.time() - t0 > budget_s * 0.7:
            break
        try:
            res = search_ddg(kw, proxy)
            stats["queries"].append({"q": kw, "ok": True, "n": len(res)})
            cands.extend(res)
            stats["queried"] += 1
        except Exception as e:
            stats["queries"].append({"q": kw, "ok": False, "err": str(e)[:60]})
            stats["failed"] += 1
        time.sleep(3.5)  # 温和限速,尊重公开接口(实测 1.6s 会被限流)
    try:
        chsi = fetch_chsi(proxy)
        cands.extend(chsi)
        stats["queries"].append({"q": "研招网资讯/政策", "ok": True, "n": len(chsi)})
    except Exception as e:
        stats["queries"].append({"q": "研招网", "ok": False, "err": str(e)[:60]})
        stats["failed"] += 1

    # GitHub 官方 API 通道(直连,无需代理;按天轮换 2 组)
    day_ord = today.toordinal()
    for i in range(2):
        kw = GITHUB_QUERIES[(day_ord + i) % len(GITHUB_QUERIES)]
        if time.time() - t0 > budget_s * 0.85:
            break
        try:
            res = search_github(kw)
            cands.extend(res)
            stats["queries"].append({"q": "github:" + kw, "ok": True, "n": len(res)})
        except Exception as e:
            stats["queries"].append({"q": "github:" + kw, "ok": False, "err": str(e)[:60]})
            stats["failed"] += 1
        time.sleep(1.2)  # 官方限速 10 次/分钟,留余量

    # 小红书/抖音公开索引通道:公开搜索引擎 site: 限定,不登录不绕过反爬。
    # 依赖代理出境;未配置代理时如实跳过,绝不伪造"已抓取"。
    sites = (("xiaohongshu.com", "小红书"), ("douyin.com", "抖音"))
    for i, (site, name) in enumerate(sites):
        if time.time() - t0 > budget_s:
            break
        if not proxy:
            stats["queries"].append({"q": "%s站点索引" % name, "ok": False,
                                     "err": "未配置代理,通道跳过(不伪造抓取)"})
            stats["failed"] += 1
            continue
        kw = kws[i % len(kws)] if kws else "27考研 数学"
        try:
            res = search_ddg_site(site, kw, proxy)
            cands.extend(res)
            stats["queries"].append({"q": "site:%s %s" % (name, kw), "ok": True, "n": len(res)})
        except Exception as e:
            stats["queries"].append({"q": "site:%s" % name, "ok": False, "err": str(e)[:60]})
            stats["failed"] += 1
        time.sleep(2.0)

    stats["candidates"] = len(cands)
    if not cands:
        state["failure_reason"] = "本轮未取得任何候选(网络/代理不可用?)"
        state["last_stats"] = stats
        store.save("radar_state", state)
        return stats

    items = store.load("radar")
    existing_hashes = {i.get("dedup_hash") for i in items}
    existing_titles = [i.get("title", "") for i in items]
    now_iso = datetime.datetime.now().isoformat(timespec="seconds")
    new_items = []

    # 抽样核验原文页(只核分数最高的前几张,控制时长)
    enriched = []
    for c in cands:
        ctype, hits = classify(c)
        c["ctype"] = ctype
        c["marketing_hits"] = hits
        enriched.append(c)
    ranked = sorted(enriched, key=lambda c: (
        c.get("official") is True, c["ctype"] not in ("warn",), len(c.get("snippet", ""))), reverse=True)
    # GitHub 条目不抓原文页:元数据(含真实 pushed_at 日期)已由官方 API 给出
    to_fetch = [c for c in ranked
                if not c.get("official") and c.get("platform") != "GitHub"][:5]

    for c in to_fetch:
        if time.time() - t0 > budget_s:
            break
        try:
            page = http_text(c["url"], proxy, timeout=10)
            d = extract_date(page, c["url"])
            desc, author = extract_meta(page)
            if d:
                c["published_at"] = d
            if desc and len(desc) > len(c.get("snippet", "")) * 0.6:
                c["snippet"] = desc[:300]
            c["author"] = author
            c["verify_status"] = "verified_page"
            c["verified_at"] = now_iso
            stats["fetched_pages"] += 1
        except Exception:
            c["verify_status"] = "snippet_only"  # 如实:只有摘要,日期未核验
        time.sleep(0.8)

    for c in enriched:
        if c.get("verify_status") is None:
            if c.get("official"):
                c["verify_status"] = "verified_page"
            elif c.get("platform") == "GitHub":
                c["verify_status"] = "api"  # 元数据来自官方 API(pushed_at 为真实日期)
            else:
                c["verify_status"] = "snippet_only"
        h = dedup_hash(c["url"], c["title"])
        if h in existing_hashes or any(i.get("dedup_hash") == h for i in new_items):
            stats["duplicates"] += 1
            continue
        ctype, hits = c["ctype"], c["marketing_hits"]
        # 门槛过滤:标题过短/纯营销强命中/无日期且无摘要 → 拒绝入库
        if len(c["title"]) < 8:
            stats["rejected"] += 1
            continue
        if ctype == "warn" and len(hits) >= 1 and any(k in MARKETING_STRONG for k in hits):
            stats["rejected"] += 1  # 强营销不入推荐库(软营销保留为 G 类供警惕)
            continue
        pub = c.get("published_at")
        if pub:
            try:
                days = (today - datetime.date.fromisoformat(pub)).days
            except ValueError:
                days = None
            if days is not None:
                if days <= 7:
                    stats["bucket_7d"] += 1
                elif days <= 30:
                    stats["bucket_30d"] += 1
                elif days <= 90:
                    stats["bucket_90d"] += 1
                else:
                    stats["older"] += 1
        else:
            stats["unknown_date"] += 1

        subject = detect_subject(c["title"] + " " + c.get("snippet", ""))
        if ctype == "policy":
            subject = "general"
        item = {
            "id": "rd-" + h[:12],
            "title": c["title"], "summary": (c.get("snippet") or "")[:300],
            "url": c["url"], "platform": platform_of(c["url"]),
            "author": c.get("author", ""),
            "published_at": pub, "fetched_at": now_iso,
            "verified_at": c.get("verified_at"),
            "verify_status": c["verify_status"],
            "subject": subject, "tags": [],
            "stage": "通用" if ctype in ("policy", "warn", "hot") and subject == "general" else user_ctx["stage"],
            "ctype": ctype, "category": classify_category(ctype, c["title"], c.get("snippet", "")),
            "marketing_hits": hits,
            "heat": None,
            "score": None, "recommend_reason": "", "action_advice": "",
            "shown": False, "favorite": False, "hidden": False,
            "feedback": {"useful": 0, "not_useful": 0, "practiced": False, "dislike_type": False},
            "expires_at": ((datetime.date.fromisoformat(pub) + datetime.timedelta(days=365)).isoformat()
                           if ctype == "policy" and pub else
                           (datetime.date.fromisoformat(pub) + datetime.timedelta(days=180)).isoformat()
                           if pub else (today + datetime.timedelta(days=30)).isoformat()),
            "dedup_hash": h, "submitted_by": "system", "via_query": c.get("via_query", ""),
        }
        item["score"] = score_item(item, user_ctx, existing_titles + [i["title"] for i in new_items])
        if item["score"]["total"] < 30:
            stats["rejected"] += 1
            continue
        existing_titles.append(item["title"])
        new_items.append(item)
        stats["added"] += 1

    if new_items:
        items.extend(new_items)
        store.save("radar", items)
    state["keywords_used"][today.isoformat()] = [q["q"] for q in stats["queries"] if q.get("ok")]
    # 只保留 21 天的关键词记录
    state["keywords_used"] = {k: v for k, v in state["keywords_used"].items()
                              if k >= (today - datetime.timedelta(days=21)).isoformat()}
    state["last_success"] = datetime.datetime.now().isoformat(timespec="seconds")
    state["last_stats"] = stats
    state["failure_reason"] = None
    store.save("radar_state", state)
    return stats


# ---------------------------------------------------------------- 后台定时

_auto_thread = None  # 模块级守卫:重复调用不叠加线程


def start_auto_thread(store):
    """每 6 小时检查一次设置并刷新(启动 5 分钟后先跑一轮)。
    仅在用户开启 auto_refresh 且非测试环境由 server.main 调用。"""
    global _auto_thread

    def loop():
        time.sleep(300)
        while True:
            try:
                s = store.load("settings")
                if (s.get("radar") or {}).get("auto_refresh"):
                    refresh(store, s)
                    expire_pass(store)
            except Exception:
                pass  # 后台任务失败不影响主服务;失败原因已记录在 radar_state
            time.sleep(6 * 3600)

    th = threading.Thread(target=loop, daemon=True, name="radar-auto")
    th.start()
    _auto_thread = th
    return th


def ensure_auto_thread(store):
    """设置开关即时生效用:线程未启动才拉起,已启动则循环内自会读新设置。"""
    if _auto_thread is None or not _auto_thread.is_alive():
        return start_auto_thread(store)
    return _auto_thread


# ---------------------------------------------------------------- 过期标记

def expire_pass(store, today=None):
    """把超过有效期/失效链接的内容标记为 H 类。返回标记数。"""
    today = today or datetime.date.today()
    items = store.load("radar")
    n = 0
    for i in items:
        if i.get("ctype") == "expired":
            continue
        if i.get("expires_at") and i["expires_at"] < today.isoformat():
            i["ctype"], i["expired_at"] = "expired", today.isoformat()
            n += 1
    if n:
        store.save("radar", items)
    return n


# ---------------------------------------------------------------- 个性化

def user_snapshot(store, settings, today=None):
    """从真实学习数据构建快照;没有记录就如实说没有。"""
    today = today or datetime.date.today()
    tr = store.load("train") or {}
    t = tr if tr.get("date") == today.isoformat() else {}
    answers = t.get("answers") or {}
    done = len(answers)
    total = len(t.get("questions") or [])
    correct = sum(1 for a in answers.values() if a.get("correct"))

    # 近 7 天做题统计(train 只存当天,从 records 里聚合历史)
    records = store.load("records")
    week = [r for r in records if (r.get("date") or "") >= (today - datetime.timedelta(days=7)).isoformat()]
    w_total = len(week)
    w_correct = sum(1 for r in week if r.get("correct") is True)
    active_days = len({r.get("date") for r in week if r.get("date")})

    mistakes = store.load("mistakes")
    open_m = [m for m in mistakes if not m.get("resolved")]
    due = [m for m in open_m if (m.get("due") or "9999") <= today.isoformat()]
    tags = {}
    for m in open_m:
        tg = m.get("error_tag") or "未标注"
        tags[tg] = tags.get(tg, 0) + 1
    top_tags = sorted(tags.items(), key=lambda kv: -kv[1])[:3]

    # 各科近 7 天正确率
    acc_by_sub = {}
    by_sub = {}
    for r in week:
        s = r.get("subject")
        if not s:
            continue
        by_sub.setdefault(s, [0, 0])
        by_sub[s][0] += 1
        by_sub[s][1] += 1 if r.get("correct") is True else 0
    for s, (n, c) in by_sub.items():
        if n >= 3:
            acc_by_sub[s] = {"n": n, "acc": round(100 * c / n)}
    weak = min(acc_by_sub.items(), key=lambda kv: kv[1]["acc"]) if acc_by_sub else None

    # V2.0:persona 阶段与模拟成绩趋势(真实录入数据,不使用主观评价)
    persona = store.load("persona") or {}
    days_left = None
    try:
        exam = datetime.date(int(persona.get("exam_year") or 2028), 12, 1)
        days_left = (exam - today).days
    except (ValueError, TypeError, KeyError):
        pass
    mock_trend = None
    rows = [m for m in store.load("mock_scores") if m.get("subject") in ("math", "cs408")]
    by_m = {}
    for m in rows:
        by_m.setdefault(m["subject"], []).append(m)
    for sub, ms in by_m.items():
        ms = sorted(ms, key=lambda r: r.get("month") or "")[-2:]
        if len(ms) == 2 and ms[0].get("full_mark"):
            delta = (ms[1]["score"] - ms[0]["score"]) / ms[0]["full_mark"]
            if delta <= -0.08:
                mock_trend = {"subject": sub, "delta_pct": round(100 * delta)}
                break

    return {
        "has_records": bool(records or answers),
        "today": {"done": done, "total": total, "correct": correct},
        "week": {"total": w_total, "correct": w_correct, "active_days": active_days,
                 "acc": (round(100 * w_correct / w_total) if w_total else None)},
        "due_today": len(due), "mistakes_open": len(open_m),
        "error_tags": top_tags, "acc_by_subject": acc_by_sub,
        "weak_subject": weak[0] if weak else None,
        "stage": stage_of(today),
        "days_left": days_left, "mock_trend": mock_trend,
        "exam_year": (persona or {}).get("exam_year") or 2028,
    }


NEED_TEMPLATES = {
    "baseline": {
        "why": "还没有足够的学习记录,系统不假装了解你的状态。",
        "action": "今天先完成每日训练 20 题(四科各 5 题),做完后系统才能基于真实数据给建议。",
        "metric": "完成 20 题;明天的建议将基于今天的正确率与错题标签。",
    },
    "key_stage": {
        "why": "距离 {exam_year} 考试约 {days_left} 天,进入关键阶段;此时拼的是稳定输出而非新花样。",
        "action": "把每日任务砍到可 100% 完成的最小集:到期错题复测 + 每科 1 组保持性练习;新增内容只补最薄弱一科。",
        "metric": "本周计划完成率 ≥ 90%;不因赶进度牺牲睡眠。",
    },
    "mock_drop": {
        "why": "{mock_subject} 最近两次模拟成绩下滑约 {mock_delta}%,波动本身是信息不是判决。",
        "action": "把最近两次模拟卷的丢分点各归成三类(概念/计算/审题),找出膨胀最快的一类,今天只针对它做 5 题专项。",
        "metric": "下次同科模拟,该类丢分不超过总丢分的 1/3;若继续下滑,降低难度回归基础讲义。",
    },
    "shrink": {
        "why": "今日计划完成率偏低({done}/{total}),与其自责不如缩小任务。",
        "action": "从今日计划里挑 1 项最小可完成任务先做完,再把剩余任务顺延;不要重排全部计划。",
        "metric": "今天至少完成 1 项;明早只安排 3 项以内。",
    },
    "math_method": {
        "why": "近 7 天数学正确率 {math_acc}%,高频问题是「{top_tag}」。",
        "action": "在刷题软件里挑 3 道最近做错的数学题重做一遍,写清每一步为什么成立;完成后记录独立解出的题数。",
        "metric": "3 道中独立解出 ≥2 道才算过关;否则把该知识点加入明日专项训练。",
    },
    "english_method": {
        "why": "近 7 天英语正确率 {english_acc}%,阅读正确率上不去通常卡在定位或长难句。",
        "action": "取 1 篇做错最多的阅读真题,只做两件事:逐句划出主干(谁做了什么),以及把每个错误选项对应的原文句子标出来。",
        "metric": "能说出每个错误选项错在哪一类(偷换/扩大范围/无中生有)再收工。",
    },
    "cs408_method": {
        "why": "408 知识点量大,近期问题集中在「{top_tag}」。",
        "action": "用主动回忆复习:合上书,把最近出错的 408 知识点默写成「定义-例子-易错点」三行,写不出的当场翻书补全。",
        "metric": "默写覆盖今日到期复测项;明晚再默写一次看保持率。",
    },
    "advanced": {
        "why": "近 7 天活跃 {active_days} 天、正确率 {week_acc}%,状态稳定,可以上强度。",
        "action": "今天在刷题软件加一组限时训练:连续 8 题、每题限时 5 分钟,模拟考场压力;做完把丢分点归类记进复盘。",
        "metric": "记录限时组的正确率,与不限时对比;掉超过 15 个百分点说明速度还没稳。",
    },
    "maintain": {
        "why": "近 7 天完成 {week_total} 题、正确率 {week_acc}%。",
        "action": "保持节奏:完成今日计划,并把昨天的学习内容用三句话讲给自己听(费曼法)。",
        "metric": "能不看答案讲明白即为达标。",
    },
    "restart": {
        "why": "最近 7 天只有 {active_days} 天有学习记录,中断不可怕,恢复成本才重要。",
        "action": "今天只做一件小事:在刷题软件里完成一组保持性练习 + 复盘 1 篇经验贴,找回手感即可,不求进度。",
        "metric": "明天同一时间继续,连续 3 天后恢复完整训练量。",
    },
}


def pick_need(snap):
    days = snap.get("days_left")
    if days is not None and 0 < days <= 100:
        return "key_stage"
    if not snap["has_records"]:
        return "baseline"
    if snap.get("mock_trend"):
        return "mock_drop"
    t, w = snap["today"], snap["week"]
    hour = datetime.datetime.now().hour
    if t["total"] and t["done"] / t["total"] < 0.5 and hour >= 18:
        return "shrink"
    if w["active_days"] and w["active_days"] <= 2 and w["total"] < 20:
        return "restart"
    acc = snap["acc_by_subject"]
    if snap["weak_subject"] == "math" and acc.get("math", {}).get("acc", 100) < 70:
        return "math_method"
    if snap["weak_subject"] == "english" and acc.get("english", {}).get("acc", 100) < 70:
        return "english_method"
    tags = dict(snap["error_tags"])
    if tags.get("不会做", 0) + tags.get("概念不清", 0) >= 3 and "cs408" in acc or snap["due_today"] >= 5:
        return "cs408_method"
    if w["active_days"] >= 6 and (w["acc"] or 0) >= 75:
        return "advanced"
    return "maintain"


def _fmt(template, snap):
    t = template
    t = t.replace("{done}", str(snap["today"]["done"])).replace("{total}", str(snap["today"]["total"]))
    t = t.replace("{week_total}", str(snap["week"]["total"]))
    t = t.replace("{week_acc}", str(snap["week"]["acc"] if snap["week"]["acc"] is not None else "—"))
    t = t.replace("{active_days}", str(snap["week"]["active_days"]))
    m = snap["acc_by_subject"].get("math", {})
    t = t.replace("{math_acc}", str(m.get("acc", "—")))
    e = snap["acc_by_subject"].get("english", {})
    t = t.replace("{english_acc}", str(e.get("acc", "—")))
    tg = snap["error_tags"][0][0] if snap["error_tags"] else "未标注"
    t = t.replace("{top_tag}", tg).replace("{due}", str(snap["due_today"]))
    t = t.replace("{exam_year}", str(snap.get("exam_year") or 2028))
    t = t.replace("{days_left}", str(snap.get("days_left") or "—"))
    mt = snap.get("mock_trend") or {}
    t = t.replace("{mock_subject}", SUBJECT_NAMES.get(mt.get("subject"), mt.get("subject") or "—"))
    t = t.replace("{mock_delta}", str(abs(mt.get("delta_pct") or 0)))
    return t


def build_daily_brief(store, settings, today=None, force=False):
    """五段式今日行动卡:近期发现/为何与你有关/今天能做什么/来源/复盘指标。
    规则引擎为主,AI 只在可用时改写文案,事实字段一律来自真实数据。"""
    today = today or datetime.date.today()
    snap = user_snapshot(store, settings, today)
    need = pick_need(snap)
    tmpl = NEED_TEMPLATES[need]

    # 从库里找一条匹配该需求的近期内容做"近期发现"
    items = [i for i in store.load("radar")
             if not i.get("hidden") and i["ctype"] not in ("warn", "expired", "ai")]
    want_sub = {"math_method": "math", "english_method": "english",
                "cs408_method": "cs408"}.get(need)
    pool = [i for i in items if not want_sub or i.get("subject") == want_sub]
    pool.sort(key=lambda i: -(i.get("score") or {}).get("total", 0))
    found = pool[0] if pool else None

    card = {
        "date": today.isoformat(), "need": need,
        "found": ({"title": found["title"], "url": found["url"],
                   "platform": found["platform"], "published_at": found.get("published_at"),
                   "summary": found["summary"][:160], "score": found["score"]["total"]}
                  if found else None),
        "found_note": ("未检索到与当前需求匹配的近期内容,以下建议由规则引擎基于你的真实学习数据生成。"
                       if not found else ""),
        "why": _fmt(tmpl["why"], snap),
        "action": _fmt(tmpl["action"], snap),
        "metric": tmpl["metric"],
        "generator": "rule", "model": "",
        "snapshot_keys": {"week_acc": snap["week"]["acc"], "due": snap["due_today"],
                          "weak": snap["weak_subject"], "need": need},
    }

    # 可选:本地 AI 改写(仅润色,不新增事实)
    ai_cfg = None
    try:
        from . import ai as AI
        ai_cfg = AI.get_ai_config(settings)
    except Exception:
        ai_cfg = None
    if ai_cfg and ai_cfg.get("available"):
        try:
            facts = json.dumps({k: card[k] for k in ("found", "why", "action", "metric")},
                               ensure_ascii=False)
            sys_prompt = ("你是考研教练。只依据给定 JSON 中的事实,改写 why/action 两段中文,"
                          "使其更具体自然。禁止新增分数、经历、录取结果等事实。"
                          '输出 JSON:{"why":"...","action":"..."}')
            out, err = AI._post_chat(ai_cfg, [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": facts}], timeout=45, json_mode=True)
            if err or not out:
                raise RuntimeError(err or "empty reply")
            data = json.loads(out)
            if data.get("why") and data.get("action"):
                card["why"], card["action"] = str(data["why"])[:200], str(data["action"])[:200]
                card["generator"] = "ai"
                card["model"] = ai_cfg.get("model", "")
        except Exception:
            pass  # AI 失败就保留规则版,不声张为 AI

    state = store.load("radar_state") or default_state()
    state["daily_card"] = card
    # 反馈记录在卡片上
    store.save("radar_state", state)
    return card


SUBJECT_NAMES = {"math": "数学", "cs408": "408", "english": "英语",
                 "politics": "政治", "general": "通用"}


def experience_breakdown(store, settings, today=None):
    """挑一条近期高分的经验/方法内容做结构化拆解:
    适用条件/操作步骤/潜在局限。规则兜底,AI 可用时按原文摘要提炼(不编造)。"""
    items = [i for i in store.load("radar")
             if i["ctype"] in ("method", "exp") and not i.get("hidden")]
    items.sort(key=lambda i: -(i.get("score") or {}).get("total", 0))
    if not items:
        return None
    it = items[0]
    # 缓存:同一天且拆解对象未变时直接复用,首页不必每次等本地 AI
    state = store.load("radar_state") or {}
    cache = state.get("breakdown_cache") or {}
    today_iso = datetime.date.today().isoformat()
    if (cache.get("date") == today_iso and cache.get("item_id") == it["id"]
            and cache.get("data")):
        return cache["data"]
    sub_name = SUBJECT_NAMES.get(it.get("subject"), "通用")
    out = {
        "item": {"id": it["id"], "title": it["title"], "url": it["url"],
                 "platform": it["platform"], "published_at": it.get("published_at"),
                 "verify_status": it.get("verify_status"),
                 "score": (it.get("score") or {}).get("total")},
        "conditions": "适用于%s阶段、正在复习%s的考生;个人经验,基础和目标不同效果可能不同。"
                      % (it.get("stage") or "通用", sub_name),
        "steps": "打开原文提炼作者的具体做法(不超过3条);对照你当前的做法,挑1条本周试运行并记录效果。",
        "limits": "属于个人分享,其中的分数、进度、录取结果未经系统核验;"
                  "%s请自行判断适用性。" % ("摘要信息有限,以下为通用拆解;" if it.get("verify_status") == "snippet_only" else ""),
        "generator": "rule", "model": "",
    }
    try:
        from . import ai as AI
        cfg = AI.get_ai_config(settings)
        if cfg and cfg.get("available"):
            raw = json.dumps({"title": it["title"], "summary": it["summary"]},
                             ensure_ascii=False)
            resp, err = AI._post_chat(cfg, [
                {"role": "system", "content":
                    "你是备考分析助手。仅依据给定标题与摘要,提炼该内容的适用条件、操作步骤、潜在局限。"
                    "摘要里没有的信息用『原文未提供』说明,禁止编造分数、经历或细节。"
                    '输出JSON:{"conditions":"...","steps":"...","limits":"..."},各段≤80字。'},
                {"role": "user", "content": raw}], timeout=45, json_mode=True)
            if err or not resp:
                raise RuntimeError(err or "empty reply")
            data = json.loads(resp)
            for k in ("conditions", "steps", "limits"):
                if data.get(k):
                    out[k] = str(data[k])[:120]
            out["generator"], out["model"] = "ai", cfg.get("model", "")
    except Exception:
        pass  # AI 不可用,保留规则拆解
    state["breakdown_cache"] = {"date": today_iso, "item_id": it["id"], "data": out}
    store.save("radar_state", state)
    return out


def weekly_observation(store, today=None, days=14):
    """近 N 天入库内容的主题频次 + 用户自身错题标签,注明样本量,不过度概括。"""
    today = today or datetime.date.today()
    since = (today - datetime.timedelta(days=days)).isoformat()
    items = [i for i in store.load("radar")
             if (i.get("fetched_at") or "")[:10] >= since and not i.get("hidden")]
    kw = ("数学", "英语", "政治", "408", "复盘", "真题", "模拟", "报名", "大纲",
          "焦虑", "时间管理", "作文", "强化", "冲刺")
    freq = {}
    for i in items:
        text = i.get("title", "") + i.get("summary", "")
        for k in kw:
            if k in text:
                freq[k] = freq.get(k, 0) + 1
    top = sorted(freq.items(), key=lambda kv: -kv[1])[:5]
    snap = user_snapshot(store, store.load("settings"), today)
    return {
        "sample": {"items": len(items), "days": days,
                   "note": "样本为近 %d 天本系统检索并入库的 %d 条内容,不代表全网趋势" % (days, len(items))},
        "topics": [{"tag": k, "count": n} for k, n in top],
        "my_tags": snap["error_tags"],
        "my_week": {"total": snap["week"]["total"], "acc": snap["week"]["acc"]},
    }
