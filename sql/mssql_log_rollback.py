# -*- coding: UTF-8 -*-
import json

from django.contrib.auth.decorators import permission_required
from django.http import JsonResponse
from django.shortcuts import render

from sql.models import Instance
from sql.plugins.mssql_log_rollback import MssqlLogRollback


def _instance_for_request(request):
    instance_id = request.POST.get("instance_id") or request.GET.get("instance_id")
    instance_name = request.POST.get("instance_name") or request.GET.get("instance_name")
    if instance_id:
        instance = Instance.objects.get(id=int(instance_id))
    elif instance_name:
        instance = Instance.objects.get(instance_name=instance_name)
    else:
        raise ValueError("必须指定 MSSQL 实例")
    if instance.db_type != "mssql":
        raise ValueError("该工具仅支持 MSSQL 实例")
    return instance


@permission_required("sql.menu_mssql_log_rollback", raise_exception=True)
def mssql_log_rollback(request):
    # 长驻 gunicorn 进程会缓存模板，修改模板文件后需强制刷新，避免返回旧版本
    _clear_template_cache()
    return render(request, "mssql_log_rollback.html")


def _clear_template_cache():
    """清空 Django 模板加载器缓存，确保下次渲染读取最新的模板文件。"""
    try:
        from django.template import engines

        engine = engines["django"].engine
        for loader in getattr(engine, "template_loaders", []) or []:
            cache = getattr(loader, "get_template_cache", None)
            if isinstance(cache, dict):
                cache.clear()
    except Exception:
        pass


@permission_required("sql.menu_mssql_log_rollback", raise_exception=True)
def mssql_log_rollback_list(request):
    try:
        instance = _instance_for_request(request)
        tool = MssqlLogRollback(instance)
        rows = tool.list_transactions(
            db_name=request.POST.get("db_name", ""),
            begin_time=(request.POST.get("begin_time") or "").replace("T", " ") or None,
            end_time=(request.POST.get("end_time") or "").replace("T", " ") or None,
            transaction_id=request.POST.get("transaction_id") or None,
            table_name=request.POST.get("table_name") or None,
            operation=request.POST.get("operation") or None,
            limit=min(int(request.POST.get("limit", 200)), 1000),
            log_backup_file=request.POST.get("log_backup_file") or None,
        )
        return JsonResponse({"status": 0, "msg": "ok", "data": rows})
    except Exception as exc:
        return JsonResponse({"status": 1, "msg": str(exc), "data": []})


@permission_required("sql.menu_mssql_log_rollback", raise_exception=True)
def mssql_log_rollback_databases(request):
    engine = None
    try:
        instance = _instance_for_request(request)
        engine = MssqlLogRollback(instance).engine
        result = engine.get_all_databases()
        if result.error:
            raise RuntimeError(result.error)
        return JsonResponse({"status": 0, "msg": "ok", "data": result.rows})
    except Exception as exc:
        return JsonResponse({"status": 1, "msg": str(exc), "data": []})
    finally:
        if engine:
            engine.close()


@permission_required("sql.menu_mssql_log_rollback", raise_exception=True)
def mssql_log_rollback_schema(request):
    try:
        instance = _instance_for_request(request)
        tool = MssqlLogRollback(instance)
        return JsonResponse({
            "status": 0,
            "msg": "ok",
            "data": tool.get_table_schema(
                request.POST.get("db_name", ""), request.POST.get("table_name", "")
            ),
        })
    except Exception as exc:
        return JsonResponse({"status": 1, "msg": str(exc), "data": []})


@permission_required("sql.menu_mssql_log_rollback", raise_exception=True)
def mssql_log_rollback_generate(request):
    try:
        entries = json.loads(request.POST.get("entries", "[]"))
        if not isinstance(entries, list) or len(entries) > 1000:
            raise ValueError("日志记录数量不合法")
        schema = json.loads(request.POST.get("schema", "[]"))
        if not isinstance(schema, list) or not schema:
            raise ValueError("必须提供表结构")
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            entry["decoded"] = MssqlLogRollback.decode_log_entry(entry, schema)
        draft = MssqlLogRollback.build_rollback_draft(entries)
        return JsonResponse({"status": 0, "msg": "ok", "data": {"sql": draft}})
    except Exception as exc:
        return JsonResponse({"status": 1, "msg": str(exc), "data": {"sql": ""}})