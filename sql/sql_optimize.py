# -*- coding: UTF-8 -*-
"""
@author: hhyo
@license: Apache Licence
@file: sql_optimize.py
@time: 2019/03/04
"""

import MySQLdb
import re

import simplejson as json
import sqlparse
from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse
from common.config import SysConfig
from common.utils.extend_json_encoder import ExtendJSONEncoder
from common.utils.openai import OpenaiClient, check_openai_config
from sql.engines import get_engine
from sql.models import Instance
from sql.plugins.soar import Soar
from sql.plugins.sqladvisor import SQLAdvisor
from sql.sql_tuning import SqlTuning
from sql.utils.resource_group import user_instances

__author__ = "hhyo"


@permission_required("sql.optimize_sqladvisor", raise_exception=True)
def optimize_sqladvisor(request):
    sql_content = request.POST.get("sql_content")
    instance_name = request.POST.get("instance_name")
    db_name = request.POST.get("db_name")
    verbose = request.POST.get("verbose", 1)
    result = {"status": 0, "msg": "ok", "data": []}

    # 服务器端参数验证
    if sql_content is None or instance_name is None:
        result["status"] = 1
        result["msg"] = "页面提交参数可能为空"
        return HttpResponse(json.dumps(result), content_type="application/json")

    try:
        instance_info = user_instances(request.user, db_type=["mysql"]).get(
            instance_name=instance_name
        )
    except Instance.DoesNotExist:
        result["status"] = 1
        result["msg"] = "你所在组未关联该实例！"
        return HttpResponse(json.dumps(result), content_type="application/json")

    # 检查sqladvisor程序路径
    sqladvisor_path = SysConfig().get("sqladvisor")
    if sqladvisor_path is None:
        result["status"] = 1
        result["msg"] = "请配置SQLAdvisor路径！"
        return HttpResponse(json.dumps(result), content_type="application/json")

    # 提交给sqladvisor获取分析报告
    sqladvisor = SQLAdvisor()
    # 准备参数
    args = {
        "h": instance_info.host,
        "P": instance_info.port,
        "u": instance_info.user,
        "p": instance_info.password,
        "d": db_name,
        "v": verbose,
        "q": sql_content.strip(),
    }

    # 参数检查
    args_check_result = sqladvisor.check_args(args)
    if args_check_result["status"] == 1:
        return HttpResponse(
            json.dumps(args_check_result), content_type="application/json"
        )
    # 参数转换
    cmd_args = sqladvisor.generate_args2cmd(args)
    # 执行命令
    try:
        stdout, stderr = sqladvisor.execute_cmd(cmd_args).communicate()
        result["data"] = f"{stdout}{stderr}"
    except RuntimeError as e:
        result["status"] = 1
        result["msg"] = str(e)
    return HttpResponse(json.dumps(result), content_type="application/json")


@permission_required("sql.optimize_soar", raise_exception=True)
def optimize_soar(request):
    instance_name = request.POST.get("instance_name")
    db_name = request.POST.get("db_name")
    sql = request.POST.get("sql")
    result = {"status": 0, "msg": "ok", "data": []}

    # 服务器端参数验证
    if not (instance_name and db_name and sql):
        result["status"] = 1
        result["msg"] = "页面提交参数可能为空"
        return HttpResponse(json.dumps(result), content_type="application/json")
    try:
        instance = user_instances(request.user, db_type=["mysql"]).get(
            instance_name=instance_name
        )
    except Exception:
        result["status"] = 1
        result["msg"] = "你所在组未关联该实例"
        return HttpResponse(json.dumps(result), content_type="application/json")

    # 检查测试实例的连接信息和soar程序路径
    soar_test_dsn = SysConfig().get("soar_test_dsn")
    soar_path = SysConfig().get("soar")
    if not (soar_path and soar_test_dsn):
        result["status"] = 1
        result["msg"] = "请配置soar_path和test_dsn！"
        return HttpResponse(json.dumps(result), content_type="application/json")

    # 目标实例的连接信息
    online_dsn = (
        f"{instance.user}:{instance.password}@{instance.host}:{instance.port}/{db_name}"
    )

    # 提交给soar获取分析报告
    soar = Soar()
    # 准备参数
    args = {
        "online-dsn": online_dsn,
        "test-dsn": soar_test_dsn,
        "allow-online-as-test": False,
        "report-type": "markdown",
        "query": sql.strip(),
    }
    # 参数检查
    args_check_result = soar.check_args(args)
    if args_check_result["status"] == 1:
        return HttpResponse(
            json.dumps(args_check_result), content_type="application/json"
        )
    # 参数转换
    cmd_args = soar.generate_args2cmd(args)
    # 执行命令
    try:
        stdout, stderr = soar.execute_cmd(cmd_args).communicate()
        result["data"] = stdout if stdout else stderr
    except RuntimeError as e:
        result["status"] = 1
        result["msg"] = str(e)
    return HttpResponse(json.dumps(result), content_type="application/json")


