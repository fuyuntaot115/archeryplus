# Archery 本地二次开发部署指南

> 本文档基于本项目实际开发环境整理，用于在本地搭建可二次开发的 Archery 环境。
> 涵盖环境搭建、数据库初始化、服务启动、已定制功能说明、测试与常见问题。

---

## 一、环境要求

| 组件 | 版本 | 说明 |
|---|---|---|
| Python | 3.10 ~ 3.13 | 本项目使用 3.13 |
| MySQL | 5.7 / 8.0 | Archery 主库（本项目 8.0 兼容，本地用 5.7/8.0 均可） |
| Redis | 5+ | django-q 异步队列 |
| Git | 2.x | 版本管理 |
| Docker | 可选 | 构建/运行镜像 |

### MySQL 性能优化（重要）

MySQL 默认 `innodb_buffer_pool_size=8M` 会导致建表/迁移极慢。建议调大：

```sql
SET GLOBAL innodb_buffer_pool_size = 268435456;      -- 256M
SET GLOBAL innodb_flush_log_at_trx_commit = 2;
```

> 否则首次 `migrate` 建库可能耗时 100+ 秒。

---

## 二、环境搭建

### 1. 克隆/进入项目

```bash
cd D:\software\Archery-master        # Windows
# cd /path/to/Archery-master         # Linux/macOS
```

### 2. 创建虚拟环境并安装依赖

```bash
# Windows PowerShell
python -m venv venv_archery
.\venv_archery\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r dev-requirements.txt   # 测试依赖（pytest 等）

# Linux/macOS
python3 -m venv venv_archery
source venv_archery/bin/activate
pip install -r requirements.txt
pip install -r dev-requirements.txt
```

> `dev-requirements.txt` 中 `pytest-django==4.9.0` 已固定（4.14 不兼容 Django 4.2）。

### 3. 配置 `.env`

复制 `.env.list` 为 `.env` 并修改：

```ini
DEBUG=true
DATABASE_URL=mysql://root:123456@127.0.0.1:3306/archery
CACHE_URL=redis://127.0.0.1:6379/0
SECRET_KEY="你的随机密钥"
ALLOWED_HOSTS=*
Q_CLUSTER_WORKERS=4
Q_CLUSTER_TIMEOUT=60
Q_CLUISTER_SYNC=true      # 调试时同步模式便于看任务日志
```

> 本地开发把 `DEBUG` 设为 `true`，可避免模板缓存问题（否则改模板需重启）。

---

## 三、数据库初始化

### 1. 创建数据库

```sql
CREATE DATABASE archery CHARACTER SET utf8mb4;
```

### 2. 迁移 + 导入初始化 SQL（必须）

```bash
python manage.py migrate
python manage.py dbshell < sql/fixtures/auth_group.sql
python manage.py dbshell < src/init_sql/mysql_slow_query_review.sql
python manage.py dbshell < src/init_sql/redis_slow_query_review.sql
```

> 后 3 个 SQL 创建 `managed=False` 的表（慢查询历史等），**必须执行**，否则 Dashboard/慢查询功能报错。

### 3. 创建超级管理员

```bash
python manage.py createsuperuser
```

---

## 四、启动服务

### Web 服务器（必须 `--insecure --noreload`）

```bash
python manage.py runserver 127.0.0.1:8000 --insecure --noreload
```

> - `--insecure`：ManifestStaticFilesStorage 需要，否则静态资源 404
> - `--noreload`：配合 `DEBUG=false` 时避免自动重载
> - **改模板后必须重启**（非 DEBUG 下有模板缓存）

### 异步任务队列（必须运行，否则工作流卡排队）

```bash
python manage.py qcluster
```

> 在另一个终端运行。负责 SQL 上线工单执行、通知等异步任务。

### 访问

浏览器打开 http://127.0.0.1:8000 ，用创建的超级管理员登录。

---

## 五、添加 MSSQL 测试实例（二次开发用）

| 项 | 值 |
|---|---|
| 实例名 | `local_MSSQL2019` |
| 地址 | 192.168.123.21:1433 |
| 数据库 | `test` |
| 测试表 | `dbo.fyt`（id bigint, name nvarchar(100)，无主键 heap） |

