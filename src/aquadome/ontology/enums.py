"""Controlled vocabularies for the AquaDome canonical ontology."""

from enum import StrEnum


class ObjectClass(StrEnum):
    VESSEL = "Vessel"
    TRAP = "Trap"
    DEBRIS_ITEM = "DebrisItem"
    STRUCTURE = "Structure"
    UNKNOWN = "Unknown"


class EntityType(StrEnum):
    VESSEL = "Vessel"
    TRAP = "Trap"
    DEBRIS_ITEM = "DebrisItem"
    STRUCTURE = "Structure"


class GeolocationSource(StrEnum):
    KLV_CORNER_POINT = "klv_corner_point"   # MISB ST 0601 frame corners
    ORTHOMOSAIC = "orthomosaic"             # georeferenced orthomosaic
    GNSS_DIRECT = "gnss_direct"             # drone GPS projected to surface


class HumanReviewStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class ResolutionMethod(StrEnum):
    EMBEDDING_GEO_OCR = "embedding+geo+ocr"
    EMBEDDING_GEO = "embedding+geo"
    OCR_ONLY = "ocr_only"
    MANUAL = "manual"


class DwellStatus(StrEnum):
    """HB 481 / FS 327.4108 traffic-light tiers."""
    GREEN = "green"    # 0–13 days in rolling 6-month window
    YELLOW = "yellow"  # 14–29 days — flag long-term anchoring permit (§327.4111)
    RED = "red"        # 30+ days = violation (up to $500/day)


class AtRiskTier(StrEnum):
    """FWC at-risk scoring tiers."""
    NONE = "none"
    WATCH = "watch"     # 1–2 criteria
    AT_RISK = "at_risk" # 3–4 criteria
    CRITICAL = "critical" # 5 criteria (all)


class TrapGearType(StrEnum):
    BLUE_CRAB = "blue_crab"
    STONE_CRAB = "stone_crab"
    SPINY_LOBSTER = "spiny_lobster"
    UNKNOWN = "unknown"


class SeasonStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    UNKNOWN = "unknown"


class TrapLegalStatus(StrEnum):
    LAWFUL = "lawful"
    DERELICT = "derelict"
    ILLEGAL = "illegal"
    REQUIRES_REVIEW = "requires_review"


class DroneHardwareTier(StrEnum):
    """NDAA/ASDA compliance tier for hardware procurement."""
    COMMERCIAL = "commercial"           # DJI/Autel — private/non-federal flights only
    BLUE_UAS = "blue_uas"               # DCMA Blue UAS Cleared List — required for federal work
