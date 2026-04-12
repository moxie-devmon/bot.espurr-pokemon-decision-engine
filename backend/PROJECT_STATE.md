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

Espurr has completed a major structural backend pass centered on:
- provider-backed meta priors
- candidate-world construction
- canonical data/provider migration
- engine alignment around world-aware evaluation

We are now in the:

🧠 ENGINE INTELLIGENCE REFINEMENT PHASE

This phase exists because the structural bottlenecks that were blocking intelligence work have been addressed enough that scenario tests now expose real reasoning gaps instead of architecture gaps.

Focus has shifted from:
- cleaning up backend structure
- building provider-backed priors
- replacing placeholder/local prior islands
- creating canonical mechanics/data access
- aligning engine modules around richer opponent worlds

→ to:

- improving decision quality under realistic competitive scenarios
- refining setup / tempo / utility / hazard / uncertainty reasoning
- strengthening response realism and continuation valuation
- using scenario buckets to drive targeted intelligence upgrades
- keeping architecture stable while increasing competitive sophistication

Important note:
the architecture is no longer the main blocker in the same way it was before.
The next gains come from cleaner competitive reasoning and better use of the now-stronger world model.


--------------------------------------------------

# Supported Competitive Scope

Espurr currently focuses on:

- Gen 9 OU first

Long-term target remains Smogon OU formats across generations, but active development is intentionally centered on Gen 9 OU until the engine intelligence is stronger.

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
- revealed-move constraints
- branch evidence updates
- cross-world reweighting during continuation reasoning

Current meta-prior direction:
- provider-backed normalized snapshots
- rolling 3-month Gen 9 OU priors
- Smogon-derived usage / set / tera / association structure
- candidate construction from normalized species priors

Long-term intended external sources:
- Smogon usage stats / moveset data
- MunchStats
- richer association / teammate / archetype priors

Key realization from the last engineering pass:
the engine substrate is now good enough that future intelligence quality depends heavily on:
- response realism
- projection fidelity
- continuation valuation
- scenario-guided refinement


--------------------------------------------------

# Confidence Categories

CONFIRMED
- revealed moves
- HP
- status
- hazards
- boosts

CONSTRAINED
- inferred item
- inferred ability
- inferred tera type
- narrowed move pool
- branch evidence updates from revealed responses

META-INFERRED
- EV spreads
- items
- abilities
- move sets
- archetype-level priors
- tera preferences


--------------------------------------------------

# Evaluation Strategy

Espurr evaluates actions across multiple plausible opponent worlds.

Each action currently considers:
- immediate projected outcome
- survivability
- turn order
- response risk
- switch value
- expected / worst / best aggregation
- shallow continuation value
- branch-updated opponent pressure
- world-weighted aggregation

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

Important current lesson:
the high-level evaluation contract is good enough to build on,
but setup / tempo / utility / hazard / uncertainty reasoning still need refinement through scenario-driven engine work.

Near-term direction:
- keep the current evaluation contract
- continue targeted patches guided by scenario buckets
- delay scoring-sublayer extraction until multiple buckets clearly demand it

Longer-term direction:
- cleaner scoring decomposition
- stronger expected value across inferred distributions
- better utility / progress / tempo scoring
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
    move_tags.py

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
    __init__.py
    models.py
    set_inference.py
    belief_updater.py
    candidate_builder.py
    consistency_checks.py

  explain/
    __init__.py
    explanation_engine.py

  providers/
    canonical_loader.py
    pokemon_provider.py
    move_provider.py
    type_chart_provider.py
    item_provider.py
    ability_provider.py
    nature_provider.py
    format_provider.py
    meta_provider.py
    meta_loader.py
    meta_normalizer.py
    provider_utils.py

  schemas/
    battle_state.py
    damage_preview.py
    data_endpoints.py
    type_effectiveness.py

  services/
    name_normalize.py

  tests/
    providers/
    engine/
    inference/
    scenarios/

  data/
    canonical/
      species.json
      moves.json
      items.json
      abilities.json
      type_chart.json
      natures.json
      formats.json
      field_effects.json
      statuses.json
      meta/
        gen9ou/
          1695/
            rolling_3m.json
    ...

