# dsh-archmap-explorer 曝光规划

> 状态：已规划，未开始执行<br>
> 记录日期：2026-11-20<br>
> 范围：只做分发、呈现与收录，不改分析内核、不改 bundle schema<br>
> 依据：本仓库当前状态（git / package.json / docs）+ 2026-11-20 公开渠道实测<br>
> 结论先行：当前不是“曝光不足”，是“还没有接上任何分发管道”。先修管道与首屏，再投放。

## 1. 现状诊断

### 1.1 仓库事实（2026-11-20 实测）

| 项 | 实测值 | 判断 |
|---|---|---|
| GitHub topics | 空 | 不在 `dsh-plugin` 聚合页，等于主动退出生态入口 |
| star / fork / watcher | 0 / 0 / 0 | 仓库 11-18 创建，除作者外无人知晓 |
| homepage / Pages | 无 / 未启用 | 没有“点开就能玩”的入口 |
| CI / issue 模板 | 无 / 无 | 无质量徽章，外部问题只能靠自由格式 |
| 仓库图片资产 | 0 张（`git ls-files` 无 png/gif/svg/webp） | README 纯文字，架构图产品却无一张图 |
| 提交文件数 | 187（docs 54、archmap 57、tests 50） | 文档与测试密度高，工程可信度好 |
| npm 包 | `dsh-archmap-explorer` registry 404 | 未发布；README 与 `docs/dsh-plugin.md` 已把“npm 包名”当事实写 |
| 生态索引 | 不在 awesome-dsh-plugin、不在 dshbase | 26,846 条插件目录里搜不到 |

### 1.2 产物能力（实测）

| 验证项 | 结果 |
|---|---|
| 零配置首次运行 | `python3 -m archmap build . --out ...` 在无 `archmap.config.json` 的新目录可跑通（1 模块 / 5 函数） |
| HTML 自包含 | 无 `fetch` / XHR / 外部 `script`、`link`，可 `file://` 直接打开、可直接静态托管 |
| 体积 | 玩具项目 212 KB；`student_system_v15` 760 KB；`.archmap/self` 8.38 MB；`yield/dsh_archmap_v14` 6.9 MB |
| 界面语言 | `<html lang="zh-CN">`，`archmap/render/assets/app.js` 内为中文串，无 i18n |
| 测试基线 | Python 163 passed / 1 skipped；Node 11 passed；浏览器冒烟 1 passed |
| 包体 | `npm pack` 77 files / 223.2 kB |

### 1.3 五个断点（按影响排序）

1. **npm 未发布**：所有生态索引（awesome 列表 / dshbase / DSH 原生 Discover）都按 npm 包和版本号收录；没有 npm，就没有任何一条自动发现路径。
2. **安装摩擦**：唯一安装方式是 `git+https`，且 pnpm 10 会拦 `prepare`，必须手改 `onlyBuiltDependencies`（见 HANDOFF 0.2.1 §4）。这不是“多一步”，这是新用户流失点。
3. **首屏不可读**：README 第一屏是版本号、`bundle schema 6.4`、“ArkTS 前端尚未实现”和三层投影 ASCII 树。读者 5 秒内得不到“输入什么 / 输出什么 / 怎么试”。
4. **无法试玩**：没有 demo 站点。而本项目的产物恰好是自包含 HTML，天然适合零安装体验——这是最被浪费的优势。
5. **Quick Start 在克隆后断裂**：第 2、5 条命令引用 `Projects/student_system`，而 `Projects/` 在 `.gitignore` 内；第 4 条 `check yield/...` 依赖未入库的 `yield/`。新克隆者必失败。

### 1.4 产品成熟度（决定“什么时候能对外说”）

`docs/2026-11-19-...-改进计划.md` 第 13 节记录：P0-1 / P0-2 / P0-3 完成，P0-4 / P0-5 部分完成，P1-1（属性链 / cast / Protocol 单实现解析）、P1-2、P1-3、P1-5 未做。含义：

