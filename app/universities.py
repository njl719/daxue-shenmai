# -*- coding: utf-8 -*-
"""目标院校资料库:种子数据 + 图片获取管线(仅采用自由许可来源)。

数据原则:
- 只写入可核验字段(校名/城市/官网/计算机学院名),其余一律「待核实」,禁止编造招生数字;
- 招生人数/复试线等必须绑定年份与来源,未核验即标待核实;
- 图片只接受 Wikimedia Commons 托管(自由许可)资源,记录来源/许可/获取日期,
  并做加载测试;无合适自由图片的学校用本地生成的单字徽标降级(明确标注)。
"""
import datetime
import json
import os
import re
import ssl
import urllib.parse
import urllib.request

CAMPUS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "campus")

# 初始候选(不代表最终报考选择);wiki_en 为英文维基条目名(用于图片检索)
SEED_UNIVERSITIES = [
    {"id": "tsinghua", "name": "清华大学", "short": "清华", "city": "北京",
     "campus": "北京市海淀区(主校区)", "official_site": "https://www.tsinghua.edu.cn/",
     "cs_school": "计算机科学与技术系", "wiki_en": "Tsinghua_University"},
    {"id": "pku", "name": "北京大学", "short": "北大", "city": "北京",
     "campus": "北京市海淀区(燕园)", "official_site": "https://www.pku.edu.cn/",
     "cs_school": "计算机学院(信息科学技术学院)", "wiki_en": "Peking_University"},
    {"id": "sjtu", "name": "上海交通大学", "short": "上交", "city": "上海",
     "campus": "上海市闵行区(主校区)", "official_site": "https://www.sjtu.edu.cn/",
     "cs_school": "电子信息与电气工程学院", "wiki_en": "Shanghai_Jiao_Tong_University"},
    {"id": "zju", "name": "浙江大学", "short": "浙大", "city": "杭州",
     "campus": "杭州市西湖区(紫金港主校区)", "official_site": "https://www.zju.edu.cn/",
     "cs_school": "计算机科学与技术学院", "wiki_en": "Zhejiang_University"},
    {"id": "hust", "name": "华中科技大学", "short": "华科", "city": "武汉",
     "campus": "武汉市洪山区(主校区)", "official_site": "https://www.hust.edu.cn/",
     "cs_school": "计算机科学与技术学院", "wiki_en": "Huazhong_University_of_Science_and_Technology"},
    {"id": "uestc", "name": "电子科技大学", "short": "电子科大", "city": "成都",
     "campus": "成都市高新区(清水河主校区)", "official_site": "https://www.uestc.edu.cn/",
     "cs_school": "计算机科学与工程学院", "wiki_en": "University_of_Electronic_Science_and_Technology_of_China"},
    {"id": "xidian", "name": "西安电子科技大学", "short": "西电", "city": "西安",
     "campus": "西安市雁塔区(北校区)/长安区(南校区)", "official_site": "https://www.xidian.edu.cn/",
     "cs_school": "计算机科学与技术学院", "wiki_en": "Xidian_University"},
    {"id": "swufe", "name": "西南财经大学", "short": "西南财大", "city": "成都",
     "campus": "成都市温江区(柳林主校区)", "official_site": "https://www.swufe.edu.cn/",
     "cs_school": "计算机与人工智能学院", "wiki_en": "Southwestern_University_of_Finance_and_Economics"},
    {"id": "whu", "name": "武汉大学", "short": "武大", "city": "武汉",
     "campus": "武汉市武昌区(珞珈山主校区)", "official_site": "https://www.whu.edu.cn/",
     "cs_school": "计算机学院", "wiki_en": "Wuhan_University"},
    {"id": "scut", "name": "华南理工大学", "short": "华南理工", "city": "广州",
     "campus": "广州市天河区(五山校区)", "official_site": "https://www.scut.edu.cn/",
     "cs_school": "计算机科学与工程学院", "wiki_en": "South_China_University_of_Technology"},
]