backend/

  scripts/
    bootstrap_canonical_data.py
    build_meta_snapshot.py
    ingest_smogon_stats.py
    debug_species_candidates.py
    ...

scripts/ owns data bootstrapping, ingestion, snapshot generation, and engineering/debug utilities
scripts are maintenance/build tooling, not runtime app modules


Legacy bootstrap source:
- backend/data_legacy_bootstrap/

Near-future architectural direction:

backend/app/

  engine/
    evaluation_engine.py
    response_engine.py
    projection_engine.py
    lookahead_engine.py
    scoring/                      (still planned, not immediate)
      tactical_scorer.py
      switch_scorer.py
      utility_scorer.py
      setup_scorer.py
      hazard_scorer.py
      continuation_scorer.py
      uncertainty_scorer.py

The intended ownership is now:

- canonical data/providers own mechanics source-of-truth access
- meta providers own normalized competitive priors
- inference owns candidate world construction and reweighting
- engine owns battle reasoning and action ranking
- scenarios expose reasoning failures by theme


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
- ranked action fields for world / continuation metrics

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

Pure battle logic modules:

damage_engine
speed_engine
field_engine
switch_engine
response_engine
projection_engine
lookahead_engine
evaluation_engine

Current intelligence work is still primarily happening here.

INFERENCE LAYER

Current:
- provider-backed candidate set construction
- consistency filtering
- revealed move preservation
- branch evidence updates
- cross-world reweighting
- normalized world weighting via final candidate weight

Near-future goal:
- stronger belief updates from speed / damage / repeated behavior
- better archetype narrowing
- better team-aware priors later

EXPLANATION LAYER

- converts engine decisions into human-readable reasoning
- surfaces continuation / stability / world influence

ADAPTER LAYER

- converts schema → domain
- isolates engine from API format

PROVIDER LAYER

Current:
- canonical mechanics providers
- meta prior provider
- item / ability / nature / format providers

Near-future:
- richer canonical coverage
- automated meta refresh
- eventual DB-backed provider implementations


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
  ranked actions + confidence + world / continuation signals

Important context:
this pipeline now works end-to-end with provider-backed priors and canonical data.
The current bottleneck is no longer data plumbing.
The current bottleneck is competitive reasoning quality under scenario pressure.


--------------------------------------------------

# Current Engine Capabilities

- response_engine.py was refactored to use shared domain/move_tags.py instead of local competitive-tag sets
- canonical provider tests are green after bootstrapping from data_legacy_bootstrap

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
- opponent switch responses are now ranked from bench candidates instead of blindly using bench order

Opponent modeling:
- weighted candidate opponent worlds
- provider-backed world construction
- confirmed vs assumed move separation
- association-aware candidate building
- contradiction penalties
- tera-aware candidate shaping
- hydrated move metadata when available
- fallback proxy modeling when exact move details are weak

Projection / continuation:
- move and switch projected-state application
- forced-switch handling
- item / ability subset hooks
- replacement selection is improved over raw bench-order behavior
- shallow lookahead
- second-ply opponent response generation from updated branch distributions

Item / ability hooks (first-pass subset):
- Levitate
- Intimidate
- Leftovers
- Choice Band / Specs / Scarf
- Focus Sash

Inference / belief:
- real provider-backed priors for Gen 9 OU / 1695 / rolling 3m
- revealed moves preserved
- branch evidence updates
- cross-world reweighting
- candidate normalization via final weight
- debug tooling for species candidate inspection

Layered evaluation:
- tactical score bucket
- positional score bucket
- strategic score bucket carries continuation / search value
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
- stability and world-influence framing
- inference summary now respects final candidate weights

Testing:
- provider tests
- inference / builder regression tests
- engine regression tests
- scenario bucket pack v1

Current testing state:
- canonical provider layer is green
- candidate-builder quality pack is green
- projection quality pack is green
- evaluation / lookahead quality pack is green
- first scenario bucket pack is partially green


--------------------------------------------------

# Known Limitations

- Current concrete failing scenario: SCN-ST-01 (Setup / Tempo) still ranks immediate damage / switch safety above Dragon Dance, so next session should inspect lookahead continuation candidate ranking before attempting a broader scoring refactor.


