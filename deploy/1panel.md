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

### 1.0 当前用户可用 Docker（避免事事 sudo）

`/opt` 下部署可以，但**不要用 `sudo ./deploy/*.sh`**（会引发权限混乱）。将登录用户加入 docker 组：

```bash
sudo usermod -aG docker "$USER"
# 退出 SSH 重新登录后验证：
docker ps
```

若仍提示 permission denied，再执行 `sudo chown -R "$USER":"$USER" /opt/buque`。

### 1.1 国内构建加速（ECS `.env` 建议配置）

```bash
DOCKER_REGISTRY_PREFIX=mirror.ccs.tencentyun.com/library/
DEBIAN_APT_MIRROR=mirrors.tencent.com
UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright
NPM_REGISTRY=https://registry.npmmirror.com
```

避免 `apt-get update` / `pip` / Playwright / npm 卡在境外源。本地 `make docker-ip-*` 会自动禁用上述项。

---

## 阶段 2：准备代码与 `.env`

### 方式 A：1Panel 终端

**容器 → 终端** 或 SSH：

```bash
sudo mkdir -p /opt/buque && sudo chown "$USER":"$USER" /opt/buque
cd /opt/buque
git clone <仓库地址> .
```

**勿用 `sudo git clone` / `sudo git pull`**，否则 `.git` 归 root 所有，后续 `ubuntu` 用户会报 `Permission denied`。

若目录已是 root 所有，修复：

```bash
sudo chown -R "$USER":"$USER" /opt/buque
```

`git pull` 若报 `HTTP2 framing layer`，在当前用户下执行一次：

```bash
git config --global http.version HTTP/1.1
git pull
```

仍失败可用本机 `rsync` 同步代码（见文末「git 拉取失败」）。

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

## git 拉取失败：本机 rsync 同步

ECS 访问 GitHub 不稳定时，在**本地 Mac**执行（排除 `.env`、`node_modules` 等）：

```bash
rsync -avz --delete \
  --exclude '.git' --exclude '.env' --exclude 'node_modules' --exclude 'backend/.venv' \
  --exclude 'backend/data' --exclude 'frontend/dist' \
  /Users/s/Documents/projects/buque/ ubuntu@<ECS公网IP>:/opt/buque/
```

服务器上单独 `scp` 上传 `.env`。同步后：

```bash
cd /opt/buque && ./deploy/migrate-ip.sh && ./deploy/up-ip.sh
```

---

## 故障排查

| 现象 | 处理 |
|------|------|
| build 拉镜像超时 | 先 `git pull` 用项目内镜像前缀；仍失败再 `sudo bash deploy/configure-docker-mirror.sh` |
| `dubious ownership` / `.git` 权限 | `sudo chown -R $USER:$USER /opt/buque`，勿 `sudo git pull` |
| `HTTP2 framing layer` | `git config --global http.version HTTP/1.1` 后重试 `git pull` |
| git 仍拉不下来 | 本机 `rsync` 同步（见下） |
| 无法访问 | 腾讯云安全组 + 1Panel 防火墙是否放行端口 |
| 80 启动失败 | 端口被占，改 `HTTP_PORT=8080` 并同步改 `SITE_URL` |
| 页面白屏 / API 404 | `SITE_URL` 与浏览器地址不一致 → 改 `.env` 后 **重新 build**：`./deploy/up-ip.sh` |
| 登录后跨域错误 | 同上，CORS 来自 `SITE_URL` |
| ERP 失败 | 确认 ECS 能访问积加；查 `logs api` |
