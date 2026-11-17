"""Composition root for the terminal student information system."""

from __future__ import annotations

import sys

from .managers.database_manager import Database
from .managers.menu_manager import MenuSystem
from .managers.network_manager import NetworkAdapter
from .managers.spinner_manager import Spinner


def server(sockets):
    """服务器端：接收客户端发信，操作本地数据库，发送数据库快照"""
    with Spinner("等待连接中") as spinner:
        client_password = sockets.recv(4096).decode("utf-8")
    if spinner.timeout_occurred:
        print("等待客户端连接超时。\n")
        return

    with Database(client_password) as database:
        if database:
            sockets.send("SUCCESS".encode("utf-8"))
            while True:
                try:
                    client_input = sockets.recv(4096).decode("utf-8")
                    if client_input == "EXIT":
                        break
                    result = database.actions(client_input)
                    sockets.send(result)
                except (Exception, ConnectionError) as exc:
                    print(f"\n错误信息：{exc}\n")
                    break
        else:
            sockets.send("FAILURE".encode("utf-8"))


def client(sockets):
    """客户端：接收数据库快照，组织展示数据库快照，接收用户操作并向服务器端发信"""
    while True:
        sockets.send(input("请输入密码：").encode("utf-8"))
        received = "FAILURE"
        with Spinner("等待连接中"):
            received = sockets.recv(4096).decode("utf-8")
        if received == "SUCCESS":
            menu = MenuSystem(sockets)
            menu.run()
            break
        if received == "FAILURE":
            sys.stdout.write("连接失败\n")
            break


def main():
    """程序入口：选择角色并编排客户端/服务端主循环。"""
    network = NetworkAdapter()
    while True:
        sockets, model = network.init_connection()
        sockets.settimeout(10)
        if model == "SERVER":
            server(sockets)
        elif model == "CLIENT":
            client(sockets)
            sockets.send("EXIT".encode("utf-8"))

        status = input("按Q键退出，或者按其他键返回主菜单：")
        if status.upper() == "Q":
            break


if __name__ == "__main__":
    main()