# 图片匹配 token:防止抓到名字相近的其他学校(如杭州电子科技大学)
IMG_TOKENS = {
    "tsinghua": ["Tsinghua"],
    "pku": ["Peking University"],
    "sjtu": ["Shanghai Jiao Tong", "上海交通"],
    "zju": ["Zhejiang University", "浙江大学"],
    "hust": ["Huazhong University", "华中科技"],
    "uestc": ["University of Electronic Science", "UESTC"],
    "xidian": ["Xidian", "西安电子科技"],
    "swufe": ["Southwestern University of Finance", "SWUFE", "西南财经"],
    "whu": ["Wuhan University", "武汉大学"],
    "scut": ["South China University", "华南理工"],
}

# 完整度统计追踪字段(招生数字类必须年份+来源才算已填)
TRACKED_FIELDS = ["name", "city", "official_site", "cs_school", "campus",
                  "program", "program_code", "degree_type", "exam_subjects",
                  "uses_408", "admission_catalog_url", "retest_rules_url",
                  "history_admission_url", "enrollment", "enrollment_year",
                  "retest_line", "retest_line_year", "tuition", "duration_years",
                  "intro", "image"]


def _ctx():
    """本地网络存在拦截代理(自签证书);仅对公开维基媒体只读请求放宽校验。"""
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    return c


def _wiki_summary(title):
    url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title)
    req = urllib.request.Request(url, headers={"User-Agent": "daxue-shenmai/1.0"})
    with urllib.request.urlopen(req, timeout=15, context=_ctx()) as r:
        return json.loads(r.read().decode("utf-8"))


def _commons_license(file_url):
    """从 Commons 文件 URL 提取 File: 标题并查询许可。失败返回占位说明。"""
    m = re.search(r"/commons/(?:thumb/)?[0-9a-f]/[0-9a-f]{2}/([^/]+)", file_url)
    if not m:
        return None, None
    fname = urllib.parse.unquote(m.group(1))
    if fname.endswith(".svg.png") or re.search(r"\.\w+px\.", fname):
        fname = re.sub(r"/[^/]+$", "", m.group(0).split("/thumb/")[-1])
        fname = urllib.parse.unquote(fname)
    api = ("https://commons.wikimedia.org/w/api.php?action=query&prop=imageinfo"
           "&iiprop=extmetadata&format=json&titles=" +
           urllib.parse.quote("File:" + fname))
    try:
        req = urllib.request.Request(api, headers={"User-Agent": "daxue-shenmai/1.0"})
        with urllib.request.urlopen(req, timeout=12, context=_ctx()) as r:
            d = json.loads(r.read().decode("utf-8"))
        pages = d.get("query", {}).get("pages", {})
        for p in pages.values():
            md = (p.get("imageinfo") or [{}])[0].get("extmetadata", {})
            lic = md.get("LicenseShortName", {}).get("value", "")
            artist = re.sub(r"<[^>]+>", "", md.get("Artist", {}).get("value", ""))[:60]
            page = p.get("title", "")
            return lic or "见来源页", (artist + " · " + page) if page else artist
    except Exception:
        pass
    return None, None


