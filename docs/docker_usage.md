# Archery 自定义镜像使用指南

本指南说明构建好的自定义镜像（`fuyuntao/archeryplus:v1.14.0-custom`）如何推送、部署与使用。

## 一、当前镜像状态

```bash
docker images
# archery:v1.14.0-custom               ← 本地自定义镜像（源码构建）
# fuyuntao/archeryplus:v1.14.0-custom  ← 同一镜像的推送 tag
```

## 二、推送镜像到 Docker Hub（部署到其他机器前）

```bash
# 1. 登录 Docker Hub（输入 fuyuntao 账号密码）
docker login

# 2. 推送
docker push fuyuntao/archeryplus:v1.14.0-custom
```

> 若只在本机使用，可跳过本步骤。

## 三、部署

### 方式 A：docker-compose 全栈（推荐，含 MySQL/Redis/goinception）

**本机使用**（在项目 `src/docker-compose` 目录）：

```bash
cd D:\software\Archery-master\src\docker-compose
```

**服务器使用**（先复制 compose 目录到服务器）：

```bash
# 把 src/docker-compose 目录整个拷到服务器
scp -r src/docker-compose user@server:/opt/archery-deploy/
cd /opt/archery-deploy
```

**修改 `docker-compose.yml`**：把 archery 服务的 `image` 改为您的镜像：

```yaml
archery:
    image: fuyuntao/archeryplus:v1.14.0-custom   # 原来是 hhyo/archery:v1.14.0
    # ...其余不变
```

**启动**：

```bash
docker compose up -d        # 旧版 docker-compose up -d
```

启动后访问 **http://127.0.0.1:9123**（服务器则访问 `http://服务器IP:9123`）。

### 方式 B：单独运行 archery（复用已有 MySQL/Redis）

```bash
docker run -d --name archery -p 9123:9123 \
  -e DATABASE_URL='mysql://root:123456@mysql:3306/archery' \
  -e CACHE_URL='redis://redis:6379/0?PASSWORD=123456' \
  fuyuntao/archeryplus:v1.14.0-custom
```

## 四、首次初始化（必须）

进入容器执行迁移和初始化：

```bash
docker exec -it archery bash
cd /opt/archery
source venv4archery/bin/activate

# 1. 迁移（创建 Django 表）
python manage.py migrate

# 2. 导入基础数据 + managed=False 表（3 个 SQL 必须执行）
python manage.py dbshell < sql/fixtures/auth_group.sql
python manage.py dbshell < src/init_sql/mysql_slow_query_review.sql
python manage.py dbshell < src/init_sql/redis_slow_query_review.sql

# 3. 创建超级管理员
python manage.py createsuperuser
```

## 五、登录与使用

1. 浏览器访问 http://127.0.0.1:9123（或服务器 IP）
2. 用刚创建的超级管理员登录
3. 首次使用需在「实例管理」中添加数据库实例（MySQL/MSSQL/Oracle 等）
4. 添加实例后即可使用 SQL 查询、SQL 上线、数据导出、SQL 分析等功能

## 六、常用运维命令

```bash
# 查看日志
docker logs -f archery

# 查看服务状态（gunicorn / qcluster）
docker exec archery supervisorctl status

# 停止/启动
docker compose down        # 停止（compose 方式）
docker compose up -d       # 启动
docker stop archery && docker start archery   # 单容器方式

# 更新镜像（改了代码重新构建后）
docker compose pull && docker compose up -d   # 或重新 build 后替换 image
```

## 七、常见问题

1. **启动后访问 502/无法访问**：确认 `docker exec archery supervisorctl status` 中 gunicorn 与 qcluster 均 RUNNING
2. **Dashboard 报"表不存在"**：未执行第四步的初始化 SQL
3. **工作流卡排队**：qcluster 未运行，检查 supervisorctl status
4. **端口冲突**：修改 docker-compose.yml 的 `ports: - "9123:9123"` 为其他端口（如 `9124:9123`）
