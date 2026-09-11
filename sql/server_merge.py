# -*- coding: UTF-8 -*-
"""
合服管理（工具插件）页面与接口。

合服共 5 个步骤：
1. 选择目标库和源库（仅配置，不执行 SQL）
2. 创建外部数据源和存储过程
3. 复制和清理（Pre_work / Copy / Delete）
4. 数据写入（Insert）
5. 后处理（Post_work）

第 2~5 步的 SQL 均在事务中执行，默认库取第一步选择的目标库（源库预处理项除外）。
"""

import json
import logging
import time
import traceback

from django.contrib.auth.decorators import permission_required
from django.http import JsonResponse
from django.shortcuts import render

from sql.engines import get_engine
from sql.models import (
    Instance,
    ServerMergeLog,
    ServerMergeProfile,
    ServerMergeTask,
    ServerMergeTemplate,
)
from sql.plugins import server_merge as merge_service
from sql.utils.resource_group import user_instances

logger = logging.getLogger("default")

MENU_PERM = "sql.menu_server_merge"
STEP_TITLES = {1: "选择目标库和源库", 2: "创建外部数据源和存储过程", 3: "复制和清理", 4: "数据写入", 5: "后处理"}
MASK_TEXT = "******"


def _payload(request):
    """兼容 JSON 与表单提交"""
    if request.content_type and "application/json" in request.content_type:
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except ValueError:
            return {}
    return request.POST.dict()


def _get_instance(user, instance_name, field_name):
    if not instance_name:
        raise ValueError("必须指定%s" % field_name)
    try:
        instance = user_instances(user, db_type=["mssql"]).get(
            instance_name=instance_name
        )
    except Instance.DoesNotExist:
        raise ValueError("你所在组未关联该 MSSQL 实例：%s" % instance_name)
    if instance.db_type != "mssql":
        raise ValueError("合服功能仅支持 MSSQL 实例：%s" % instance_name)
    return instance


def _parse_domain(payload):
    """
    解析第一步的配置，返回 (modules, index_db)
    modules: {"game": {"target_db": "", "source_db": ""}}
    支持新格式（行数组，可添加多行）与旧的字典格式
    """
    raw = payload.get("modules")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw or "[]")
        except ValueError:
            raw = []
    rows = []
    if isinstance(raw, dict):
        rows = [dict(value, module=key) for key, value in raw.items() if isinstance(value, dict)]
    elif isinstance(raw, list):
        rows = raw
    config = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        module = str(row.get("module") or "").strip().lower()
        if module not in merge_service.CONFIG_MODULES:
            continue
        config[module] = {
            "target_db": str(row.get("target_db") or "").strip(),
            "source_db": str(row.get("source_db") or "").strip(),
        }
    index_db = str(payload.get("index_db") or "").strip()
    return config, index_db


def _render_context(payload, module, config, index_db=""):
    """
    构造渲染变量。页面不再填写合服变量，TARGET_DB / SOURCE_DB 由模块库配置推导，
    INDEX 相关条目统一使用 INDEX 库。
    """
    variables = merge_service.build_variables(payload)
    target_db = ""
    source_db = ""
    if module in config:
        target_db = config[module]["target_db"]
        source_db = config[module]["source_db"]
    elif module == "index":
        target_db = index_db
    if not target_db:
        for value in config.values():
            target_db = value["target_db"] or index_db
            break
    if not source_db:
        for value in config.values():
            source_db = value["source_db"]
            break
    variables["TARGET_DB"] = target_db
    variables["SOURCE_DB"] = source_db
    variables["INDEX_DB"] = index_db
    return variables


def _mask(sql, variables):
    """执行记录与页面回显中屏蔽密码"""
    for key in ("SOURCE_PASSWORD", "TARGET_PASSWORD"):
        secret = variables.get(key)
        if secret:
            sql = sql.replace(secret, MASK_TEXT)
    return sql


