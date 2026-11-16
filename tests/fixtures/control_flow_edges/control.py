def guard_then_loop(items):
    """guard 分支终止后紧跟 loop。"""
    if not items:
        return None
    total = 0
    for item in items:
        total += item
    return total


def nested_loop_last(rows):
    """内层循环位于外层循环体末尾。"""
    count = 0
    for row in rows:
        for cell in row:
            count += cell
    return count


def if_break_loop(items):
    """循环体内 if + break。"""
    total = 0
    for item in items:
        if item is None:
            break
        total += item
    return total
