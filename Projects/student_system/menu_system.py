import sys
import json
import colorama
import unicodedata
from pynput import keyboard
from thread_waiting import Spinner

colorama.init()


def _get_display_width(text):
    """计算字符串在终端的显示宽度（中文算2，英文算1）"""
    width = 0
    for ch in text:
        # F: Fullwidth, W: Wide, A: Ambiguous（中文环境下视为宽字符）
        if unicodedata.east_asian_width(ch) in ('F', 'W', 'A'):
            width += 2
        else:
            width += 1
    return width


class MenuSystem:
    key_one_time_set = set()

    def __init__(self, sockets):
        """学生信息管理系统前端展示UI初始化"""
        self.menu_items = [
            ("1.录入学生信息    ", self._add_student),
            ("2.查找学生信息    ", self._query_student),
            ("3.删除学生信息    ", self._delete_student),
            ("4.修改学生信息    ", self._modify_student),
            ("5.排序            ", self._sort_students),
            ("6.统计学生总人数  ", self._count_students),
            ("7.显示所有学生信息", self._show_all_students),
            ("0.退出系统        ", self._exit_system)
        ]
        self.sockets = sockets

        self.table = "student_python"
        self.columns = ["sno", "sname", "ssex", "sbirthday", "speciality", "tc"]
        self.current_selection = 0
        self.running = True

        self.listener = None

    def _print_menu(self, highlight_index):
        """内部API：打印学生信息管理系统菜单"""
        length = 76
        sys.stdout.write("\033[20A")
        sys.stdout.write('\r' + ' ' * 100 + '\n')
        sys.stdout.write("-" * int((length - 18) / 2) + "学生信息管理系统" + "-" * int((length - 18) / 2) + "+" + "\n")
        sys.stdout.write("|" + " " * (length - 2) + "|" + "\n")
        sys.stdout.write("|" + "=" * int((length - 12) / 2) + " 功能菜单 " + "=" * int((length - 12) / 2) + "|" + "\n")
        sys.stdout.write("|" + " " * (length - 2) + "|" + "\n")

        for i, (item_name, _) in enumerate(self.menu_items):
            if i == highlight_index:
                item_display = "> " + item_name + " <"
                spaces = " " * (length - _get_display_width(item_display) - 4)
                sys.stdout.write("\033[7m" + f"|  {item_display}{spaces}|" + "\033[0m" + "\n")
            else:
                spaces = " " * (length - _get_display_width(item_name) - 4)
                sys.stdout.write(f"|  {item_name}{spaces}|" + "\n")

        sys.stdout.write("|" + "=" * (length - 2) + "|" + "\n")
        sys.stdout.write("|" + "说明：通过数字或者↑↓方向键选择菜单，回车确认" + " " * (length - 48) + "|" + "\n")
        sys.stdout.write("+" + "-" * (length - 2) + "+" + "\n")
        sys.stdout.flush()

    def _build_table(self, tables):
        """内部API：打印学生信息表格"""
        # 定义表头和宽度
        if len(tables) == 0:
            return 0

        headers = self.columns
        widths = [8, 8, 6, 12, 12, 6]  # 根据实际数据调整

        # 上边框
        sys.stdout.write("+" + "+".join(["-" * w for w in widths]) + "+\n")

        # 表头
        sys.stdout.write("|")
        for i, header in enumerate(headers):
            sys.stdout.write(f"{header:<{widths[i]}}|")
        sys.stdout.write("\n")

        # 分隔线
        sys.stdout.write("+" + "+".join(["-" * w for w in widths]) + "+\n")

        # 数据行
        for table in tables:
            sys.stdout.write("|")
            for column in range(len(table)):
                sys.stdout.write(f"{table[column]}{' ' * (widths[column] - _get_display_width(str(table[column]))) }|")
            sys.stdout.write("\n")

        # 下边框
        sys.stdout.write("+" + "+".join(["-" * w for w in widths]) + "+\n")
        sys.stdout.flush()
        return len(tables) + 4

    @staticmethod
    def _encode_message(model: int, *args ,**kwargs) -> bytes:
        """
        将 model 和 parameters 编码为 JSON 格式的字节数据，用于 socket 发送

        Args:
            model: 整数类型，表示消息类型或命令码
            parameters: 元组类型，包含要传递的参数

        Returns:
            bytes: 编码后的字节数据，可直接用于 sockets.send()

        Example:
            data = _encode_message(1, ("login", "user123", "pass123"))
            client_socket.send(data)
        """
        message = {
            "model": model,
            "args": args,
            "kwargs": kwargs
        }
        # 转换为 JSON 字符串，再编码为字节
        return json.dumps(message).encode('utf-8')

    @staticmethod
    def _key_one_time(func):
        def wrapper(*args, **kwargs):
            key = args[1]
            if key not in MenuSystem.key_one_time_set:
                func(*args, **kwargs)

        return wrapper

    @_key_one_time
    def _on_press(self, key, is_press):
        try:
            MenuSystem.key_one_time_set.add(key)
            if key == keyboard.Key.up:
                self.current_selection = (self.current_selection - 1) % len(self.menu_items)
                self._print_menu(self.current_selection)
            elif key == keyboard.Key.down:
                self.current_selection = (self.current_selection + 1) % len(self.menu_items)
                self._print_menu(self.current_selection)
            elif key == keyboard.Key.enter:
                _, action = self.menu_items[self.current_selection]
                action()
                # self._print_menu(self.current_selection)
            elif hasattr(key, 'char') and key.char and key.char.isdigit():
                num = int(key.char)
                if 0 <= num < len(self.menu_items):
                    self.current_selection = num
                    _, action = self.menu_items[num]
                    action()
                    self._print_menu(self.current_selection)
        except Exception as e:
            pass

    def _on_release(self, key):
        try:
            MenuSystem.key_one_time_set.remove(key)
        except Exception as e:
            pass

    @staticmethod
    def _linespace(func):
        def wrapper(*args, **kwargs):
            space = func(*args, **kwargs)
            '''print(space)
            time.sleep(3)
            sys.stdout.write(f"\033[1A")
            sys.stdout.write('\r' + ' ' * 100 + '\r')'''
            input("操作结束，按任意键返回功能菜单")
            for _ in range(space+1):
                sys.stdout.write(f"\033[1A")
                sys.stdout.write('\r' + ' ' * 100 + '\r')

        return wrapper

    @staticmethod
    def _cyclic_operation(func):
        def wrapper(*args, **kwargs):
            space = 0
            while True:
                result = func(*args, **kwargs)
                space += int(result[2:]) + 1
                if input(f"操作{result[:2]}，是否继续操作？(y/n)") == 'n':
                    break
            return space

        return wrapper

    @_linespace
    @_cyclic_operation
    def _add_student(self):
        """内部API：录入学生信息"""
        contents = []
        for column in self.columns:
            content = input(f"请输入学生{column}:")
            if not content:
                content = None
            contents.append(content)
        contents = tuple(contents)

        with Spinner("正在录入学生信息"):
            self.sockets.send(self._encode_message(0, contents, table_name=self.table))
            result_decode = self.sockets.recv(4096).decode('utf-8')
            result = tuple(json.loads(result_decode))

        if not result[0]:
            print(result[1])
            return f"失败{len(contents) + 1}"
        else:
            return f"成功{len(contents)}"

    @_linespace
    @_cyclic_operation
    def _query_student(self):
        """内部API：查询学生信息"""
        columns = "/".join(self.columns)
        key = input(f"请输入信息查询列名({columns})：")
        value = input("请输入信息查询值：")

        with Spinner("正在查询学生信息"):
            self.sockets.send(self._encode_message(1, key, value, table_name=self.table))
            result_decode = self.sockets.recv(4096).decode('utf-8')
            result = tuple(json.loads(result_decode))

        if not result[0]:
            print(result[1])
            result = f"失败{3}"
        else:
            space = self._build_table(result[1])
            if not space:
                sys.stdout.write("查询为空\n")
                result = f"成功{3}"
            else:
                result = f"成功{2 + space}"
        return result

    @_linespace
    @_cyclic_operation
    def _delete_student(self):
        """内部API：删除学生信息"""
        sno = input("请输入待删学生信息sno：")
        with Spinner("正在删除学生信息"):
            self.sockets.send(self._encode_message(2, sno, table_name=self.table))
            result_decode = self.sockets.recv(4096).decode('utf-8')
            result = tuple(json.loads(result_decode))

        if not result[0]:
            print(result[1])
            return f"失败{2}"
        else:
            return f"成功{1}"

    @_linespace
    @_cyclic_operation
    def _modify_student(self):
        """内部API：修改学生信息"""
        columns = "/".join(self.columns)
        sno = input("请输入修改学生sno：")
        key = input(f"请输入信息修改列名({columns})：")
        value = input("请输入信息修改值：")

        with Spinner("正在修改学生信息"):
            self.sockets.send(self._encode_message(3, sno, key, value, table_name=self.table))
            result_decode = self.sockets.recv(4096).decode('utf-8')
            result = tuple(json.loads(result_decode))

        if not result[0]:
            print(result[1])
            return f"失败{4}"
        else:
            return f"成功{3}"

    @_linespace
    @_cyclic_operation
    def _sort_students(self):
        """内部API：学生信息排序"""
        desc = input("请输入按tc进行排序(正序/倒序)：")

        with Spinner("正在进行排序"):
            self.sockets.send(self._encode_message(4, desc, table_name=self.table))
            result_decode = self.sockets.recv(4096).decode('utf-8')
            result = tuple(json.loads(result_decode))

        if not result[0]:
            print(result[1])
            result = f"失败{2}"
        else:
            space = self._build_table(result[1])
            result = f"成功{1 + space}"
        return result

    @_linespace
    @_cyclic_operation
    def _count_students(self):
        """内部API：学生信息统计"""
        with Spinner("正在显示统计学生总人数"):
            self.sockets.send(self._encode_message(5, table_name=self.table))
            result_decode = self.sockets.recv(4096).decode('utf-8')
            result = tuple(json.loads(result_decode))

        if not result[0]:
            print(result[1])
            result = f"失败{1}"
        else:
            print(f"学生总人数为：{result[1][0][0]}")
            result = f"成功{1}"
        return result

    @_linespace
    @_cyclic_operation
    def _show_all_students(self):
        """内部API：查询学生信息整表"""
        with Spinner("正在显示全部学生信息"):
            self.sockets.send(self._encode_message(6, table_name=self.table))
            result_decode = self.sockets.recv(4096).decode('utf-8')
            result = tuple(json.loads(result_decode))

        if not result[0]:
            print(result[1])
            result = f"失败{1}"
        else:
            space = self._build_table(result[1])
            if not space:
                sys.stdout.write("查询为空\n")
                result = f"成功{1}"
            else:
                result = f"成功{space}"
        return result

    def _exit_system(self):
        """内部API：退出学生信息管理系统"""
        print("感谢使用，再见！")
        self.running = False
        if self.listener and self.listener.running:
            self.listener.stop()
        return False

    def run(self):
        """公开API，面向用户：启动学生信息管理系统的交互式菜单主循环"""
        self._print_menu(self.current_selection)
        with keyboard.Listener(on_press=self._on_press, on_release=self._on_release, suppress=True) as self.listener:
            self.listener.join()
