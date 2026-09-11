# -*- coding: UTF-8 -*-
"""合服工具（工具插件 - 合服管理）单元测试"""

import json

import pytest
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory

from sql.models import (
    Instance,
    ServerMergeLog,
    ServerMergeProfile,
    ServerMergeTask,
)
from sql.plugins import server_merge as sm
from sql import server_merge as sm_views


class MssqlStub:
    """仅用于执行器测试的实例占位对象"""

    db_type = "mssql"
    instance_name = "merge_target"


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.description = None
        self.rowcount = -1
        self._rows = []

    def execute(self, sql, *args):
        self.connection.executed.append(sql)
        if self.connection.fail_on and self.connection.fail_on in sql:
            raise RuntimeError("模拟执行失败")
        if sql.strip().upper().startswith("SELECT"):
            self.description = ["col"]
            self._rows = [(1,)]
        else:
            self.description = None
            self.rowcount = 2

    def fetchall(self):
        return self._rows

    def nextset(self):
        return False

    def close(self):
        pass


class FakeConnection:
    def __init__(self, fail_on=None):
        self.executed = []
        self.commits = 0
        self.rollbacks = 0
        self.autocommit = True
        self.timeout = 0
        self.fail_on = fail_on

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class FakeEngine:
    def __init__(self, connection):
        self.connection = connection
        self.closed = False

    def get_connection(self, db_name=None):
        return self.connection

    def close(self):
        self.closed = True


@pytest.fixture
def merge_instances(db, super_user, resource_group):
    """创建目标/源 MSSQL 实例并授权给测试用户"""
    target = Instance.objects.create(
        instance_name="merge_target",
        type="master",
        db_type="mssql",
        host="10.0.0.1",
        port=1433,
        user="sa",
        password="target_pwd",
    )
    source = Instance.objects.create(
        instance_name="merge_source",
        type="master",
        db_type="mssql",
        host="10.0.0.2",
        port=1433,
        user="sa",
        password="source_pwd",
    )
    super_user.resource_group.add(resource_group)
    target.resource_group.add(resource_group)
    source.resource_group.add(resource_group)
    yield target, source
    target.delete()
    source.delete()


def _item(
    step=3,
    module="game",
    seq=1,
    run_on="target",
    db_name="target_db",
    instance_name="merge_target",
    sql="SELECT 1",
    use_transaction=True,
):
    return {
        "step": step,
        "module": module,
        "seq": seq,
        "title": "test item",
        "run_on": run_on,
        "instance_name": instance_name,
        "db_name": db_name,
        "sql": sql,
        "use_transaction": use_transaction,
    }


def test_split_batches_by_go():
    batches = sm.split_batches("SELECT 1\nGO\nSELECT 2\ngo\n\nSELECT 3")
    assert batches == ["SELECT 1", "SELECT 2", "SELECT 3"]


def test_split_batches_ignores_go_inside_comment_and_string():
    script = (
        "/*\nGO\n*/\n"
        "PRINT 'not a\nGO\nseparator'\n"
        "GO\n"
        "-- GO\n"
        "SELECT 1\n"
        "GO"
    )
    batches = sm.split_batches(script)
    assert len(batches) == 2
    assert "PRINT 'not a" in batches[0]
    assert batches[1].endswith("SELECT 1")


def test_render_sql_replaces_variables_and_escapes_quotes():
    sql = "SELECT N'{{SOURCE_DB}}', {{SOURCE_WORLD}}"
    rendered = sm.render_sql(sql, {"SOURCE_DB": "it's_db", "SOURCE_WORLD": 123})
    assert rendered == "SELECT N'it''s_db', 123"


def test_render_sql_raises_on_unknown_variable():
    with pytest.raises(sm.ServerMergeError):
        sm.render_sql("SELECT {{NOT_EXIST}}", {})


def test_build_variables_uses_internal_defaults():
    """页面不再填写合服变量，全部使用内部默认值"""
    variables = sm.build_variables({})
    assert variables == {"LINKED_SERVER": "XDS"}
    assert sm.build_variables({"linked_server": " LNK "})["LINKED_SERVER"] == "LNK"


@pytest.mark.parametrize("step", [2, 3, 4, 5])
def test_default_sql_files_exist(step):
    items = sm.describe_default_items(step, ["game", "front"], index_db="INDEX_DB")
    assert items
    for item in items:
        assert item["sql"].strip(), item


