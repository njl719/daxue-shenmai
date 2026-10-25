# -*- coding: utf-8 -*-
"""院校资料库测试:种子/图片/完整度/年份绑定校验/优先级/比较数据。"""


def test_universities_seeded(client):
    """迁移 v4 后 10 所院校入库(测试环境关闭联网抓图,用降级徽标)。"""
    items = client.get("/api/universities").get_json()
    assert len(items) >= 10
    names = {u["name"] for u in items}
    assert {"清华大学", "北京大学", "浙江大学", "西安电子科技大学", "西南财经大学"} <= names
    for u in items:
        assert u["completeness"] >= 0
        img = u.get("image") or {}
        assert img.get("file", "").startswith("/static/campus/")
        assert "license" in img and "fetched" in img


def test_university_detail_and_search(client):
    one = client.get("/api/universities/tsinghua").get_json()
    assert one["name"] == "清华大学"
    assert one["city"] == "北京"
    lst = client.get("/api/universities?q=成都").get_json()
    assert all("成都" in (u["city"] + u["name"]) for u in lst)
    assert len(lst) >= 2  # 电子科大 + 西南财经


def test_enrollment_requires_year_and_source(client):
    rv = client.put("/api/universities/tsinghua",
                    json={"enrollment": 200})
    assert rv.status_code == 400 and "年份" in rv.get_json()["error"]
    rv = client.put("/api/universities/tsinghua",
                    json={"enrollment": 200, "enrollment_year": "2025"})
    assert rv.status_code == 400 and "来源" in rv.get_json()["error"]
    rv = client.put("/api/universities/tsinghua", json={
        "enrollment": 200, "enrollment_year": "2025",
        "admission_source": "清华研招网 2025 招生目录(用户核验)"})
    assert rv.status_code == 200
    j = rv.get_json()
    assert j["enrollment"] == 200 and j["enrollment_year"] == "2025"
    assert j["completeness"] > client.get("/api/universities/pku").get_json()["completeness"] - 30


def test_priority_ordering(client):
    client.put("/api/universities/zju", json={"priority": 3})
    client.put("/api/universities/pku", json={"priority": 2})
    items = client.get("/api/universities?order=priority").get_json()
    assert items[0]["id"] == "zju"


def test_verify_and_edit_flow(client):
    rv = client.post("/api/universities/whu/verify",
                     json={"result": "已对照 2026 招生目录核验"})
    assert rv.status_code == 200
    j = rv.get_json()
    assert j["last_verified"]
    assert "2026" in j["data_status"]
    # 编辑专业与 408
    rv = client.put("/api/universities/whu", json={
        "program": "计算机技术", "program_code": "085404",
        "degree_type": "专硕", "uses_408": True,
        "exam_subjects": ["101", "201", "302", "408"]})
    j = rv.get_json()
    assert j["program_code"] == "085404" and j["uses_408"] is True


def test_add_delete_university(client):
    rv = client.post("/api/universities", json={
        "name": "测试大学", "city": "测试市", "official_site": "https://t.edu.cn"})
    assert rv.status_code == 201
    uid = rv.get_json()["id"]
    assert rv.get_json()["image"]["file"].startswith("/static/campus/")
    assert client.delete("/api/universities/" + uid).status_code == 200
    assert client.get("/api/universities/" + uid).status_code == 404


def test_no_fabricated_admission_data(client):
    """种子数据不得包含编造的招生数字:10 所默认全部待核实。"""
    items = client.get("/api/universities").get_json()
    seeded = [u for u in items if u["id"] in (
        "tsinghua", "pku", "sjtu", "zju", "hust", "uestc", "xidian", "swufe", "whu", "scut")]
    for u in seeded:
        assert u["enrollment"] is None, u["id"] + " 不应预填招生人数"
        assert u["retest_line"] is None, u["id"] + " 不应预填复试线"
