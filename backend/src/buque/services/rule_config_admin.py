from datetime import date

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from buque.models.entities import RuleConfig
from buque.services.rule_catalog import catalog_for


class RuleConfigValidationError(ValueError):
    pass


def _validate_param(rule_code: str, param_type: str, param_value: str) -> None:
    val = param_value.strip()
    if not val:
        raise RuleConfigValidationError("参数值不能为空")
    if param_type == "bool":
        if val.lower() not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
            raise RuleConfigValidationError("布尔值须为 true/false")
        return
    if param_type == "int":
        n = int(float(val))
        if rule_code.startswith("DOS_") or rule_code.startswith("SLOW_DOS_"):
            if not 1 <= n <= 365:
                raise RuleConfigValidationError("DOS 阈值须在 1–365 天")
        if rule_code == "CAUSE_TOP_N" and not 1 <= n <= 10:
            raise RuleConfigValidationError("解释条数须在 1–10")
        return
    if param_type == "float":
        f = float(val)
        if rule_code.endswith("_FACTOR"):
            if not 0.1 <= f <= 5.0:
                raise RuleConfigValidationError("倍率须在 0.1–5.0")
        elif rule_code in {"SALES_SURGE_RATIO", "SALES_DROP_RATIO", "FC_ERR_RED"}:
            if not 0.1 <= f <= 5.0:
                raise RuleConfigValidationError("比值须在 0.1–5.0")
        return


def _latest_rules_query(db: Session, *, enabled_only: bool):
    subq = db.query(
        RuleConfig.rule_code,
        func.max(RuleConfig.version).label("max_version"),
    ).group_by(RuleConfig.rule_code)
    if enabled_only:
        subq = subq.filter(RuleConfig.is_enabled.is_(True))
    subq = subq.subquery()
    return (
        db.query(RuleConfig)
        .join(
            subq,
            (RuleConfig.rule_code == subq.c.rule_code)
            & (RuleConfig.version == subq.c.max_version),
        )
        .order_by(RuleConfig.rule_code)
    )


def list_effective_rules(db: Session) -> list[RuleConfig]:
    return _latest_rules_query(db, enabled_only=True).all()


def list_admin_rules(db: Session) -> list[RuleConfig]:
    return _latest_rules_query(db, enabled_only=False).all()


def get_rule_history(db: Session, rule_code: str) -> list[RuleConfig]:
    return (
        db.query(RuleConfig)
        .filter(RuleConfig.rule_code == rule_code)
        .order_by(RuleConfig.version.desc())
        .all()
    )


def get_effective_rule(db: Session, rule_code: str) -> RuleConfig | None:
    latest = get_latest_rule(db, rule_code)
    if latest is None or not latest.is_enabled:
        return None
    return latest


def get_latest_rule(db: Session, rule_code: str) -> RuleConfig | None:
    return (
        db.query(RuleConfig)
        .filter(RuleConfig.rule_code == rule_code)
        .order_by(RuleConfig.version.desc())
        .first()
    )


def update_rule(
    db: Session,
    rule_code: str,
    change_reason: str,
    param_value: str | None = None,
    is_enabled: bool | None = None,
    proposer: str | None = None,
) -> RuleConfig:
    reason = (change_reason or "").strip()
    if not reason:
        raise RuleConfigValidationError("变更原因不能为空")

    current = get_latest_rule(db, rule_code)
    if current is None:
        raise HTTPException(status_code=404, detail="规则不存在")

    new_param = param_value.strip() if param_value is not None else current.param_value
    new_enabled = is_enabled if is_enabled is not None else current.is_enabled

    if new_param == current.param_value and new_enabled == current.is_enabled:
        raise RuleConfigValidationError("未检测到变更")

    _validate_param(rule_code, current.param_type, new_param)

    next_version = (
        db.query(func.max(RuleConfig.version))
        .filter(RuleConfig.rule_code == rule_code)
        .scalar()
        or 0
    ) + 1

    row = RuleConfig(
        rule_code=rule_code,
        rule_name=current.rule_name,
        param_value=new_param,
        param_type=current.param_type,
        is_enabled=new_enabled,
        version=next_version,
        effective_date=date.today(),
        proposer=proposer or "user",
        approver=None,
        change_reason=reason,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    from buque.services.rule_config import RuleConfigService

    RuleConfigService(db).reload()
    return row


def rule_to_dict(row: RuleConfig) -> dict:
    meta = catalog_for(row.rule_code)
    return {
        "rule_code": row.rule_code,
        "rule_name": row.rule_name,
        "param_value": row.param_value,
        "param_type": row.param_type,
        "version": row.version,
        "effective_date": row.effective_date,
        "is_enabled": row.is_enabled,
        "change_reason": row.change_reason,
        "proposer": row.proposer,
        "category": meta.category,
        "description": meta.description,
        "editor": meta.editor,
    }
