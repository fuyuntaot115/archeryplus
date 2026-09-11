# -*- coding: UTF-8 -*-
"""
合服工具（工具插件 - 合服管理）核心逻辑。

职责：
1. 维护合服 5 个步骤的默认 SQL 清单（默认值来自 ``server_merge_sql/`` 目录下的模板文件）；
2. 把第一步选择的库信息渲染为 SQL 变量；
3. 按步骤把多条 SQL 拆分为 GO 批次，在目标库上以事务方式执行。
"""

import logging
import os
import re
import time
import traceback

from sql.engines import get_engine

logger = logging.getLogger("default")

DEFAULT_SQL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server_merge_sql")

# 步骤定义，与前端横向流程条保持一致
STEP_DEFINITIONS = [
    {"step": 2, "title": "创建外部数据源和存储过程"},
    {"step": 3, "title": "复制和清理(Pre_work/Copy/Delete)"},
    {"step": 4, "title": "数据写入(Insert)"},
    {"step": 5, "title": "后处理(Post_work)"},
]

MODULE_ORDER = ["common", "game", "front", "index"]

# 第一步模块库配置里可选的模块（模块下拉框的选项）
CONFIG_MODULES = ["game", "front"]

MODULE_LABELS = {
    "common": "通用",
    "game": "GAME",
    "front": "FRONT",
    "index": "INDEX",
}

# 可在页面上编辑并落库的默认 SQL 清单
# run_on: target=目标库所在实例 & 模块目标库, source=源库所在实例 & 模块源库
DEFAULT_ITEMS = [
    {
        "step": 2,
        "modules": ("common",),
        "seq": 1,
        "title": "创建外部数据源(链接服务器)",
        "file": "common/02_01_linked_server.sql",
        "run_on": "target",
    },
    {
        "step": 2,
        "modules": ("game", "front"),
        "seq": 2,
        "title": "创建 UP_COPY_TABLE 存储过程",
        "file": "common/02_02_up_copy_table.sql",
        "run_on": "target",
    },
    {
        "step": 2,
        "modules": ("index",),
        "seq": 3,
        "title": "创建 MergeMapping 映射表(INDEX 库)",
        "file": "common/02_03_merge_mapping.sql",
        "run_on": "target",
    },
    {
        "step": 3,
        "modules": ("game",),
        "seq": 1,
        "title": "GAME 源库预处理(Pre_work)",
        "file": "game/03_01_pre_work.sql",
        "run_on": "source",
    },
    {
        "step": 3,
        "modules": ("game",),
        "seq": 2,
        "title": "GAME 复制(Copy)",
        "file": "game/03_02_copy.sql",
        "run_on": "target",
    },
    {
        "step": 3,
        "modules": ("game",),
        "seq": 3,
        "title": "GAME 清理(Delete)",
        "file": "game/03_03_delete.sql",
        "run_on": "target",
    },
    {
        "step": 3,
        "modules": ("front",),
        "seq": 1,
        "title": "FRONT 源库预处理(Pre_work)",
        "file": "front/03_01_pre_work.sql",
        "run_on": "source",
    },
    {
        "step": 3,
        "modules": ("front",),
        "seq": 2,
        "title": "FRONT 复制(Copy)",
        "file": "front/03_02_copy.sql",
        "run_on": "target",
    },
    {
        "step": 3,
        "modules": ("front",),
        "seq": 3,
        "title": "FRONT 清理(Delete)",
        "file": "front/03_03_delete.sql",
        "run_on": "target",
    },
    {
        "step": 4,
        "modules": ("game",),
        "seq": 1,
        "title": "GAME 数据写入(Insert)",
        "file": "game/04_01_insert.sql",
        "run_on": "target",
    },
    {
        "step": 4,
        "modules": ("front",),
        "seq": 1,
        "title": "FRONT 数据写入(Insert)",
        "file": "front/04_01_insert.sql",
        "run_on": "target",
    },
    {
        "step": 5,
        "modules": ("game",),
        "seq": 1,
        "title": "GAME 后处理(Post_work)",
        "file": "game/05_01_post_work.sql",
        "run_on": "target",
    },
    {
        "step": 5,
        "modules": ("front",),
        "seq": 1,
        "title": "FRONT 后处理(Post_work)",
        "file": "front/05_01_post_work.sql",
        "run_on": "target",
    },
    {
        "step": 5,
        "modules": ("index",),
        "seq": 1,
        "title": "INDEX 库数据变更(Data_Change)",
        "file": "index/05_01_data_change.sql",
        "run_on": "target",
    },
]

# 内部变量：不需要在页面上填写，全部由第一步的选择自动推导
DEFAULT_VARIABLES = {
    "LINKED_SERVER": "XDS",
}