- **可以对外说**：模块/执行流/方法下钻、确定性静态分析、离线单文件、`impact/trace/dsm` 查询。
- **不能对外说**：完整的调用图事实、高置信度 Provider Role、适用于任意动态 Python 代码。
- **曝光必须配套**：demo 选题要避开 Protocol / 动态分发密集的项目；README 要有一节“已知限制”，把 `复盘` 里的 P1 项写成人话，先降低预期，再兑现。

### 1.5 环境前置（发布前必须处理）

| 项 | 现状 | 处理 |
|---|---|---|
| npm registry | `~/.npmrc` 指向 `registry.npmmirror.com`（镜像只读，不能发布） | 发布时显式 `--registry=https://registry.npmjs.org` |
| npm 登录态 | `npm whoami` → `ENEEDAUTH` | `npm login --registry=https://registry.npmjs.org`，建议开 2FA |
| 包名可用性 | `dsh-archmap-explorer` 在 registry 404 | 可用；发布当天再确认一次 |
| 目标 DSH | 本机 `@deepseek-ai/dsh` 0.2.2-rc.1，与 `engines.dsh` 一致 | 保持；发布说明写清实测版本区间 |

## 2. 定位与叙事

### 2.1 一句话定位（三选一，A/B 后固定）

- **A（用户视角，推荐）**：把 Python 仓库变成可逐层下钻的架构图，不用运行代码。
- **B（场景视角）**：接手陌生 Python 项目的第一个命令：一个离线 HTML，从项目结构点到函数源码。
- **C（差异视角）**：静态、确定、可下钻——LLM 画图给不了的三件事。

### 2.2 对谁说话

| 人群 | 他们的原话 | 我们的答句 |
|---|---|---|
| 接手遗留项目的开发者 | “这库没人敢改” | 先看结构，再改代码；一个命令出图 |
| 做 code review / 架构评审的人 | “这个 PR 动了哪一层？” | `impact` / `dsm` 给事实，不给结论 |
| DSH 用户 | “agent 说它懂架构，但没证据” | 架构事实由 Python 静态分析产出，模型只写注解 |
| 教学 / 面试准备 | “讲不清模块边界” | 图 + 源码 + callers 三件套 |

### 2.3 差异化（对外只讲三条）

| 维度 | ArchMap | LLM 生成式架构图（如 archify） | 传统依赖图工具 |
|---|---|---|---|
| 结果 | 确定性、可 check、可 diff | 每次不同，无法校验 | 确定但只到模块依赖 |
| 运行 | 不跑被测代码、不联网、不烧 token | 需要模型与 key | 通常需要装环境 |
| 粒度 | 项目 → 执行流 → 模块 → 方法/源码/callers | 多为概念层 | 模块层 |
| 产物 | 单文件 HTML，可进邮件/PR/内网 | 图片或在线页 | 图片 |

**反定位**（必须写进 README）：不是运行时追踪器，不生成 CFG、数据流图，不保证覆盖动态分发。

### 2.4 门面文案（三个触点，一次写死）

- **GitHub Description**：`DSH plugin + CLI: static Python architecture maps — drill down project → flow → module → method, offline single-file HTML, no code execution, no tokens.`
- **npm description/keywords**：保留现有 `dsh / dsh-plugin / dsh-bundle / architecture / python / archmap`，补 `static-analysis`、`code-visualization`、`legacy-code`。
- **awesome 条目（一行，面向人和 agent 双检索）**：`static architecture maps for Python projects: one command produces a self-contained drillable HTML (project → execution flow → module → method/source/callers), no runtime, no LLM, no network.`

> 生态里的“被发现”有一半是被 agent 检索：DSH 0.2.1+ 的 Discover 索引与 `plugin_market` 工具读的是同一份条目描述。文案要写成可语义匹配的句子，不是口号。

## 3. 漏斗与指标

