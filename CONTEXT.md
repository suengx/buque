# 补雀 BuQue

面向跨境电商计划团队的库存与销量监控预警 Agent。规则负责稳定判断，Agent 负责解释与建议，人工反馈负责学习闭环。

## Language

**Basic SKU**:
公司内部最小库存与销量分析单元，ERP「产品名称/SKU」中的货号。
_Avoid_: SKU（单独使用时歧义大）, GSKU

**MSKU**:
平台店铺链接级售卖编号，订单「订购数量」的原始粒度。
_Avoid_: 平台 SKU, 链接 SKU

**FNSKU**:
Amazon FBA 仓内履约标签，仅 FBA 发货/库存场景使用。
_Avoid_: MSKU, Basic SKU

**GSKU**:
对齐包备注用语，非 ERP 正式字段；等同于 Basic SKU（计划/预测维度）。
_Avoid_: 作为独立主键层维护

**订购数量**:
订单商品行的下单件数，销量统计唯一来源；与订单状态、发货数量无关。
_Avoid_: 付款量, 出库量, 发货数量

**DOS**:
可售天数，等于当前可售库存除以未来参考日均销量；分子不含在途。
_Avoid_: 把在途加进 DOS 分子

**在途安全窗口**:
独立于 DOS 的断货缓释判断：比较预计断货日与在途 ETA、未收量及 TMS 状态。
_Avoid_: 与 DOS 混算

**未来参考日均销量**:
DOS 分母。一期无预测输入时，**原样**取 ERP 产品库存「7天日均」为 ref_daily_sales；`SALES_SPIKE_TRIM` 规则预留、**一期默认关闭**。预测接入后按 `BASE_SALES_PRIORITY` 配置取值。
_Avoid_: 一期硬编码预测优先, 无预测时阻塞 DOS, 一期擅自修正 ERP 7天日均

**预测接入**:
计划系统/Excel 的正式预测数据输入；一期可选，二期用于预测偏差与 BASE_SALES_PRIORITY 首选来源。
_Avoid_: 把预测当作一期 DOS 的前置条件

## 监控粒度（Monitoring Scope）

**GLOBAL**:
Basic SKU 在全渠道、全仓合并视角下的指标rollup。
_Avoid_: 全平台（与「平台」混淆时）

**WAREHOUSE**:
Basic SKU 在单个仓库（如 COSIEST:US_FBA、W508 三方仓）视角下的指标。
_Avoid_: 站点, 店铺

**CHANNEL**:
Basic SKU 在单个销售平台（Amazon、Wayfair、Temu）视角下的指标。
_Avoid_: 店铺, 仓库

**产品库存**:
ERP 仓库模块下 SKU×仓库明细视图；提供可售库存、7天日均、周转天数等，是 WAREHOUSE 作用域的主数据源。
_Avoid_: 仓库库存（整仓汇总，非 SKU 明细）

## Relationships

- 多个 **MSKU** 映射到一个 **Basic SKU**
- **订购数量** 原始粒度为 MSKU + 平台 + 店铺；可 rollup 为 CHANNEL 或 WAREHOUSE 或 GLOBAL，**各粒度分别存事实表，不互相替代**
- **DOS** 公式相同（可售库存 ÷ 参考日销），但在 **GLOBAL / WAREHOUSE / CHANNEL** 各作用域分别计算；分子分母必须处于同一作用域
- **在途安全窗口** 在 **Basic SKU + 仓库** 层判断，不修改 DOS 公式
- 有 ETA 且 TMS 状态为**已出运 / 入库中**的在途批次，可参与缓释判断；**提货中**仅展示、不参与降灯；无 ETA 的仓内在途量仅展示/校验，不参与缓释
- DOS 红灯且缓释成立时，**允许降一级为橙灯**，须输出「需关注到货兑现」；`INBOUND_DELAY_DAYS` 触发延期则升回
- 风险清单默认展示 **WAREHOUSE** 作用域；日报总览可同时展示 **GLOBAL** 汇总

## Example dialogue

> **Dev:** 「COS-F1001016 昨天卖了 3 件，C0150515 的 DOS 怎么算？」
> **Domain expert:** 「订购数量先挂在 MSKU 上。C0150515 在 COSIEST:US_FBA 仓看仓级 DOS，用该仓可售和该仓参考日销；全局是否紧张再看 GLOBAL rollup。在途不并进 DOS，单独看 ETA。」

