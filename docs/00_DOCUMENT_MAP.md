# 文档地图与对齐包映射

本文档说明 BuQue 项目的文档组织方式，以及业务对齐包中各 sheet 与项目文档、系统模块之间的关系。

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

具体规则、字段、路线图、验收、实现、治理，应拆分为专题文档，并与业务对齐包保持映射关系。

---

## 推荐文档结构

```text
.
├── README.md
└── docs
    ├── 00_DOCUMENT_MAP.md
    ├── 01_PROJECT_CHARTER.md
    ├── 02_ROADMAP.md
    ├── 03_ARCHITECTURE.md
    ├── 04_IMPLEMENTATION_PLAN.md
    ├── 05_RULES_AND_OUTPUTS.md
    └── 06_GOVERNANCE.md
```

---

## 对齐包 sheet 映射

| 对齐包 sheet | 主要内容 | 对应项目文档 | 对应系统模块 |
|---|---|---|---|
| 09_使用文档 | 推进顺序、会议节奏、维护方式 | 00_DOCUMENT_MAP / 04_IMPLEMENTATION_PLAN | 项目协同机制 |
| 01_规则说明书 | 项目定义、职责边界、风险类型、建议动作 | 01_PROJECT_CHARTER / 05_RULES_AND_OUTPUTS | Rule Engine / Advisor |
| 02_字段口径 | 字段定义、来源、刷新、质量要求 | 03_ARCHITECTURE / 06_GOVERNANCE | Field Contract / Data Quality |
| 03_输出模板 | 日报、风险清单、单 SKU 分析卡、反馈模板 | 05_RULES_AND_OUTPUTS | Report / Alert / Feedback |
| 04_开发实现清单 | 数据接入、处理链路、表结构、开发任务 | 03_ARCHITECTURE / 04_IMPLEMENTATION_PLAN | Data Pipeline / Agent Runtime |
| 05_一期范围_验收 | 一期范围、验收指标、关键口径待确认 | 02_ROADMAP / 04_IMPLEMENTATION_PLAN | Acceptance / Release Gate |
| 06_规则参数表 | 参数编码、阈值、权限、版本管理 | 05_RULES_AND_OUTPUTS / 06_GOVERNANCE | Config Registry |
| 07_业务解释规则表 | 现象、候选解释、证据排序、建议动作 | 05_RULES_AND_OUTPUTS | Explanation Engine |
| 08_解释选项库 | 解释选项字典与下拉标准 | 05_RULES_AND_OUTPUTS / 06_GOVERNANCE | Explanation Taxonomy |
| 只读账户 | 只读账号信息 | 不进入 README，不进入仓库 | Secret / 环境变量管理 |

---

## SSOT 关系

SSOT 是 Single Source of Truth，即“单一事实源”。

本项目中建议这样划分：

| 内容 | SSOT 建议 |
|---|---|
| 字段定义 | 字段口径表 + docs/03_ARCHITECTURE.md |
| 风险规则 | 规则参数表 + docs/05_RULES_AND_OUTPUTS.md |
| 解释选项 | 解释选项库 + docs/05_RULES_AND_OUTPUTS.md |
| 一期范围 | docs/02_ROADMAP.md + docs/04_IMPLEMENTATION_PLAN.md |
| 验收指标 | docs/04_IMPLEMENTATION_PLAN.md |
| 权限与安全 | docs/06_GOVERNANCE.md |
| 产品总览 | README.md |

---

## 文档维护规则

1. README 不直接维护大段规则参数，只保留能力摘要和入口。
2. 风险阈值变更必须优先改规则参数表，再同步 docs/05。
3. 字段口径变更必须同步字段契约、数据质量校验和下游输出。
4. 涉及账号、密码、Cookie、Token 的内容不得进入 README 或 docs。
5. 每次口径变更应记录版本号、生效日期、提出人、审批人和变更原因。
6. 对齐包可以作为业务评审材料，但系统实现应以“配置表 + 版本化文档 + 代码测试”共同固化。
