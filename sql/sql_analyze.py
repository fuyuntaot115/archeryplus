# -*- coding: UTF-8 -*-
"""
@author: hhyo
@license: Apache Licence
@file: sql_analyze.py
@time: 2019/03/14
"""

from pathlib import Path

import simplejson as json
from django.contrib.auth.decorators import permission_required
from django.core.files.temp import NamedTemporaryFile

from common.config import SysConfig
from sql.plugins.soar import Soar
from sql.engines import get_engine
from sql.utils.resource_group import user_instances
from sql.utils.sql_utils import generate_sql
from django.http import HttpResponse, JsonResponse
from common.utils.extend_json_encoder import ExtendJSONEncoder
from .models import Instance

__author__ = "hhyo"

# MSSQL 执行计划分析时展示的关键列（SHOWPLAN_ALL 输出列较多，只展示重点）
MSSQL_PLAN_KEY_COLUMNS = [
    "StmtText",
    "PhysicalOp",
    "LogicalOp",
    "Argument",
    "EstimateRows",
    "EstimateIO",
    "EstimateCPU",
    "TotalSubtreeCost",
    "Parallel",
    "Warnings",
]


def _mssql_plan_to_markdown(result_set):
    """将 MSSQL SHOWPLAN_ALL 结果集转换为 markdown 报告（执行计划树 + 明细表格）"""
    if not result_set.column_list:
        return "无执行计划输出"
    cols = result_set.column_list
    lines = []

    # 1. 执行计划树（StmtText 列，缩进表示节点层级）
    if "StmtText" in cols:
        stmt_idx = cols.index("StmtText")
        plan_lines = []
        for row in result_set.rows:
            if stmt_idx < len(row) and row[stmt_idx] is not None:
                plan_lines.append(str(row[stmt_idx]).rstrip())
        if plan_lines:
            lines.append("### 执行计划树")
            lines.append("```text")
            lines.extend(plan_lines)
            lines.append("```")

    # 2. 关键列明细表格
    key_cols = [c for c in MSSQL_PLAN_KEY_COLUMNS if c in cols and c != "StmtText"]
    if key_cols:
        col_index = [cols.index(c) for c in key_cols]
        lines.append("### 执行计划明细")
        lines.append("| " + " | ".join(key_cols) + " |")
        lines.append("|" + "---|" * len(key_cols))
        for row in result_set.rows:
            cells = []
            for i in col_index:
                v = row[i] if i < len(row) else None
                if v is None:
                    cells.append("")
                else:
                    s = str(v)
                    s = s.replace("|", "\\|").replace("\n", "<br>").replace("\r", "")
                    cells.append(s)
            lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


@permission_required("sql.sql_analyze", raise_exception=True)
def generate(request):
    """
    解析上传文件为SQL列表
    :param request:
    :return:
    """
    text = request.POST.get("text")
    if text is None:
        result = {"total": 0, "rows": []}
    else:
        rows = generate_sql(text)
        result = {"total": len(rows), "rows": rows}
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


@permission_required("sql.sql_analyze", raise_exception=True)
def analyze(request):
    """
    利用soar分析SQL
    :param request:
    :return:
    """
    text = request.POST.get("text")
    instance_name = request.POST.get("instance_name")
    db_name = request.POST.get("db_name")
    if not text:
        result = {"total": 0, "rows": []}
    else:
        rows = generate_sql(text)
        instance = None
        if instance_name and db_name:
            try:
                instance = user_instances(request.user, db_type=["mysql", "mssql"]).get(
                    instance_name=instance_name
                )
            except Instance.DoesNotExist:
                return JsonResponse(
                    {"status": 1, "msg": "你所在组未关联该实例！", "data": []}
                )
        for row in rows:
            # 验证是不是传过来的文件, 如果是文件, 报错
            try:
                p = Path(row["sql"].strip())
                if p.exists():
                    return JsonResponse(
                        {"status": 1, "msg": "SQL 语句不合法", "data": []}
                    )
            except OSError:
                pass
            if instance is not None and instance.db_type == "mssql":
                # MSSQL：使用 SQL Server 执行计划（SET SHOWPLAN_ALL ON）分析
                engine = get_engine(instance=instance)
                plan_sql = "SET SHOWPLAN_ALL ON;\n{}\nSET SHOWPLAN_ALL OFF;".format(
                    row["sql"]
                )
                result_set = engine.query(db_name=db_name, sql=plan_sql)
                if result_set.error:
                    row["report"] = "MSSQL 执行计划生成失败：{}".format(
                        result_set.error
                    )
                else:
                    row["report"] = _mssql_plan_to_markdown(result_set)
                continue
            soar = Soar()
            if instance is not None and db_name:
                soar_test_dsn = SysConfig().get("soar_test_dsn")
                # 获取实例连接信息
                user, password = instance.get_username_password()
                online_dsn = f"{user}:{password}@{instance.host}:{instance.port}/{db_name}"
            else:
                online_dsn = ""
                soar_test_dsn = ""
            args = {
                "report-type": "markdown",
                "query": "",
                "online-dsn": online_dsn,
                "test-dsn": soar_test_dsn,
                "allow-online-as-test": False,
            }
            args["query"] = row["sql"]
            cmd_args = soar.generate_args2cmd(args=args)
            stdout, stderr = soar.execute_cmd(cmd_args).communicate()
            row["report"] = stdout if stdout else stderr
        result = {"total": len(rows), "rows": rows}
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )
