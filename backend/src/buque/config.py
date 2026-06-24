from functools import lru_cache
import logging
import secrets
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://buque:buque@localhost:5432/buque"
    timezone: str = "Asia/Shanghai"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000"

    erp_base_url: str = ""
    erp_username: str = ""
    erp_password: str = ""
    erp_web_prefix: str = "/amzv-web"

    llm_api_base: str = ""
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    # off=仅规则解释；on_demand=单 SKU 深读可调 LLM；批量分析永不调 LLM
    llm_explain_mode: Literal["off", "on_demand"] = "on_demand"

    data_dir: str = "data"
    export_dir: str = "data/exports"
    # 传输中心轮询上限（实测 job#13：库存 ~34s、订单 ~3min、全程 ~4min）
    erp_sync_timeout_ms: int = 240_000  # 库存导出，4min
    erp_orders_export_timeout_ms: int = 360_000  # 订单导出，6min
    erp_job_stale_buffer_seconds: int = 90  # TMS 抓取 + 落库

    jwt_secret: str = ""
    jwt_expire_minutes: int = 10080
    google_client_id: str = ""
    auth_required: bool = True
    auth_password_enabled: bool | None = None

    @field_validator("jwt_secret", mode="before")
    @classmethod
    def _default_jwt_secret(cls, value: object) -> str:
        if value:
            return str(value)
        generated = secrets.token_urlsafe(32)
        logger.warning("JWT_SECRET 未配置，已生成临时密钥（重启后 token 失效）")
        return generated

    @property
    def password_auth_enabled(self) -> bool:
        if self.auth_password_enabled is not None:
            return self.auth_password_enabled
        return not bool(self.google_client_id)

    @property
    def google_auth_enabled(self) -> bool:
        return bool(self.google_client_id)

    @property
    def erp_job_stale_seconds(self) -> int:
        """同步 job 最大存活时间：库存导出 + 订单导出 + 缓冲。"""
        return (
            self.erp_sync_timeout_ms // 1000
            + self.erp_orders_export_timeout_ms // 1000
            + self.erp_job_stale_buffer_seconds
        )

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
