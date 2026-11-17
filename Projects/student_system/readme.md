# Student System

一个用于验证 ArchMap 模块化、Provider Role 与主流程投影的 Python 终端学生信息管理样例。

## 架构

```text
student_system/
├── __main__.py                 # python -m student_system
├── main.py                     # 主模块：入口与顶层编排
├── config/                     # 静态配置
│   └── database_config.py
├── model/                      # 运行期数据模型
│   ├── student_model.py
│   └── protocol_model.py
├── managers/                   # 有状态 Provider / 外部适配器
│   ├── database_manager.py
│   ├── menu_manager.py
│   ├── network_manager.py
│   └── spinner_manager.py
├── utility/                    # 无状态内部工具
│   ├── display_utility.py
│   └── protocol_utility.py
└── tests/                      # 独立验证脚本
    └── table_demo.py
```

- `main` 是唯一主模块，主流程从 `main()` 开始。
- `network`、`database`、`menu`、`async`、`contracts`、`test` 是功能模块。
- 功能模块不拥有输入/输出端口，只通过公开 Provider/Capability 暴露能力。
- `database` 与 `network` 是 adapter；`menu`、`async` 是 component/service；配置与模型属于共享契约模块。

## 运行

```bash
pip install -r requirements.txt
python -m student_system
```

表格渲染验证：

```bash
python -m student_system.tests.table_demo
```

## ArchMap

```bash
python -m archmap build Projects/student_system \
  --config examples/student_system.archmap.json \
  --out yield/student_system
```
