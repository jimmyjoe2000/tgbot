# Telegram Command Center

这是一个以 Telegram 机器人为唯一操作入口的运维与交付中枢。目标是把日常的客户录入、到期提醒、部署执行、域名解析和续费确认，逐步从“人工处理”升级成“系统指挥”。

当前仓库已经完成首版后端脚手架、Bot 管理入口、Docker 部署链路和测试服务器初始化，可作为后续继续开发和迁移环境的基础版本。

## 项目目标

- 用 Telegram Bot 作为管理员唯一入口
- 用 FastAPI 作为业务中枢和接口中心
- 用 PostgreSQL 保存客户、域名、服务器、账单、部署任务
- 用 Redis 和 Worker 承担定时任务与后台任务
- 通过配置化实现多客户共用一套逻辑
- 逐步接入 Cloudflare DNS、SSH 部署、USDT 支付确认、AI 文案/前端生成

## 当前架构

- 服务器区域：阿里云新加坡
- 操作系统：Ubuntu 24.04 LTS
- 部署方式：Docker Compose
- 多租户方式：业务级隔离
- Bot 模式：`long polling`
- 域名方案：阿里云注册，DNS 后续托管到 Cloudflare
- 首版范围：只做 Telegram 管理，不做 Web 后台
- 语言：中文

## 代码结构

```text
app/
  api/          FastAPI 路由
  bot/          Telegram Bot 指令处理
  core/         配置读取
  db/           SQLAlchemy 模型与数据库初始化
  schemas/      Pydantic 响应模型
  services/     DNS / SSH / 支付等服务层
  worker/       APScheduler 后台任务
deploy/
  install_docker_ubuntu.sh   Ubuntu Docker 初始化脚本
```

## 已实现内容

- FastAPI 基础应用和健康检查接口
- Telegram 管理 Bot 基础指令
- PostgreSQL / Redis / API / Bot / Worker 的 Docker Compose 编排
- 客户、域名、服务器、账单、部署任务、通知日志数据模型
- `/status` 管理汇总接口和 Bot 展示逻辑
- `/add 客户名 服务器IP 域名 到期日期` 录入骨架
- `/my` 查询客户基础配置
- 每日到期扫描任务框架
- Cloudflare DNS 服务封装骨架
- SSH 部署服务封装骨架
- USDT 链上查询服务封装骨架
- Ubuntu 24.04 测试机 Docker 自动安装脚本

## 关键文件

- [`app/main.py`](app/main.py)
- [`app/bot/handlers.py`](app/bot/handlers.py)
- [`app/db/models.py`](app/db/models.py)
- [`app/services/deploy/ssh.py`](app/services/deploy/ssh.py)
- [`docker-compose.yml`](docker-compose.yml)
- [`deploy/install_docker_ubuntu.sh`](deploy/install_docker_ubuntu.sh)

## 环境变量

以 [`.env.example`](.env.example) 为模板。

最少需要：

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ADMIN_USER_ID`
- `ADMIN_API_TOKEN`
- `POSTGRES_PASSWORD`
- `CLOUDFLARE_API_TOKEN`
- `DEPLOY_SSH_PRIVATE_KEY_PATH`

测试期如果暂时没有私钥，也支持：

- `DEPLOY_SSH_PASSWORD`

注意：

- 真实 `.env` 已存在于本地与测试服务器，但不纳入版本库
- 所有敏感信息在本文档中均已脱敏

## 本地运行

1. 复制环境变量模板

```bash
cp .env.example .env
```

2. 安装依赖

```bash
py -m pip install --user -e .
```

3. 启动容器

```bash
docker compose up --build
```

4. 常用验证接口

- `GET /api/v1/health`
- `GET /api/v1/admin/summary`
- `GET /api/v1/public/config/{customer_code}`

`/api/v1/admin/summary` 需要请求头：

```text
X-Admin-Token: <your-admin-token>
```

## Telegram 指令

- `/start` 查看帮助
- `/status` 查看系统总览和到期提醒
- `/add 客户名 服务器IP 域名 到期日期`
- `/my 客户名或客户代号`

示例：

```text
/add 客户A 1.1.1.1 example.com 2027-01-01
```

## 测试服务器执行情况

已完成：

- 测试服务器已确认是 `Ubuntu 24.04.2 LTS`
- 机器资源约为 `8 GB RAM / 50 GB Disk`
- 已安装 Docker Engine、Docker Compose Plugin、Buildx
- 项目已上传到服务器目录 `/opt/telegram-command-center`
- 当前容器 `api / bot / worker / db / redis` 均已启动
- 容器内健康检查通过
- Telegram Bot Token 已通过 `getMe` 校验

当前已知问题：

- 服务器内 `8000` 端口监听正常
- 容器内访问 `http://127.0.0.1:8000/api/v1/health` 正常
- 从公网访问 `http://<server-ip>:8000/api/v1/health` 超时
- 高概率原因是阿里云安全组尚未放行 `TCP 8000`