def _resolve_items(user, payload):
    """
    把前端提交的条目解析为可执行条目：
    补充执行实例、执行库、渲染后的 SQL。
    """
    config, index_db = _parse_domain(payload)
    if not config and not index_db:
        raise ValueError("请先在第 1 步配置模块库或 INDEX 库")
    target_instance = _get_instance(
        user, payload.get("target_instance_name"), "目标实例"
    )
    source_instance = _get_instance(
        user, payload.get("source_instance_name"), "源实例"
    )

    raw_items = payload.get("items") or []
    if isinstance(raw_items, str):
        raw_items = json.loads(raw_items or "[]")

    items = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        if not raw.get("enabled", True):
            continue
        module = raw.get("module") or "common"
        sql_text = raw.get("sql") or ""
        if not sql_text.strip():
            continue
        variables = _render_context(payload, module, config, index_db)
        variables["SOURCE_USER"] = source_instance.user
        variables["SOURCE_PASSWORD"] = source_instance.password
        variables["SOURCE_HOST"] = source_instance.host
        variables["SOURCE_PORT"] = source_instance.port

        run_on = raw.get("run_on") or "target"
        if run_on == "source":
            instance = source_instance
            db_name = config.get(module, {}).get("source_db", "")
        else:
            instance = target_instance
            if module == "common":
                db_name = ""
            elif module == "index":
                db_name = index_db
            else:
                db_name = config.get(module, {}).get("target_db", "")
        if module in merge_service.CONFIG_MODULES and not db_name:
            raise ValueError(
                "请在第 1 步为模块 %s 选择%s"
                % (module.upper(), "源库" if run_on == "source" else "目标库")
            )
        if merge_service.INDEX_DB_PLACEHOLDER in sql_text and not index_db:
            raise ValueError("该 SQL 引用了 INDEX 库，请先在第 1 步选择 INDEX 库")

        sql_text = merge_service.render_sql(sql_text, variables)
        items.append(
            {
                "step": int(raw.get("step")),
                "module": module,
                "seq": int(raw.get("seq") or 0),
                "title": raw.get("title") or "",
                "run_on": run_on,
                "instance_name": instance.instance_name,
                "db_name": db_name,
                "sql": sql_text,
                "log_sql": _mask(sql_text, variables),
                "use_transaction": bool(raw.get("use_transaction", True)),
            }
        )
    if not items:
        raise ValueError("没有可执行的内容，请确认已勾选条目并填写 SQL")
    return items


def _module_instances(user, items):
    """收集执行需要的实例对象"""
    names = sorted({item["instance_name"] for item in items})
    instances = {}
    for name in names:
        instances[name] = _get_instance(user, name, "执行实例")
    return instances


@permission_required(MENU_PERM, raise_exception=True)
def server_merge(request):
    """合服页面"""
    return render(
        request,
        "server_merge.html",
        {
            "step_definitions": merge_service.STEP_DEFINITIONS,
            "config_modules": merge_service.CONFIG_MODULES,
            "module_labels": merge_service.MODULE_LABELS,
        },
    )


@permission_required(MENU_PERM, raise_exception=True)
def server_merge_databases(request):
    """获取实例的数据库列表"""
    payload = _payload(request)
    engine = None
    try:
        instance = _get_instance(
            request.user, payload.get("instance_name"), "实例"
        )
        engine = get_engine(instance=instance)
        result = engine.get_all_databases()
        if result.error:
            raise RuntimeError(result.error)
        return JsonResponse({"status": 0, "msg": "ok", "data": result.rows})
    except Exception as exc:
        return JsonResponse({"status": 1, "msg": str(exc), "data": []})
    finally:
        if engine:
            try:
                engine.close()
            except Exception:  # pragma: no cover
                logger.warning("关闭连接失败", exc_info=True)


@permission_required(MENU_PERM, raise_exception=True)
def server_merge_templates(request):
    """
    获取指定步骤的默认 SQL 清单，数据库中存在覆盖值时优先返回覆盖值
    """
    payload = _payload(request)
    try:
        step = int(payload.get("step") or 0)
        if step not in (2, 3, 4, 5):
            raise ValueError("步骤参数不合法")
        raw_modules = payload.get("modules")
        if isinstance(raw_modules, str):
            raw_modules = [m for m in raw_modules.split(",") if m]
        modules = [m for m in (raw_modules or []) if m in merge_service.CONFIG_MODULES]
        index_db = payload.get("index_db") or ""
        overrides = {
            (item.step, item.module, item.seq): item
            for item in ServerMergeTemplate.objects.filter(step=step)
        }
        data = []
        for item in merge_service.describe_default_items(step, modules, index_db):
            override = overrides.get((item["step"], item["module"], item["seq"]))
            data.append(
                {
                    "step": item["step"],
                    "module": item["module"],
                    "module_label": merge_service.MODULE_LABELS.get(item["module"], item["module"]),
                    "seq": item["seq"],
                    "title": item["title"],
                    "run_on": item["run_on"],
                    "sql": override.sql if override else item["sql"],
                    "enabled": override.enabled if override else True,
                    "use_transaction": override.use_transaction if override else True,
                    "customized": override is not None,
                }
            )
        return JsonResponse({"status": 0, "msg": "ok", "data": data})
    except Exception as exc:
        return JsonResponse({"status": 1, "msg": str(exc), "data": []})