@permission_required("sql.optimize_sqltuning", raise_exception=True)
def optimize_sqltuning(request):
    instance_name = request.POST.get("instance_name")
    db_name = request.POST.get("db_name")
    sqltext = request.POST.get("sql_content")
    option = request.POST.getlist("option[]")
    sqltext = sqlparse.format(sqltext, strip_comments=True)
    sqltext = sqlparse.split(sqltext)[0]
    if re.match(r"^select|^show|^explain", sqltext, re.I) is None:
        result = {"status": 1, "msg": "只支持查询SQL！", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")
    try:
        user_instances(request.user).get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {"status": 1, "msg": "你所在组未关联该实例！", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")

    sql_tunning = SqlTuning(
        instance_name=instance_name, db_name=db_name, sqltext=sqltext
    )
    result = {"status": 0, "msg": "ok", "data": {}}
    if "sys_parm" in option:
        basic_information = sql_tunning.basic_information()
        sys_parameter = sql_tunning.sys_parameter()
        optimizer_switch = sql_tunning.optimizer_switch()
        result["data"]["basic_information"] = basic_information
        result["data"]["sys_parameter"] = sys_parameter
        result["data"]["optimizer_switch"] = optimizer_switch
    if "sql_plan" in option:
        plan, optimizer_rewrite_sql = sql_tunning.sqlplan()
        result["data"]["optimizer_rewrite_sql"] = optimizer_rewrite_sql
        result["data"]["plan"] = plan
    if "obj_stat" in option:
        result["data"]["object_statistics"] = sql_tunning.object_statistics()
    if "sql_profile" in option:
        session_status = sql_tunning.exec_sql()
        result["data"]["session_status"] = session_status
    # 关闭连接
    sql_tunning.engine.close()
    result["data"]["sqltext"] = sqltext
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


def explain(request):
    """
    SQL优化界面获取SQL执行计划
    :param request:
    :return:
    """
    sql_content = request.POST.get("sql_content")
    instance_name = request.POST.get("instance_name")
    db_name = request.POST.get("db_name")
    result = {"status": 0, "msg": "ok", "data": []}

    # 服务器端参数验证
    if sql_content is None or instance_name is None:
        result["status"] = 1
        result["msg"] = "页面提交参数可能为空"
        return HttpResponse(json.dumps(result), content_type="application/json")

    try:
        instance = user_instances(request.user).get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {"status": 1, "msg": "实例不存在", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")

    # 删除注释语句，进行语法判断，执行第一条有效sql
    sql_content = sqlparse.format(sql_content.strip(), strip_comments=True)
    try:
        sql_content = sqlparse.split(sql_content)[0]
    except IndexError:
        result["status"] = 1
        result["msg"] = "没有有效的SQL语句"
        return HttpResponse(json.dumps(result), content_type="application/json")
    else:
        # 过滤非explain的语句
        if not re.match(r"^explain", sql_content, re.I):
            result["status"] = 1
            result["msg"] = "仅支持explain开头的语句，请检查"
            return HttpResponse(json.dumps(result), content_type="application/json")

    # 执行获取执行计划语句
    query_engine = get_engine(instance=instance)
    db_name = query_engine.escape_string(db_name)
    sql_result = query_engine.query(str(db_name), sql_content).to_sep_dict()
    result["data"] = sql_result

    # 返回查询结果
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


def optimize_sqltuningadvisor(request):
    """
    sqltuningadvisor工具获取优化报告
    :param request:
    :return:
    """
    sql_content = request.POST.get("sql_content")
    instance_name = request.POST.get("instance_name")
    db_name = request.POST.get("schema_name")
    result = {"status": 0, "msg": "ok", "data": []}

    # 服务器端参数验证
    if sql_content is None or instance_name is None:
        result["status"] = 1
        result["msg"] = "页面提交参数可能为空"
        return HttpResponse(json.dumps(result), content_type="application/json")

    try:
        instance = user_instances(request.user).get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {"status": 1, "msg": "实例不存在", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")

    # 不删除注释语句，已获取加hints的SQL优化建议，进行语法判断，执行第一条有效sql
    sql_content = sqlparse.format(sql_content.strip(), strip_comments=False)
    # 对单引号加转义符,支持plsql语法
    sql_content = sql_content.replace("'", "''")
    try:
        sql_content = sqlparse.split(sql_content)[0]
    except IndexError:
        result["status"] = 1
        result["msg"] = "没有有效的SQL语句"
        return HttpResponse(json.dumps(result), content_type="application/json")
    else:
        # 过滤非Oracle语句
        if not instance.db_type == "oracle":
            result["status"] = 1
            result["msg"] = "SQLTuningAdvisor仅支持oracle数据库的检查"
            return HttpResponse(json.dumps(result), content_type="application/json")

    # 执行获取优化报告
    query_engine = get_engine(instance=instance)
    db_name = query_engine.escape_string(db_name)
    sql_result = query_engine.sqltuningadvisor(str(db_name), sql_content).to_sep_dict()
    result["data"] = sql_result

    # 返回查询结果
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


def optimize_sqltuningai(request):
    """
    sqltuningai工具获取优化建议
    :param request:
    :return:
    """
    sql_content = request.POST.get("sql_content")
    instance_name = request.POST.get("instance_name")
    db_name = request.POST.get("schema_name")
    result = {"status": 0, "msg": "ok", "data": []}

    # 服务器端参数验证
    if sql_content is None or instance_name is None:
        result["status"] = 1
        result["msg"] = "页面提交参数可能为空"
        return HttpResponse(json.dumps(result), content_type="application/json")

    try:
        instance = user_instances(request.user).get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {"status": 1, "msg": "实例不存在", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")

    # 不删除注释语句，已获取加hints的SQL优化建议，进行语法判断，执行第一条有效sql
    sql_content = sqlparse.format(sql_content.strip(), strip_comments=False)
    # 对单引号加转义符,支持plsql语法
    sql_content = sql_content.replace("'", "''")
    try:
        sql_content = sqlparse.split(sql_content)[0]
    except IndexError:
        result["status"] = 1
        result["msg"] = "没有有效的SQL语句"
        return HttpResponse(json.dumps(result), content_type="application/json")
    else:
        # 过滤非Oracle语句
        if not instance.db_type == "oracle":
            result["status"] = 1
            result["msg"] = "SQLTuningAdvisor仅支持oracle数据库的检查"
            return HttpResponse(json.dumps(result), content_type="application/json")

    # 执行获取优化报告
    query_engine = get_engine(instance=instance)
    db_name = query_engine.escape_string(db_name)
    sql_result = query_engine.sqltuningai(str(db_name), sql_content).to_sep_dict()
    result["data"] = sql_result

    # 返回查询结果
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


def _extract_table_names(sql):
    """从 SQL 中提取涉及的表名（兼容 [schema].[table] 方括号写法）"""
    tables = []
    pattern = r"\b(?:FROM|JOIN|UPDATE|INTO|TABLE)\s+([\[\]\w\.]+)"
    for m in re.finditer(pattern, sql, re.I):
        t = m.group(1).strip().replace("[", "").replace("]", "")
        if "." in t:
            t = t.split(".")[-1]
        low = t.lower()
        if t and low not in ("select", "set", "where", "values", "insert", "delete"):
            if t not in tables:
                tables.append(t)
    return tables


def _build_table_schema_context(engine, db_name, tables):
    """获取表结构信息，拼装成 AI 可读的上下文"""
    context = []
    for tb in tables:
        try:
            desc = engine.get_table_desc_data(db_name=db_name, tb_name=tb)
            rows = desc.get("rows", [])
            if not rows:
                continue
            lines = [f"### 表 {tb}"]
            for row in rows:
                # 列名、类型、是否为空、默认值
                name = row[0] if len(row) > 0 else ""
                dtype = row[1] if len(row) > 1 else ""
                nullable = row[3] if len(row) > 3 else ""
                lines.append(f"- {name} {dtype} {'NULL' if str(nullable) == 'YES' else 'NOT NULL'}")
            context.append("\n".join(lines))
        except Exception:
            continue
    return "\n\n".join(context)


@permission_required("sql.optimize_sqltuning", raise_exception=True)
def optimize_sql_ai(request):
    """
    通过 OpenAI 兼容接口对 SQL（支持 MSSQL/MySQL）进行 AI 优化分析
    :param request:
    :return:
    """
    sql_content = request.POST.get("sql_content")
    instance_name = request.POST.get("instance_name")
    db_name = request.POST.get("db_name")
    result = {"status": 0, "msg": "ok", "data": []}

    # 服务器端参数验证
    if not (sql_content and instance_name and db_name):
        result["status"] = 1
        result["msg"] = "页面提交参数可能为空"
        return HttpResponse(json.dumps(result), content_type="application/json")

    # AI 配置检查
    if not check_openai_config():
        result["status"] = 1
        result["msg"] = "请先在系统管理-配置项管理中配置 OPENAI_API_KEY（OPENAI_BASE_URL、DEFAULT_CHAT_MODEL）！"
        return HttpResponse(json.dumps(result), content_type="application/json")

    try:
        instance = user_instances(request.user, db_type=["mysql", "mssql"]).get(
            instance_name=instance_name
        )
    except Instance.DoesNotExist:
        result["status"] = 1
        result["msg"] = "你所在组未关联该实例！"
        return HttpResponse(json.dumps(result), content_type="application/json")

    # 获取表结构作为 AI 上下文
    engine = get_engine(instance=instance)
    tables = _extract_table_names(sql_content)
    schema_context = _build_table_schema_context(engine, db_name, tables)

    # 构造 AI 提示词
    db_type_label = "Microsoft SQL Server" if instance.db_type == "mssql" else "MySQL"
    prompt = f"""你是一名资深的 {db_type_label} 数据库优化专家，请对下面的 SQL 进行优化分析，并用 Markdown 格式输出。

### 数据库类型
{db_type_label}

### 数据库名
{db_name}

### 涉及的表结构
{schema_context if schema_context else '（未能获取到表结构信息）'}

### 待优化的 SQL
```sql
{sql_content}
```

### 输出要求
请按以下结构输出：
1. **SQL 分析**：指出 SQL 中存在的问题（如全表扫描、隐式转换、缺少索引、查询写法不合理等）
2. **执行计划解读**：若能从表结构判断，说明可能的执行方式及代价
3. **优化建议**：具体可操作的优化方案（改写 SQL、添加索引、调整写法等）
4. **优化后的 SQL**：给出优化后的完整 SQL 语句（如有）
"""

    try:
        openai_client = OpenaiClient()
        completion = openai_client.request_chat_completion(
            [dict(role="user", content=prompt)]
        )
        result["data"] = completion.choices[0].message.content or "AI 未返回内容"
    except Exception as e:
        result["status"] = 1
        result["msg"] = f"AI 优化请求失败: {e}"
    return HttpResponse(json.dumps(result), content_type="application/json")