VARIABLE_PATTERN = re.compile(r"\{\{\s*([A-Z0-9_]+)\s*\}\}")

# 需要 INDEX 库才能渲染的占位符（game/front Post_work 跨库引用 MergeMapping）
INDEX_DB_PLACEHOLDER = "{{INDEX_DB}}"

GO_PATTERN = re.compile(r"^\s*GO\s*(\d+)?\s*$", re.IGNORECASE)


class ServerMergeError(Exception):
    """合服执行异常"""


def load_default_sql(relative_file):
    """读取代码库内自带的默认 SQL 模板文件"""
    path = os.path.join(DEFAULT_SQL_DIR, relative_file)
    if not os.path.isfile(path):
        raise ServerMergeError("默认 SQL 模板不存在：%s" % relative_file)
    with open(path, "r", encoding="utf-8") as fp:
        return fp.read()


def step_items(step):
    """返回指定步骤的默认条目定义"""
    return [item for item in DEFAULT_ITEMS if item["step"] == step]


def describe_default_items(step, modules, index_db=""):
    """
    组装指定步骤在给定模块下的默认条目（未合并数据库覆盖值）
    :param step: 步骤编号
    :param modules: 已启用的模块列表，如 ["game", "front"]
    :param index_db: INDEX 库名，为空表示未配置 INDEX 库，此时不返回 index 相关条目
    """
    items = []
    for item in step_items(step):
        for module in item["modules"]:
            if module == "common":
                if modules:
                    items.append(
                        {
                            "step": step,
                            "module": "common",
                            "seq": item["seq"],
                            "title": item["title"],
                            "run_on": item["run_on"],
                            "sql": load_default_sql(item["file"]),
                        }
                    )
                continue
            if module == "index":
                if index_db:
                    items.append(
                        {
                            "step": step,
                            "module": "index",
                            "seq": item["seq"],
                            "title": item["title"],
                            "run_on": item["run_on"],
                            "sql": load_default_sql(item["file"]),
                        }
                    )
                continue
            if module in modules:
                items.append(
                    {
                        "step": step,
                        "module": module,
                        "seq": item["seq"],
                        "title": item["title"],
                        "run_on": item["run_on"],
                        "sql": load_default_sql(item["file"]),
                    }
                )
    return items


def build_variables(payload=None):
    """构造内部变量，页面不再需要填写任何合服变量"""
    variables = dict(DEFAULT_VARIABLES)
    payload = payload or {}
    linked_server = str(payload.get("linked_server") or "").strip()
    if linked_server:
        variables["LINKED_SERVER"] = linked_server
    return variables


def find_default_item(step, module, seq):
    """按 (步骤, 模块, 序号) 查找默认条目定义（不受模块是否配置影响）"""
    for entry in step_items(step):
        if module not in entry["modules"] or entry["seq"] != seq:
            continue
        return {
            "step": step,
            "module": module,
            "seq": seq,
            "title": entry["title"],
            "run_on": entry["run_on"],
            "sql": load_default_sql(entry["file"]),
        }
    return None


def render_sql(sql, variables):
    """
    使用第一步的配置渲染 SQL 变量。
    变量值中的单引号会被转义，避免破坏 SQL 字面量。
    """
    def _replace(match):
        key = match.group(1)
        value = variables.get(key)
        if value is None:
            raise ServerMergeError("SQL 中存在未定义的变量：{{%s}}" % key)
        return str(value).replace("'", "''")

    return VARIABLE_PATTERN.sub(_replace, sql)


def _clean_line_for_go(line, state):
    """
    去掉行内注释/字符串内容，仅用于判断是否为 GO 批次分隔行。
    state 用于跨行跟踪块注释与字符串字面量。
    """
    result = []
    index = 0
    length = len(line)
    while index < length:
        char = line[index]
        if state["block"]:
            if char == "*" and index + 1 < length and line[index + 1] == "/":
                state["block"] = False
                index += 2
                continue
            index += 1
            continue
        if state["string"]:
            if char == "'":
                if index + 1 < length and line[index + 1] == "'":
                    index += 2
                    continue
                state["string"] = False
            index += 1
            continue
        if char == "-" and index + 1 < length and line[index + 1] == "-":
            break
        if char == "/" and index + 1 < length and line[index + 1] == "*":
            state["block"] = True
            index += 2
            continue
        if char == "'":
            state["string"] = True
            index += 1
            continue
        result.append(char)
        index += 1
    return "".join(result)


def split_batches(script):
    """
    按 GO 把脚本拆分为可独立提交的批次。
    GO 是客户端批次分隔符，不能直接交给驱动执行。
    """
    batches = []
    current = []
    state = {"block": False, "string": False}
    for line in script.split("\n"):
        cleaned = _clean_line_for_go(line, state)
        if GO_PATTERN.match(cleaned):
            batch = "\n".join(current).strip()
            if batch:
                batches.append(batch)
            current = []
            continue
        current.append(line)
    batch = "\n".join(current).strip()
    if batch:
        batches.append(batch)
    return batches