High-priority intelligence limitations:
- setup / tempo reasoning is still weak and is the first clear scenario-bucket failure
- continuation is still driven partly by cheap heuristic next-action scoring
- response generation is much better than before, but still not fully competitive-realistic
- switch prediction and pivot punishment are still first-pass
- utility / progress / tempo value is not yet a first-class clean layer
- hazard removal / hazard preservation value is not yet well modeled
- team-role, win-condition, and sack logic are not implemented
- uncertainty handling exists but is still thinner than it should be
- hidden coverage prediction is still limited
- speed-evidence and damage-roll-evidence belief updates are not implemented yet

Search / simulation limitations:
- search is still shallow and heuristic rather than deep multi-turn planning
- continuation-state rebuilding is evaluation-grade, not simulator-grade
- secondary effects / status loops / item consumption are not simulator-complete
- randomness-aware outcome distributions remain limited
- lookahead still uses cheap continuation heuristics more than ideal

Competitive modeling limitations:
- Gen 9 OU is the real supported target right now; other formats are aspirational
- EV / nature modeling is not yet active in battle reasoning
- Tera modeling exists in candidate construction but is still limited in downstream engine use
- item / ability modeling exists only for a subset of high-impact mechanics
- no team-aware prior adjustment yet
- no full move_tera / item_ability / deeper joint association modeling yet

Canonical data / infra limitations:
- canonical JSONs are populated via bootstrap from data_legacy_bootstrap, so canonical structure is correct but data breadth is still limited by the legacy subset source
- canonical mechanics coverage is still incomplete / thin relative to a full Pokémon database
- meta-prior ingestion refresh is currently manual
- DB backing is not implemented yet
- future auth / saved teams / Pokepaste persistence are not implemented yet

Product / UX limitations:
- frontend is usable for inspection/debugging, but not polished as a public-facing product
- explanation quality is useful for engineering validation, not yet polished for end users

Important priority note:
not all known limitations are immediate next steps.

Current priority order is:
1. scenario-driven engine intelligence refinement
2. stronger setup / utility / tempo / uncertainty reasoning
3. stronger response realism and continuation quality
4. broader strategic Pokémon reasoning
5. DB/auth/product features later


--------------------------------------------------

# Scenario Testing Harness

Located in:

backend/app/tests/scenarios/

Uses serialized or directly constructed battle states.

Validates:
- decision correctness
- regression prevention
- competitive realism failures
- whether targeted engine upgrades improve reasoning quality

Current role of scenarios:
scenario tests are now a primary driver for the next intelligence phase.

Use them to:
- expose failure clusters
- decide which competitive concept is missing
- patch the missing concept cleanly
- rerun the whole bucket

Do not use them to:
- justify random one-off hacks
- bypass the existing architecture
- hide missing concepts inside brittle helper patches

Current first scenario bucket pack:
- Hazard / Positioning Value
- Setup / Tempo
- Defensive Pivot / Switch Prediction
- Risk / Uncertainty Handling

Current result:
- 3/4 first-pass scenarios green
- Setup / Tempo bucket is the first clear failing bucket
- this suggests the next engine refactor target is continuation/setup valuation, not more data plumbing

Preferred scenario usage now:
1. keep a small baseline regression pack
2. expand bucket by bucket
3. let failure clusters determine the next intelligence patch
4. rerun the whole bucket after each refinement pass


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
domain/move_tags.py
adapters/manual_input_adapter.py

inference/models.py
inference/set_inference.py
inference/belief_updater.py
inference/candidate_builder.py
inference/consistency_checks.py

providers/canonical_loader.py
providers/pokemon_provider.py
providers/move_provider.py
providers/type_chart_provider.py
providers/item_provider.py
providers/ability_provider.py
providers/nature_provider.py
providers/format_provider.py
providers/meta_provider.py
providers/meta_loader.py
providers/meta_normalizer.py
providers/provider_utils.py

explain/explanation_engine.py