定义五级漏斗，每级一个可观测判据；不达标不进入下一级。

| 级别 | 定义 | 判据 | 目标（4 周） |
|---|---|---|---|
| G0 可安装 | 干净 profile 一条命令装成功 | `dsh plugin add dsh-archmap-explorer` 无手工步骤 | 100% |
| G1 可试玩 | 无需安装即可看到产物 | demo URL 打开 ≤3s 可交互，体积 ≤2 MB | 3 个 demo |
| G2 被收录 | 生态索引可检索 | Discover / dshbase / awesome 三处可搜到 | 3/3 |
| G3 被试用 | 有人真的跑 | npm 周下载、demo 访问、外部 issue | ≥30 下载 / ≥3 issue |
| G4 被传播 | 有人替你说 | star、转发、他人文章引用 | ≥50 star |

辅助指标：GitHub Insights referrers（哪个渠道真带量）、issue 里出现的渠道名、dshbase 卡片浏览。

## 4. P0 门槛（不完成不投放）

按顺序做，全部完成约 1.5–2 人日。

- [x] **P0-1 可分发**（2h）：npm 账号注册被风控阻断，改为 GitHub + Release tarball 主路径；`prepare`→`prepack` 后安装不再需要 pnpm 白名单，两条命令均在全新 profile 实测通过。npm 留作后补，不影响收录。
- [x] **P0-2 修 Quick Start**（1h）：已把样例整理为 `examples/taskboard` 与 `examples/student_system` 入库，README 不再引用 `Projects/` 与 `yield/`。
- [x] **P0-3 README 首屏重写**（3h）：`README.md` 英文默认（一个定位 + 徽章 + demo 入口 + 首图 + 三行 Quick Start），`README.zh.md` 保留完整中文正文。
- [~] **P0-4 demo 站点**（2h）：已可用 `scripts/build-demo-site.sh` 生成 3 个 demo + 落地页（9.2 MB）；`scripts/publish-demo-site.sh` 待推送 `gh-pages` 并开 Pages。
- [x] **P0-5 GIF**（1.5h）：`docs/assets/demo.gif`（900×562，10 帧，1.7 MB）由 4 张真实页面截图合成，展示项目页→执行流→模块→方法四层；四分镜同源 PNG 也在 `docs/assets/`。
- [~] **P0-6 仓库门面**（0.5h）：issue 模板与 `CONTRIBUTING.md` 已入仓；topics / About / Discussions 待网页操作（见操作清单 §2）。
- [x] **P0-7 CI 徽章**（1h）：`.github/workflows/ci.yml` 覆盖 Python 测试、自构建校验、插件测试；徽章已放入两份 README。

> 判据：让一个没用过 DSH 的 Python 开发者只看 README 前 20 行，能说出“输入什么、输出什么、怎么不装就试”。

## 5. 渠道矩阵

### 5.1 P0：生态内（必须做，本周）

| 渠道 | 动作 | 门槛 | 判据 | 工时 |
|---|---|---|---|---|
| GitHub topic | 加 `dsh-plugin`、`dsh`、`python`、`static-analysis`、`architecture`、`code-visualization` | 无 | topic 页能搜到自己；dshbase 抓取源命中 | 0.2h |
| npm | 发布 0.2.2（或 0.3.0） | 登录 + 正式 registry | `npm search dsh-plugin` 可命中 | 2h |
| awesome-dsh-plugin | 提一行 PR（分类：Git & Code Review 或 Development & Runtime，按实际评审意见调整） | 能用 `dsh plugin add` 装、声明 `dsh.bundle`、描述与实际一致 | PR 合并；该列表同时是 DSH 原生 Discover 的索引源 | 1h |
| 官方 Discussions | 发布贴：问题 → 产物 → demo → 一条安装命令 | 分区名以现场为准 | 有非作者回复或提问 | 1h |
| dshbase | 提交收录（issue 模板），补全 npm 状态 | 非官方站点，仅作索引 | 卡片出现并标 on npm | 0.5h |
| Release | `dsh-plugin-v0.3.0` + release notes（新增能力 / 安装方式 / 已知限制） | 版本号策略确定 | 卡片 last updated 正常 | 1h |

