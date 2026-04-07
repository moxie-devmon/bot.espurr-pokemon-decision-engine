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

Espurr has completed its first major backend intelligence refactor.

We are now in the:

🚀 ENGINE INTELLIGENCE + SCENARIO REFINEMENT PHASE

Focus has shifted from:
- structuring code
- building endpoints
- installing the core decision substrate

→ to:

- improving competitive decision quality
- refining search and opponent modeling
- improving uncertainty handling
- reconnecting the frontend to the modern backend contract
- using scenario testing to drive intelligence upgrades


--------------------------------------------------

# Supported Competitive Scope

Espurr targets Smogon OU formats across all generations.

Examples:
- Gen 9 OU
- Gen 8 OU
- Gen 7 OU

The engine supports a FormatContext:

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

Espurr evaluates uncertain states by maintaining:

→ a distribution over plausible opponent sets / worlds

Instead of:
- assuming a single build

We model:
- multiple candidate sets
- weighted probabilities
- confidence levels
- branch evidence updates
- cross-world reweighting during continuation reasoning

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
- branch evidence updates from revealed responses

META-INFERRED
- EV spreads
- items
- abilities
- move sets
- archetype-level priors


--------------------------------------------------

# Evaluation Strategy

Espurr evaluates actions across multiple plausible opponent worlds.

Each action now considers:
- immediate projected outcome
- survivability
- turn order
- response risk
- switch value
- expected / worst / best aggregation
- shallow continuation value
- branch-updated opponent pressure

Current high-level evaluation style:

my action
→ opponent world
→ likely opponent responses
→ projected continuation states
→ expected / worst / best aggregation
→ ranked actions

Current output includes:
- tactical score bucket
- positional score bucket
- strategic / continuation bucket
- uncertainty bucket
- expected / worst / best
- stability
- dominant reason
- continuation-driven signal

Longer-term direction:
- stronger expected value across inferred distributions
- better branch-specific belief updates
- better continuation search
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
    response_engine.py
    projection_engine.py
    lookahead_engine.py

  inference/
    __init__.py (empty)
    models.py
    set_inference.py
    belief_updater.py

  explain/
    __init__.py (empty)
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

  services/
    name_normalize.py

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
- mySide / opponentSide
- active Pokémon
- bench
- hazards
- moves
- field conditions
- format context

API LAYER

FastAPI routes call:
- adapters → domain
- engine → evaluation
- explain → reasoning

SCHEMA LAYER

Defines API contracts:
- BattleStateRequest
- EvaluatePositionResponse
- ranked action fields for search / continuation metrics

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
response_engine
projection_engine
lookahead_engine
evaluation_engine

INFERENCE LAYER

- candidate set modeling
- belief updating
- branch evidence updates
- cross-world reweighting
- placeholder priors now structurally integrated into evaluation

EXPLANATION LAYER

- converts engine decisions into human-readable reasoning
- now surfaces continuation / search signals, stability, and dominant drivers

ADAPTER LAYER

- converts schema → domain
- isolates engine from API format

PROVIDER LAYER

- data access (pokemon, moves, types)
- future home for external meta-prior ingestion


--------------------------------------------------

# ENGINE ENTRYPOINT MAP

POST /evaluate-position

1. Request → BattleStateRequest

2. Adapter:
   to_domain_battle_state(payload)

3. Engine:
   evaluate_battle_state(state)

4. Evaluation pipeline:

Inference:
  infer_opposing_active_set(state)
  build_opponent_worlds(...)

For each candidate action:
  generate_opponent_responses(...)
  project_action_against_response(...)
  score immediate projected line
  aggregate across responses
  aggregate across worlds

Continuation:
  shallow lookahead
  followup-state rebuilding
  branch evidence updates
  cross-world branch reweighting
  second-ply response generation from updated world distribution

5. Explanation:
  explanation_engine

6. Output:
  ranked actions + confidence + search / continuation signals


--------------------------------------------------

# Current Engine Capabilities

Battle modeling:
- side-based state (active + bench)
- hazards per side
- weather + terrain
- format context

Damage:
- gen-style formula
- STAB, crit, burn
- type effectiveness
- damage ranges

Turn order:
- speed
- boosts
- priority
- first-pass Choice Scarf interaction

Switching:
- hazard impact
- defensive typing
- HP + speed heuristics
- first-pass switch evaluation
- opponent switch responses exist, but are still simplistic

Opponent modeling:
- weighted candidate opponent worlds
- world-aware response generation
- hydrated move metadata when available
- fallback proxy modeling when exact move details are weak

Projection / continuation:
- move and switch projected-state application
- continuation-state rebuilding
- forced-switch handling (first-pass)
- shallow lookahead
- second-ply opponent response generation from updated branch distributions

Item / ability hooks (first-pass subset):
- Levitate
- Intimidate
- Leftovers
- Choice Band / Specs / Scarf
- Focus Sash

Inference / belief:
- seeded / placeholder priors
- revealed moves preserved
- branch evidence updates
- cross-world reweighting

Layered evaluation:
- tactical score bucket
- positional score bucket
- strategic score bucket now carries real continuation / search value
- uncertainty score bucket
- total action score derived from score breakdown

Ranked output:
- expected score
- worst score
- best score
- stability
- top inferred world
- immediate score
- continuation score
- uncertainty penalty
- dominant reason
- continuation-driven flag

Explanation:
- structured recommendation explanation
- continuation / search-aware explanation language
- stability and world-influence framing

Testing:
- unit tests (engines)
- scenario tests (decision behavior)
- targeted hook tests for new item / ability / continuation behavior


--------------------------------------------------

# Known Limitations

