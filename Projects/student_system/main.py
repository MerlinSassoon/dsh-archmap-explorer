import sys
from database import Database
from thread_waiting import Spinner
from menu_system import MenuSystem
from TcpConnect import init_connection


def server(sockets):
    """服务器端：接收客户端发信，操作本地数据库，发送数据库快照"""
    with Spinner("等待连接中") as sp:
        client_password = sockets.recv(4096).decode('utf-8')
    if sp.timeout_occurred:
        print("等待客户端连接超时。\n")
        return  # 关键：不要继续往下走
    with Database(client_password) as db:
        if db:
            sockets.send("SUCCESS".encode('utf-8'))
            while True:
                try:
                    client_input = sockets.recv(4096).decode('utf-8')
                    if client_input == 'EXIT':
                        break
                    result = db.actions(client_input)
                    sockets.send(result)
                except (Exception, ConnectionError) as e:
                    print(f"\n错误信息：{e}\n")
                    break
        else:
            sockets.send("FAILURE".encode('utf-8'))


def client(sockets):
    """客户端：接收数据库快照，组织展示数据库快照，接收用户操作并向服务器端发信"""
    while True:
        sockets.send(input("请输入密码：").encode('utf-8'))
        received = 'FAILURE'
        with Spinner("等待连接中"):
            received = sockets.recv(4096).decode('utf-8')
        if received == 'SUCCESS':
            menu = MenuSystem(sockets)
            menu.run()
            break
        elif received == 'FAILURE':
            sys.stdout.write("连接失败\n")
            break


if __name__ == "__main__":
    while True:
        sockets, MODEL = init_connection()
        sockets.settimeout(10)
        if MODEL == 'SERVER':
            server(sockets)

        elif MODEL == 'CLIENT':
            client(sockets)
            sockets.send('EXIT'.encode('utf-8'))

        status = input("按Q键退出，或者按其他键返回主菜单：")
        if status.upper() == 'Q':
            break