@permission_required(MENU_PERM, raise_exception=True)
def server_merge_template_save(request):
    """保存为默认 SQL"""
    payload = _payload(request)
    try:
        step = int(payload.get("step") or 0)
        module = payload.get("module") or ""
        seq = int(payload.get("seq") or 0)
        if step not in (2, 3, 4, 5) or module not in merge_service.MODULE_ORDER or seq <= 0:
            raise ValueError("参数不合法")
        sql_text = payload.get("sql") or ""
        if not sql_text.strip():
            raise ValueError("SQL 不能为空")
        default_item = merge_service.find_default_item(step, module, seq)
        title = payload.get("title") or (default_item["title"] if default_item else "")
        enabled = payload.get("enabled", True)
        if isinstance(enabled, str):
            enabled = enabled.lower() in ("1", "true", "yes", "on")
        use_transaction = payload.get("use_transaction", True)
        if isinstance(use_transaction, str):
            use_transaction = use_transaction.lower() in ("1", "true", "yes", "on")
        ServerMergeTemplate.objects.update_or_create(
            step=step,
            module=module,
            seq=seq,
            defaults={
                "title": title,
                "sql": sql_text,
                "enabled": enabled,
                "use_transaction": use_transaction,
                "update_user": request.user.username,
            },
        )
        return JsonResponse({"status": 0, "msg": "已保存为默认 SQL", "data": {}})
    except Exception as exc:
        return JsonResponse({"status": 1, "msg": str(exc), "data": {}})


@permission_required(MENU_PERM, raise_exception=True)
def server_merge_template_reset(request):
    """恢复默认 SQL（删除数据库覆盖值）"""
    payload = _payload(request)
    try:
        step = int(payload.get("step") or 0)
        module = payload.get("module") or ""
        seq = int(payload.get("seq") or 0)
        ServerMergeTemplate.objects.filter(step=step, module=module, seq=seq).delete()
        default_item = merge_service.find_default_item(step, module, seq)
        return JsonResponse(
            {
                "status": 0,
                "msg": "已恢复默认 SQL",
                "data": {"sql": default_item["sql"] if default_item else ""},
            }
        )
    except Exception as exc:
        return JsonResponse({"status": 1, "msg": str(exc), "data": {"sql": ""}})


@permission_required(MENU_PERM, raise_exception=True)
def server_merge_preview(request):
    """按第一步的配置预览渲染后的 SQL"""
    payload = _payload(request)
    try:
        config, index_db = _parse_domain(payload)
        variables = _render_context(payload, payload.get("module") or "common", config, index_db)
        sql_text = payload.get("sql") or ""
        if merge_service.INDEX_DB_PLACEHOLDER in sql_text and not index_db:
            raise ValueError("该 SQL 引用了 INDEX 库，请先在第 1 步选择 INDEX 库")
        sql_text = merge_service.render_sql(sql_text, variables)
        return JsonResponse(
            {"status": 0, "msg": "ok", "data": {"sql": _mask(sql_text, variables)}}
        )
    except Exception as exc:
        return JsonResponse({"status": 1, "msg": str(exc), "data": {"sql": ""}})


@permission_required(MENU_PERM, raise_exception=True)
def server_merge_test_link(request):
    """测试外部数据源（链接服务器）连通性"""
    payload = _payload(request)
    engine = None
    try:
        instance = _get_instance(request.user, payload.get("target_instance_name"), "目标实例")
        config, index_db = _parse_domain(payload)
        variables = _render_context(payload, "common", config, index_db)
        linked_server = merge_service.quote_name(variables.get("LINKED_SERVER") or "XDS")
        engine = get_engine(instance=instance)
        result = engine.query(
            sql="EXEC (N'SELECT DB_NAME() AS remote_db') AT %s" % linked_server
        )
        if result.error:
            raise RuntimeError(result.error)
        remote_db = result.rows[0][0] if result.rows else ""
        return JsonResponse(
            {"status": 0, "msg": "外部数据源连通正常，远端默认库：%s" % remote_db, "data": {}}
        )
    except Exception as exc:
        return JsonResponse({"status": 1, "msg": "外部数据源连通失败：%s" % exc, "data": {}})
    finally:
        if engine:
            try:
                engine.close()
            except Exception:  # pragma: no cover
                logger.warning("关闭连接失败", exc_info=True)


