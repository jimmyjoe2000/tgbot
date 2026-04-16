# Deployment Notes

## Server Check Result

当前测试服务器已确认：

- 系统：Ubuntu 24.04.2 LTS
- 内存：约 8 GB
- 磁盘：50 GB
- Docker：未安装

这台机器满足首版部署要求，下一步只需要完成 Docker 初始化。

## Docker Bootstrap

仓库内置了 `install_docker_ubuntu.sh`，用于在 Ubuntu 22.04 / 24.04 上安装：

- Docker Engine
- Docker Compose Plugin
- Docker Buildx Plugin

脚本依据 Docker 官方 Ubuntu 安装流程整理，适合新机器首装。

