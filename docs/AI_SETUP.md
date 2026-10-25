# AI 配置指南(本地模型优先)

## 当前部署状态(2026-10-25,已完成)

| 项 | 值 |
|---|---|
| 推理服务 | Ollama 0.40.10(本机 127.0.0.1:11434,已随系统部署) |
| 主模型 | `qwen2.5:7b-instruct-q4_K_M`(4.7GB,Q4 量化,Apache-2.0) |
| 视觉模型 | `qwen2.5vl:7b`(6.0GB,错题拍照识别,Qwen 研究许可证) |
| 模型存储 | `E:\ollama\models`(用户环境变量 `OLLAMA_MODELS` 指向;C 盘留有完整副本作回退) |
| 云端 API | 默认关闭,未配置(可选扩展) |
| 评测结果 | **8/8 通过**,见 [BENCHMARK.md](BENCHMARK.md) |

硬件适配依据:RTX 4060 Laptop(8GB 显存)→ 7B Q4 量化模型可全量驻留显存(实测 6.4/8.2GB,26 tok/s,冷加载 7s)。

## 日常使用(无需任何配置)

系统默认使用本地 Ollama,**不需要 API Key**。打开「AI 教练」页看到"本地模型 qwen2.5…"即正常;错题拍照页点"AI 识别此图"走 qwen2.5vl。

## 模型管理

```bash
ollama list                     # 查看已下载模型
ollama pull qwen2.5:7b-instruct-q4_K_M   # 下载主力模型
ollama pull qwen2.5vl:7b                 # 下载视觉模型
ollama pull qwen2.5:3b-instruct-q4_K_M   # 显存不足时的轻量替代(2.2GB)
```

设置页可随时切换主/视觉模型(列表自动从本机 Ollama 发现,不假设已安装)。

## 云端 API(可选,默认关闭)

设置 → AI 模型 → 切换"云端 API",填 Base URL / API Key / 模型名(如智谱 `https://open.bigmodel.cn/api/paas/v4` + glm-4-flash)。Key 只存本地,界面显示掩码。也可用环境变量:`ZHIPUAI_API_KEY`、`DEEPSEEK_API_KEY`、`OPENAI_API_KEY` 等(自动带默认模型)。

## 数据与隐私

- 图片、对话、学习数据全部保存在本地 `data/`;
- 使用本地模型时,**任何数据都不出你的电脑**;
- 使用云端模型时,仅当次识别/对话所需内容发送给你自己配置的服务;
- 密钥不写入日志;界面只显示掩码。

## 部署过程记录与回滚方式(2026-10-25)

1. 诊断:Ollama 0.40.8 已安装运行,仅 `deepseek-r1:1.5b` 本地模型(实测不适合作主力);C 盘空间紧张 → 迁移模型库。
2. 迁移:`OLLAMA_MODELS=E:\ollama\models`(setx 写入用户环境变量,注册表 `HKCU\Environment`);模型复制到 E 盘。**回滚:删除该环境变量 + 重启 Ollama 即回到 C 盘**。
3. 下载两个模型(约 11GB)。期间发现两个 Ollama 行为并已处置:
   - **自动更新**把 0.40.8 升到 0.40.10,更新器重启的 serve 不继承会话环境变量 → 改用 ProcessStartInfo 显式注入环境变量启动;
   - **启动清理**:serve 启动时会清理"无 manifest 引用的悬空 blob",下载中断的半截文件会被删(E 盘 3.4GB→1.1GB 由此而来),最终以 C 盘完整下载为准再整体同步到 E 盘。
4. C 盘与 E 盘当前各有一份完整模型(11GB);C 盘空间已充足(62.9GB 空闲),两份并存互为备份。

## AI 不可用时的降级(已实测)

Ollama 停止时:AI 状态如实显示"未运行";错题/计划/画像/周报/导出全部照常;反思自动回退到内置规则解析(界面标注"未调用 AI");对话返回诚实的启动指引而非伪造回复。
