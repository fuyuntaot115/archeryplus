# -*- coding: UTF-8 -*-
"""
生成 Archery 合服工具（工具插件 - 合服管理）的默认 SQL 模板文件。

默认 SQL 的原始素材来源于合服脚本目录（默认 D:\\Wemade\\合服脚本\\ServerMerge_china_backup），
生成时会做最小改写，使脚本可以参数化执行：

1. ``EXEC [UP_COPY_TABLE] 'XDS'``  ->  ``EXEC [dbo].[UP_COPY_TABLE] N'{{LINKED_SERVER}}'``
2. ``linked server`` 名称统一使用 ``{{LINKED_SERVER}}`` 变量
3. ``UP_COPY_TABLE`` 存储过程内的远端源库名使用 ``{{SOURCE_DB}}`` 变量

用法::

    python scripts/generate_server_merge_defaults.py
    python scripts/generate_server_merge_defaults.py --source "D:\\Wemade\\合服脚本\\ServerMerge_china_backup"

生成结果位于 ``sql/plugins/server_merge_sql/``，属于随代码库一起提交的默认模板，
页面上的「保存为默认」会写入数据库覆盖默认值，「恢复默认」会删除覆盖并回落到这些文件。
"""

import argparse
import pathlib
import re
import sys

DEFAULT_SOURCE = r"D:\Wemade\合服脚本\ServerMerge_china_backup"

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
TARGET_ROOT = PROJECT_ROOT / "sql" / "plugins" / "server_merge_sql"

# 参考文件 -> 生成的默认模板文件
COPY_PLAN = [
    ("1. MergeMapping/0.mappingTable.sql", "common/02_03_merge_mapping.sql"),
    ("GAME/0. GAME_Pre_work.sql", "game/03_01_pre_work.sql"),
    ("GAME/1. GAME_Copy.sql", "game/03_02_copy.sql"),
    ("GAME/2. GAME_Delete.sql", "game/03_03_delete.sql"),
    ("GAME/3. GAME_Insert.sql", "game/04_01_insert.sql"),
    ("GAME/4. GAME_Post_work.sql", "game/05_01_post_work.sql"),
    ("FRONT/0. FRONT_Pre_work.sql", "front/03_01_pre_work.sql"),
    ("FRONT/1. FRONT_Copy.sql", "front/03_02_copy.sql"),
    ("FRONT/2. FRONT_Delete.sql", "front/03_03_delete.sql"),
    ("FRONT/3. FRONT_Insert.sql", "front/04_01_insert.sql"),
    ("FRONT/4. FRONT_Post_work.sql", "front/05_01_post_work.sql"),
    ("INDEX/0. INDEX_Data_Change.sql", "index/05_01_data_change.sql"),
]

ENCODINGS = ("utf-8-sig", "gbk", "cp949", "latin-1")

# 生成文件时额外加上的说明头
PREPEND = {
    "common/02_03_merge_mapping.sql": (
        "-- ============================================================================\n"
        "-- 步骤 2：在 INDEX 库中创建/更新合服映射表 MergeMapping\n"
        "-- 来源：合服脚本 1. MergeMapping/0.mappingTable.sql（可直接编辑）\n"
        "-- 说明：映射数据（WorldUID / RegionCode / WorldName / DBName）需按本次合服实际情况修改；\n"
        "--       index_data_change 会 JOIN 这张表，两者在同一个 INDEX 库中执行。\n"
        "-- ============================================================================\n"
    ),
}

# UP_COPY_TABLE 存储过程中需要参数化的远端源库名
REMOTE_DB_PATTERN = re.compile(
    r"^\s*--\s*DECLARE\s+@RemoteDBName\s+NVARCHAR\(256\)\s*=\s*N'[^']*';.*$",
    re.IGNORECASE | re.MULTILINE,
)

PROC_START_PATTERN = re.compile(r"^CREATE\s+OR\s+ALTER\s+PROC", re.IGNORECASE | re.MULTILINE)

# MergeMapping 只建在 INDEX 库，但下面这些文件的 Post_work 在 game/front 目标库执行，
# 因此需要改成跨库引用 [{{INDEX_DB}}].dbo.MergeMapping
CROSS_DB_INDEX_TARGETS = {
    "game/05_01_post_work.sql",
    "front/05_01_post_work.sql",
}

