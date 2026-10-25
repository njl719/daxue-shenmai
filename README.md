# 大雪深埋 · AI 考研私人教练

本地优先的考研复习平台:间隔刷题、错题拍照、AI 反思教练、学习画像(带证据的薄弱点)、成长时间线、目标院校资料库、题库与个性化计划。AI 由本地 Ollama 驱动(qwen2.5),无云端依赖;模型不可用时全部基础功能照常。

![Python](https://img.shields.io/badge/Python-3.10+-3776AB) ![Flask](https://img.shields.io/badge/Flask-3.x-white) ![Tests](https://img.shields.io/badge/tests-117%20passed-brightgreen) ![License](https://img.shields.io/badge/license-MIT-blue)

## 功能一览

| 模块 | 说明 |
|---|---|
| 🏠 今日作战室 | 目标院校卡、四科状态、连续学习天数、下一项最值得做的任务(带依据) |
| 🎯 学习中心 | 间隔刷题(SRS)、错题本(拍照+AI 识别校对)、生词、题库(版权标注+哈希去重)、知识库 |
| 🤖 AI 教练 | 流式对话、反思结构化提取、工具提案(确认制)、本地 Ollama 默认 |
| 📈 成长 | 时间线、学习热力图、里程碑、经验库(来源/授权字段) |
| 🔭 情报站 | GitHub 搜索、来源清单+链接核验、10 所目标院校库(自由许可校园图)、数据质量报告 |
| 👤 个人中心 | 账号(PBKDF2)、各科水平自评、激励风格、审计日志、备份/导出/删除 |

## 本地运行

```bash
pip install flask
python run.py
# 打开 http://127.0.0.1:8321,首次进入创建账号
# 手机(同 Wi-Fi): http://<电脑IP>:8321,可添加到主屏幕当 App 用
```

测试:`pip install pytest && python -m pytest tests/ -q`(117 项)

## 一键部署为公开网站(Render,免费档)

点击下方按钮,登录 Render 后一键创建公网 HTTPS 实例:

[![Deploy to Render](https://render.com/images/deploy-to-render.svg)](https://render.com/deploy)

> 免费档说明:15 分钟无访问会休眠(首次打开慢约 1 分钟);磁盘是临时的,重新部署后数据重置——适合体验与演示,**个人长期数据请用本地运行**。Ollama 无法在免费云主机运行,AI 功能自动降级为规则解析(界面明确标注),其余功能完整。

其他平台:仓库含 `deploy/Dockerfile` 与 docker-compose(Caddy 自动 HTTPS),可部署到任何 Docker 主机。

## 隐私与数据

- 全部学习数据存于本地 `data/`(JSON + 图片),不上传任何第三方;
- 本仓库**不含任何个人学习数据**(见 .gitignore);
- 校园图片来自 Wikimedia Commons 自由许可资源,来源与许可见 `app/static/campus/CREDITS.md`。

## 目录结构

```
app/            后端(Flask)与前端(static/)
  ai.py         AI 适配层(本地 Ollama / 云端可选,流式+降级)
  questionbank.py 题库(哈希去重/版权标注/AI 生成标注)
  universities.py 院校库(自由许可图片管线)
  profile.py    学习画像与薄弱点(证据链)
  planner.py    复习计划引擎
data/           运行时生成,含全部学习数据(不入库)
tests/          117 项测试
docs/           设计/测试/部署/资源审计文档
```

## License

MIT(见 LICENSE)。 bundled 校园图片遵循各自许可(见 CREDITS)。