def commons_campus_photo(query, tokens=None):
    """在 Commons 检索校园实景照(仅 CC/PD 位图),返回图片记录或 None。

    tokens: 校名标识列表;文件标题必须包含其一,防止抓到名字相近的其他学校
    (例:杭州电子科技大学 ≠ 电子科技大学)。
    """
    api = ("https://commons.wikimedia.org/w/api.php?action=query&generator=search"
           "&gsrsearch=" + urllib.parse.quote(query + " filetype:bitmap") +
           "&gsrnamespace=6&gsrlimit=12&prop=imageinfo"
           "&iiprop=url|extmetadata&iiurlwidth=800&format=json")
    try:
        req = urllib.request.Request(api, headers={"User-Agent": "daxue-shenmai/1.0"})
        with urllib.request.urlopen(req, timeout=15, context=_ctx()) as r:
            d = json.loads(r.read().decode("utf-8"))
    except Exception:
        return None
    for p in (d.get("query", {}).get("pages") or {}).values():
        title = p.get("title", "")
        if tokens and not any(t.lower() in title.lower() for t in tokens):
            continue  # 不是本校照片,拒绝
        info = (p.get("imageinfo") or [{}])[0]
        md = info.get("extmetadata", {})
        lic = md.get("LicenseShortName", {}).get("value", "")
        if not lic or "fair use" in lic.lower():
            continue
        url = info.get("thumburl") or info.get("url")
        if not url:
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "daxue-shenmai/1.0"})
            with urllib.request.urlopen(req, timeout=25, context=_ctx()) as r:
                data = r.read(5 * 1024 * 1024)
        except Exception:
            continue
        if len(data) < 2000 or data[:3] != b"\xff\xd8\xff":
            continue  # 非完整 JPEG
        return {"data": data, "ext": ".jpg",
                "license": lic,
                "title": p.get("title", "").replace("File:", "")[:80],
                "source_page": "https://commons.wikimedia.org/wiki/" +
                               urllib.parse.quote(p.get("title", "").replace(" ", "_")),
                "credit": re.sub(r"<[^>]+>", "", md.get("Artist", {}).get("value", ""))[:100]}
    return None


def fetch_university_image(uni):
    """抓取学校主图:优先维基条目主图(仅 Commons),否则 Commons 校园照(仅 CC/PD)。"""
    try:
        summary = _wiki_summary(uni["wiki_en"])
    except Exception:
        summary = None
    img_rec = None
    if summary:
        for key in ("originalimage", "thumbnail"):
            info = summary.get(key)
            if not info:
                continue
            src = info.get("source", "")
            # 只接受 Commons 托管(wikipedia/en 为本地 fair-use,不可用)
            if "/wikipedia/commons/" not in src:
                continue
            # SVG 缩略图 → 标准 500px PNG 渲染(Wikimedia 命名规范)
            if ".svg" in src:
                m = re.match(r"(.*/thumb/[0-9a-f]/[0-9a-f]{2}/([^/]+)\.svg)/\d+px-.*$", src)
                if m:
                    src = m.group(1) + "/500px-" + m.group(2) + ".svg.png"
                else:
                    continue
            try:
                req = urllib.request.Request(src, headers={"User-Agent": "daxue-shenmai/1.0"})
                with urllib.request.urlopen(req, timeout=20, context=_ctx()) as r:
                    data = r.read(4 * 1024 * 1024)
            except Exception:
                raw = summary.get(key, {}).get("source", "")
                try:
                    req = urllib.request.Request(raw, headers={"User-Agent": "daxue-shenmai/1.0"})
                    with urllib.request.urlopen(req, timeout=20, context=_ctx()) as r:
                        data = r.read(4 * 1024 * 1024)
                except Exception:
                    continue
            ext = ".png" if data[:8] == b"\x89PNG\r\n\x1a\n" else (
                ".jpg" if data[:3] == b"\xff\xd8\xff" else ".svg" if b"<svg" in data[:600] else ".png")
            os.makedirs(CAMPUS_DIR, exist_ok=True)
            fname = uni["id"] + ext
            with open(os.path.join(CAMPUS_DIR, fname), "wb") as f:
                f.write(data)
            lic, credit = _commons_license(src)
            img_rec = {
                "file": "/static/campus/" + fname,
                "title": uni["name"] + " 主图",
                "source_page": "https://en.wikipedia.org/wiki/" + uni["wiki_en"],
                "license": lic or "见来源页",
                "credit": (credit or "")[:120],
                "fetched": datetime.date.today().isoformat(),
                "load_tested": len(data) > 500,
                "purpose": "院校封面",
            }
            break
    if img_rec:
        return img_rec
    # 降级路径:Commons 校园实景(CC 许可)
    campus = commons_campus_photo(
        uni["name"] + " campus", IMG_TOKENS.get(uni["id"]))
    if campus:
        os.makedirs(CAMPUS_DIR, exist_ok=True)
        fname = uni["id"] + campus["ext"]
        with open(os.path.join(CAMPUS_DIR, fname), "wb") as f:
            f.write(campus["data"])
        return {
            "file": "/static/campus/" + fname,
            "title": campus["title"],
            "source_page": campus["source_page"],
            "license": campus["license"],
            "credit": campus["credit"],
            "fetched": datetime.date.today().isoformat(),
            "load_tested": True,
            "purpose": "院校封面(校园实景)",
        }
    return None


