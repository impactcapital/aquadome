"""
FWC At-Risk Vessel Scorer
Statute: Florida FWC derelict vessel at-risk criteria (published by FWC).

The five statutory at-risk criteria a vessel must meet to be flagged:
  1. Taking on water without means to dewater
  2. Enclosed spaces open to the elements
  3. Broken or breaking loose from anchor/mooring
  4. Listing from water intrusion
  5. No effective propulsion within 48 hours

Scoring tiers:
  NONE      0 criteria — no flag
  WATCH     1–2 criteria — monitor
  AT_RISK   3–4 criteria — notify FWC; flag VTIP / grant removal pathway
  CRITICAL  5 criteria — escalate immediately

At-risk removal is cheaper than derelict removal:
  Derelict removal in Miami-Dade: ~$357K for 51 vessels (2021).
  Model quantifies avoided cost per at-risk flag → conversion to VTIP surrender.

Enforcement note: FALSE POSITIVES ARE COSTLY — hold AT_RISK+ to human review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ...ontology.enums import AtRiskTier
from ...ontology.models import Entity


# Criteria keys aligned to FWC published language
CRITERIA_KEYS = [
    "taking_on_water_no_dewater",
    "enclosed_spaces_open_to_elements",
    "broken_breaking_loose_from_anchor",
    "listing_from_water_intrusion",
    "no_effective_propulsion_48h",
]

# Estimated avoided cost per VTIP surrender relative to derelict removal
_DERELICT_REMOVAL_COST_USD = 7_000     # ~$357K / 51 vessels (Miami-Dade 2021)
_ATRISK_REMOVAL_COST_USD = 1_200       # estimate for while-afloat removal
_AVOIDED_COST_PER_FLAG_USD = _DERELICT_REMOVAL_COST_USD - _ATRISK_REMOVAL_COST_USD


@dataclass
class AtRiskResult:
    entity_id: str
    fl_registration_number: str | None
    criteria_met: list[str]
    criteria_count: int
    tier: AtRiskTier
    estimated_avoided_cost_usd: float
    requires_human_review: bool
    vtip_eligible: bool                # FWC free surrender/disposal program
    grant_removal_eligible: bool       # FWC Derelict Vessel Removal Grant (100% reimbursement)
    evaluated_at: datetime
    notes: list[str] = field(default_factory=list)


class AtRiskScorer:
    """
    Scores a Vessel entity against FWC's five published at-risk criteria.

    Criteria evidence comes from:
      - Visual observations (listing, open compartments) from the detection model
      - Change detection (vessel settled lower between flights = water intrusion)
      - AIS / patrol reports (propulsion status)
      - Dwell-time data (anchored 48+ hours without movement = propulsion flag)

    Usage:
        scorer = AtRiskScorer()
        result = scorer.score(entity, observed_criteria=["listing_from_water_intrusion"])
    """

    def score(
        self,
        entity: Entity,
        observed_criteria: list[str],
        as_of: datetime | None = None,
    ) -> AtRiskResult:
        if as_of is None:
            from datetime import timezone
            as_of = datetime.now(timezone.utc)

        valid_criteria = [c for c in observed_criteria if c in CRITERIA_KEYS]
        count = len(valid_criteria)
        tier = self._classify(count)

        avoided_cost = (
            _AVOIDED_COST_PER_FLAG_USD if tier in (AtRiskTier.AT_RISK, AtRiskTier.CRITICAL) else 0.0
        )

        notes: list[str] = []
        if tier == AtRiskTier.CRITICAL:
            notes.append("All five FWC at-risk criteria met — escalate to FWC immediately")
        if "no_effective_propulsion_48h" in valid_criteria:
            notes.append("VTIP free surrender pathway applicable (no-propulsion criterion met)")

        return AtRiskResult(
            entity_id=str(entity.entity_id),
            fl_registration_number=entity.fl_registration_number,
            criteria_met=valid_criteria,
            criteria_count=count,
            tier=tier,
            estimated_avoided_cost_usd=avoided_cost,
            requires_human_review=tier in (AtRiskTier.AT_RISK, AtRiskTier.CRITICAL),
            vtip_eligible=count >= 1,
            grant_removal_eligible=tier in (AtRiskTier.AT_RISK, AtRiskTier.CRITICAL),
            evaluated_at=as_of,
            notes=notes,
        )

    @staticmethod
    def _classify(count: int) -> AtRiskTier:
        if count == 0:
            return AtRiskTier.NONE
        if count <= 2:
            return AtRiskTier.WATCH
        if count <= 4:
            return AtRiskTier.AT_RISK
        return AtRiskTier.CRITICAL
