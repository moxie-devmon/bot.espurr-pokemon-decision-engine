from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.damage_preview import CombatantInfo, MoveInfo


StatusCondition = Literal["brn", "par", "psn", "tox", "slp", "frz"]
Weather = Literal["sun", "rain", "sand", "snow"]
Terrain = Literal["electric", "grassy", "misty", "psychic"]
ActionType = Literal["move", "switch"]


class StatBoosts(BaseModel):
    atk: int = Field(default=0, ge=-6, le=6)
    def_: int = Field(default=0, ge=-6, le=6)
    spa: int = Field(default=0, ge=-6, le=6)
    spd: int = Field(default=0, ge=-6, le=6)
    spe: int = Field(default=0, ge=-6, le=6)


class PokemonStateRequest(CombatantInfo):
    species: Optional[str] = None
    spe: Optional[int] = Field(default=100, ge=1)
    currentHp: Optional[int] = Field(default=None, ge=0)
    status: Optional[StatusCondition] = None
    boosts: StatBoosts = Field(default_factory=StatBoosts)
    revealedMoves: List[str] = Field(default_factory=list)


class BenchPokemonRequest(BaseModel):
    species: str
    types: List[str] = Field(min_length=1, max_length=2)
    atk: Optional[int] = Field(default=100, ge=1)
    def_: Optional[int] = Field(default=100, ge=1)
    spa: Optional[int] = Field(default=100, ge=1)
    spd: Optional[int] = Field(default=100, ge=1)
    spe: Optional[int] = Field(default=100, ge=1)
    hp: Optional[int] = Field(default=100, ge=1)
    currentHp: Optional[int] = Field(default=None, ge=0)
    burned: bool = False
    tera_active: bool = False
    status: Optional[StatusCondition] = None
    revealedMoves: List[str] = Field(default_factory=list)


class SideConditionsRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    stealth_rock: bool = Field(default=False, alias="stealthRock")
    spikes_layers: int = Field(default=0, ge=0, le=3, alias="spikesLayers")
    sticky_web: bool = Field(default=False, alias="stickyWeb")
    toxic_spikes_layers: int = Field(default=0, ge=0, le=2, alias="toxicSpikesLayers")


class SideStateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    active: PokemonStateRequest
    bench: List[BenchPokemonRequest] = Field(default_factory=list)
    side_conditions: SideConditionsRequest = Field(default_factory=SideConditionsRequest, alias="sideConditions")


class FieldStateRequest(BaseModel):
    weather: Optional[Weather] = None
    terrain: Optional[Terrain] = None


class FormatContextRequest(BaseModel):
    generation: int = Field(default=9, ge=1, le=9)
    formatName: Optional[str] = "manual"
    ruleset: List[str] = Field(default_factory=list)


class BattleStateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    my_side: SideStateRequest = Field(alias="mySide")
    opponent_side: SideStateRequest = Field(alias="opponentSide")
    moves: List[MoveInfo] = Field(min_length=1, max_length=24)
    field: FieldStateRequest = Field(default_factory=FieldStateRequest)
    format_context: FormatContextRequest = Field(default_factory=FormatContextRequest, alias="formatContext")


class RankedAction(BaseModel):
    actionType: ActionType
    name: str
    moveType: Optional[str] = None
    moveCategory: Optional[str] = None
    basePower: Optional[int] = None
    typeMultiplier: Optional[float] = None
    minDamage: Optional[float] = None
    maxDamage: Optional[float] = None
    minDamagePercent: Optional[float] = None
    maxDamagePercent: Optional[float] = None
    score: float
    confidence: float
    notes: List[str] = Field(default_factory=list)
    scoreBreakdown: ScoreBreakdownResponse


class EvaluatePositionResponse(BaseModel):
    bestAction: str
    confidence: float
    rankedActions: List[RankedAction]
    explanation: str
    assumptionsUsed: List[str]


class ScoreBreakdownResponse(BaseModel):
    tactical: float
    positional: float
    strategic: float
    uncertainty: float
    total: float