def _run_items(request, task, items):
    """
    执行一组条目并写入执行记录，返回 (结果列表, 错误信息, 耗时)。
    同一组（同一个步骤）的条目共用一个事务。
    """
    logs = []
    for item in items:
        logs.append(
            ServerMergeLog.objects.create(
                task=task,
                step=item["step"],
                module=item["module"],
                seq=item["seq"],
                title=item["title"],
                run_db=item["db_name"] or item["instance_name"],
                use_transaction=item["use_transaction"],
                sql_text=item["log_sql"],
                status="running",
                user_name=request.user.username,
                user_display=getattr(request.user, "display", "") or "",
            )
        )
    try:
        runner = merge_service.ServerMergeRunner(_module_instances(request.user, items))
    except Exception as exc:
        for log in logs:
            log.status = "failed"
            log.error_info = str(exc)
            log.save(update_fields=["status", "error_info"])
        raise

    started = time.time()
    results, error_message = runner.execute(items)
    cost_time = round(time.time() - started, 3)

    data = []
    for index, item in enumerate(items):
        result = results[index] if index < len(results) else {}
        log = logs[index]
        log.status = result.get("status", "failed")
        log.affected_rows = result.get("affected_rows", 0)
        log.cost_time = result.get("cost_time", 0)
        log.error_info = result.get("error", "")
        log.save(update_fields=["status", "affected_rows", "cost_time", "error_info"])
        data.append(
            {
                "module": item["module"],
                "module_label": merge_service.MODULE_LABELS.get(
                    item["module"], item["module"]
                ),
                "seq": item["seq"],
                "title": item["title"],
                "instance_name": item["instance_name"],
                "db_name": item["db_name"],
                "status": log.status,
                "affected_rows": log.affected_rows,
                "cost_time": log.cost_time,
                "batch_count": result.get("batch_count", 0),
                "error": log.error_info,
            }
        )
    return data, error_message, cost_time


@permission_required(MENU_PERM, raise_exception=True)
def server_merge_execute(request):
    """执行单个合服步骤，整个步骤共用一个事务"""
    payload = _payload(request)
    task = None
    try:
        items = _resolve_items(request.user, payload)
        step = items[0]["step"]
        if any(item["step"] != step for item in items):
            raise ValueError("一次只能执行一个步骤，执行全部请使用「一键执行全部」")
        if step not in STEP_TITLES or step == 1:
            raise ValueError("第 1 步仅做配置，不执行 SQL")

        task = _get_or_create_task(request, payload, step)
        data, error_message, cost_time = _run_items(request, task, items)
        if error_message:
            return JsonResponse(
                {
                    "status": 1,
                    "msg": "步骤 %s 执行失败，已回滚：%s"
                    % (STEP_TITLES.get(step, step), error_message),
                    "data": {
                        "task_id": task.id,
                        "step": step,
                        "cost_time": cost_time,
                        "items": data,
                    },
                }
            )
        return JsonResponse(
            {
                "status": 0,
                "msg": "步骤 %s 执行成功，耗时 %.3fs"
                % (STEP_TITLES.get(step, step), cost_time),
                "data": {
                    "task_id": task.id,
                    "step": step,
                    "cost_time": cost_time,
                    "items": data,
                },
            }
        )
    except Exception as exc:
        logger.error("合服执行异常：%s", traceback.format_exc())
        return JsonResponse(
            {
                "status": 1,
                "msg": str(exc),
                "data": {"task_id": task.id if task else None, "items": []},
            }
        )