- search is still shallow and heuristic rather than deep multi-turn planning
- continuation-state rebuilding is evaluation-grade, not simulator-grade
- inference architecture exists, but priors are still seeded / placeholder-level
- item / ability modeling exists only for a limited high-impact subset
- EV / nature modeling is not implemented
- Tera modeling is still very limited
- response generation is improved, but switch prediction and hidden coverage prediction are still coarse
- opponent modeling exists, but branch reweighting and evidence handling are still first-pass
- uncertainty handling is still relatively thin compared to tactical / positional / strategic scoring
- no team-role, win-condition, or preservation logic yet
- no hazard removal / pivot move value yet
- no robust randomness-aware outcome distribution beyond min/max damage-style estimates
- no strong speed-evidence or damage-roll-evidence belief updates yet
- no full meta-prior pipeline from real external competitive sources yet
- no polished simulator-like action resolution for statuses, secondary effects, recovery loops, or item consumption
- forced-switch replacement selection is still simplistic
- setup-value modeling is still weak
- tempo / initiative is not yet a first-class modeled concept
- frontend is now reconnected, but still needs polish around the modern decision-engine output


--------------------------------------------------

# Scenario Testing Harness

Located in:

backend/app/tests/scenarios/

Uses serialized battle states.

Validates:
- decision correctness
- regression prevention
- intelligence improvements after refactors

Examples already relevant to the new backend:
- hazard-aware switching
- choice-scarf order pressure
- Levitate blocking Ground lines
- Focus Sash survival
- Leftovers end-of-line recovery
- continuation-aware reasoning

Next scenario-testing goal:
- competitive scenario refinement against real battle patterns
- use failures to prioritize the next intelligence upgrades


--------------------------------------------------

# CRITICAL FILES

Always check before modifying logic:

engine/evaluation_engine.py
engine/lookahead_engine.py
engine/projection_engine.py
engine/response_engine.py
engine/damage_engine.py
engine/switch_engine.py
engine/speed_engine.py
engine/field_engine.py

domain/battle_state.py
domain/actions.py
adapters/manual_input_adapter.py

inference/models.py
inference/set_inference.py
inference/belief_updater.py

explain/explanation_engine.py

Frontend reconnect surface:
frontend/src/app/components/EvaluatePositionPanel.tsx
frontend/src/app/lib/api.ts
frontend/src/app/page.tsx

Scenario refinement surface:
engine/evaluation_engine.py
engine/lookahead_engine.py
engine/response_engine.py
inference/set_inference.py
inference/belief_updater.py
tests/scenarios/test_scenarios.py


--------------------------------------------------

# Next Major Development Steps (ENGINE INTELLIGENCE)

1. Competitive scenario refinement
- run realistic battle scenarios through the current engine
- identify where decisions still fail despite the new substrate
- prioritize upgrades based on observed competitive failure modes

2. Improve opponent response realism
- better switch likelihood modeling
- better switch target selection
- better hidden coverage prediction
- better setup / utility move handling

3. Strengthen inference quality
- move from seeded priors toward real meta-prior ingestion
- add better consistency filtering
- improve item / ability / archetype narrowing

4. Improve strategic Pokémon reasoning
- team-role preservation
- win-condition preservation
- sack logic
- pivot / hazard-control value
- setup-value logic

5. Improve uncertainty realism
- speed evidence updates
- damage-roll evidence updates
- better confidence handling
- better randomness-aware outcome modeling

6. Improve continuation search
- stronger continuation-state rebuilding
- deeper / cleaner lookahead
- better branch-specific state transitions
- possible future recursive expectimax-style expansion

7. Expand mechanics coverage
- more items and abilities
- stronger Tera handling
- statuses / secondary effects / item consumption
- better forced-switch / replacement logic


--------------------------------------------------

# FRONTEND STATUS

Frontend is now reconnected to the modern evaluate-position backend contract.

Current recommended UI role split:

Core product surface:
- EvaluatePositionPanel

Supporting utility panels:
- DamagePreviewPanel
- TypeEffectivenessPanel


Frontend should now be used to:
- inspect ranked actions
- inspect continuation / search signals
- inspect explanation quality
- support scenario refinement and debugging


--------------------------------------------------

# Development Philosophy

Core architecture is now stable enough for real intelligence work.

Focus is now on:
- decision quality
- competitive realism
- explainability
- scenario-driven refinement
- keeping frontend and backend aligned

Build vertically through scenario-driven improvements.

Every improvement should:
- fix a failing scenario OR
- add a new scenario OR
- expose an important reasoning signal more clearly

Do not refactor backend in the abstract without a concrete decision-quality reason.

At this phase, scenario failures should decide the next intelligence upgrade.

Development should now move fastest through scenario batches, not abstract limitation lists.

Best workflow:
- collect a batch of competitive scenarios
- group them by failure theme
- identify the shared missing concept behind the failures
- implement one refactor per theme
- rerun the whole scenario batch

Examples of good scenario themes:
- switch prediction / defensive pivots
- preservation / sack logic
- setup / tempo
- risk / uncertainty handling

Do not treat every scenario as an isolated patch if multiple scenarios point to the same missing intelligence layer.

At this phase, the goal is not “fix one known limitation at a time.”
The goal is:
- use scenario clusters to discover the next missing reasoning layer
- implement the smallest stable refactor that fixes many related failures
- avoid brittle case-by-case heuristics when a shared abstraction is missing

Preferred refinement loop:
1. collect 10–20 scenarios
2. cluster them into 2–4 themes
3. refactor engine logic around those themes
4. rerun the full scenario pack
5. repeat

Frontend should stay aligned enough to inspect:
- ranked actions
- continuation / search signals
- explanation quality
- failure patterns during scenario testing