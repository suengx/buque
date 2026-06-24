# 1Panel + IP 访问部署指引（未备案）

无域名备案时走 **HTTP + 公网 IP**，使用 `docker-compose.ip.yml`。有备案域名后改回 `docker-compose.prod.yml` + `DOMAIN`。

## 架构

```
浏览器 http://<公网IP>[:端口]
    → Caddy :80（容器内）
        /api/* → api:8000
        /*     → web:3000
    postgres / scheduler（内网）
```

Google 登录在纯 IP 下通常不可用，请保持 `AUTH_PASSWORD_ENABLED=true`。

---

## 阶段 0：腾讯云 ECS

| 项 | 建议 |
|----|------|
| 规格 | 4C8G+，系统盘 ≥40GB |
| 系统 | Ubuntu 22.04 / 24.04 |
| 安全组入站 | **22**、**80**（若用 8080 则再加 **8080**） |
| 公网 IP | 记下，例如 `43.x.x.x` |

---

## 阶段 1：安装 1Panel

SSH 登录 ECS 后执行（以 1Panel 官网最新安装命令为准）：

```bash
curl -sS https://resource.fit2cloud.com/1panel/package/quick_start.sh -o quick_start.sh
sudo bash quick_start.sh
```

安装完成后记录：

- 1Panel 面板地址（一般为 `http://<IP>:端口`）
- 用户名 / 密码

在 1Panel **防火墙** 中放行 80（或你选用的 HTTP 端口）。

### 1.1 Docker 镜像拉取（项目内已配置，一般无需手动）

`docker-compose.ip.yml` 默认经 **腾讯云镜像** `mirror.ccs.tencentyun.com/library/` 拉取 `python` / `node` / `postgres` / `caddy`，**`git pull` 后直接部署即可**。

仅当仍超时时，再执行兜底脚本（改 Docker 守护进程全局配置）：

```bash
sudo bash deploy/configure-docker-mirror.sh
```

---

## 阶段 2：准备代码与 `.env`

### 方式 A：1Panel 终端

**容器 → 终端** 或 SSH：

```bash
sudo mkdir -p /opt/buque && sudo chown "$USER":"$USER" /opt/buque
cd /opt/buque
git clone <仓库地址> .
```

### 方式 B：本地上传 `.env`

本地已配好 ERP/LLM 时：

```bash
scp .env ubuntu@<ECS公网IP>:/opt/buque/.env
```

### `.env` 必填项（IP 模式）

在原有配置基础上增加 / 修改：

```bash
# IP 访问（无备案）— 与浏览器地址栏完全一致，含 http、无尾部斜杠
SITE_URL=http://43.x.x.x
# 若 80 被 1Panel 占用，compose 用 HTTP_PORT=8080，则：
# SITE_URL=http://43.x.x.x:8080
# HTTP_PORT=8080

# 以下保持你本地已有配置即可
ERP_BASE_URL=...
ERP_USERNAME=...
ERP_PASSWORD=...
ANTHROPIC_AUTH_TOKEN=...
JWT_SECRET=...
AUTH_PASSWORD_ENABLED=true
```

**不要填** `DOMAIN`（域名模式再用）。`DATABASE_URL` 仍保持 `localhost` 默认值，Compose 会自动改为 `postgres`。

---

## 阶段 3：在 1Panel 部署 Compose

### 3.1 端口冲突检查

1Panel 若已占用宿主机 **80**，二选一：

| 方案 | 做法 |
|------|------|
| **推荐** | `.env` 设 `HTTP_PORT=8080`，`SITE_URL=http://<IP>:8080`，安全组放行 8080 |
| 进阶 | 停 1Panel 网站服务，让补雀占 80（一般不推荐） |

### 3.2 创建编排

1. 1Panel → **容器** → **编排** → **创建编排**
2. 名称：`buque`
3. 路径：`/opt/buque`
4. 编排文件：选择 **`docker-compose.ip.yml`**
5. 环境变量：勾选读取目录下 **`.env`**
6. 保存并 **启动**

### 3.3 或用命令行（等价）

```bash
cd /opt/buque
chmod +x deploy/*.sh
./deploy/migrate-ip.sh   # 首次
./deploy/up-ip.sh
```

首次 **build 约 10–20 分钟**（Playwright + 前端）。

---

## 阶段 4：验证

```bash
# 在 ECS 上
docker compose -f docker-compose.ip.yml ps
curl -f http://<公网IP>/api/v1/health
# 若用 8080：curl -f http://<公网IP>:8080/api/v1/health
```

浏览器打开 `SITE_URL` 与之一致的地址，邮箱密码登录。

手动 ERP 日批：

```bash
docker compose -f docker-compose.ip.yml exec -e BUQUE_USE_ERP=1 api buque-job
```

定时任务（每日 06:00）：

```bash
docker compose -f docker-compose.ip.yml logs scheduler | tail -20
```

---

## 阶段 5：日常运维（1Panel）

| 操作 | 做法 |
|------|------|
| 看日志 | 编排 → buque → 日志（或 `docker compose -f docker-compose.ip.yml logs -f api`） |
| 重启 | 编排 → 重启 |
| 更新 | 终端 `cd /opt/buque && git pull && ./deploy/up-ip.sh` |
| 备份 DB | `crontab -e` 加入 `0 2 * * * /opt/buque/deploy/backup-db-ip.sh` |

---

## 阶段 6：日后有备案域名

1. DNS A 记录 → ECS IP  
2. `.env` 设 `DOMAIN=buque.xxx.com`、`ACME_EMAIL=...`  
3. 停用 IP 编排，改用 `docker-compose.prod.yml` + `./deploy/up.sh`  
4. 配置 Google OAuth（可选）

---

## 故障排查

| 现象 | 处理 |
|------|------|
| build 拉镜像超时 | 先 `git pull` 用项目内镜像前缀；仍失败再 `sudo bash deploy/configure-docker-mirror.sh` |
| 无法访问 | 腾讯云安全组 + 1Panel 防火墙是否放行端口 |
| 80 启动失败 | 端口被占，改 `HTTP_PORT=8080` 并同步改 `SITE_URL` |
| 页面白屏 / API 404 | `SITE_URL` 与浏览器地址不一致 → 改 `.env` 后 **重新 build**：`./deploy/up-ip.sh` |
| 登录后跨域错误 | 同上，CORS 来自 `SITE_URL` |
| ERP 失败 | 确认 ECS 能访问积加；查 `logs api` |
