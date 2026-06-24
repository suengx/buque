# 腾讯云 ECS 生产部署指引

> **未备案 / 纯 IP + 1Panel**：见 [`1panel.md`](1panel.md)（`docker-compose.ip.yml` + `SITE_URL`）。

## 前置条件

| 项 | 建议 |
|----|------|
| ECS | Ubuntu 22.04/24.04，≥ 4C8G（Playwright + 订单导出耗内存） |
| 安全组 | 放行 22（SSH）、80、443 |
| 域名 | A 记录指向 ECS 公网 IP |
| 仓库 | `git clone` 到 `/opt/buque` 或 CI 发布 |

## 1. 安装 Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"
# 重新登录 SSH 后
docker compose version
```

## 2. 配置环境

开发与生产共用根目录 **`.env`**。本地怎么配，上 ECS 就怎么拷过去——**不用改 `DATABASE_URL`、`CORS_ORIGINS`、`VITE_API_BASE_URL`**，`docker-compose.prod.yml` 会按 `DOMAIN` 自动覆盖。

```bash
cd /opt/buque
cp .env.example .env   # 或 scp 本地已有 .env
# 生产只需补：
#   DOMAIN=buque.company.com
#   ACME_EMAIL=ops@company.com
#   POSTGRES_PASSWORD=<可选，默认 buque；改后 compose 自动拼 DATABASE_URL>
openssl rand -base64 32   # JWT_SECRET 若尚未设置
```

本地前端 dev 时，`VITE_GOOGLE_CLIENT_ID` 与 `GOOGLE_CLIENT_ID` 填同一值（生产构建只读 `GOOGLE_CLIENT_ID`）。

## 3. 首次部署

```bash
chmod +x deploy/*.sh
./deploy/migrate.sh    # 可选：compose up 也会自动跑 migrate
./deploy/up.sh
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f api scheduler
```

## 4. Google OAuth

在 [Google Cloud Console](https://console.cloud.google.com/) 的 OAuth 客户端中增加：

- 已授权的 JavaScript 来源：`https://<你的域名>`
- 已授权的重定向 URI：`https://<你的域名>/login`（按前端实际回调调整）

`GOOGLE_CLIENT_ID` 与 `VITE_GOOGLE_CLIENT_ID` 填同一值。

## 5. 验证清单

- [ ] `curl -f https://<域名>/api/v1/health`
- [ ] 浏览器打开 `https://<域名>` 可登录
- [ ] 顶栏「数据同步」手动跑通 ERP 日批
- [ ] `docker compose -f docker-compose.prod.yml logs scheduler` 显示「调度器已启动 每日 06:00」
- [ ] 次日 06:00 后日报有新快照（或 `docker compose exec api buque-job` 试跑，`BUQUE_USE_ERP=1` 写入 compose 环境）

## 6. 手动触发日批

```bash
docker compose -f docker-compose.prod.yml exec -e BUQUE_USE_ERP=1 api buque-job
```

## 7. 数据库备份（建议 crontab 每日）

```bash
# crontab -e
0 2 * * * /opt/buque/deploy/backup-db.sh >> /var/log/buque-backup.log 2>&1
```

## 8. 更新发布

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

## 故障排查

| 现象 | 处理 |
|------|------|
| Caddy 证书失败 | 检查域名 DNS、80/443 是否可达 |
| ERP 同步超时 | 调大 `ERP_*_TIMEOUT_MS`；查 ECS 能否访问积加 |
| 监控助手无响应 | 检查 `ANTHROPIC_*` 配置 |
| scheduler 未跑 | `docker compose logs scheduler`；确认 ERP 已配置 |

验收材料见 [`docs/delivery/补雀_一期交付验收确认表.xlsx`](../docs/delivery/补雀_一期交付验收确认表.xlsx)。
