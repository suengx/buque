# 文档地图与对齐包映射

本文档说明 BuQue 项目的文档组织方式，以及业务对齐包中各 sheet 与项目文档、系统模块之间的关系。

**一期 Grill 已于 2026-06-22 收口。** 领域术语与已拍板决策以根目录 [`CONTEXT.md`](../CONTEXT.md) 为准；实现启动见 [`04_IMPLEMENTATION_PLAN.md`](04_IMPLEMENTATION_PLAN.md) 第 9 节。

---

## 文档设计原则

BuQue 的文档不应把所有内容堆进 README。

README 只负责说明：

- 项目是什么
- 为什么做
- 解决什么问题
- 当前能力是什么
- 文档入口在哪里
- 项目边界是什么

具体规则、字段、路线图、验收、实现、治理，应拆分为专题文档。对齐包 xlsx 保留为业务评审历史材料，**不作为实现 SSOT**。

---

## 推荐文档结构

```text
.
├── CONTEXT.md                    ← 领域术语 + 已决议项（Grill SSOT）
├── README.md
└── docs
    ├── 00_DOCUMENT_MAP.md
    ├── 01_PROJECT_CHARTER.md
    ├── 02_ROADMAP.md
    ├── 03_ARCHITECTURE.md
    ├── 04_IMPLEMENTATION_PLAN.md
    ├── 05_RULES_AND_OUTPUTS.md
    ├── 06_GOVERNANCE.md
    ├── adr/                        ← 难逆转架构决策（按需）
    │   ├── 0001-dos-and-inbound-separate.md
    │   └── 0002-multi-grain-monitoring.md
    └── desensitized_raw_docs.xlsx  ← 对齐包（只读参考）
```

---

## 开发阅读顺序

| 顺序 | 文档 | 用途 |
|---|---|---|
| 1 | `CONTEXT.md` | 术语、关系、一期决议、默认配置 |
| 2 | `03_ARCHITECTURE.md` | 数据链路、表结构、质量拦截 |
| 3 | `05_RULES_AND_OUTPUTS.md` | 规则参数、解释、输出模板 |
| 4 | `04_IMPLEMENTATION_PLAN.md` | 里程碑、工作流、开发启动清单 |
| 5 | `06_GOVERNANCE.md` | 变更、权限、安全 |
| 6 | `docs/adr/` | 关键取舍的背景（可选） |

---

## 对齐包 sheet 映射

| 对齐包 sheet | 主要内容 | 对应项目文档 | 对应系统模块 |
|---|---|---|---|
| 09_使用文档 | 推进顺序、会议节奏、维护方式 | 00_DOCUMENT_MAP / 04_IMPLEMENTATION_PLAN | 项目协同机制 |
| 01_规则说明书 | 项目定义、职责边界、风险类型、建议动作 | 01_PROJECT_CHARTER / 05_RULES_AND_OUTPUTS | Rule Engine / Advisor |
| 02_字段口径 | 字段定义、来源、刷新、质量要求 | 03_ARCHITECTURE / 06_GOVERNANCE | Field Contract / Data Quality |
| 03_输出模板 | 日报、风险清单、单 SKU 分析卡、反馈模板 | 05_RULES_AND_OUTPUTS | Report / Alert / Feedback |
| 04_开发实现清单 | 数据接入、处理链路、表结构、开发任务 | 03_ARCHITECTURE / 04_IMPLEMENTATION_PLAN | Data Pipeline / Agent Runtime |
| 05_一期范围_验收 | 一期范围、验收指标（口径已同步至 CONTEXT） | 02_ROADMAP / 04_IMPLEMENTATION_PLAN | Acceptance / Release Gate |
| 06_规则参数表 | 参数编码、阈值、权限、版本管理 | 05_RULES_AND_OUTPUTS / 06_GOVERNANCE | Config Registry |
| 07_业务解释规则表 | 现象、候选解释、证据排序、建议动作 | 05_RULES_AND_OUTPUTS | Explanation Engine |
| 08_解释选项库 | 解释选项字典与下拉标准 | 05_RULES_AND_OUTPUTS / 06_GOVERNANCE | Explanation Taxonomy |
| 只读账户 | RPA 抓取规格（账号不进仓库） | 04 §9 / Secret 管理 | Data Ingestion |

---

## SSOT 关系

SSOT 是 Single Source of Truth，即“单一事实源”。

| 内容 | SSOT |
|---|---|
| 领域术语与已拍板决策 | **`CONTEXT.md`** |
| 难逆转架构取舍 | **`docs/adr/`** |
| 字段定义与表结构 | `03_ARCHITECTURE.md` + 字段契约（实现时固化） |
| 风险规则与一期默认参数 | `05_RULES_AND_OUTPUTS.md` + 规则配置表（实现时） |
| 解释选项 | `05_RULES_AND_OUTPUTS.md` + 解释选项库 |
| 一期范围与验收 | `02_ROADMAP.md` + `04_IMPLEMENTATION_PLAN.md` |
| 权限与安全 | `06_GOVERNANCE.md` |
| 产品总览 | `README.md` |
| 业务对齐包 | `desensitized_raw_docs.xlsx`（**只读参考，不驱动实现**） |

**冲突处理**：`CONTEXT.md` 决议 > 专题 docs > 对齐包 xlsx。

---

## 文档维护规则

1. README 不直接维护大段规则参数，只保留能力摘要和入口。
2. Grill 产生的新决议先写 `CONTEXT.md`，再按需同步专题 docs。
3. 难逆转取舍补充 `docs/adr/`，不重复扩写 CONTEXT。
4. 风险阈值变更必须优先改规则配置表，再同步 `05`。
5. 字段口径变更必须同步字段契约、数据质量校验和下游输出。
6. 涉及账号、密码、Cookie、Token 的内容不得进入 README 或 docs。
7. 每次口径变更应记录版本号、生效日期、提出人、审批人和变更原因。
