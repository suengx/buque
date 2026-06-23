from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from buque.db import get_db
from buque.schemas.api import (
    MetricLabelsOut,
    RuleConfigOut,
    RuleConfigUpdate,
    RulesGroupedOut,
)
from buque.services.rule_config import RuleConfigService
from buque.services.rule_config_admin import (
    RuleConfigValidationError,
    get_rule_history,
    list_admin_rules,
    rule_to_dict,
    update_rule,
)
from buque.services.rule_metric_labels import build_metric_labels, build_rules_grouped

router = APIRouter(prefix="/api/v1/rules", tags=["rules"])


@router.get("", response_model=RulesGroupedOut)
def list_rules(db: Session = Depends(get_db)) -> RulesGroupedOut:
    cfg = RuleConfigService(db)
    rows = list_admin_rules(db)
    groups = build_rules_grouped(cfg, rows)
    return RulesGroupedOut(groups=groups)


@router.get("/metric-labels", response_model=MetricLabelsOut)
def metric_labels(db: Session = Depends(get_db)) -> MetricLabelsOut:
    cfg = RuleConfigService(db)
    data = build_metric_labels(cfg)
    return MetricLabelsOut(**data)


@router.get("/{rule_code}/history", response_model=list[RuleConfigOut])
def rule_history(rule_code: str, db: Session = Depends(get_db)) -> list[RuleConfigOut]:
    rows = get_rule_history(db, rule_code)
    if not rows:
        raise HTTPException(status_code=404, detail="规则不存在")
    return [RuleConfigOut(**rule_to_dict(r)) for r in rows]


@router.put("/{rule_code}", response_model=RuleConfigOut)
def put_rule(
    rule_code: str,
    body: RuleConfigUpdate,
    db: Session = Depends(get_db),
) -> RuleConfigOut:
    try:
        row = update_rule(
            db,
            rule_code,
            body.change_reason,
            param_value=body.param_value,
            is_enabled=body.is_enabled,
            proposer=body.proposer,
        )
    except RuleConfigValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RuleConfigOut(**rule_to_dict(row))