### 5.2 P1：中文开发者社区（第 2 周）

| 渠道 | 切入点 | 注意 |
|---|---|---|
| V2EX `/go/python` | “接手一个 3 万行 Python 老项目，我先画了张能下钻的图” | 先讲故事与踩坑，工具放文末；不贴裸链接 |
| 掘金 / 知乎 | 同题长文，配 before/after 截图 | 一篇多平台改编，不要复制粘贴 |
| 即刻 / 小红书 | 单图 + 6 秒 GIF，讲“一张图看懂模块边界” | 面向非 DSH 用户，弱化插件、强调 CLI |
| 微信 / QQ 技术群 | 仅在自己活跃的群，一次一条 | 禁群发；被踢一次损失大于收益 |

### 5.3 P2：英文社区（第 3 周起，取决于 i18n 决策）

| 渠道 | 形式 | 前置条件 |
|---|---|---|
| Hacker News | `Show HN: Static architecture maps for Python – one HTML file, no code execution`，首评自述“为什么做 / 不做什么” | 英文 README + 英文 UI 或明确标注“UI 目前中文” + demo 秒开 |
| r/Python | 复盘帖（不是招募帖） | 遵守自推广规则；先参与他人讨论再发 |
| r/coolgithubprojects / Lobsters | 简短提交 | demo 可用 |
| Python Weekly / PyCoder's Weekly | 邮件投稿 | 需英文一句话 + 链接 |
| dev.to | 迁移中文长文 | 加 canonical 链接指回仓库 |

**暂不做**：付费推广、刷 star、跨群复制粘贴、在解析缺口修复前上 HN。

## 6. 素材清单

### 6.1 README 首屏（重写目标结构）

```text
H1 + 一句话定位（§2.1 A）
badge 行：npm version / dsh-plugin / MIT / Python 3.10+ / CI
GIF（6 秒，§6.2）
三行 Quick Start：零配置出图 / 打开 HTML / DSH 里安装
▶ 在线 demo（三个入口）
“它解决什么” 3 条（接手老项目 / code review / 给 agent 一份架构事实）
“和其他工具比” 表（§2.3）
“已知限制” 4 条（诚实，来自复盘 P1）
—— 以下保留现有技术正文：配置、契约、CLI、边界
```

硬性要求：

- 第一屏不出现 `bundle schema`、`ArkTS 未实现`、`Provider Role 七类` 这类内部词汇。
- 删掉“npm 包名”这类未兑现的表述，除非 P0-1 已完成。
- 中英双 README：`README.md` 英文默认，`README.zh.md` 中文。若暂不做 i18n，英文首页必须显式写 “UI currently in Chinese”。

### 6.2 GIF 分镜（6 秒，1920×1080 → 1280×720）

| 时间 | 画面 | 字幕 |
|---|---|---|
| 0–1s | 终端：`python3 -m archmap build .` 输出 `html: .../architecture.html` | 一个命令 |
| 1–2.5s | 浏览器打开项目页，flow card 与模块卡片同层 | 项目 → 流程 → 模块 |
| 2.5–4s | 点 flow card，进入主流程，分支/循环骨架出现 | 执行流有边界 |
| 4–5s | 点模块 → 方法 → 源码 + callers | 一路点到源码 |
| 5–6s | 断网图标 + 文件图标 | 离线单文件 |

要求：录制前隐藏桌面杂物；鼠标轨迹平滑；不出现真实项目名与私有路径。

### 6.3 demo 三件套

