from repo import read_all, write_one


def load_items():
    """加载全部学生记录。"""
    rows = read_all()
    return rows


def save_item(item):
    # 保存单个学生记录并返回结果
    return write_one(item)
