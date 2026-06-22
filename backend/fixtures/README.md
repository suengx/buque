# M1 业务输入清单

开工前请计划/仓储团队提供以下材料，放入 `backend/fixtures/` 对应路径：

| 文件 | 说明 | 状态 |
|---|---|---|
| `focus_skus.csv` | 重点 SKU 清单 | 已提供样例 |
| `focus_warehouses.csv` | 重点仓库清单 | 已提供样例 |
| `msku_mapping.csv` | MSKU→Basic SKU 映射 | 已提供样例 |
| `excel_baseline.xlsx` | Excel 监控对照基准 | **待业务提供** |
| `mapping_anomalies.csv` | 映射异常样例 | **待业务提供** |

字段契约 SSOT：`backend/contracts/field_contract.yaml`

对照脚本：

```bash
uv run python scripts/compare_excel.py --baseline fixtures/excel_baseline.xlsx --system data/system_export.csv --keys sku,warehouse
```
