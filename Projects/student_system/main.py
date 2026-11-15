import sys
from database import Database
from thread_waiting import Spinner
from menu_system import MenuSystem
from TcpConnect import init_connection


def server(sockets):
    with Spinner("等待连接中"):
        client_password = sockets.recv(4096).decode('utf-8')
    with Database(client_password) as db:
        if db:
            sockets.send("SUCCESS".encode('utf-8'))
            while True:
                try:
                    client_input = sockets.recv(4096).decode('utf-8')
                    result = db.actions(client_input)
                    sockets.send(result)
                except (Exception, ConnectionError) as e:
                    print(f"错误信息：{e}")
                    break
        else:
            sockets.send("FAILURE".encode('utf-8'))


def client(sockets):
    while True:
        sockets.send(input("请输入密码：").encode('utf-8'))
        with Spinner("等待连接中"):
            received = sockets.recv(4096).decode('utf-8')
        if received == 'SUCCESS':
            menu = MenuSystem(sockets)
            menu.run()
            break
        elif received == 'FAILURE':
            sys.stdout.write("连接失败\n")
            continue


if __name__ == "__main__":
    sockets, MODEL = init_connection()
    sockets.settimeout(30)

    if MODEL == 'SERVER':
        while True:
            server(sockets)
            sockets, MODEL = init_connection()
            sockets.settimeout(30)
    elif MODEL == 'CLIENT':
        client(sockets)

    input("按任意键退出")