| demo | 项目 | 预期体积 | 作用 |
|---|---|---|---|
| D1 最小 | `examples/demo_project`（自造 200–400 行） | ~220 KB | 秒开，给第一次点击 |
| D2 熟悉 | 一个知名 OSS 子集（建议 `rich` 或 `requests`） | 1–3 MB | 让读者看到自己认识的结构 |
| D3 自指 | ArchMap 分析自身（按需裁剪 `include`） | 目标 ≤3 MB | 证明能吃自己 |

D3 若压不到 3 MB，放次级链接，不进首屏。

## 7. 节奏（4 周）

| 周 | 主题 | 交付 | 工时 |
|---|---|---|---|
| W0（本周） | 通管道 | P0-1..P0-7 全部完成，awesome PR 已提 | ~10h |
| W1 | 生态内扩散 | Discussions 贴、dshbase 收录、release notes；观察首批 issue | ~5h |
| W2 | 中文社区 | 一篇长文 + 三个平台改编；V2EX 一帖 | ~6h |
| W3 | 英文（决策后） | i18n 最小面 / 英文 README；HN + 一个 subreddit | ~8h |
| W4 | 复盘 | 漏斗数据、渠道效率排序、下一轮选题 | ~2h |

发布节奏建议：把 npm 首发、README 改版、demo 上线、Quick Start 修复合成**一次 0.3.0**，形成一个可讲的故事，而不是四次小补丁。

## 8. 需要拍板的四件事

1. **是否做最小 i18n**：只翻 topbar / 图例 / 详情栏标题（约 200 条中文串），约 1–2 天。不做，英文渠道推迟；做了，HN 窗口打开。
2. **demo 主推项目**：`rich`（纯 Python、动态魔法少、结构清晰）vs `requests`（认知度高、但代码偏扁平）。建议 `rich`。
3. **样例入库**：是否把 `Projects/student_system` 整理成 `examples/demo_project/` 入库（同时修 README 断链）。
4. **版本策略**：对外是否只讲插件版本（0.2.x / 0.3.0），把 core 2.6.1 与 schema 6.4 降为内部信息。

## 9. 风险与红线

| 风险 | 触发方式 | 缓解 |
|---|---|---|
| 过早曝光 | 首发渠道第一条评论是“图不对/漏调用” | 先出 demo 与“已知限制”，P1-1 修复后再上英文渠道 |
| 安装失败即流失 | pnpm `ERR_PNPM_GIT_DEP_PREPARE_NOT_ALLOWED` | npm 发布；把 `prepare` 降级为 `prepack` 或去掉文档校验依赖 |
| demo 太大 | 首屏 8 MB HTML 加载 10s+ | 首屏只用 D1/D2；D3 次级入口 |
| 中文 UI 劝退英文用户 | HN 点击后看到中文界面 | 首屏显式标注；或做最小 i18n |
| 版本三元组混乱 | 读者分不清 0.2.1 / 2.6.1 / 6.4 | 对外只讲一个版本号 |
| 2.6 万插件噪音 | 收录后仍无人点 | 不拼功能，拼“一句话可懂”与 demo |
| 信誉透支 | 承诺“完整调用图” | README 与帖子里主动写边界 |

## 10. 复盘机制

每周一次，只看四个数：G0 安装成功率、demo 访问数、npm 下载数、外部 issue 数；再加一个定性问题：新 issue 的第一句话是“装不上”还是“图不对”。

- 若多数是“装不上”→ 停下所有投放，修安装；
- 若多数是“图不对”→ 停英文渠道，补 P1-1/P1-3；
- 若两样都少 → 渠道选错，换渠道而不是加渠道。

## 11. 与既有文档的关系

- 产品改进优先级仍以 [2026-11-19 改进计划](2026-11-19-dsh-archmap-explorer-改进计划.md) 为准；本规划不改变实现顺序，只在“可对外说”的范围上做约束。
- 安装与验证事实以 [HANDOFF 0.2.1](HANDOFF-DSH-PLUGIN-0.2.1.md) 为准。
- 本规划只新增分发与呈现动作，不改 bundle schema、不改 CLI 契约。
