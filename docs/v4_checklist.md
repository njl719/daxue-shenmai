# 第四轮清单:删除/保留功能(第一步产出)

## 删除(前端+后端+路由;数据文件保留)
- 本地 Ollama:local 模式、local_service_ok、list_local_models、LOCAL_BASE_URL、模型发现/切换 UI、Ollama 安装提示
- AI 顾问:#coach 页与 /api/coach/*(对话、流式、工具提案、反思对话入口)、/api/ai/coach-stream、/api/ai/recognize(错题OCR)、/api/tools/*
- 刷题系统:#study 全部页签及 /api/practice/*、/api/train/*、/api/questions*、/api/mistakes*、/api/vocab*、/api/images*(错题图上传)
- 说题/题库导入/题目管理/答题判题/复习队列/答题统计的专属端点与组件

## 保留(数据与逻辑,不再新增入口)
- 数据文件:mistakes/train/questions/vocab 等 json 历史数据**原样保留**(不删库)
- records/plan/reflections/profile/weekly:学习记录、时间统计、周报、画像(经典依据仍在,错题证据随历史数据冻结)
- planner:学习计划引擎(保留;到期错题任务随 legacy 数据自然减少)
- radar/admission/persona/mock_scores/decision/datasources:V2.0 决策与情报中心
- motivations(语录数据):并入经验贴页"今日一句"(只展示有出处条目)
- 云端 AI 接口(OpenAI 兼容):保留为经验贴 AI 分析的可选能力,未配 Key 时规则降级

## 重构
- 成长-经验库与语录 → 新「经验贴」页(12 分类/搜索/卡片/来源追溯/AI或规则拆解/今日一句)
- 首页 → 考研进度 + 重要提醒(brief)+ 近期动态(radar)
- 导航 → 首页/院校库/院校预测/经验贴/成长记录/设置(+数据源管理在情报站)
- 默认主题 → 浅色(玻璃质感方向),深色仍可切换
