from datetime import date

from sqlalchemy.orm import Session

from buque.models.entities import RuleConfig
from buque.services.rule_config_seed import RULE_CONFIG_SEED, SEED_EFFECTIVE_DATE


def seed_rule_config(db: Session) -> int:
    inserted = 0
    for item in RULE_CONFIG_SEED:
        exists = (
            db.query(RuleConfig)
            .filter(
                RuleConfig.rule_code == item["rule_code"],
                RuleConfig.version == 1,
            )
            .first()
        )
        if exists:
            continue
        db.add(
            RuleConfig(
                rule_code=item["rule_code"],
                rule_name=item["rule_name"],
                param_value=item["param_value"],
                param_type=item["param_type"],
                is_enabled=True,
                version=1,
                effective_date=SEED_EFFECTIVE_DATE,
                proposer="system",
                approver="grill",
                change_reason="一期默认配置",
            )
        )
        inserted += 1
    db.commit()
    return inserted


class RuleConfigService:
    def __init__(self, db: Session):
        self.db = db
        self._cache: dict[str, str] | None = None

    def reload(self) -> None:
        self._cache = None

    def all_params(self) -> dict[str, str]:
        if self._cache is not None:
            return self._cache
        rows = (
            self.db.query(RuleConfig)
            .filter(RuleConfig.is_enabled.is_(True))
            .order_by(RuleConfig.rule_code, RuleConfig.version.desc())
            .all()
        )
        seen: set[str] = set()
        params: dict[str, str] = {}
        for row in rows:
            if row.rule_code in seen:
                continue
            seen.add(row.rule_code)
            params[row.rule_code] = row.param_value
        self._cache = params
        return params

    def get_str(self, code: str, default: str = "") -> str:
        return self.all_params().get(code, default)

    def get_bool(self, code: str, default: bool = False) -> bool:
        val = self.get_str(code, str(default).lower())
        return val.lower() in {"true", "1", "yes", "on"}

    def get_int(self, code: str, default: int = 0) -> int:
        val = self.get_str(code, str(default))
        return int(float(val))

    def get_float(self, code: str, default: float = 0.0) -> float:
        val = self.get_str(code, str(default))
        return float(val)

    def get_list(self, code: str, sep: str = ",") -> list[str]:
        raw = self.get_str(code, "")
        return [x.strip() for x in raw.split(sep) if x.strip()]
