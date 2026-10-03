"""Unit tests for the FWC at-risk vessel scorer."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from aquadome.ontology.enums import AtRiskTier
from aquadome.ontology.models import Entity, EntityType
from aquadome.rule_engines.fwc import AtRiskScorer


def _vessel() -> Entity:
    now = datetime.now(timezone.utc)
    return Entity(
        entity_type=EntityType.VESSEL,
        first_observed=now,
        last_observed=now,
        tenant_id="fwc",
    )


class TestAtRiskScorer:
    def setup_method(self):
        self.scorer = AtRiskScorer()

    def test_no_criteria_is_none_tier(self):
        result = self.scorer.score(_vessel(), [])
        assert result.tier == AtRiskTier.NONE
        assert result.estimated_avoided_cost_usd == 0.0

    def test_one_criterion_is_watch(self):
        result = self.scorer.score(_vessel(), ["listing_from_water_intrusion"])
        assert result.tier == AtRiskTier.WATCH

    def test_three_criteria_is_at_risk(self):
        criteria = [
            "listing_from_water_intrusion",
            "taking_on_water_no_dewater",
            "enclosed_spaces_open_to_elements",
        ]
        result = self.scorer.score(_vessel(), criteria)
        assert result.tier == AtRiskTier.AT_RISK
        assert result.requires_human_review
        assert result.grant_removal_eligible

    def test_all_five_criteria_is_critical(self):
        from aquadome.rule_engines.fwc.at_risk import CRITERIA_KEYS
        result = self.scorer.score(_vessel(), CRITERIA_KEYS)
        assert result.tier == AtRiskTier.CRITICAL
        assert result.vtip_eligible

    def test_invalid_criteria_key_ignored(self):
        result = self.scorer.score(_vessel(), ["not_a_real_criterion"])
        assert result.tier == AtRiskTier.NONE
        assert result.criteria_count == 0
