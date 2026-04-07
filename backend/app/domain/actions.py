from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional, Union


ActionType = Literal["move", "switch"]
DominantReason = Literal["tactical", "positional", "strategic", "uncertainty"]


@dataclass(frozen=True)
class MoveAction:
    move_name: str
    move_type: str
    move_category: str
    base_power: int
    priority: int = 0
    action_type: ActionType = "move"


@dataclass(frozen=True)
class SwitchAction:
    target_species: str
    action_type: ActionType = "switch"


Action = Union[MoveAction, SwitchAction]


@dataclass
class ScoreBreakdown:
    tactical: float = 0.0
    positional: float = 0.0
    strategic: float = 0.0
    uncertainty: float = 0.0

    @property
    def total(self) -> float:
        return (
            self.tactical
            + self.positional
            + self.strategic
            + self.uncertainty
        )

    def to_dict(self) -> dict:
        return {
            "tactical": self.tactical,
            "positional": self.positional,
            "strategic": self.strategic,
            "uncertainty": self.uncertainty,
            "total": self.total,
        }


@dataclass
class EvaluatedAction:
    action: Action
    score_breakdown: ScoreBreakdown = field(default_factory=ScoreBreakdown)
    confidence: float = 0.0
    notes: list[str] = field(default_factory=list)

    type_multiplier: Optional[float] = None
    min_damage: Optional[float] = None
    max_damage: Optional[float] = None
    min_damage_percent: Optional[float] = None
    max_damage_percent: Optional[float] = None

    expected_score: Optional[float] = None
    worst_score: Optional[float] = None
    best_score: Optional[float] = None
    stability: Optional[float] = None

    top_world_label: Optional[str] = None
    top_world_weight: Optional[float] = None

    @property
    def score(self) -> float:
        return self.score_breakdown.total

    @property
    def action_type(self) -> ActionType:
        return self.action.action_type

    @property
    def name(self) -> str:
        if isinstance(self.action, MoveAction):
            return self.action.move_name
        return self.action.target_species

    @property
    def immediate_score(self) -> float:
        return self.score_breakdown.tactical + self.score_breakdown.positional

    @property
    def continuation_score(self) -> float:
        return self.score_breakdown.strategic

    @property
    def uncertainty_penalty(self) -> float:
        return self.score_breakdown.uncertainty

    @property
    def dominant_reason(self) -> DominantReason:
        bucket_pairs: list[tuple[DominantReason, float]] = [
            ("tactical", self.score_breakdown.tactical),
            ("positional", self.score_breakdown.positional),
            ("strategic", self.score_breakdown.strategic),
            ("uncertainty", self.score_breakdown.uncertainty),
        ]
        dominant_bucket, _ = max(bucket_pairs, key=lambda item: abs(item[1]))
        return dominant_bucket

    @property
    def continuation_driven(self) -> bool:
        strategic = abs(self.score_breakdown.strategic)
        immediate = abs(self.immediate_score)
        return strategic >= 3.0 or strategic > immediate

    def to_dict(self) -> dict:
        base = {
            "actionType": self.action.action_type,
            "name": self.name,
            "score": self.score,
            "scoreBreakdown": self.score_breakdown.to_dict(),
            "confidence": self.confidence,
            "notes": self.notes,
            "expectedScore": self.expected_score,
            "worstScore": self.worst_score,
            "bestScore": self.best_score,
            "stability": self.stability,
            "topWorldLabel": self.top_world_label,
            "topWorldWeight": self.top_world_weight,
            "immediateScore": self.immediate_score,
            "continuationScore": self.continuation_score,
            "uncertaintyPenalty": self.uncertainty_penalty,
            "dominantReason": self.dominant_reason,
            "continuationDriven": self.continuation_driven,
        }

        if isinstance(self.action, MoveAction):
            base.update(
                {
                    "moveType": self.action.move_type,
                    "moveCategory": self.action.move_category,
                    "basePower": self.action.base_power,
                    "typeMultiplier": self.type_multiplier,
                    "minDamage": self.min_damage,
                    "maxDamage": self.max_damage,
                    "minDamagePercent": self.min_damage_percent,
                    "maxDamagePercent": self.max_damage_percent,
                }
            )
            return base

        base.update(
            {
                "moveType": None,
                "moveCategory": None,
                "basePower": None,
                "typeMultiplier": None,
                "minDamage": None,
                "maxDamage": None,
                "minDamagePercent": None,
                "maxDamagePercent": None,
            }
        )
        return base