MERGE_MAPPING_PATTERN = re.compile(r"(?<![\w.\]]])MergeMapping\b")

# 针对改写过的文件额外加的说明头
CROSS_DB_HEADER = (
    "-- ============================================================================\n"
    "-- 说明：MergeMapping 建在 INDEX 库，本文件在 game/front 目标库执行，\n"
    "--       因此下面使用跨库引用 [{{INDEX_DB}}].dbo.MergeMapping（INDEX 库由第一步选择自动带入）。\n"
    "-- ============================================================================\n"
)


def read_text(path: pathlib.Path) -> str:
    """按常见编码读取脚本，参考脚本混合了 utf-8 与 gbk。"""
    raw = path.read_bytes()
    for encoding in ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def normalize(text: str) -> str:
    """统一换行符并去掉行尾空白。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n"


def parameterize(text: str) -> str:
    """把写死的链接服务器名替换为变量。"""
    # EXEC [UP_COPY_TABLE] 'XDS', 'dbo', 'xxx', 1
    text = re.sub(
        r"\[\s*UP_COPY_TABLE\s*\]\s*'XDS'",
        r"[dbo].[UP_COPY_TABLE] N'{{LINKED_SERVER}}'",
        text,
        flags=re.IGNORECASE,
    )
    return text


def qualify_merge_mapping(text: str) -> str:
    """将未限定的 MergeMapping 改为跨库引用 INDEX 库中的表"""
    return MERGE_MAPPING_PATTERN.sub("[{{INDEX_DB}}].dbo.MergeMapping", text)


def build_up_copy_table(source_file: pathlib.Path) -> str:
    """从 linkserver.sql 中抽取 UP_COPY_TABLE 存储过程定义。"""
    text = read_text(source_file)
    match = PROC_START_PATTERN.search(text)
    if not match:
        raise RuntimeError("未在 %s 中找到 UP_COPY_TABLE 存储过程定义" % source_file)
    text = text[match.start():]
    text = REMOTE_DB_PATTERN.sub(
        "DECLARE @RemoteDBName NVARCHAR(256) = N'{{SOURCE_DB}}';", text
    )
    if "@RemoteDBName NVARCHAR(256) = N'{{SOURCE_DB}}'" not in text:
        text = text.replace(
            "@RemoteDBName NVARCHAR(256)",
            "@RemoteDBName NVARCHAR(256) = N'{{SOURCE_DB}}'",
            1,
        )
    return normalize(text)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成合服默认 SQL 模板")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="参考合服脚本目录")
    args = parser.parse_args()

    source_root = pathlib.Path(args.source)
    if not source_root.exists():
        print("参考目录不存在: %s" % source_root, file=sys.stderr)
        return 1

    TARGET_ROOT.mkdir(parents=True, exist_ok=True)

    written = []

    # 1. UP_COPY_TABLE 存储过程（来自 linkserver.sql）
    proc_text = build_up_copy_table(source_root / "linkserver.sql")
    proc_path = TARGET_ROOT / "common" / "02_02_up_copy_table.sql"
    proc_path.parent.mkdir(parents=True, exist_ok=True)
    proc_path.write_text(proc_text, encoding="utf-8", newline="\n")
    written.append(proc_path)

    # 2. 业务脚本（GAME / FRONT / INDEX）
    for relative_source, relative_target in COPY_PLAN:
        source_file = source_root / relative_source
        if not source_file.exists():
            print("跳过缺失文件: %s" % source_file, file=sys.stderr)
            continue
        content = parameterize(read_text(source_file))
        if relative_target in CROSS_DB_INDEX_TARGETS:
            content = CROSS_DB_HEADER + qualify_merge_mapping(content)
        content = PREPEND.get(relative_target, "") + content
        target_file = TARGET_ROOT / relative_target
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(normalize(content), encoding="utf-8", newline="\n")
        written.append(target_file)

    for path in written:
        print("生成 %s" % path.relative_to(PROJECT_ROOT))
    print("共生成 %d 个默认 SQL 模板" % len(written))
    return 0


if __name__ == "__main__":
    sys.exit(main())
