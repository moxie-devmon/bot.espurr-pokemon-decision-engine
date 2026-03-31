Espurr Decision Engine — Project State

# ESPURR SYSTEM CONTEXT (FOR AI ASSISTANT)

If code changes are needed, always request the exact file before generating modifications.

Espurr is a modular Pokémon battle decision engine designed to evaluate battle states and recommend optimal actions.

The system is built with a layered architecture so the core decision engine operates independently of input sources.

Future inputs may include:
- manually constructed battle states
- JSON sandbox simulations
- Pokémon Showdown battle states
- replay logs

All inputs convert into:

BattleState → Evaluation Engine → Ranked Actions

The evaluation engine must remain input-agnostic.


--------------------------------------------------

# CURRENT DEVELOPMENT PHASE

Espurr has completed its **core backend architecture refactor**.

We are now in the:

🚀 **ENGINE INTELLIGENCE PHASE**

Focus has shifted from:
- structuring code
- building endpoints

→ to:

- improving decision quality
- modeling real competitive reasoning
- handling uncertainty properly


--------------------------------------------------

# Supported Competitive Scope

Espurr targets **Smogon OU formats across all generations**.

Examples:
- Gen 9 OU
- Gen 8 OU
- Gen 7 OU

The engine supports a **FormatContext**:

FormatContext
  generation
  format_name
  ruleset

This will determine:
- mechanics
- legal sets
- meta priors
- inference assumptions


--------------------------------------------------

# Core Engine Principle — Partial Information Modeling

Pokémon battles are partially observable.

Espurr evaluates **uncertain states** by maintaining:

→ a distribution over plausible opponent sets

Instead of:
- assuming a single build

We model:
- multiple candidate sets
- weighted probabilities
- confidence levels

Future data sources:
- Smogon usage stats
- Smogon sample sets
- MunchStats


--------------------------------------------------

# Confidence Categories

CONFIRMED
- revealed moves
- HP
- status
- hazards
- boosts

CONSTRAINED
- inferred speed
- inferred item
- inferred ability
- narrowed move pool

META-INFERRED
- EV spreads
- items
- abilities
- move sets


--------------------------------------------------

# Evaluation Strategy

Espurr evaluates actions across multiple plausible opponent states.

Each action considers:

- damage output
- survivability
- turn order
- retaliation risk
- switch value

Future:

- expected value across inferred distributions
- worst-case vs best-case tradeoffs
- confidence-aware recommendations


--------------------------------------------------

# Backend Architecture

Backend Framework: FastAPI

Current structure:

backend/app/

  main.py

  routes/
    battle_routes.py
    data_routes.py
    type_routes.py

  adapters/
    manual_input_adapter.py

  domain/
    battle_state.py
    actions.py

  engine/
    damage_engine.py
    evaluation_engine.py
    speed_engine.py
    field_engine.py
    switch_engine.py
    type_engine.py

  inference/
    models.py
    set_inference.py
    belief_updater.py

  explain/
    explanation_engine.py

  providers/
    pokemon_provider.py
    move_provider.py
    type_chart_provider.py
    provider_utils.py

  schemas/
    battle_state.py
    damage_preview.py
    data_endpoints.py
    type_effectiveness.py

  tests/
    unit/
    scenarios/

  data/
    pokemon.json
    moves.json
    typeChart.json


--------------------------------------------------

# Architecture Layers

INPUT LAYER

Frontend collects:
- sides (mySide, opponentSide)
- active Pokémon
- bench
- hazards
- moves
- field conditions

API LAYER

FastAPI routes call:
- adapters → domain
- engine → evaluation
- explain → reasoning

SCHEMA LAYER

Defines API contracts:
- BattleStateRequest (side-native)
- EvaluatePositionResponse

DOMAIN LAYER

Core internal representation:

BattleState
  my_side
  opponent_side
  field
  format_context

SideState
  active
  bench
  side_conditions

PokemonState
  stats
  boosts
  status
  revealed_moves

ENGINE LAYER

Pure logic modules:

damage_engine
speed_engine
field_engine
switch_engine
evaluation_engine

INFERENCE LAYER

- candidate set modeling
- belief updating
- placeholder → future meta integration

EXPLANATION LAYER

- converts engine decisions into human-readable reasoning

ADAPTER LAYER

- converts schema → domain
- isolates engine from API format

PROVIDER LAYER

- data access (pokemon, moves, types)


--------------------------------------------------

# ENGINE ENTRYPOINT MAP

POST /evaluate-position

1. Request → BattleStateRequest

2. Adapter:
   to_domain_battle_state(payload)

3. Engine:
   evaluate_battle_state(state)

4. Evaluation pipeline:

Move actions:
  estimate_damage
  field modifiers
  turn order
  retaliation modeling
  scoring

Switch actions:
  hazard impact
  defensive typing
  HP + speed context
  scoring

5. Inference:
  infer_opposing_active_set(state)

6. Explanation:
  explanation_engine

7. Output:
  ranked actions + confidence


--------------------------------------------------

# Current Engine Capabilities

Battle modeling:
- side-based state (active + bench)
- hazards per side
- weather + terrain

Damage:
- gen-style formula
- STAB, crit, burn
- type effectiveness
- damage ranges

Turn order:
- speed
- boosts
- priority

Survivability:
- proxy retaliation
- KO risk penalties

Switching:
- hazard impact
- defensive typing
- HP + speed heuristics

Inference:
- placeholder candidate sets
- revealed moves preserved

Explanation:
- structured reasoning layer

Testing:
- unit tests (engines)
- scenario tests (decision behavior)


--------------------------------------------------

# Known Limitations

- evaluation is mostly single-turn
- inference is placeholder
- no items or abilities yet
- no EV / nature modeling
- no coverage prediction
- no switching prediction
- no multi-turn planning
- no real opponent modeling yet


--------------------------------------------------

# Scenario Testing Harness

Located in:

backend/app/tests/scenarios/

Uses serialized battle states.

Validates:
- decision correctness
- regression prevention

Examples:
- type advantage (Electric vs Gyarados)
- hazard-aware switching
- priority vs speed
- status vs damage
- inference visibility


--------------------------------------------------

# CRITICAL FILES

Always check before modifying logic:

engine/evaluation_engine.py
engine/damage_engine.py
engine/switch_engine.py
engine/speed_engine.py
engine/field_engine.py

domain/battle_state.py
adapters/manual_input_adapter.py

inference/set_inference.py
explain/explanation_engine.py


--------------------------------------------------

# Next Major Development Steps (ENGINE INTELLIGENCE)

1. Fix decision gaps (HIGH PRIORITY)

Example:
- priority vs damage (KO-before-being-hit logic)
- survivability weighting

2. Improve retaliation modeling

- use inferred sets instead of proxy STAB
- incorporate move coverage risk

3. Integrate inference into evaluation

- weight outcomes across candidate sets
- replace single proxy retaliation

4. Add item and ability awareness

Start with high-impact:
- Choice items
- Leftovers
- Life Orb
- Focus Sash
- Intimidate

5. Improve switch evaluation

- retaliation vs switch-in
- hazard removal value
- pivoting value

6. Add groundedness and field correctness

- Flying / Levitate
- terrain interactions

7. Introduce shallow lookahead

- 1-turn + opponent response
- basic minimax heuristics


--------------------------------------------------

# Development Philosophy

Architecture is now stable.

Focus is now on:

- decision quality
- competitive realism
- explainability
- incremental intelligence

Build vertically through scenario-driven improvements.

Every improvement should:
- fix a failing scenario OR
- add a new scenario