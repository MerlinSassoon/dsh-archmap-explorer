"""Interactive terminal menu component."""

from __future__ import annotations

import json
import sys

import colorama
from pynput import keyboard

from ..async_feedback.spinner_manager import Spinner
from ..network.protocol_codec import ProtocolCodec
from .display_utility import get_display_width, write_table
from .student_model import STUDENT_COLUMNS, STUDENT_COLUMN_WIDTHS


colorama.init()


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
                spaces = " " * (length - get_display_width(item_display) - 4)
                sys.stdout.write("\033[7m" + f"|  {item_display}{spaces}|" + "\033[0m" + "\n")
            else:
                spaces = " " * (length - get_display_width(item_name) - 4)
                sys.stdout.write(f"|  {item_name}{spaces}|" + "\n")

        sys.stdout.write("|" + "=" * (length - 2) + "|" + "\n")
        sys.stdout.write("|" + "说明：通过数字或者↑↓方向键选择菜单，回车确认" + " " * (length - 48) + "|" + "\n")
        sys.stdout.write("+" + "-" * (length - 2) + "+" + "\n")
        sys.stdout.flush()

    def _build_table(self, tables):
        """内部 API：打印学生信息表格"""
        return write_table(tables, self.columns, self.widths)

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
            self.sockets.send(ProtocolCodec.encode(0, contents, table_name=self.table))
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
            self.sockets.send(ProtocolCodec.encode(1, key, value, table_name=self.table))
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
            self.sockets.send(ProtocolCodec.encode(2, sno, table_name=self.table))
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
            self.sockets.send(ProtocolCodec.encode(3, sno, key, value, table_name=self.table))
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
            self.sockets.send(ProtocolCodec.encode(4, desc, table_name=self.table))
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
            self.sockets.send(ProtocolCodec.encode(5, table_name=self.table))
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
            self.sockets.send(ProtocolCodec.encode(6, table_name=self.table))
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
