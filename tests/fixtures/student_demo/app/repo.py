def read_all():
    """读取全部记录。"""
    return []


def write_one(item):
    """写入单条记录。"""
    if item is None:
        raise ValueError("item cannot be empty")
    return True