def test_describe_default_items_respects_modules_and_index_db():
    assert len(sm.describe_default_items(3, ["game"])) == 3
    assert len(sm.describe_default_items(3, ["game", "front"])) == 6
    assert len(sm.describe_default_items(4, ["game", "front"])) == 2
    # INDEX 相关条目只有配置了 INDEX 库才会返回
    assert len(sm.describe_default_items(5, ["game"])) == 1
    assert len(sm.describe_default_items(5, ["game"], index_db="INDEX_DB")) == 2
    # 步骤 2：1 个通用数据源 + 每个模块 1 个存储过程 + INDEX 库映射表
    step2 = sm.describe_default_items(2, ["game", "front"], index_db="INDEX_DB")
    assert sorted(item["module"] for item in step2) == ["common", "front", "game", "index"]
    assert len(sm.describe_default_items(2, ["game", "front"])) == 3


def test_find_default_item_ignores_module_config():
    item = sm.find_default_item(2, "index", 3)
    assert item is not None
    assert "MergeMapping" in item["sql"]
    assert sm.find_default_item(2, "index", 99) is None


@pytest.mark.parametrize("module", ["game", "front"])
def test_post_work_uses_cross_db_merge_mapping(module):
    """MergeMapping 只建在 INDEX 库，game/front 的 Post_work 需要跨库引用"""
    item = sm.find_default_item(5, module, 1)
    assert item is not None
    assert "[{{INDEX_DB}}].dbo.MergeMapping" in item["sql"]
    # 渲染后应带上真实 INDEX 库名
    rendered = sm.render_sql(item["sql"], {"INDEX_DB": "IDX_DB"})
    assert "[IDX_DB].dbo.MergeMapping" in rendered
    assert "{{INDEX_DB}}" not in rendered


def test_index_data_change_keeps_local_merge_mapping():
    """index_data_change 本身就在 INDEX 库执行，保持本地表名即可"""
    item = sm.find_default_item(5, "index", 1)
    assert item is not None
    assert "[{{INDEX_DB}}]" not in item["sql"]


@pytest.mark.django_db
def test_execute_rejects_missing_index_db(client, super_user, merge_instances):
    target, source = merge_instances
    client.force_login(super_user)
    payload = {
        "target_instance_name": target.instance_name,
        "source_instance_name": source.instance_name,
        "index_db": "",
        "modules": [{"module": "game", "target_db": "dest_db", "source_db": "src_db"}],
        "items": [
            {
                "step": 5,
                "module": "game",
                "seq": 1,
                "title": "GAME 后处理(Post_work)",
                "run_on": "target",
                "sql": "SELECT * FROM [{{INDEX_DB}}].dbo.MergeMapping",
                "enabled": True,
            }
        ],
    }
    response = client.post(
        "/server_merge/execute/",
        data=json.dumps(payload),
        content_type="application/json",
    )
    result = json.loads(response.content.decode("utf-8"))
    assert result["status"] == 1
    assert "INDEX 库" in result["msg"]


