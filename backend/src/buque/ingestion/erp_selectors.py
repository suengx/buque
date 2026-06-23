"""积加 gerpgo ERP 页面选择器 SSOT（经真实环境探测固化）。"""

from dataclasses import dataclass

WEB_PREFIX = "/amzv-web"
LOGIN_PATH = "/auth/login"
APP_FRAME_URL_CONTAINS = "amzv-app"

DISMISS_TEXTS = (
    "立即体验",
    "跳过教程",
    "下一条",
    "我知道了",
    "知道了",
    "关闭",
)

INVENTORY_MULTI_PLATFORM_TABS: tuple[str, ...] = ()

TRANSPORT_TASK_HINTS = type(
    "TransportHints",
    (),
    {
        "inventory": "仓库产品库存",
        "orders": "全渠道销售订单",
    },
)()

TMS_ELIGIBLE_STATUSES = ("已出运", "入库中", "提货中")
TMS_STATUS_FILTER = TMS_ELIGIBLE_STATUSES
TMS_LIST_BATCH_PATTERN = r"DL\d{10}"
TMS_DETAIL_RECEIPT_TAB = "产品收发货明细"

TMS_LIST_TABLE = "table tbody tr, .ant-table-tbody tr"
TMS_DETAIL_LINK = 'a:has-text("详情"), button:has-text("详情"), [class*="detail"]'
TMS_DETAIL_TABLE = "table tbody tr, .ant-table-tbody tr"

ORDERS_DATE_WINDOW_DAYS = 30
ORDERS_DATE_QUICK_LABELS = ("近30天", "30天", "最近30天", "Last 30 days")
ORDERS_EXPORT_MENU_ITEM = "导出订单行数据"

INVENTORY_CUSTOM_EXPORT_MENU_ITEM = "自定义导出"
INVENTORY_CUSTOM_EXPORT_MODAL_TITLE = "自定义导出"
INVENTORY_CUSTOM_EXPORT_RESTORE_DEFAULT = "恢复默认配置"

INVENTORY_P0_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "sku": ("SKU", "sku", "产品SKU"),
    "warehouse": ("仓库", "warehouse", "目的仓"),
    "available_inventory": ("可用量", "可售库存", "available_inventory", "可用库存"),
    "ref_daily_sales": ("7天日均", "ref_daily_sales", "日均销量", "7日日均"),
}

ORDERS_P0_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "msku": ("msku", "MSKU"),
    "channel": ("平台", "channel", "销售渠道"),
    "order_qty": ("订购数量", "order_qty"),
    "order_date": ("订购时间(市场)", "订购时间", "order_date"),
}

TMS_P0_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "sku": ("SKU", "sku", "产品SKU"),
    "warehouse": ("目的仓", "warehouse", "仓库"),
    "batch_id": ("批次号", "batch_id", "发货单号"),
    "tms_status": ("TMS状态", "tms_status", "状态"),
    "unreceived_qty": ("未收量", "unreceived_qty", "未收数量"),
}


@dataclass(frozen=True)
class ErpPaths:
    login: str = LOGIN_PATH
    inventory_product: str = "/gip/inventoryManage/product"
    inventory_multi_platform: str = "/gip/inventoryManage/multiPlatform"
    orders: str = "/sales/multiChannel/orders"
    tms_inbound: str = "/tms/logisticsBill"


@dataclass(frozen=True)
class ErpSelectors:
    username: str = 'input[placeholder="用户名"]'
    password: str = 'input[placeholder="请输入密码"]'
    login_submit: str = 'button:has-text("登录")'
    import_export_menu: str = "text=导入导出"
    export_button_role: str = "导出"
    inventory_custom_export_menu: str = "自定义导出"
    inventory_custom_export_modal_title: str = "自定义导出"
    inventory_custom_export_restore_default: str = "恢复默认配置"
    orders_date_picker: str = ".arco-picker"
    transport_center_path: str = "/platform/reports/transmission-center"
    transport_center_icon: str = ".download-icon"
    modal_close: str = ".arco-modal-close-icon, .arco-icon-close"
    mask: str = ".mask"


PATHS = ErpPaths()
SELECTORS = ErpSelectors()
