"""Socket adapter for role selection and connection establishment."""

from __future__ import annotations

import socket
import sys

from .spinner_manager import Spinner


class NetworkAdapter:
    """Adapter that owns user role selection and socket setup."""

    def __init__(self, port: int = 12345):
        self.port = port

    def init_connection(self):
        """初始化连接：让用户选择角色并建立初始化套接字接口"""
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("8.8.8.8", 80))
        local_ip = probe.getsockname()[0]

        sys.stdout.write("\033[1A")
        sys.stdout.write("=" * 40 + "\n")
        sys.stdout.write(f"{'学生信息管理系统':^32}\n")
        sys.stdout.write("=" * 40 + "\n")
        sys.stdout.write(f"本机IP: {local_ip}\n")
        sys.stdout.write("\n")
        sys.stdout.write("1. 创建服务器\n")
        sys.stdout.write("2. 连接服务器（输入服务器IP）\n")
        sys.stdout.write("\n")

        choice = input("请选择 (1/2): ").strip()
        if choice == "1":
            sys.stdout.write("\033[2B")
            return self.create_server(local_ip)
        if choice == "2":
            host = input("请输入服务器IP地址: ").strip()
            sys.stdout.write("\033[1B")
            if not host:
                host = local_ip
            return self.connect_to_server(host)
        print("无效选择")
        return self.init_connection()

    def create_server(self, local_ip: str):
        """创建服务端监听套接字并等待对端连接"""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((local_ip, self.port))
        server.listen(1)

        with Spinner("等待连接"):
            connection, _ = server.accept()
        server.close()
        return connection, "SERVER"

    def connect_to_server(self, local_ip: str):
        """创建客户端套接字并连接服务端"""
        connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connection.settimeout(2)
        try:
            with Spinner("尝试连接服务器"):
                connection.connect((local_ip, self.port))
        except (ConnectionRefusedError, socket.timeout, OSError):
            return self.connect_to_server(local_ip)
        return connection, "CLIENT"
