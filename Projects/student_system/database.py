import json
import pymysql


class Database:
    HOST = 'localhost'
    USER = 'root'
    DATABASE_NAME = 'stusys'
    PORT = 3306
    CHARSET = 'utf8mb4'
    EFFECTIVE_TABLES = ['student_python', ]

    def __init__(self, password):
        """数据库初始化"""
        self.password = password
        self.database_name = Database.DATABASE_NAME

        self.connection = None
        self.cursor = None

        self.tables_dict = {}

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
            # 建立连接
            self.connection = pymysql.connect(
                host=Database.HOST,
                user=Database.USER,
                password=self.password,
                database=self.database_name,  # 你的数据库名
                port=Database.PORT,
                charset=Database.CHARSET,
            )
            # 创建游标
            self.cursor = self.connection.cursor()
            return self
        except pymysql.err.Error as e:
            print(f"连接失败：{e}")
            return None

    def __exit__(self, *args):
        """数据库上下文管理器出口：关闭操作游标，关闭本地数据库连接"""
        # 关闭连接
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()


    @staticmethod
    def _decode_message(received: bytes) -> tuple:
        """
        解码接收到的 JSON 字节数据，还原为 (model, parameters)

        Args:
            received: 从 socket.recv() 接收到的字节数据

        Returns:
            tuple: (model, parameters) 元组
                   model 是整数，parameters 是元组

        Example:
            received = client_socket.recv(4096)
            model, params = _decode_message(received)
            print(f"model: {model}, params: {params}")
        """
        # 解码字节为字符串，再解析 JSON
        if not received:
            raise ConnectionError("接收到空包，连接已断开")
        message = json.loads(received)
        return message['model'], message['args'], message['kwargs']

    def actions(self, client_input):
        """公开API：接收操作指令，根据指令操作数据库"""
        model, args, kwargs = self._decode_message(client_input)
        _, action = self.menu_items[model]
        result = action(*args, **kwargs)
        return json.dumps(result, default=str).encode('utf-8')

    def _get_columns(self, table_name):
        columns = self.tables_dict.get(table_name, False)
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
        def wrapper(*args, **kwargs) -> tuple:
            try:
                table_name = kwargs.get('table_name')
                # 验证表名（防止SQL注入）
                if table_name not in Database.EFFECTIVE_TABLES:
                    raise ValueError(f"无效的表名{table_name}")
                return func(*args, **kwargs)
            except (Exception, pymysql.err.Error) as e:
                if isinstance(e, pymysql.err.Error):
                    errno = e.args[0]  # 1366
                    errmsg = e.args[1]  # "Incorrect integer value: 'NULL'..."
                    return False, f"错误码: {errno}, 错误信息: {errmsg}"
                else:
                    return False, f"异常信息: {e}"

        return wrapper

    @_error_detection
    def _add_content(self, content, table_name) -> tuple:
        """内部API，面向上层应用：添加信息"""
        placeholders = ", ".join(["%s"] * len(content))
        sql = f"INSERT INTO {table_name} VALUES ({placeholders})"
        self.cursor.execute(sql, content)
        self.connection.commit()
        return True,

    @_error_detection
    def _query_key_value(self, key, value, table_name) -> tuple:
        """内部API，面向上层应用：查询信息"""
        columns = self._get_columns(table_name)
        if key not in columns:
            raise ValueError(f"无效的字段名: {key}")

        placeholders = '%s'
        sql = f"SELECT * FROM {table_name} WHERE {key} = {placeholders}"
        self.cursor.execute(sql, value)
        tables = self.cursor.fetchall()
        return True, tables

    @_error_detection
    def _delete_sno(self, sno, table_name) -> tuple:
        """内部API，面向上层应用：删除信息"""
        placeholders = '%s'
        sql = f"DELETE FROM {table_name} WHERE sno = {placeholders}"
        self.cursor.execute(sql, sno)
        self.connection.commit()
        return True,

    @_error_detection
    def _modify_sno(self, sno, key, value, table_name) -> tuple:
        """内部API，面向上层应用：更新信息"""
        columns = self._get_columns(table_name)
        if key not in columns:
            raise ValueError(f"无效的字段名: {key}")

        sql = f'UPDATE {table_name} SET {key} = %s WHERE sno = %s'
        self.cursor.execute(sql, (value, sno))
        self.connection.commit()
        return True,

    @_error_detection
    def _sort_all(self, desc, table_name) -> tuple:
        """内部API，面向上层应用：信息排序"""
        # 验证输入是否合法
        order = ""
        if desc == "倒序":
            order = "DESC"
        elif desc == "正序":
            order = "ASC"  # 或者保持空字符串
        else:
            raise ValueError("排序参数错误")

        sql = f"SELECT * FROM {table_name} ORDER BY tc {order}"
        self.cursor.execute(sql)
        tables = self.cursor.fetchall()
        return True, tables

    @_error_detection
    def _count_all(self, table_name) -> tuple:
        """内部API，面向上层应用：信息计数"""
        sql = f"SELECT COUNT(*) FROM {table_name}"
        self.cursor.execute(sql)
        tables = self.cursor.fetchall()
        return True, tables

    @_error_detection
    def _query_all(self, table_name) -> tuple:
        """内部API，面向上层应用：查询整表"""
        sql = f"SELECT * FROM {table_name}"
        self.cursor.execute(sql)
        tables = self.cursor.fetchall()
        return True, tables
