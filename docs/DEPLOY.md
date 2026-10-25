# 公网 HTTPS 部署方案(需你提供账号;未实际部署)

当前状态:**未部署公网**。系统已在局域网可用(电脑 + 手机同 Wi-Fi)。
公网 HTTPS 需要以下任一资源,均涉及注册账号/付费/授权,必须由你操作或明确授权后我才能继续:

## 方案 A:Cloudflare Tunnel(推荐 · 免费 · 无需公网 IP)

1. 注册 [Cloudflare](https://dash.cloudflare.com/) 账号(免费);
2. 安装 cloudflared:`winget install Cloudflare.cloudflared`;
3. 登录:`cloudflared tunnel login`(浏览器授权);
4. 创建隧道并绑定你的域名(免费域名需托管到 Cloudflare):
   ```bash
   cloudflared tunnel create ascent
   cloudflared tunnel route dns ascent ascent.你的域名.com
   cloudflared tunnel run --url http://127.0.0.1:8321 ascent
   ```
5. 获得自动 HTTPS 的公网网址,源站无需开放端口。
需要你提供:Cloudflare 账号 + 一个域名(约 ¥10/年,或使用需账号的 trycloudflare 临时地址)。

## 方案 B:VPS + Caddy(全托管,自动 HTTPS)

1. 购买 VPS(如阿里云/腾讯云轻量 ¥30-60/月)+ 域名;
2. 使用本目录 `deploy/` 下的 Dockerfile 与 docker-compose:
   ```bash
   # 服务器上
   scp -r 上岸计划 user@vps:/opt/ascent
   cd /opt/ascent/deploy && docker compose up -d
   ```
3. Caddy 自动申请续期 HTTPS 证书(域名 A 记录指向 VPS)。
需要你提供:VPS + 域名。

## 方案 C:保持局域网(现状)

零成本零暴露;手机与电脑同 Wi-Fi 使用。数据永不离开你的机器。

## 无论哪种方案,部署前必须完成

- [ ] 设置强密码(登录页首次初始化时创建)
- [ ] 评估是否开放注册(当前单账号,建议保持)
- [ ] data/ 目录纳入加密备份(VPS 上建议每日 rsync 回本地)
- [ ] 生产环境变量:`DX_DATA_DIR` 指定数据目录;**不要**把密钥写进代码仓库

## deploy/ 目录内容(已就绪)

- `Dockerfile`:Python 3.11-slim + 应用 + 数据卷
- `docker-compose.yml`:应用 + Caddy(自动 HTTPS)+ 卷挂载
- `Caddyfile`:域名占位符,替换后自动签证书
