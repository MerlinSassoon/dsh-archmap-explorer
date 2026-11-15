from service import load_items, save_item


def main():
    """程序主入口，加载并处理学生数据。"""
    items = load_items()
    for item in items:
        if item:
            save_item(item)
    return len(items)
