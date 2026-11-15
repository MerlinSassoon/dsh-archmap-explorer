def hear(*content):
    print(str(content))


# hear("191005", "王燕", "女", "1999-04-17", "NULL", "NULL")

import sys
def print_students(students):
    """打印学生信息表格"""
    # 定义表头和宽度
    headers = ["sno", "sname", "ssex", "sbirthday", "speciality", "tc"]
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
    for student in students:
        sys.stdout.write("|")
        sys.stdout.write(f"{student[0]:<{widths[0]}}|")
        sys.stdout.write(f"{student[1]:<{widths[1]}}|")
        sys.stdout.write(f"{student[2]:<{widths[2]}}|")
        sys.stdout.write(f"{student[3]:<{widths[3]}}|")
        sys.stdout.write(f"{student[4]:<{widths[4]}}|")
        sys.stdout.write(f"{student[5]:>{widths[5]}}|")  # tc 右对齐
        sys.stdout.write("\n")

    # 下边框
    sys.stdout.write("+" + "+".join(["-" * w for w in widths]) + "+\n")
    sys.stdout.flush()


# 使用
students = [("191002", "张慧玲", "女", "1999-11-07", "计算机", 50)]
print_students(students)

input()