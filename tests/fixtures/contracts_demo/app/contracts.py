class Resource:
    def __init__(self, name: str = "default"):
        """公开API：资源上下文。"""
        self.name = name
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def run(self):
        """公开API：执行资源任务。"""
        return self.name

    # 公开API：通过前置注释声明。
    def comment_public(self):
        return 2

    def _helper(self):
        """内部API：内部辅助。"""
        return 1


class CallableThing:
    def __init__(self, label: str = "callable"):
        self.label = label

    def __call__(self, value):
        """公开API：调用对象。"""
        return value


class IterableThing:
    def __init__(self):
        self.values = [1, 2, 3]

    def __iter__(self):
        return iter(self.values)


class SequenceThing:
    def __len__(self):
        return 0

    def __getitem__(self, index):
        raise IndexError(index)


def main():
    """公开API：程序入口。"""
    return Resource().run()


def _config_public():
    """内部API：由配置覆盖为公开。"""
    return "config"


def _local_helper():
    """内部API：普通内部函数。"""
    return "internal"
