# 多粒度监控分别维护

GLOBAL、WAREHOUSE、CHANNEL 三种作用域分别存事实表、分别计算 DOS，不硬编码单一粒度。WAREHOUSE 以 ERP 产品库存（SKU×仓库）为主数据源，含该仓 7天日均；订单 MSKU 销量用于 CHANNEL/GLOBAL rollup 与校验。风险清单默认 WAREHOUSE 作用域。拒绝「全国销量 ÷ 单仓库存」的隐式混算，是为与 ERP 分仓管理和业务盯仓习惯一致。