def test_runner_commits_once_per_step(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(sm, "get_engine", lambda instance: FakeEngine(connection))
    runner = sm.ServerMergeRunner({"merge_target": MssqlStub()})
    items = [
        _item(seq=1, db_name="db_a", sql="SELECT 1"),
        _item(seq=2, db_name="db_a", sql="SELECT 2"),
        _item(seq=3, db_name="db_b", sql="SELECT 3"),
    ]
    results, error = runner.execute(items)
    assert error == ""
    assert [result["status"] for result in results] == ["success"] * 3
    assert connection.commits == 1
    assert connection.rollbacks == 0
    # db_name 变化时通过 USE 切换默认库
    assert connection.executed.count("USE [db_a]") == 1
    assert connection.executed.count("USE [db_b]") == 1


def test_runner_rolls_back_when_failed(monkeypatch):
    connection = FakeConnection(fail_on="SELECT 2")
    monkeypatch.setattr(sm, "get_engine", lambda instance: FakeEngine(connection))
    runner = sm.ServerMergeRunner({"merge_target": MssqlStub()})
    items = [
        _item(seq=1, sql="SELECT 1"),
        _item(seq=2, sql="SELECT 2"),
        _item(seq=3, sql="SELECT 3"),
    ]
    results, error = runner.execute(items)
    assert "模拟执行失败" in error
    assert [result["status"] for result in results] == ["success", "failed", "skipped"]
    assert connection.commits == 0
    assert connection.rollbacks == 1


def test_runner_rejects_non_mssql_instance(monkeypatch):
    class NonMssql:
        db_type = "mysql"
        instance_name = "mysql_ins"

    monkeypatch.setattr(sm, "get_engine", lambda instance: FakeEngine(FakeConnection()))
    runner = sm.ServerMergeRunner({"mysql_ins": NonMssql()})
    results, error = runner.execute([_item(instance_name="mysql_ins")])
    assert "仅支持 MSSQL" in error
    assert results[0]["status"] == "failed"


@pytest.mark.django_db
def test_page_requires_permission(normal_user):
    request = RequestFactory().get("/server_merge/")
    request.user = normal_user
    with pytest.raises(PermissionDenied):
        sm_views.server_merge(request)


@pytest.mark.django_db
def test_page_renders_for_authorized_user(client, super_user):
    client.force_login(super_user)
    response = client.get("/server_merge/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "ServerMerge" in body
    assert "sm-module-rows" in body


@pytest.mark.django_db
def test_templates_api_returns_defaults_and_override(client, super_user):
    client.force_login(super_user)
    response = client.post(
        "/server_merge/templates/", {"step": 3, "modules": "game"}
    )
    payload = json.loads(response.content.decode("utf-8"))
    assert payload["status"] == 0
    assert len(payload["data"]) == 3
    assert payload["data"][0]["customized"] is False

    response = client.post(
        "/server_merge/templates/save/",
        {"step": 3, "module": "game", "seq": 1, "sql": "SELECT 42", "enabled": True, "use_transaction": True},
    )
    assert json.loads(response.content.decode("utf-8"))["status"] == 0

    response = client.post("/server_merge/templates/", {"step": 3, "modules": "game"})
    payload = json.loads(response.content.decode("utf-8"))
    first = [item for item in payload["data"] if item["seq"] == 1][0]
    assert first["sql"] == "SELECT 42"
    assert first["customized"] is True

    response = client.post(
        "/server_merge/templates/reset/", {"step": 3, "module": "game", "seq": 1}
    )
    result = json.loads(response.content.decode("utf-8"))
    assert result["status"] == 0
    assert "Pre_work" in result["data"]["sql"] or result["data"]["sql"].strip()


@pytest.mark.django_db
def test_preview_api_renders_variables(client, super_user):
    client.force_login(super_user)
    response = client.post(
        "/server_merge/preview/",
        {
            "module": "game",
            "sql": "SELECT N'{{TARGET_DB}}'",
            "modules": json.dumps([{"module": "game", "target_db": "dest_db", "source_db": "src_db"}]),
        },
    )
    payload = json.loads(response.content.decode("utf-8"))
    assert payload["status"] == 0
    assert payload["data"]["sql"] == "SELECT N'dest_db'"


@pytest.mark.django_db
def test_execute_api_writes_logs(client, super_user, merge_instances, monkeypatch):
    target, source = merge_instances
    monkeypatch.setattr(sm, "get_engine", lambda instance: FakeEngine(FakeConnection()))
    client.force_login(super_user)
    payload = {
        "target_instance_name": target.instance_name,
        "source_instance_name": source.instance_name,
        "index_db": "index_db",
        "modules": [{"module": "game", "target_db": "dest_db", "source_db": "src_db"}],
        "items": [
            {
                "step": 4,
                "module": "game",
                "seq": 1,
                "title": "GAME 数据写入",
                "run_on": "target",
                "sql": "INSERT INTO t SELECT N'{{SOURCE_DB}}'",
                "enabled": True,
                "use_transaction": True,
            }
        ],
    }
    response = client.post(
        "/server_merge/execute/",
        data=json.dumps(payload),
        content_type="application/json",
    )
    result = json.loads(response.content.decode("utf-8"))
    assert result["status"] == 0, result
    assert ServerMergeTask.objects.count() == 1
    log = ServerMergeLog.objects.get()
    assert log.status == "success"
    assert log.step == 4
    assert "src_db" in log.sql_text
    # 密码不会写入执行记录
    assert source.password not in log.sql_text


@pytest.mark.django_db
def test_execute_api_rejects_non_mssql_instance(client, super_user, db_instance):
    client.force_login(super_user)
    payload = {
        "target_instance_name": db_instance.instance_name,
        "source_instance_name": db_instance.instance_name,
        "modules": [{"module": "game", "target_db": "a", "source_db": "b"}],
        "items": [
            {
                "step": 4,
                "module": "game",
                "seq": 1,
                "title": "x",
                "run_on": "target",
                "sql": "SELECT 1",
                "enabled": True,
            }
        ],
    }
    response = client.post(
        "/server_merge/execute/",
        data=json.dumps(payload),
        content_type="application/json",
    )
    result = json.loads(response.content.decode("utf-8"))
    assert result["status"] == 1


@pytest.mark.django_db
def test_logs_api_returns_rows(client, super_user):
    task = ServerMergeTask.objects.create(
        title="merge task",
        target_instance_name="t",
        source_instance_name="s",
        create_user=super_user.username,
    )
    ServerMergeLog.objects.create(
        task=task, step=2, module="game", seq=1, title="x", status="success"
    )
    client.force_login(super_user)
    response = client.get("/server_merge/logs/")
    payload = json.loads(response.content.decode("utf-8"))
    assert payload["status"] == 0
    assert payload["data"][0]["title"] == "x"


@pytest.mark.django_db
def test_profile_save_load_list_delete(client, super_user):
    client.force_login(super_user)
    payload = {
        "name": "ASIA041 合服",
        "target_instance_name": "merge_target",
        "source_instance_name": "merge_source",
        "index_db": "IDX",
        "modules": [{"module": "game", "target_db": "DEST", "source_db": "SRC"}],
        "items": [
            {
                "step": 2,
                "module": "common",
                "seq": 1,
                "title": "创建外部数据源",
                "run_on": "target",
                "enabled": True,
                "use_transaction": True,
                "sql": "SELECT 1",
            },
            {
                "step": 5,
                "module": "game",
                "seq": 1,
                "title": "GAME 后处理",
                "run_on": "target",
                "enabled": False,
                "use_transaction": False,
                "sql": "SELECT 2",
            },
        ],
    }
    response = client.post(
        "/server_merge/profile/save/",
        data=json.dumps(payload),
        content_type="application/json",
    )
    result = json.loads(response.content.decode("utf-8"))
    assert result["status"] == 0, result
    profile_id = result["data"]["id"]

    response = client.get("/server_merge/profile/list/")
    rows = json.loads(response.content.decode("utf-8"))["data"]
    assert rows[0]["name"] == "ASIA041 合服"
    assert rows[0]["item_count"] == 2

    response = client.post("/server_merge/profile/load/", {"id": profile_id})
    data = json.loads(response.content.decode("utf-8"))["data"]
    assert data["index_db"] == "IDX"
    assert data["modules"][0]["target_db"] == "DEST"
    assert len(data["items"]) == 2
    assert data["items"][1]["enabled"] is False
    assert data["items"][1]["use_transaction"] is False

    # 同名再次保存应该更新而不是新增
    payload["index_db"] = "IDX2"
    response = client.post(
        "/server_merge/profile/save/",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert json.loads(response.content.decode("utf-8"))["data"]["id"] == profile_id
    assert ServerMergeProfile.objects.count() == 1

    response = client.post("/server_merge/profile/delete/", {"id": profile_id})
    assert json.loads(response.content.decode("utf-8"))["status"] == 0
    assert ServerMergeProfile.objects.count() == 0


@pytest.mark.django_db
def test_profile_save_requires_name_and_items(client, super_user):
    client.force_login(super_user)
    response = client.post(
        "/server_merge/profile/save/", {"name": "  ", "items": "[]"}
    )
    result = json.loads(response.content.decode("utf-8"))
    assert result["status"] == 1
    assert "方案名称" in result["msg"]

    response = client.post("/server_merge/profile/save/", {"name": "x", "items": "[]"})
    result = json.loads(response.content.decode("utf-8"))
    assert result["status"] == 1
    assert "没有可保存的内容" in result["msg"]


@pytest.mark.django_db
def test_execute_all_runs_steps_in_order(
    client, super_user, merge_instances, monkeypatch
):
    target, source = merge_instances
    connection = FakeConnection()
    monkeypatch.setattr(sm, "get_engine", lambda instance: FakeEngine(connection))
    client.force_login(super_user)
    payload = {
        "target_instance_name": target.instance_name,
        "source_instance_name": source.instance_name,
        "index_db": "IDX",
        "modules": [{"module": "game", "target_db": "dest_db", "source_db": "src_db"}],
        "items": [
            {"step": 3, "module": "game", "seq": 2, "title": "copy", "run_on": "target", "sql": "SELECT 3", "enabled": True},
            {"step": 2, "module": "common", "seq": 1, "title": "link", "run_on": "target", "sql": "SELECT 2", "enabled": True},
            {"step": 4, "module": "game", "seq": 1, "title": "insert", "run_on": "target", "sql": "SELECT 4", "enabled": True},
        ],
    }
    response = client.post(
        "/server_merge/execute_all/",
        data=json.dumps(payload),
        content_type="application/json",
    )
    result = json.loads(response.content.decode("utf-8"))
    assert result["status"] == 0, result
    assert [row["step"] for row in result["data"]["steps"]] == [2, 3, 4]
    assert all(row["status"] == "success" for row in result["data"]["steps"])
    assert list(
        ServerMergeLog.objects.order_by("id").values_list("step", flat=True)
    ) == [2, 3, 4]


@pytest.mark.django_db
def test_execute_all_stops_on_failure(
    client, super_user, merge_instances, monkeypatch
):
    target, source = merge_instances
    connection = FakeConnection(fail_on="SELECT 99")
    monkeypatch.setattr(sm, "get_engine", lambda instance: FakeEngine(connection))
    client.force_login(super_user)
    payload = {
        "target_instance_name": target.instance_name,
        "source_instance_name": source.instance_name,
        "modules": [{"module": "game", "target_db": "dest_db", "source_db": "src_db"}],
        "items": [
            {"step": 2, "module": "common", "seq": 1, "title": "link", "run_on": "target", "sql": "SELECT 2", "enabled": True},
            {"step": 3, "module": "game", "seq": 2, "title": "copy", "run_on": "target", "sql": "SELECT 99", "enabled": True},
            {"step": 4, "module": "game", "seq": 1, "title": "insert", "run_on": "target", "sql": "SELECT 4", "enabled": True},
        ],
    }
    response = client.post(
        "/server_merge/execute_all/",
        data=json.dumps(payload),
        content_type="application/json",
    )
    result = json.loads(response.content.decode("utf-8"))
    assert result["status"] == 1
    assert [row["step"] for row in result["data"]["steps"]] == [2, 3]
    assert "模拟执行失败" in result["msg"]
    # 第 4 步没有执行，也没有生成日志
    assert list(
        ServerMergeLog.objects.order_by("id").values_list("step", flat=True)
    ) == [2, 3]


@pytest.mark.django_db
def test_execute_single_step_rejects_mixed_steps(
    client, super_user, merge_instances, monkeypatch
):
    target, source = merge_instances
    monkeypatch.setattr(sm, "get_engine", lambda instance: FakeEngine(FakeConnection()))
    client.force_login(super_user)
    payload = {
        "target_instance_name": target.instance_name,
        "source_instance_name": source.instance_name,
        "modules": [{"module": "game", "target_db": "dest_db", "source_db": "src_db"}],
        "items": [
            {"step": 2, "module": "common", "seq": 1, "title": "a", "run_on": "target", "sql": "SELECT 1", "enabled": True},
            {"step": 3, "module": "game", "seq": 2, "title": "b", "run_on": "target", "sql": "SELECT 2", "enabled": True},
        ],
    }
    response = client.post(
        "/server_merge/execute/",
        data=json.dumps(payload),
        content_type="application/json",
    )
    result = json.loads(response.content.decode("utf-8"))
    assert result["status"] == 1
    assert "一键执行全部" in result["msg"]


@pytest.mark.django_db
def test_databases_api_requires_instance(client, super_user):
    client.force_login(super_user)
    response = client.post("/server_merge/databases/", {})
    payload = json.loads(response.content.decode("utf-8"))
    assert payload["status"] == 1
    assert "目标实例" in payload["msg"] or "必须指定" in payload["msg"]


@pytest.mark.django_db
def test_all_endpoints_require_permission(normal_user):
    """无权限用户无法访问任何合服接口"""
    request = RequestFactory().post("/server_merge/")
    request.user = normal_user
    endpoints = [
        sm_views.server_merge,
        sm_views.server_merge_databases,
        sm_views.server_merge_templates,
        sm_views.server_merge_template_save,
        sm_views.server_merge_template_reset,
        sm_views.server_merge_preview,
        sm_views.server_merge_test_link,
        sm_views.server_merge_execute,
        sm_views.server_merge_logs,
    ]
    for endpoint in endpoints:
        with pytest.raises(PermissionDenied):
            endpoint(request)


@pytest.mark.django_db
def test_merge_template_unique_together(db, super_user):
    """同一步骤+模块+序号只能保留一份覆盖值"""
    from django.db import IntegrityError, transaction

    from sql.models import ServerMergeTemplate

    ServerMergeTemplate.objects.create(step=5, module="index", seq=1, sql="SELECT 1")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ServerMergeTemplate.objects.create(
                step=5, module="index", seq=1, sql="SELECT 2"
            )