def quote_name(name):
    """SQL Server 标识符加方括号"""
    return "[{}]".format(str(name).replace("]", "]]"))


class ServerMergeRunner:
    """
    合服 SQL 执行器。

    同一个实例上的该步骤 SQL 共用一个连接与一个事务，
    步骤内出现跨实例（源库预处理）时按实例分别开启事务，最终一起提交；
    任一条 SQL 失败则全部回滚。
    """

    def __init__(self, instances):
        """
        :param instances: {instance_name: Instance} 本步骤涉及到的实例
        """
        self.instances = instances
        self.engines = {}
        self.connections = {}
        self.current_db = {}

    def _connection(self, instance_name, db_name):
        if instance_name not in self.connections:
            instance = self.instances[instance_name]
            if instance.db_type != "mssql":
                raise ServerMergeError("合服功能仅支持 MSSQL 实例：%s" % instance_name)
            engine = get_engine(instance=instance)
            conn = engine.get_connection()
            conn.autocommit = False
            try:
                conn.timeout = 0  # 大数据量复制不设置查询超时
            except Exception:  # pragma: no cover - 某些驱动不支持该属性
                logger.warning("设置连接超时失败", exc_info=True)
            self.engines[instance_name] = engine
            self.connections[instance_name] = conn
            self.current_db[instance_name] = None

        conn = self.connections[instance_name]
        if db_name and self.current_db[instance_name] != db_name:
            cursor = conn.cursor()
            cursor.execute("USE {}".format(quote_name(db_name)))
            cursor.close()
            self.current_db[instance_name] = db_name
        return conn

    @staticmethod
    def _run_batch(cursor, batch):
        cursor.execute(batch)
        affected = 0
        while True:
            if cursor.description is not None:
                cursor.fetchall()
            elif cursor.rowcount and cursor.rowcount > 0:
                affected += cursor.rowcount
            if not cursor.nextset():
                break
        return affected

    @staticmethod
    def _empty_result(status, error=""):
        return {
            "status": status,
            "affected_rows": 0,
            "cost_time": 0,
            "batch_count": 0,
            "error": error,
        }

    def _rollback_all(self):
        for conn in self.connections.values():
            try:
                conn.rollback()
            except Exception:  # pragma: no cover - 回滚失败仅记录
                logger.warning("合服回滚失败", exc_info=True)

    def execute(self, items):
        """
        按顺序执行条目，返回 (结果列表, 错误信息)。
        整个步骤共用一个事务，任意条目失败则整体回滚；
        条目显式关闭事务时改为逐条提交。
        :param items: [{"instance_name","db_name","sql","step","module","seq","title","run_on","use_transaction"}]
        """
        results = []
        step_transaction = all(item.get("use_transaction", True) for item in items)
        error_message = ""
        try:
            for item in items:
                started = time.time()
                affected = 0
                batches = split_batches(item["sql"])
                try:
                    conn = self._connection(item["instance_name"], item.get("db_name"))
                    cursor = conn.cursor()
                    try:
                        for batch in batches:
                            affected += self._run_batch(cursor, batch)
                    finally:
                        cursor.close()
                    if not step_transaction:
                        conn.commit()
                    results.append(
                        {
                            "status": "success",
                            "affected_rows": affected,
                            "cost_time": round(time.time() - started, 3),
                            "batch_count": len(batches),
                            "error": "",
                        }
                    )
                except Exception as exc:  # noqa: BLE001 - 需要把原始错误回传页面
                    logger.error(
                        "合服步骤 %s-%s 执行失败：%s",
                        item.get("step"),
                        item.get("title"),
                        traceback.format_exc(),
                    )
                    results.append(
                        {
                            "status": "failed",
                            "affected_rows": affected,
                            "cost_time": round(time.time() - started, 3),
                            "batch_count": len(batches),
                            "error": str(exc),
                        }
                    )
                    error_message = str(exc)
                    raise ServerMergeError(str(exc))
            if step_transaction:
                for conn in self.connections.values():
                    conn.commit()
        except ServerMergeError:
            if step_transaction:
                self._rollback_all()
            # 失败之后的条目补齐为 skipped，便于前端完整渲染
            for _ in range(len(results), len(items)):
                results.append(
                    self._empty_result("skipped", "前序 SQL 执行失败，已跳过")
                )
        finally:
            for engine in self.engines.values():
                try:
                    engine.close()
                except Exception:  # pragma: no cover
                    logger.warning("合服连接关闭失败", exc_info=True)
        return results, error_message
