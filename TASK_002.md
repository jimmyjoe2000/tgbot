# 任务：标准化 API 接口 + Docker 一键部署

## 需求描述

### 1. 标准化 API 接口
- 完善 FastAPI Swagger 文档
- 确保所有接口都有清晰的文档
- 便于 AI 前端自动生成代码

### 2. Docker 一键部署
- 创建 Dockerfile（后端）
- 创建 docker-compose.yml（完整编排）
- 创建一键部署脚本

## 需要完成的工作

### API 接口标准化

1. 检查所有 API 路由是否有完整的文档
2. 添加请求/响应示例
3. 添加错误码说明
4. 确保 Swagger UI 可访问

### Docker 部署

1. 创建 `Dockerfile`（多阶段构建，优化体积）
2. 完善 `docker-compose.yml`（包含所有服务）
3. 创建 `deploy.sh`（一键部署脚本）
4. 创建 `.env.example`（环境变量模板）

## 验收标准

1. ✅ Swagger 文档完整（/docs 可访问）
2. ✅ Docker 镜像可以正常构建
3. ✅ docker-compose up 可以启动所有服务
4. ✅ deploy.sh 可以一键部署
5. ✅ 测试环境可以正常运行

## 文件清单

- `Dockerfile` - 后端镜像
- `docker-compose.yml` - 服务编排
- `deploy.sh` - 部署脚本
- `.env.example` - 环境变量模板
- `README.md` - 部署说明