@permission_required(MENU_PERM, raise_exception=True)
def server_merge_execute_all(request):
    """一键执行全部步骤：按 2→3→4→5 顺序执行，每个步骤一个事务，失败即停止"""
    payload = _payload(request)
    task = None
    try:
        items = _resolve_items(request.user, payload)
        steps = sorted({item["step"] for item in items if item["step"] != 1})
        if not steps:
            raise ValueError("没有可执行的内容，请确认已勾选条目并填写 SQL")

        task = _get_or_create_task(request, payload, steps[0])
        step_results = []
        failed_step = None
        error_message = ""
        for step in steps:
            step_items = [item for item in items if item["step"] == step]
            data, step_error, cost_time = _run_items(request, task, step_items)
            step_results.append(
                {
                    "step": step,
                    "step_title": STEP_TITLES.get(step, str(step)),
                    "status": "failed" if step_error else "success",
                    "cost_time": cost_time,
                    "error": step_error,
                    "items": data,
                }
            )
            if step_error:
                failed_step = step
                error_message = step_error
                break

        total_cost = round(sum(row["cost_time"] for row in step_results), 3)
        if error_message:
            return JsonResponse(
                {
                    "status": 1,
                    "msg": "第 %s 步执行失败，已回滚并停止：%s"
                    % (STEP_TITLES.get(failed_step, failed_step), error_message),
                    "data": {
                        "task_id": task.id,
                        "steps": step_results,
                        "cost_time": total_cost,
                    },
                }
            )
        return JsonResponse(
            {
                "status": 0,
                "msg": "全部步骤执行成功，共耗时 %.3fs" % total_cost,
                "data": {
                    "task_id": task.id,
                    "steps": step_results,
                    "cost_time": total_cost,
                },
            }
        )
    except Exception as exc:
        logger.error("合服一键执行异常：%s", traceback.format_exc())
        return JsonResponse(
            {
                "status": 1,
                "msg": str(exc),
                "data": {"task_id": task.id if task else None, "steps": []},
            }
        )


def _as_bool(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).lower() in ("1", "true", "yes", "on")


def _as_list(value):
    if isinstance(value, str):
        try:
            value = json.loads(value or "[]")
        except ValueError:
            return []
    return value if isinstance(value, list) else []


@permission_required(MENU_PERM, raise_exception=True)
def server_merge_profile_save(request):
    """把第一步配置与所有步骤的 SQL 配置整体保存为一个方案"""
    payload = _payload(request)
    try:
        name = str(payload.get("name") or "").strip()
        if not name:
            raise ValueError("请填写方案名称")
        if len(name) > 100:
            raise ValueError("方案名称不能超过 100 个字符")
        modules = []
        for row in _as_list(payload.get("modules")):
            if not isinstance(row, dict):
                continue
            modules.append(
                {
                    "module": str(row.get("module") or "").strip(),
                    "target_db": str(row.get("target_db") or "").strip(),
                    "source_db": str(row.get("source_db") or "").strip(),
                }
            )
        items = []
        for row in _as_list(payload.get("items")):
            if not isinstance(row, dict):
                continue
            items.append(
                {
                    "step": int(row.get("step") or 0),
                    "module": str(row.get("module") or ""),
                    "seq": int(row.get("seq") or 0),
                    "title": str(row.get("title") or ""),
                    "run_on": str(row.get("run_on") or "target"),
                    "enabled": _as_bool(row.get("enabled"), True),
                    "use_transaction": _as_bool(row.get("use_transaction"), True),
                    "sql": str(row.get("sql") or ""),
                }
            )
        if not items:
            raise ValueError("没有可保存的内容，请先加载各步骤的默认 SQL")
        profile, created = ServerMergeProfile.objects.update_or_create(
            name=name,
            create_user=request.user.username,
            defaults={
                "target_instance_name": str(payload.get("target_instance_name") or ""),
                "source_instance_name": str(payload.get("source_instance_name") or ""),
                "index_db": str(payload.get("index_db") or ""),
                "modules": json.dumps(modules, ensure_ascii=False),
                "items": json.dumps(items, ensure_ascii=False),
                "create_user_display": getattr(request.user, "display", "") or "",
            },
        )
        return JsonResponse(
            {
                "status": 0,
                "msg": "配置已%s：%s（共 %d 条 SQL）"
                % ("新建" if created else "更新", profile.name, len(items)),
                "data": {"id": profile.id},
            }
        )
    except Exception as exc:
        return JsonResponse({"status": 1, "msg": str(exc), "data": {}})


