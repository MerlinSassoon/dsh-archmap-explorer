# ArchMap API 契约阶段规划与实现记录归档

> 归档日期：2026-11-19<br>
> 本文承接原 `docs/archmap-api-contract-model.md` 的阶段规划和 P2.2 实现记录，仅用于追溯。当前 API 契约以当前权威文档为准。

## 13. 阶段规划

```text
P2.2  Provider Role 与模块组合（已完成）
      - role 判定、config/model/manager 展示过滤
      - moduleComposition + providerRoleCounts
      - 类型卡片与 manager API 卡片分离

P2.3  ArchMap 自身 config/model/manager 重构（已完成）
      - 四类物理文件规范
      - config/model/manager/utility 目录迁移
      - providerVisibility 与 public 投影
      - 旧 import shim 已在最终清理中删除

P3    类型契约、Manager 接口与继承 API（已完成）
      - inherits / implements
      - 继承 API + override 来源
      - 多态 candidates 与 polymorphic dispatch
      - 不新增类焦点页

P4    关系、组合/聚合、API/type/provider/surface impact、trace、user surface 传播与 DSM（已完成）
      - 角色感知结构关系
      - User Surface 投影
      - Impact / Trace 查询
      - Module/Provider DSM

P8    executionOnlyCallables 与空能力模块（已完成）
      - 显式能力面排除
      - 自由函数与类方法
      - 空能力模块后端保留、前端隐藏
      - schema 6.1

P9    自由函数能力边界与模块默认面（已完成）
      - 保守自由函数推断
      - defaultFreeFunctionSurface
      - functionSurface / surface source
      - schema 6.3
```

P2.2 是 P3/P4 的前置层，不应跳过。


## 14. P2.2 实现记录

- 语言前端新增 Python Provider Role 判定，优先级为显式配置、注释/装饰器、结构规则、命名弱提示；
- 支持 `contract.providerRoles` 显式覆盖；
- Provider 节点、`apiProviders`、API capability 与自由函数 FunctionDetail 输出角色字段；
- `moduleComposition` 与 `providerRoleCounts` 进入 ModuleGraph 和项目模块卡片；
- config/model 类生成 `typeSummary`，并把方法能力从 `providedApis` 中过滤；
- 常量、枚举、dataclass/NamedTuple/TypedDict、ABC/Protocol、协议组件、外部 IO、manager 状态与静态工具类均有结构判定；
- schemaVersion 升级为 3.5，校验器新增角色、组合覆盖率、公开组合、providerVisibility、ownerProviderId 与 config/model/utility API 泄漏检查。
