# Archery Docker 镜像制作指南

本文档说明如何将 Archery 代码制作成 Docker 镜像并部署。

## 一、前置条件

- 安装 Docker（Windows 用 Docker Desktop；Linux/macOS 安装对应 Docker Engine）
- 确认 Docker 运行正常：
  ```bash
  docker version
  ```

## 二、镜像构建原理

项目自带完整构建体系，包含**两个镜像**：

| 镜像 | 文件 | 内容 |
|---|---|---|
| 基础镜像 `archery-base` | `src/docker/Dockerfile-base` + `setup.sh` | Python 3.11 + sqladvisor/soar/my2sql/mongo 客户端 + msodbcsql18(Oracle客户端) + percona-toolkit + `venv4archery` 虚拟环境 |
| 应用镜像 `archery` | `src/docker/Dockerfile` | 拷贝代码到 `/opt/archery/`、安装 Python 依赖、配置 nginx + supervisord + qcluster |

构建时**必须以项目根目录为上下文**（Dockerfile 里 `COPY . /opt/archery/`），`.dockerignore` 已排除 venv/.env/.git 等。

## 三、方式一：使用官方基础镜像构建（推荐）

默认 `Dockerfile` 自动从 Docker Hub 拉取基础镜像 `hhyo/archery-base:sha-d8159f4`：

```bash
cd D:\software\Archery-master        # Windows PowerShell
# 或 cd /path/to/Archery-master      # Linux/macOS

docker build -f src/docker/Dockerfile -t archery:v1.14.0 .
```

> 首次构建需拉取约 1-2 GB 基础镜像并安装依赖，耗时约 10-20 分钟。

## 四、方式二：本地构建基础镜像（自定义 / 拉取失败时）

```bash
cd /path/to/Archery-master

# 1. 构建基础镜像（setup.sh 会下载 sqladvisor/soar/my2sql/mongo/oracle 客户端等）
docker build -f src/docker/Dockerfile-base -t archery-base:local .

# 2. 基于本地基础镜像构建应用镜像
docker build -f src/docker/Dockerfile --build-arg BASE_IMAGE=archery-base:local -t archery:v1.14.0 .
```

## 五、构建验证

```bash
# 查看镜像
docker images | grep archery

# 冒烟测试（临时启动查看日志）
docker run --rm archery:v1.14.0 echo "image ok"
```

## 六、运行

### 方式 A：docker-compose 一键启动（含 MySQL/Redis/goinception）

```bash
cd src/docker-compose

# 编辑 docker-compose.yml，把 archery 服务的 image 改为本地构建的 archery:v1.14.0
#   image: archery:v1.14.0

# 首次启动
docker compose up -d
```

访问 http://127.0.0.1:9123

> 首次启动后需进入容器初始化（见第七节）。

### 方式 B：单独运行（复用已有 MySQL/Redis）

```bash
docker run -d --name archery -p 9123:9123 \
  -e DATABASE_URL='mysql://root:123456@mysql:3306/archery' \
  -e CACHE_URL='redis://redis:6379/0?PASSWORD=123456' \
  archery:v1.14.0
```

## 七、首次初始化（必须）

`Dockerfile` / `startup.sh` 只负责收集静态文件并启动服务，**不含数据库迁移和初始化**。首次启动后进入容器执行：

```bash
docker exec -it archery bash
cd /opt/archery
source venv4archery/bin/activate

# 1. 数据库迁移（创建 Django 管理的表）
python manage.py migrate

# 2. 导入基础数据 + managed=False 表（3 个 SQL 必须执行）
python manage.py dbshell < sql/fixtures/auth_group.sql
python manage.py dbshell < src/init_sql/mysql_slow_query_review.sql
python manage.py dbshell < src/init_sql/redis_slow_query_review.sql

# 3. 创建超级管理员
python manage.py createsuperuser
```

> 注意：`mysql_slow_query_review` / `redis_slow_query_review` 等表为 `managed=False`，**必须**导入对应 SQL，否则慢查询/Dashboard 相关功能会报错。

## 八、容器内常用命令

```bash
# 查看日志
docker logs -f archery

# 查看运行状态
docker exec archery supervisorctl status

# 进入容器
docker exec -it archery bash

# 停止/启动/重启
docker compose down / up -d        # compose 方式
docker stop archery && docker start archery   # run 方式
```

## 九、常见问题

1. **构建拉取基础镜像慢/失败**：配置 Docker 镜像加速器，或用方式二本地构建基础镜像
2. **cx-Oracle 安装失败**：Dockerfile 已用 `setuptools<82` + `--no-build-isolation` 处理；如仍失败，检查网络能否访问 PyPI
3. **collectstatic 报错**：确认 `.dockerignore` 未排除 static 目录，且以项目根为构建上下文
4. **工作流卡在排队中**：确认容器内 qcluster 已启动（supervisord 管理），`docker exec archery supervisorctl status`
5. **Dashboard 报"表不存在"**：确认已执行第七节的 3 个初始化 SQL
6. **9123 端口被本地 runserver 占用，Docker 容器"失效"**：
   - 现象：容器已启动、镜像正确，但访问 http://127.0.0.1:9123 行为异常（旧代码/旧页面），`docker stop archery` 后 9123 仍能访问
   - 根因：宿主机上残留的 `python manage.py runserver 127.0.0.1:9123 ...` 进程占用了 9123，Docker 的端口映射从未生效
   - 排查：`Get-NetTCPConnection -LocalPort 9123 -State Listen` 查看监听进程，若 PID 是 `python.exe` 且命令行含 `manage.py runserver`，即被本地进程占用
   - 解决：杀掉本地 runserver 释放 9123，再 `docker start archery`。**切勿同时用 runserver 和 Docker 监听同一端口**
7. **docker-compose 使用官方镜像导致无定制功能**：确保 `docker-compose.yml` 的 archery 服务 `image` 为 `fuyuntao/archeryplus:v1.14.0-custom`（官方 `hhyo/archery` 无 MSSQL2SQL 等定制功能）
8. **compose 启动后 gunicorn 报 `SECRET_KEY` 为空**：`src/docker-compose/.env` 的 `SECRET_KEY` 不能为空，从根目录 `.env` 复制
9. **compose 内置 MySQL 与宿主机 3306 端口冲突**：若宿主机已有 MySQL，将 compose 改为复用宿主机（`DATABASE_URL=mysql://root:xxx@host.docker.internal:3306/archery`、`CACHE_URL=redis://host.docker.internal:6379/0`），并移除内置 redis/mysql 服务
10. **修改模板/代码后容器仍显示旧内容**：容器运行的是镜像内的代码，`docker cp` 或本地修改不会持久（重建容器即还原）。必须**增量重建镜像**再重建容器：
    ```bash
    docker build -f src/docker/Dockerfile.hotfix -t fuyuntao/archeryplus:v1.14.0-custom .
    cd src/docker-compose && docker compose up -d --force-recreate archery
    ```
    `Dockerfile.hotfix` 基于已推送镜像快速覆盖修复文件（见仓库 `src/docker/Dockerfile.hotfix`）
11. **MSSQL2SQL 生成回滚 SQL 范围**：工具默认"生成回滚草稿"仅基于**当前查询结果**（所选时间范围/条件下查到的记录），需先点"查询"再点"生成回滚草稿"；直接生成会提示"请先点击查询"
