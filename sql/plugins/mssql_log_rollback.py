# -*- coding: UTF-8 -*-
"""MSSQL online transaction log inspection and rollback draft generation."""

import datetime
import re

from sql.engines import get_engine


class MssqlLogRollback:
    SUPPORTED_SQL_TYPES = {"int", "bigint", "nchar", "nvarchar"}
    OPERATIONS = {
        "insert": "LOP_INSERT_ROWS",
        "delete": "LOP_DELETE_ROWS",
        "update": "LOP_MODIFY_ROW",
    }

    def __init__(self, instance):
        if instance.db_type != "mssql":
            raise ValueError("该工具仅支持 MSSQL 实例")
        self.instance = instance
        self.engine = get_engine(instance=instance)

    @staticmethod
    def _validate_identifier(value, name):
        if value and not re.match(r"^[\w\[\].]+$", value):
            raise ValueError("{}包含非法字符".format(name))
        return value

    def list_transactions(self, db_name, begin_time=None, end_time=None, transaction_id=None, table_name=None, operation=None, limit=200, log_backup_file=None):
        """Return transaction log metadata; this query is read-only."""
        if not db_name:
            raise ValueError("必须指定数据库名")
        self._validate_identifier(db_name, "数据库名")
        if table_name:
            for table_item in [t.strip() for t in table_name.split(",") if t.strip()]:
                self._validate_identifier(table_item, "表名")
        if operation not in (None, "", *self.OPERATIONS):
            raise ValueError("不支持的操作类型")
        conditions = ["d.[Operation] IN ('LOP_INSERT_ROWS','LOP_DELETE_ROWS','LOP_MODIFY_ROW')"]
        parameters = []
        if transaction_id:
            conditions.append("CONVERT(varchar(100), d.[Transaction ID]) = ?")
            parameters.append(transaction_id)
        if table_name:
            tables = [t.strip().strip("[]") for t in table_name.split(",") if t.strip()]
            if tables:
                table_conditions = ["d.[AllocUnitName] LIKE ?"] * len(tables)
                conditions.append("({})".format(" OR ".join(table_conditions)))
                for table_item in tables:
                    parameters.append("%{}%".format(table_item))
        if operation:
            conditions.append("d.[Operation] = ?")
            parameters.append(self.OPERATIONS[operation])
        if log_backup_file:
            if not re.match(r"^[a-zA-Z]:[\\/][^\x00]*$|^[/\\][^\x00]*$", log_backup_file):
                raise ValueError("事务日志备份文件路径不合法")
            escaped_path = log_backup_file.replace("'", "''")
            log_source = "sys.fn_dump_dblog(NULL, NULL, N'DISK', 1, N'{}')".format(escaped_path)
        else:
            log_source = "sys.fn_dblog(NULL, NULL)"
        sql = """SELECT TOP {} d.[Current LSN], d.[Transaction ID],
            b.[Begin Time] AS [Begin Time], d.[Transaction Name],
            d.[Operation], d.[Context], d.[AllocUnitName],
            d.[Page ID], d.[Slot ID], d.[RowLog Contents 0], d.[RowLog Contents 1],
            d.[RowLog Contents 2], d.[Log Record]
            FROM {} d
            LEFT JOIN (
                SELECT [Transaction ID], MAX([Begin Time]) AS [Begin Time]
                FROM {}
                WHERE [Operation] = 'LOP_BEGIN_XACT'
                GROUP BY [Transaction ID]
            ) b ON d.[Transaction ID] = b.[Transaction ID]
            WHERE {} ORDER BY d.[Current LSN] DESC""".format(
            max(1, min(int(limit), 1000)),
            log_source,
            log_source,
            " AND ".join(conditions),
        )
        result = self.engine.query(db_name=db_name, sql=sql, parameters=tuple(parameters))
        if result.error:
            raise RuntimeError(result.error)
        def _parse_time_text(value):
            if not value:
                return None
            text = str(value).strip()
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S:%f"):
                try:
                    return datetime.datetime.strptime(text, fmt)
                except ValueError:
                    continue
            return None

        parsed_begin = _parse_time_text(begin_time)
        parsed_end = _parse_time_text(end_time)

        def _parse_begin_time(value):
            if not value:
                return None
            text = str(value).strip()
            if "-" in text and ":" in text and "." not in text:
                try:
                    return datetime.datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass
            try:
                return datetime.datetime.strptime(text, "%Y/%m/%d %H:%M:%S:%f")
            except ValueError:
                return None

        formatted = []
        for row in result.rows:
            item = {}
            for key, value in zip(result.column_list, row):
                if isinstance(value, bytes):
                    item[key] = "0x{}".format(value.hex())
                elif isinstance(value, (datetime.datetime, datetime.date)):
                    item[key] = value.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    item[key] = value
            row_time = _parse_begin_time(item.get("Begin Time"))
            if row_time is not None:
                item["Begin Time"] = row_time.strftime("%Y-%m-%d %H:%M:%S")
            if parsed_begin is not None or parsed_end is not None:
                if row_time is None:
                    continue
                if parsed_begin is not None and row_time < parsed_begin:
                    continue
                if parsed_end is not None and row_time > parsed_end:
                    continue
            formatted.append(item)
        return formatted

    def get_table_schema(self, db_name, table_name):
        """Return schema metadata used by the row-image decoder."""
        self._validate_identifier(db_name, "数据库名")
        self._validate_identifier(table_name, "表名")
        result = self.engine.query(
            db_name=db_name,
            sql="""SELECT c.COLUMN_NAME, c.DATA_TYPE, c.CHARACTER_MAXIMUM_LENGTH,
                CASE WHEN pk.COLUMN_NAME IS NULL THEN 0 ELSE 1 END AS IS_PRIMARY_KEY
                FROM INFORMATION_SCHEMA.COLUMNS c
                LEFT JOIN (SELECT ku.TABLE_SCHEMA, ku.TABLE_NAME, ku.COLUMN_NAME
                    FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                    JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
                      ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
                     AND tc.TABLE_SCHEMA = ku.TABLE_SCHEMA
                     AND tc.TABLE_NAME = ku.TABLE_NAME
                    WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY') pk
                  ON pk.TABLE_SCHEMA = c.TABLE_SCHEMA
                 AND pk.TABLE_NAME = c.TABLE_NAME
                 AND pk.COLUMN_NAME = c.COLUMN_NAME
                WHERE c.TABLE_NAME = ? ORDER BY c.ORDINAL_POSITION""",
            parameters=(table_name.strip("[]").split(".")[-1],),
        )
        if result.error:
            raise RuntimeError(result.error)
        schema = []
        for row in result.rows:
            item = dict(zip(result.column_list, row))
            if item["DATA_TYPE"].lower() not in self.SUPPORTED_SQL_TYPES:
                item["supported"] = False
            else:
                item["supported"] = True
            schema.append(item)
        return schema

    @classmethod
    def decode_row_image(cls, values, schema):
        """Decode an already column-aligned row image for supported SQL types.

        The caller must provide values extracted from the log record. This method
        deliberately does not guess SQL Server's undocumented row offsets.
        """
        if len(values) != len(schema):
            raise ValueError("日志行值数量与表结构不一致")
        decoded = {}
        for value, column in zip(values, schema):
            data_type = column["DATA_TYPE"].lower()
            if data_type not in cls.SUPPORTED_SQL_TYPES:
                raise ValueError("字段 {} 类型 {} 暂不支持".format(column["COLUMN_NAME"], data_type))
            if data_type in ("int", "bigint"):
                if not isinstance(value, int):
                    raise ValueError("字段 {} 不是整数值".format(column["COLUMN_NAME"]))
            elif not isinstance(value, (str, bytes)) and value is not None:
                raise ValueError("字段 {} 不是文本值".format(column["COLUMN_NAME"]))
            decoded[column["COLUMN_NAME"]] = value.decode("utf-16-le") if isinstance(value, bytes) else value
        return decoded

    @classmethod
    def decode_log_row(cls, row_hex, schema):
        """Decode a SQL Server 2019 heap row image for supported column types."""
        if not isinstance(row_hex, str) or not row_hex.lower().startswith("0x"):
            raise ValueError("日志行内容不是十六进制数据")
        raw = bytes.fromhex(row_hex[2:])
        if len(raw) < 16:
            raise ValueError("日志行内容长度不足")
        column_count = int.from_bytes(raw[12:14], "little")
        if column_count != len(schema):
            raise ValueError("日志列数与表结构不一致")
        null_bitmap_length = (column_count + 7) // 8
        null_bitmap = raw[14:14 + null_bitmap_length]
        variable_count_offset = 14 + null_bitmap_length
        variable_count = raw[variable_count_offset]
        variable_columns = [
            column for column in schema
            if column["DATA_TYPE"].lower() == "nvarchar"
        ]
        fixed_offset = 4
        decoded = {}
        for column in schema:
            data_type = column["DATA_TYPE"].lower()
            if data_type == "int":
                size = 4
                value = int.from_bytes(raw[fixed_offset:fixed_offset + size], "little", signed=True)
                fixed_offset += size
            elif data_type == "bigint":
                size = 8
                value = int.from_bytes(raw[fixed_offset:fixed_offset + size], "little", signed=True)
                fixed_offset += size
            elif data_type == "nchar":
                length = int(column["CHARACTER_MAXIMUM_LENGTH"])
                size = length * 2
                value = raw[fixed_offset:fixed_offset + size].decode("utf-16-le").rstrip(" ")
                fixed_offset += size
            elif data_type == "nvarchar":
                value = None
            else:
                raise ValueError("字段 {} 类型 {} 暂不支持".format(column["COLUMN_NAME"], data_type))
            decoded[column["COLUMN_NAME"]] = value

        if variable_count != len(variable_columns):
            raise ValueError("日志变长列数量与表结构不一致")
        variable_offset = variable_count_offset + 1
        data_offset = variable_offset + len(variable_columns) * 2 + 1
        previous_offset = data_offset
        variable_index = 0
        for column in schema:
            column_index = schema.index(column)
            if null_bitmap[column_index // 8] & (1 << (column_index % 8)):
                decoded[column["COLUMN_NAME"]] = None
                continue
            if column["DATA_TYPE"].lower() not in ("nvarchar",):
                continue
            offset_start = variable_offset + variable_index * 2
            row_end = int.from_bytes(raw[offset_start:offset_start + 2], "big")
            if row_end < previous_offset or row_end > len(raw):
                raise ValueError("变长列偏移超出日志行范围")
            decoded[column["COLUMN_NAME"]] = raw[previous_offset:row_end].decode("utf-16-le")
            previous_offset = row_end
            variable_index += 1
        return decoded

    @classmethod
    def decode_log_entry(cls, entry, schema):
        operation = entry.get("Operation")
        if operation not in cls.OPERATIONS.values():
            return None
        context = (entry.get("Context") or "").upper()
        if context not in ("LCX_HEAP", "LCX_CLUSTERED"):
            return None
        row_hex = entry.get("RowLog Contents 0")
        if not row_hex or str(row_hex).strip() in ("0x", "0x0"):
            return None
        try:
            decoded = cls.decode_log_row(row_hex, schema)
        except ValueError:
            return None
        primary_key = {
            column["COLUMN_NAME"]: decoded[column["COLUMN_NAME"]]
            for column in schema
            if column.get("IS_PRIMARY_KEY") and column["COLUMN_NAME"] in decoded
        }
        if not primary_key:
            primary_key = dict(decoded)
        return {
            "trusted": True,
            "primary_key": primary_key,
            "columns": decoded,
            "before": decoded,
        }

    SYSTEM_CONTEXTS = {
        "LCX_PFS",
        "LCX_IAM",
        "LCX_GAM",
        "LCX_SGAM",
        "LCX_DIFF_MAP",
        "LCX_ML_MAP",
        "LCX_INDEX_LEAF",
        "LCX_INDEX_INTERIOR",
        "LCX_BOOT_PAGE",
    }

    @classmethod
    def build_rollback_draft(cls, entries):
        """Build executable SQL only from an explicitly decoded row image."""
        statements = []
        for entry in reversed(entries):
            operation = entry.get("Operation")
            table = entry.get("AllocUnitName") or "unknown_table"
            lsn = entry.get("Current LSN")
            context = (entry.get("Context") or "").upper()
            decoded = entry.get("decoded")
            if not decoded:
                if context in cls.SYSTEM_CONTEXTS:
                    statements.append(
                        "-- LSN {}: {} {} 系统页面记录（{}），非用户数据变更，无需回滚。".format(lsn, operation, table, context)
                    )
                else:
                    statements.append("-- LSN {}: {} {} skipped; row image was not decoded.".format(lsn, operation, table))
                continue
            statements.append(cls._build_decoded_statement(operation, table, decoded))
        return "\n".join(statements)

    @staticmethod
    def _quote_identifier(identifier):
        return "[{}]".format(str(identifier).strip(" []").replace("]", "]]"))

    @staticmethod
    def _sql_literal(value):
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, bytes):
            return "0x{}".format(value.hex())
        return "N'{}'".format(str(value).replace("'", "''"))

    @classmethod
    def _build_decoded_statement(cls, operation, table, decoded):
        table_sql = ".".join(cls._quote_identifier(part) for part in table.split("."))
        columns = decoded.get("columns") or {}
        primary_key = decoded.get("primary_key") or {}
        if not primary_key:
            return "-- {}: {} skipped; decoded row has no primary key.".format(operation, table)
        predicate = " AND ".join(
            "{} = {}".format(cls._quote_identifier(key), cls._sql_literal(value))
            for key, value in primary_key.items()
        )
        if operation == "LOP_INSERT_ROWS":
            return "DELETE FROM {} WHERE {};".format(table_sql, predicate)
        if operation == "LOP_DELETE_ROWS":
            names = ", ".join(cls._quote_identifier(key) for key in columns)
            values = ", ".join(cls._sql_literal(value) for value in columns.values())
            return "INSERT INTO {} ({}) VALUES ({});".format(table_sql, names, values)
        if operation == "LOP_MODIFY_ROW":
            before = decoded.get("before") or {}
            assignments = ", ".join(
                "{} = {}".format(cls._quote_identifier(key), cls._sql_literal(value))
                for key, value in before.items() if key not in primary_key
            )
            return "UPDATE {} SET {} WHERE {};".format(table_sql, assignments, predicate)
        return "-- {}: unsupported operation.".format(operation)

    def close(self):
        self.engine.close()