MONOLOGO = """<svg xmlns="http://www.w3.org/2000/svg" width="500" height="300" viewBox="0 0 500 300">
<rect width="500" height="300" fill="#0B2545"/>
<rect x="12" y="12" width="476" height="276" fill="none" stroke="#A9814B" stroke-opacity="0.5" stroke-width="2" rx="14"/>
<text x="250" y="165" font-size="120" fill="#E5C88F" text-anchor="middle"
 font-family="Georgia, 'Noto Serif SC', serif" font-weight="700">{ch}</text>
<text x="250" y="230" font-size="20" fill="#8FA3C2" text-anchor="middle" letter-spacing="4"
 font-family="sans-serif">{name}</text>
</svg>"""


def make_fallback_logo(uni):
    """无自由许可图片时的本地生成徽标(明确标注非官方图片)。"""
    os.makedirs(CAMPUS_DIR, exist_ok=True)
    fname = uni["id"] + "-fallback.svg"
    with open(os.path.join(CAMPUS_DIR, fname), "w", encoding="utf-8") as f:
        f.write(MONOLOGO.format(ch=uni["short"][0], name=uni["name"]))
    return {
        "file": "/static/campus/" + fname,
        "title": uni["name"] + " 占位徽标(本地生成)",
        "source_page": "",
        "license": "本系统生成(非官方图片)",
        "credit": "",
        "fetched": datetime.date.today().isoformat(),
        "load_tested": True,
        "purpose": "院校封面(降级)",
    }


def completeness(uni):
    filled = 0
    for f in TRACKED_FIELDS:
        v = uni.get(f)
        if f == "image":
            v = uni.get("image") or {}
            if v.get("load_tested"):
                filled += 1
        elif v not in (None, "", [], "待核实"):
            filled += 1
    return round(100 * filled / len(TRACKED_FIELDS))


def seed_universities(store, fetch_images=True):
    """初始化院校库(已存在则跳过)。fetch_images=True 时联网抓图。"""
    if store.load("universities"):
        return 0
    items = []
    for u in SEED_UNIVERSITIES:
        uni = {
            **{k: u[k] for k in ("id", "name", "short", "city", "campus",
                                 "official_site", "cs_school")},
            "priority": 0,            # 0 未标,1-3 关注度
            "program": "", "program_code": "", "degree_type": "",
            "exam_subjects": [], "uses_408": None,
            "admission_catalog_url": "", "retest_rules_url": "",
            "history_admission_url": "",
            "enrollment": None, "enrollment_year": None,
            "retest_line": None, "retest_line_year": None,
            "tuition": "", "duration_years": None,
            "intro": "", "notes": "",
            "admission_source": "", "admission_published": None,
            "last_verified": None,          # 人工核验时间
            "data_status": "基础信息已填,招生数据待核实",
            "image": None,
            "created": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        if fetch_images:
            img = fetch_university_image(uni) or make_fallback_logo(uni)
            uni["image"] = img
        items.append(uni)
    store.save("universities", items)
    return len(items)