## 沟通记录整理

以下为本轮对话的脱敏整理版，用于后续换环境继续接手。

### 需求确认

- 核心目标是“去人工化”，把你从手工中转切换成系统指挥
- 技术栈确定为 `FastAPI + Telegram Bot + Docker + AI 前端`
- 首版只做 Telegram 管理，不做网页管理后台
- 管理 Bot 只给你自己使用
- 客户侧全部使用独立域名
- 客户代码不放在你本机
- 支付方式计划为 USDT，由系统生成金额并通过第三方链上接口确认到账
- AI 侧计划接入 OpenAI 和百炼

### 基础设施决策

- 云厂商：阿里云
- 区域：新加坡
- 系统：Ubuntu 22.04/24.04 LTS，最终落地为 Ubuntu 24.04
- 多租户隔离：先做业务级隔离
- 域名：阿里云注册，后续切到 Cloudflare 做 DNS 托管
- 部署方式：通过 SSH 执行
- Bot 首版：先使用 `long polling`

### 本轮已完成执行

- 从空目录开始搭建项目结构
- 建立 `FastAPI + Bot + Worker + Postgres + Redis` 脚手架
- 增加核心数据模型和服务层骨架
- 增加 Dockerfile、docker-compose 和部署脚本
- 生成管理员 API Token，并写入本地 `.env`
- 加入 SSH 密码登录兼容，便于测试服务器直接接入
- 远程连接测试服务器，检查系统、内存、磁盘、Docker 状态
- 远程安装 Docker / Compose
- 将项目上传并在测试机启动容器
- 验证 API 健康检查与 Telegram Bot Token

### 当前仍待补充

- Cloudflare API Token
- 测试域名
- USDT 链上查询服务接口
- 正式环境 SSH 私钥
- 阿里云安全组端口放行策略

### 安全说明

- 这次对话里出现过真实 Bot Token 和服务器密码
- README 中没有原样保留这些敏感值
- 换环境前建议轮换：
  - Telegram Bot Token
  - 测试服务器 root 密码
  - 后续 Cloudflare Token

## 下一步建议

按优先级建议继续：

1. 阿里云安全组放行测试所需端口，至少确认 `8000` 是否开放
2. 提供 Cloudflare API Token 和测试域名，接入自动解析
3. 提供 USDT 链上查询服务接口，接入订单确认
4. 把 SSH 从密码认证切到私钥认证
5. 增加 Alembic 迁移和首批种子数据
6. 增加部署任务执行、日志落库和失败重试

## 迁移到新环境时的最小步骤

1. 准备一台 Ubuntu 24.04 服务器
2. 执行 [`deploy/install_docker_ubuntu.sh`](deploy/install_docker_ubuntu.sh)
3. 拷贝项目代码与 `.env`
4. 执行 `docker compose up -d --build`
5. 在 Telegram 中验证 `/start`、`/status`、`/add`

## 备注

这个仓库当前是一个可继续开发的首版基础工程，不是最终成品。已经打通了最重要的项目起步路径：代码骨架、配置结构、容器部署和真实服务器启动。后续只需要继续把 Cloudflare、支付确认、部署执行和通知闭环逐步接上即可。