Canonical data surface:
app/data/canonical/*

Legacy bootstrap source:
data_legacy_bootstrap/*

Frontend reconnect surface:
frontend/src/app/components/EvaluatePositionPanel.tsx
frontend/src/app/lib/api.ts
frontend/src/app/page.tsx

Scenario / validation surface:
tests/providers/*
tests/inference/*
tests/engine/*
tests/scenarios/*

tests/scenarios/test_scenario_bucket_pack_v1.py
tests/engine/test_projection_engine_quality.py
tests/engine/test_evaluation_lookahead_quality.py
tests/providers/test_canonical_providers.py

Scripts:
scripts/bootstrap_canonical_data.py
scripts/build_meta_snapshot.py
scripts/ingest_smogon_stats.py




--------------------------------------------------

# Next Major Development Steps

1. Fix the Setup / Tempo bucket

** the first scenario-bucket failure is specifically SCN-ST-01, where setup is still undervalued versus immediate damage / switch safety 

- inspect lookahead_engine.py continuation candidate selection and cheap heuristic move/switch ranking first
- avoid scoring-sublayer refactor unless multiple scenario buckets point there

- improve continuation valuation for setup lines
- reduce overreliance on cheap next-action heuristics in lookahead
- better recognize momentum-favorable setup windows
- rerun the scenario pack until setup reasoning is directionally correct

2. Expand the first scenario bucket pack
- add 1–2 more concrete scenarios per current bucket
- keep assertions directional and competitive, not overly brittle
- use the failing bucket to drive the next patch instead of guessing

3. Improve opponent response realism further
- better switch likelihood modeling
- better defensive pivot recognition
- better punishment of obvious immunity pivots
- better setup / utility response selection

4. Improve continuation search quality
- reduce cheap heuristic continuation choices
- make setup / recovery / pivot followups more realistic
- improve branch-specific continuation scoring
- only refactor scoring into submodules if multiple buckets clearly demand it

5. Improve broader strategic reasoning
- utility / progress move value
- hazard control / hazard preservation
- preservation / sack logic
- endgame cleaner / anti-cleaner logic
- stronger uncertainty-aware action selection

6. Strengthen inference later
- speed evidence
- damage evidence
- repeated-behavior evidence
- team-aware priors
- stronger archetype narrowing

7. Expand mechanics coverage later
- more items and abilities
- deeper Tera downstream usage
- statuses / secondary effects / consumables

8. DB / product phase later
- likely Supabase/Postgres
- auth
- saved teams
- Pokepaste imports
- provider-backed DB transition if needed

Important sequencing principle:
do not over-refactor scoring architecture before scenario buckets actually justify it.
Right now targeted engine reasoning upgrades are higher value than a broad scorer-sublayer rewrite.


--------------------------------------------------

# FRONTEND STATUS

Frontend is reconnected to the modern evaluate-position backend contract.

Current recommended UI role split:

Core product surface:
- EvaluatePositionPanel

Supporting utility panels:
- DamagePreviewPanel
- TypeEffectivenessPanel

Frontend should currently be used to:
- inspect ranked actions
- inspect world / continuation signals
- inspect explanation quality
- inspect assumption quality
- support scenario validation and debugging

Frontend is not the main priority in this phase,
but should stay aligned enough to inspect new engine reasoning outputs as they improve.


--------------------------------------------------

# Development Philosophy

Espurr is now past the phase where architecture was the main bottleneck.

The current philosophy is:

build a stable structural base first,
then let scenario buckets reveal the next missing intelligence concept.

This means:

- do not keep rebuilding infrastructure unless scenario failures clearly point back to infrastructure
- do not do broad refactors when one bucket gives a specific target
- keep competitive tags / mechanics / priors in the correct layers
- keep engine patches concept-driven, not one-off

Practical rules:

- if a scenario failure comes from missing competitive reasoning inside a now-stable engine path, patch that concept directly
- if multiple buckets fail for the same tangled reason, then refactor the owning layer
- if a failure is still due to missing source-of-truth data or priors, fix the provider/inference layer
- avoid duplicating competitive knowledge locally when shared domain/provider layers already exist
- use scenarios as validator + prioritizer + acceptance layer

Current heuristic:
- one failing bucket → targeted reasoning patch
- multiple related bucket failures → consider deeper refactor
- architecture changes should be driven by repeated failure patterns, not by aesthetics alone

The project should currently move through:

scenario bucket failure
→ identify missing competitive concept
→ patch engine reasoning cleanly
→ rerun the bucket
→ expand the scenario pack
→ only then consider deeper refactors

not:

broad architecture churn
→ patch everything preemptively
→ lose the signal from scenario-guided refinement