## 一期 Grill 收口（2026-06-22）

**状态：已闭合。** 一期 P0 架构与规则口径已拍板，可进入 M1 与开发。

### 开发阅读顺序

1. [`CONTEXT.md`](CONTEXT.md) — 术语、关系、已决议项（冲突时优先）
2. [`docs/03_ARCHITECTURE.md`](docs/03_ARCHITECTURE.md) — 链路、表结构、数据质量
3. [`docs/05_RULES_AND_OUTPUTS.md`](docs/05_RULES_AND_OUTPUTS.md) — 规则参数与输出模板
4. [`docs/04_IMPLEMENTATION_PLAN.md`](docs/04_IMPLEMENTATION_PLAN.md) — 工作流、里程碑、**开发启动清单**
5. [`docs/adr/`](docs/adr/) — 难逆转的架构取舍（可选深读）

对齐包 [`docs/desensitized_raw_docs.xlsx`](docs/desensitized_raw_docs.xlsx) 为历史评审材料，**不反向驱动实现**；实现以 CONTEXT + 配置化 docs 为准。

### 一期内延后（非歧义，不阻塞开工）

| 事项 | 处理 |
|---|---|
| 重点 SKU / 仓 / 类目清单 | M1 由业务提供 |
| 运营计划接入 | P1，可模板导入或阶段 2 再补 |
| 红即时 / 橙日报提醒 | P1，规则跑通后补 |
| RPA 字段补齐（如 TMS `未收量`） | 开发对接 ERP 时实现 |
| 阈值微调 | 试运行后按 Excel 一致率调参 |

### 一期默认配置（实现对照）

```text
BASE_SALES_PRIORITY      = ERP 7天日均（无预测时）
SALES_SPIKE_TRIM         = false
FORECAST_BIAS_ENABLED    = false
INBOUND_RELIEF_DOWNGRADE = true
INBOUND_TMS_ELIGIBLE     = 已出运, 入库中
TIMEZONE                 = Asia/Shanghai
```

## Resolved decisions（2026-06-22）

| # | 议题 | 决议 |
|---|---|---|
| 1 | 在途赶得上是否降橙灯 | **允许**红→橙，须附「需关注到货兑现」；延期升回 |
| 2 | 一期 ref_daily_sales | **原样 ERP 7天日均**；`SALES_SPIKE_TRIM` 预留、默认关闭 |
| 3 | 预测偏差一期 | `FORECAST_BIAS_ENABLED=false`；`fact_forecast_version` 表结构预留 |
| 4 | TMS 状态分层 | **已出运 / 入库中** 可缓释；**提货中** 仅展示 |
| 5 | 无 ETA 仓内在途 | **仅展示/校验**，不参与缓释与降灯 |
| 6 | 阈值默认值 | **采用 `06_规则参数表` 默认值**（DOS 30/45、`KEY_SKU_UPGRADE=TRUE` 等） |
| 7 | 解释是否一期必交付 | **是**；一期三阶段：规则跑通 → 解释+日报 → 反馈；`02` 产品 Phase 编号不与一期混读 |
| 8 | 缺预测是否拦截 | **分场景**：缺库存/销量阻断；缺预测不阻断 DOS；仅 `FORECAST_BIAS_ENABLED=true` 且缺预测时报数据异常 |

架构取舍详见 [`docs/adr/`](docs/adr/)。

## Resolved notes

以下项曾在对齐包或讨论中出现歧义，均已闭合，供开发查阅：
- 「GSKU」在对齐包字段备注中出现，但 ERP 无此字段；已 resolved：视为 Basic SKU，不单独建层。
- 「sales_d1」在对齐包 RPA 写「近 1 天」、字段口径写「昨日」；已 resolved：以昨日市场日订购量为准。
- 多粒度维护；已 resolved：**GLOBAL / WAREHOUSE / CHANNEL 分别维护，不硬编码单一粒度**。
- WAREHOUSE 销量来源；已 resolved：**ERP 产品库存页直接提供 SKU×仓库×7天日均**，扩展 RPA 抓取；订单 MSKU 数据用于 GLOBAL/CHANNEL rollup 与校验。
- ERP 产品库存页「按SKU汇总」开关对应 GLOBAL rollup 视图。
