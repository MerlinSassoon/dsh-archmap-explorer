import sys
import time
import socket
from thread_waiting import Spinner


'''def init_connection(host=socket.gethostname(), port=12345):
    """初始化连接：先连后等"""
    # 1. 尝试连接
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(2)
        s.connect((host, port))
        print("已连接到对手")
        return s, 'CLIENT'
    except (ConnectionRefusedError, socket.timeout, OSError):
        # 确保失败socket关闭
        s.close()

        # 2. 作为服务器等待

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen(1)
        with Spinner("等待对手连接"):
            conn, addr = server.accept()
        server.close()
        # print(f"对手已连接: {addr}")
        return conn, 'SERVER' '''


def init_connection(port=12345):
    """初始化连接：让用户选择角色"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    local_ip = s.getsockname()[0]

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
        return create_server(local_ip, port)
    elif choice == "2":
        host = input("请输入服务器IP地址: ").strip()
        sys.stdout.write("\033[1B")
        if not host:
            host = local_ip  # 默认本机
        return connect_to_server(host, port)
    else:
        print("无效选择")
        return init_connection(port)


def create_server(local_ip, port):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((local_ip, port))
    server.listen(1)

    with Spinner("等待连接"):
        conn, addr = server.accept()
    server.close()
    return conn, 'SERVER'


def connect_to_server(local_ip, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)

    try:
        with Spinner("尝试连接服务器"):
            s.connect((local_ip, port))
    except (ConnectionRefusedError, socket.timeout, OSError):
        # sys.stdout.write("无连接，请重试！")
        return connect_to_server(local_ip, port)

    return s, 'CLIENT'
