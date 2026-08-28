# Archery 多平台部署指南

Archery 支持 Linux / macOS / Windows 三种平台部署，也支持 Docker（最通用）。

## 环境要求

- Python 3.10 ~ 3.13
- MySQL 5.7 / 8.0（Archery 主库，生产建议 MySQL 8.0）
- Redis（django-q 队列）
- 依赖：`pip install -r requirements.txt`

> **MySQL 性能建议**：Archery 建表/迁移较多，测试库迁移耗时与 MySQL 配置强相关。
> 建议生产/测试 MySQL 至少配置：
> ```ini
> innodb_buffer_pool_size = 256M   # 按内存比例设置（默认 8M 会极慢）
> innodb_flush_log_at_trx_commit = 2
> ```
> 否则执行 `manage.py migrate`（首次建库）可能耗时数分钟。

## 一、Docker 部署（最通用，三平台一致）

```bash
# 构建镜像（含 nginx + gunicorn + supervisor）
docker build -f src/docker/Dockerfile -t archery:latest .
# 运行（需自行准备 MySQL/Redis，参考 src/docker-compose）
docker run -d -p 9123:9123 \
  -e DATABASE_URL=mysql://user:pwd@host:3306/archery \
  -e CACHE_URL=redis://host:6379/0 \
  archery:latest
```

Docker 镜像内置 nginx(9123) + gunicorn(8888) + qcluster，跨平台可用。

## 二、Linux / macOS 手动部署

使用仓库自带 bash 脚本（依赖 `supervisord` 与 `gunicorn`）：

```bash
# 1. 初始化（创建 venv 并安装依赖）
sh admin.sh init

# 2. 配置 .env（数据库、Redis、SECRET_KEY 等）
#    参考 .env.example

# 3. 迁移数据库
sh admin.sh migration

# 4. 创建超级管理员
sh admin.sh adduser

# 5. 启动（collectstatic + supervisord 启动 gunicorn + qcluster）
sh admin.sh start
```

supervisord 管理 gunicorn(8888) 与 qcluster；可用 `sh admin.sh stop|restart` 管理。

## 三、Windows 手动部署

Windows 上 `gunicorn` / `supervisord` 不可用，改用 **waitress**（纯 Python WSGI 服务器）与 PowerShell 脚本：

```powershell
# 1. 初始化（创建 .venv 并安装依赖，含 waitress）
.\scripts\deploy_windows.ps1 -Init

# 2. 配置 .env（复制 .env.example 修改）

# 3. 迁移数据库
.\scripts\deploy_windows.ps1 -Migrate

# 4. 创建超级管理员
.\scripts\deploy_windows.ps1 -AddUser

# 5. 启动（collectstatic + waitress Web(8888) + qcluster 后台）
.\scripts\start_windows.ps1
# 可选参数: -WebOnly 仅启动 Web；-Port 9123 指定端口
```

> 生产建议用 NSSM / 任务计划程序把 `start_windows.ps1` 注册为 Windows 服务/开机自启。

## 四、运行测试（三平台）

```bash
# Linux / macOS
bash scripts/run_pytest.sh

# Windows PowerShell
.\scripts\run_pytest.ps1
```

测试说明：
- 需要 MySQL 可访问（创建测试库 `test_archery`，首次约 1-3 分钟）
- 默认 `--reuse-db` 复用测试库加速；CI 可用 `--create-db` 强制重建
- 单个用例 120s 超时保护（`pytest-timeout`）
- 未安装 `oracledb` 时 Oracle 引擎测试自动跳过（可选依赖）

## 五、平台差异与注意事项

| 项目 | Linux/macOS | Windows |
|------|-------------|---------|
| 部署脚本 | `startup.sh` / `admin.sh` | `scripts/*.ps1` |
| WSGI 服务器 | gunicorn | waitress |
| 进程管理 | supervisord | 前台进程 / NSSM |
| 异步任务 | qcluster（supervisord 托管） | qcluster（`start_windows.ps1` 后台启动） |

- 代码中所有路径均使用 `os.path.join(settings.BASE_DIR, ...)`，跨平台安全
- 外部工具（soar / sqladvisor / my2sql / schemasync 等）通过配置指定路径，需按平台安装对应二进制
- 静态文件使用 `ManifestStaticFilesStorage`，务必先执行 `collectstatic`

## 六、常见问题

1. **collectstatic 后 JS/CSS 404**：开发环境请以 `--insecure` 启动 runserver，或先 `collectstatic`
2. **工作流卡在排队中**：确认 `python manage.py qcluster` 已运行
3. **测试库迁移慢**：按上文优化 MySQL 的 `innodb_buffer_pool_size`
4. **Oracle 引擎不可用**：`pip install oracledb`（已含在 requirements.txt）

## 七、初始化必须导入的 SQL（重要）

`manage.py migrate` 只创建 Django 管理的表（`managed=True`）。以下表为 `managed=False`，**必须手动导入**初始化 SQL 创建：

| 表 | 初始化 SQL | 功能 |
|---|---|---|
| mysql_slow_query_review(_history) | `src/init_sql/mysql_slow_query_review.sql` | MySQL 慢查询历史 |
| redis_slow_query_review(_history) | `src/init_sql/redis_slow_query_review.sql` | Redis 慢查询历史 |
| redis_slowlog_cursor | `src/init_sql/redis_slow_query_review.sql` | Redis 慢日志游标 |
| sql_rollback | 运行时自动创建 | Oracle 回滚 |
| mssql_sql_rollback | 运行时自动创建 | MSSQL 回滚 |
| auth_group 初始数据 | `sql/fixtures/auth_group.sql` | 默认权限组 |

Linux/macOS 执行（admin.sh migration 已包含）：
```bash
python3 manage.py dbshell < sql/fixtures/auth_group.sql
python3 manage.py dbshell < src/init_sql/mysql_slow_query_review.sql
python3 manage.py dbshell < src/init_sql/redis_slow_query_review.sql
```

Windows / Docker 手动部署请同样导入上述 3 个 SQL（Docker 进入容器后执行）。
> 未导入 redis 慢查询表时，Redis 慢日志/相关 Dashboard 统计会报错（表不存在）。