在「实例管理」中新增实例，db_type 选 `mssql`，并打上 `can_read` 标签（用于查询/导出权限）。

---

## 六、本项目已定制功能（二次开发参考）

| 功能 | 位置 | 说明 |
|---|---|---|
| MSSQL 备份/回滚 | `sql/engines/mssql.py` | 工作流 DML 自动生成回滚 SQL，表 `mssql_sql_rollback` 运行时自动创建 |
| MSSQL2SQL 工具 | `sql/plugins/mssql_log_rollback.py` + `sql/mssql_log_rollback.py` | 事务日志回滚（ApexSQL Log 风格），支持 int/bigint/nchar/nvarchar |
| MSSQL 会话管理 | `sql/db_diagnostic.py` | processlist / Top 表空间 / 事务 / 锁 |
| SQL 分析 MSSQL | `sql/sql_analyze.py` | 用 `SET SHOWPLAN_ALL` 生成执行计划报告 |
| SQL 优化 MSSQL + AI | `sql/sql_optimize.py` + `sql/templates/sqladvisor.html` | AI 优化接口（OpenAI 兼容），需配置 openai_base_url/api_key/default_chat_model |
| 数据导出 MSSQL | `sql/templates/sqlexportsubmit.html` | 修复校验（limit_num）+ 结果取数 |
| 在线查询导出 | `sql/templates/sqlquery.html` | 修复导出文件名 prompt 问题 |
| MSSQL 高危过滤 | 配置项 `MSSQL_CRITICAL_DDL_REGEX` | 空时回退通用 `critical_ddl_regex` |
| MSSQL 自动补 GO | `sql/templates/sqlsubmit.html` | 提交时自动在语句间加 GO |
| Dashboard 修复 | `common/templates/dashboard.html` | 移除 10 分钟模板缓存；慢查询表缺失容错 |

### 常用配置项（系统管理 → 配置项管理）

- `mssql_critical_ddl_regex`：MSSQL 专属高危 SQL 正则（如 `^\s*drop\s+table`）
- `OPENAI_BASE_URL` / `OPENAI_API_KEY` / `DEFAULT_CHAT_MODEL`：AI 优化接口
- `max_export_rows`：数据导出行数阈值
- `storage_type`：数据导出存储类型（Local/SFTP/S3）

---

## 七、运行测试

```bash
# Windows
.\scripts\run_pytest.ps1
# 或直接
python -m pytest -q --reuse-db

# Linux/macOS
bash scripts/run_pytest.sh
```

要点：
- 需要 MySQL 可访问（自动创建 `test_archery` 测试库）
- 首次建测试库较慢（约 1-3 分钟），之后 `--reuse-db` 复用
- 单个用例 120s 超时保护（pytest-timeout）
- 未装 `oracledb` 时 Oracle 引擎测试自动跳过（可选依赖）

---

## 八、常见问题排查

| 现象 | 原因 / 解决 |
|---|---|
| 静态文件 404 / JS 不生效 | 用 `--insecure` 启动，或先 `collectstatic` |
| 改模板不生效 | 非 DEBUG 模板缓存 → 重启 runserver；或 `DEBUG=true` |
| 工作流卡在排队 | qcluster 未运行 → 启动 `python manage.py qcluster` |
| Dashboard 报"表不存在" | 未导入 3 个初始化 SQL（见第三节） |
| 数据导出校验 Bad Request | 已修复（limit_num）；确认前端是最新模板 |
| MSSQL 连不上 | 检查 ODBC 驱动（ODBC Driver 17/18）、实例可达性 |
| 测试库迁移慢 | 调大 MySQL `innodb_buffer_pool_size` |
| Oracle 不可用 | `pip install oracledb` |

---

## 九、二次开发工作流建议

1. **改 Python 代码**：改完重启 runserver（`--noreload` 不自动重载）
2. **改模板/前端**：改完重启 runserver（模板有缓存）
3. **改模型**：`python manage.py makemigrations sql && python manage.py migrate`
4. **验证**：`python manage.py check` + 定向 pytest + 浏览器实测
5. **提交**：`git add -A && git commit && git push`（远程 `fuyuntaot115/archeryplus`）