@permission_required(MENU_PERM, raise_exception=True)
def server_merge_profile_list(request):
    """已保存的合服方案列表"""
    try:
        rows = []
        for profile in ServerMergeProfile.objects.all()[:200]:
            try:
                item_count = len(json.loads(profile.items or "[]"))
            except ValueError:
                item_count = 0
            rows.append(
                {
                    "id": profile.id,
                    "name": profile.name,
                    "target_instance_name": profile.target_instance_name,
                    "source_instance_name": profile.source_instance_name,
                    "index_db": profile.index_db,
                    "item_count": item_count,
                    "user_display": profile.create_user_display or profile.create_user,
                    "update_time": profile.update_time.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
        return JsonResponse({"status": 0, "msg": "ok", "data": rows})
    except Exception as exc:
        return JsonResponse({"status": 1, "msg": str(exc), "data": []})


@permission_required(MENU_PERM, raise_exception=True)
def server_merge_profile_load(request):
    """加载一个已保存方案的全部配置"""
    payload = _payload(request)
    try:
        profile = ServerMergeProfile.objects.filter(id=payload.get("id")).first()
        if not profile:
            raise ValueError("方案不存在或已被删除")
        return JsonResponse(
            {
                "status": 0,
                "msg": "已加载方案：%s" % profile.name,
                "data": {
                    "id": profile.id,
                    "name": profile.name,
                    "target_instance_name": profile.target_instance_name,
                    "source_instance_name": profile.source_instance_name,
                    "index_db": profile.index_db,
                    "modules": json.loads(profile.modules or "[]"),
                    "items": json.loads(profile.items or "[]"),
                },
            }
        )
    except Exception as exc:
        return JsonResponse({"status": 1, "msg": str(exc), "data": {}})


@permission_required(MENU_PERM, raise_exception=True)
def server_merge_profile_delete(request):
    """删除一个已保存方案"""
    payload = _payload(request)
    try:
        profile = ServerMergeProfile.objects.filter(id=payload.get("id")).first()
        if not profile:
            raise ValueError("方案不存在或已被删除")
        name = profile.name
        profile.delete()
        return JsonResponse({"status": 0, "msg": "已删除方案：%s" % name, "data": {}})
    except Exception as exc:
        return JsonResponse({"status": 1, "msg": str(exc), "data": {}})


def _get_or_create_task(request, payload, step):
    """同一浏览器会话内复用同一个合服任务，避免重复建任务"""
    task_id = payload.get("task_id")
    if task_id:
        task = ServerMergeTask.objects.filter(id=task_id).first()
        if task:
            return task
    config, index_db = _parse_domain(payload)
    variables = merge_service.build_variables(payload)
    variables["INDEX_DB"] = index_db
    return ServerMergeTask.objects.create(
        title=payload.get("title") or "步骤 %s：%s" % (step, STEP_TITLES.get(step, step)),
        target_instance_name=payload.get("target_instance_name") or "",
        source_instance_name=payload.get("source_instance_name") or "",
        variables=json.dumps(variables, ensure_ascii=False),
        config=json.dumps({"modules": config, "index_db": index_db}, ensure_ascii=False),
        create_user=request.user.username,
        create_user_display=getattr(request.user, "display", "") or "",
    )


@permission_required(MENU_PERM, raise_exception=True)
def server_merge_logs(request):
    """合服执行记录"""
    payload = _payload(request)
    try:
        limit = min(int(payload.get("limit") or 200), 1000)
        queryset = ServerMergeLog.objects.select_related("task").all()
        task_id = payload.get("task_id")
        if task_id:
            queryset = queryset.filter(task_id=task_id)
        rows = []
        for log in queryset[:limit]:
            rows.append(
                {
                    "id": log.id,
                    "task_id": log.task_id,
                    "task_title": log.task.title if log.task else "",
                    "step": log.step,
                    "step_title": STEP_TITLES.get(log.step, str(log.step)),
                    "module": merge_service.MODULE_LABELS.get(log.module, log.module),
                    "seq": log.seq,
                    "title": log.title,
                    "run_db": log.run_db,
                    "use_transaction": log.use_transaction,
                    "status": log.status,
                    "affected_rows": log.affected_rows,
                    "cost_time": log.cost_time,
                    "error_info": log.error_info,
                    "user_display": log.user_display or log.user_name,
                    "create_time": log.create_time.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
        return JsonResponse({"status": 0, "msg": "ok", "data": rows})
    except Exception as exc:
        return JsonResponse({"status": 1, "msg": str(exc), "data": []})
