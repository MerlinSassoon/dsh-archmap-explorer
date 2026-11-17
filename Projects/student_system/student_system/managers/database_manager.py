"""Database adapter and student CRUD operations."""

from __future__ import annotations

import json
from typing import Any

import pymysql

from ..config.database_config import DatabaseConfig
from ..utility.protocol_utility import decode_message


class Database:
    """Adapter that owns the MySQL connection and command dispatch."""

    def __init__(self, password: str):
        """数据库初始化"""
        self.password = password
        self.config = DatabaseConfig()
        self.database_name = self.config.database_name

        self.connection = None
        self.cursor = None

        self.tables_dict: dict[str, list[str]] = {}

        self.menu_items = [
            ("1.录入学生信息    ", self._add_content),
            ("2.查找学生信息    ", self._query_key_value),
            ("3.删除学生信息    ", self._delete_sno),
            ("4.修改学生信息    ", self._modify_sno),
            ("5.排序            ", self._sort_all),
            ("6.统计学生总人数  ", self._count_all),
            ("7.显示所有学生信息", self._query_all),
        ]

    def __enter__(self):
        """数据库上下文管理器入口：连接本地数据库，创建操作游标"""
        try:
            self.connection = pymysql.connect(
                host=self.config.host,
                user=self.config.user,
                password=self.password,
                database=self.database_name,
                port=self.config.port,
                charset=self.config.charset,
            )
            self.cursor = self.connection.cursor()
            return self
        except pymysql.err.Error as exc:
            print(f"连接失败：{exc}")
            return None

    def __exit__(self, *args):
        """数据库上下文管理器出口：关闭操作游标，关闭本地数据库连接"""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()

    def actions(self, client_input: bytes) -> bytes:
        """公开 API：接收操作指令，根据指令操作数据库"""
        model, args, kwargs = decode_message(client_input)
        _, action = self.menu_items[model]
        result = action(*args, **kwargs)
        return json.dumps(result, default=str).encode("utf-8")

    def _get_columns(self, table_name: str) -> list[str]:
        columns = self.tables_dict.get(table_name, [])
        if not columns:
            sql = """
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = %s AND TABLE_SCHEMA = %s
                ORDER BY ORDINAL_POSITION
            """
            self.cursor.execute(sql, (table_name, self.database_name))
            self.tables_dict[table_name] = [row[0] for row in self.cursor.fetchall()]
            columns = self.tables_dict[table_name]
        return columns

    @staticmethod
    def _error_detection(func):
        def wrapper(*args, **kwargs) -> tuple[Any, ...]:
            try:
                table_name = kwargs.get("table_name")
                if table_name not in DatabaseConfig().effective_tables:
                    raise ValueError(f"无效的表名{table_name}")
                return func(*args, **kwargs)
            except (Exception, pymysql.err.Error) as exc:
                if isinstance(exc, pymysql.err.Error):
                    errno = exc.args[0]
                    errmsg = exc.args[1]
                    return False, f"错误码: {errno}, 错误信息: {errmsg}"
                return False, f"异常信息: {exc}"

        return wrapper

    @_error_detection
    def _add_content(self, content, table_name) -> tuple[Any, ...]:
        """内部 API，面向上层应用：添加信息"""
        placeholders = ", ".join(["%s"] * len(content))
        sql = f"INSERT INTO {table_name} VALUES ({placeholders})"
        self.cursor.execute(sql, content)
        self.connection.commit()
        return (True,)

    @_error_detection
    def _query_key_value(self, key, value, table_name) -> tuple[Any, ...]:
        """内部 API，面向上层应用：查询信息"""
        columns = self._get_columns(table_name)
        if key not in columns:
            raise ValueError(f"无效的字段名: {key}")
        sql = f"SELECT * FROM {table_name} WHERE {key} = %s"
        self.cursor.execute(sql, value)
        return True, self.cursor.fetchall()

    @_error_detection
    def _delete_sno(self, sno, table_name) -> tuple[Any, ...]:
        """内部 API，面向上层应用：删除信息"""
        sql = f"DELETE FROM {table_name} WHERE sno = %s"
        self.cursor.execute(sql, sno)
        self.connection.commit()
        return (True,)

    @_error_detection
    def _modify_sno(self, sno, key, value, table_name) -> tuple[Any, ...]:
        """内部 API，面向上层应用：更新信息"""
        columns = self._get_columns(table_name)
        if key not in columns:
            raise ValueError(f"无效的字段名: {key}")
        sql = f"UPDATE {table_name} SET {key} = %s WHERE sno = %s"
        self.cursor.execute(sql, (value, sno))
        self.connection.commit()
        return (True,)

    @_error_detection
    def _sort_all(self, desc, table_name) -> tuple[Any, ...]:
        """内部 API，面向上层应用：信息排序"""
        if desc == "倒序":
            order = "DESC"
        elif desc == "正序":
            order = "ASC"
        else:
            raise ValueError("排序参数错误")
        sql = f"SELECT * FROM {table_name} ORDER BY tc {order}"
        self.cursor.execute(sql)
        return True, self.cursor.fetchall()

    @_error_detection
    def _count_all(self, table_name) -> tuple[Any, ...]:
        """内部 API，面向上层应用：信息计数"""
        sql = f"SELECT COUNT(*) FROM {table_name}"
        self.cursor.execute(sql)
        return True, self.cursor.fetchall()

    @_error_detection
    def _query_all(self, table_name) -> tuple[Any, ...]:
        """内部 API，面向上层应用：查询整表"""
        sql = f"SELECT * FROM {table_name}"
        self.cursor.execute(sql)
        return True, self.cursor.fetchall()
