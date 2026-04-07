from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional


ResponseKind = Literal["move", "switch"]


@dataclass
class CandidateSet:
    species: Optional[str]
    label: str
    moves: List[str] = field(default_factory=list)
    item: Optional[str] = None
    ability: Optional[str] = None
    tera_type: Optional[str] = None
    weight: float = 1.0
    source: str = "placeholder"


@dataclass
class InferenceResult:
    species: Optional[str]
    candidates: List[CandidateSet] = field(default_factory=list)
    confidence_label: str = "unknown"
    notes: List[str] = field(default_factory=list)

    def normalized_weights(self) -> Dict[str, float]:
        total = sum(candidate.weight for candidate in self.candidates) or 1.0
        return {
            candidate.label: candidate.weight / total
            for candidate in self.candidates
        }


@dataclass
class OpponentWorld:
    species: Optional[str]
    candidate: CandidateSet
    weight: float
    known_moves: List[str] = field(default_factory=list)
    assumed_moves: List[str] = field(default_factory=list)

    assumed_item: Optional[str] = None
    assumed_ability: Optional[str] = None
    assumed_tera_type: Optional[str] = None

    notes: List[str] = field(default_factory=list)


@dataclass
class OpponentResponse:
    kind: ResponseKind
    label: str
    weight: float

    move_name: Optional[str] = None
    move_type: Optional[str] = None
    move_category: Optional[str] = None
    base_power: int = 0
    priority: int = 0

    switch_target_species: Optional[str] = None

    notes: List[str] = field(default_factory=list)


@dataclass
class ProjectionSummary:
    my_hp_before: float
    my_hp_after: float
    opp_hp_before: float
    opp_hp_after: float
    my_fainted: bool
    opp_fainted: bool
    order_context: str
    notes: List[str] = field(default_factory=list)

    my_active_species_after: Optional[str] = None
    opp_active_species_after: Optional[str] = None

    my_forced_switch: bool = False
    opp_forced_switch: bool = False
    opponent_switched: bool = False

    revealed_response_move: Optional[str] = None

    @property
    def my_damage_taken(self) -> float:
        return max(0.0, self.my_hp_before - self.my_hp_after)

    @property
    def opp_damage_taken(self) -> float:
        return max(0.0, self.opp_hp_before - self.opp_hp_after)

    @property
    def my_damage_taken_pct_current(self) -> float:
        if self.my_hp_before <= 0:
            return 0.0
        return min(100.0, (self.my_damage_taken / self.my_hp_before) * 100.0)

    @property
    def opp_damage_taken_pct_current(self) -> float:
        if self.opp_hp_before <= 0:
            return 0.0
        return min(100.0, (self.opp_damage_taken / self.opp_hp_before) * 100.0)


@dataclass
class ActionWorldEvaluation:
    world: OpponentWorld
    expected_score: float
    worst_score: float
    best_score: float
    response_breakdown: List[dict] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


@dataclass
class AggregatedActionValue:
    expected_score: float
    worst_score: float
    best_score: float
    stability: float = 0.0
    notes: List[str] = field(default_factory=list)