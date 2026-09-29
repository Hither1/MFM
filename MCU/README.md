# MCU — World-Model Agent Harness

The long-horizon Minecraft agent this fork adds, and the machinery for running two memory
protocols against each other as controlled arms.

Everything below is specific to this fork. **The upstream AgentBeats green-agent
documentation — setup, scoring, the A2A message formats, project layout — is still in this
file, hidden inside HTML comments.** Open the raw file to read it.

| If you want to | Read |
| --- | --- |
| Run one agent on one task, or three arms against each other | [Running Comparison Arms](#-running-comparison-arms) |
| Know what the simulator does and does not give an agent | [The Actuation Floor](#-the-actuation-floor) |
| Run or read the mfm arm of branch `spatial-grid` -- every experiment option, the launch recipes, the outputs, the arms on record | [README-mfm-arms.md](README-mfm-arms.md) |
| Set up the green agent, or write a purple agent to the A2A protocol | the commented-out upstream sections in the raw file |

<!-- UPSTREAM README, hidden. This section is inherited from KWSMooBang/MCU-AgentBeats
     and is not about the agents in this fork. Kept verbatim rather than deleted so a
     merge from upstream still applies cleanly; unwrap this comment to read it.

# MCU Green Agent - AgentBeats Competition

A comprehensive Minecraft-based benchmark evaluation agent for evaluating AI agents' planning, reasoning, and multi-step execution capabilities. Green Agent evaluates Purple Agent in complex, open-world minecraft environments using the A2A protocol.

## 🎯 Overview

This Green Agent provides a rigorous evaluation for various tasks in minecraft environment that goes beyond simple task completion metrics. It evaluates:

- **Spatial Reasoning**: Navigation, building, and exploration in 3D space
- **Tool Use**: Strategic use of items and environmental interactions
- **Resource Management**: Efficient use of materials and time under constraints
- **Adaptability**: Handling diverse task types across various distinct categories
- **Multi-step Planning**: Complex tasks requiring sequential action planning (e.g., crafting requires gathering materials → using crafting table → combining items)

### Key Features

**Diverse Tasks** across 12 categories  
**Reward-based Evaluation** with simulation tracking and video assessment  
**Reproducible & Consistent** results with deterministic task initialization  
**A2A Protocol Compatible** - works with any compliant agent  
**Automated Scoring** using MCU benchmark reward system  
**Configurable** - select categories and customize step limits

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Docker (for containerized deployment)
- OpenAI API key (for video evaluation)

### 1. Installation & Environment Setup
First, clone repository and install dependencies:
```bash
# Clone repository
git clone https://github.com/KWSMooBang/MCU-AgentBeats.git
cd MCU-AgentBeats

# Install dependencies with uv
uv sync
```

Then, Create a `.env` file in the project root:
```bash
# Required for video evaluation
OPENAI_API_KEY=your-openai-api-key-here
```

### 2. Run Green Agent Server

#### Running Locally
```bash
uv python src/server.py --host 0.0.0.0 --port 9009

# With custom agent card URL
python src/server.py --host 0.0.0.0 --port 9009 --card-url "http://localhost:9009"
```

#### Running with Docker
```bash
docker build -t mcu-green-agent .
docker run \ 
  -p 9009:9009 \ 
  --env-file .env \ 
  mcu-green-agent \
  --host 0.0.0.0 \
  --port 9009
```

**Server Health Check:**
```bash
curl http://localhost:9009/.well-known/agent-card.json
```

## 📊 Test Evaluation

### Step 1: Start Purple Agent Server (Test Agent)

The repository includes a sample Purple Agent using STEVE-1 model for testing:

```bash
# In a separate terminal, start the test Purple Agent
uv run python test_purple_agent.py --host 0.0.0.0 --port 9019

# When you run green agent server with Docker
uv run python test_purple_agent.py --host 0.0.0.0 --port 9019 --card-url "http://host.docker.internal:9019"
```

### Step 2: Configure Test Scenario

Edit `test_scenario.toml` to configure your evaluation:

```toml
[green_agent]
endpoint = "http://127.0.0.1:9009"

[[participants]]
role = "agent"
endpoint = http://127.0.0.1:9019" 
or 
endpoint = "http://host.docker.internal:9019" (with Docker)

[config]
task_category = "crafting"  # Change to desired category
max_steps = 900           # Optional: customize step limit
```

**Available categories**: `building`, `combat`, `crafting`, `decoration`, `ender_dragon`, `explore`, `find`, `mine_diamond_from_scratch`, `mining_and_collecting`, `motion`, `tool_use`, `trapping`

### Step 3: Run Evaluation

```bash
# Run evaluation with scenario file
uv run python test_evaluation.py test_scenario.toml

# Save results to JSON file
uv run python test_evaluation.py test_scenario.toml output/results.json
```

**Expected Output:**
```
[Status: submitted]
Starting MCU evaluation with 8 tasks from crafting

[Status: working]
Running task: craft_furnace 

[Status: working]
Running task: craft_ladder

[Status: completed]
MCU Evaluation Result
Category: crafting
Number of Tasks: 8
Total Score: 65.4

Task Results:
Task 'craft_furnace': 8.7
Task 'craft_ladder': 7.9
Task 'craft_enchanting_table': 8.2
...
```

-->

## 🧪 Running Comparison Arms

`test_evaluation.py` runs one agent against one task. A *comparison arm* is that plus the
isolation and the settings that make two runs differ in exactly one thing. Getting this
wrong is not loud — a shared credential, a shared session store, or an inherited config
file changes results without changing any log line you would think to read — so the setup
is scripted rather than described.

### Quick version

```bash
# One arm.
scripts/run-arm.sh --arm dm_lb --agent logbook \
                   --task mine_diamond_from_scratch \
                   --green-port 9053 --purple-port 9063

# Three arms at once. Different ports, different --arm names, nothing else shared.
scripts/run-arm.sh --arm dm_pl  --agent prolong --green-port 9051 --purple-port 9061 &
scripts/run-arm.sh --arm dm_lb  --agent logbook --green-port 9053 --purple-port 9063 &
scripts/run-arm.sh --arm dm_lbc --agent logbook --green-port 9055 --purple-port 9065 --session-turns 12 --compact &
wait
```

`--dry-run` prints the plan and exits — worth doing once before a 12,000-step run.

| Option | Default | What it decides |
| --- | --- | --- |
| `--arm NAME` | required | `output/NAME`, the log prefix, and the codex home |
| `--agent KIND` | required | `logbook`, `mfm`, `vista`, `arc`, `direct` (the no-memory baseline: read-only codex, no filesystem memory, a rolling reply window as the only past), `prolong`, or `steve1` |
| `--task NAME` | `mine_diamond_from_scratch` | task category |
| `--green-port` / `--purple-port` | required | A2A ports; must be free |
| `--steps N` | `12000` | `max_steps` |
| `--step-timeout SEC` | `600` | seconds per observation |
| `--session-turns N` | `0` | turns a codex session is resumed for before it is dropped; `0` is one thread for the episode, bounded by `--session-bytes`. `1` reproduces the arms measured up to 2026-09-09 — see below |
| `--session-bytes B` | `4000000` | base64 bytes of frames one resumed session may carry; the turn whose frame would cross it cold-starts instead (`0` = no budget, which hits the wall below) |
| `--compact` | off | on a full conversation, summarise and carry on instead of cold-starting. Only does anything with `--session-turns` other than 1 |

Nothing in these scripts kills anything. Ports are checked as free and the run aborts if
one is taken. A `pkill` in a launcher has taken out four running arms on this project
before; adding one back would do it again.

### Prerequisites on a host without root

`source env.sh` handles JDK8, Xvfb and `MINESTUDIO_DIR`, and `run-arm.sh` sources it for
you. Two of its constraints matter when you place anything else:

- **`$HOME` is a network filesystem here.** MineStudio's sqlite instance registry fails on
  it with `cannot rollback - no transaction is active`, which is why `MINESTUDIO_DIR`
  points at local disk. Anything else holding sqlite needs the same treatment.
- **No GPU render path**, so the engine runs through Xvfb and Mesa llvmpipe at roughly 22
  FPS per instance. Three concurrent arms is comfortable; each Minecraft instance also
  wants a few GB of RAM for the JVM.

`steve1` additionally needs a CUDA device — set `CUDA_VISIBLE_DEVICES` before launching it,
and give concurrent neural arms different devices.

### What isolation actually means

`scripts/codex-home.sh` builds one CODEX_HOME per arm. Use it directly if you are running
something `run-arm.sh` does not cover:

```bash
eval "$(scripts/codex-home.sh my_arm)"   # exports CODEX_RUNTIME_HOME and CODEX_SQLITE_DIR
```

Each of its four jobs comes from something that went wrong here:

**A private session store.** Six arms shared one
`~/.codex/runtime-home/thread_history_1.sqlite` until it failed `PRAGMA integrity_check`
with `database disk image is malformed`. That breaks `codex exec resume` for every process
on the host, which forces `CODEX_SESSION_MAX_TURNS=1` — no conversation memory at all — and
it stayed broken for a full campaign because the `codex` wrapper auto-repairs four other
databases and not that one. If you ever see `failed to access thread history`, move the
file aside and codex rebuilds it.

**A shared credential, never a copy.** `auth.json` is symlinked, because each copy of an
OAuth credential carries the same single-use refresh token: the second arm to refresh gets
`your refresh token was already used` and every later turn 401s. Point `MCU_CODEX_AUTH` at
a different file to run a different account.

**No personal config.** The `codex` wrapper symlinks `~/.codex/{AGENTS.md,lessons.md,RTK.md}`
into whatever home it is given, and codex prepends them to every turn — 24,756 bytes on
this account, ahead of the agent's own 19.6 KB system prompt. `--ignore-user-config` does
not cover them. Empty real files defeat the symlink step, which skips a target that
already exists.

**Not under `/tmp`.** Codex refuses to create its PATH-alias helper binaries there
(`Refusing to create helper binaries under temporary dir`). The default is
`/var/tmp/mcu-codex-$USER`: same local ext4 partition, not wiped at boot, no refusal.
Override with `MCU_CODEX_ROOT`, but keep it on local disk. Budget about 6 MB per arm plus
roughly 20 KB per model turn of session history — a 12,000-step arm lands near 25 MB.
Homes are `chmod 700`: the credential is a symlink to a 600 file and was never exposed, but
the session store holds the full conversation, and a shared host has other accounts on it.

### Choosing the settings that define an arm

Two arms are only comparable if everything below is either identical or the one thing under
test.

- **`--compact` vs the default.** Codex ships auto-compaction. When a resumed conversation
  fills up, either it compacts and carries on, or it overflows and cold-starts onto the
  filesystem memory. `CODEX_AUTO_COMPACT_TOKEN_LIMIT` decides which, and `run-arm.sh` always
  sets it explicitly — leaving it unset hands the choice to whatever codex defaults to,
  which is neither measured nor guaranteed equal between two runs. `worldmodel_report.json`
  reports the limit in force alongside `compactions` and `overflow_resets`, so check there
  rather than inferring from logs. Under the byte budget a thread is cold-started before
  the token side ever fills, so this flag is inert under the default too; it only becomes
  a real choice with `--session-bytes 0`, and even then the byte wall above arrives first. Measured: a 258 K window,
  ~1.9 K tokens a turn, so the token budget is 27 % used at the point the payload has
  already stalled the arm.

- **`--step-timeout`.** The benchmark default of 60 s suits a reactive policy answering in
  milliseconds. A planning agent spends a whole model turn on the step where it re-plans,
  and at 60 s those steps silently become noops. 600 is the working value here.

- **`--session-turns` / `--session-bytes`: one thread, byte-budgeted.** Every act turn attaches the current
  frame, because the observation here is pixels rather than text. On a resumed session the
  old frames stay in the thread and codex re-sends the whole conversation on every call, so
  the request grows about 0.4 MB a turn with nothing to bound it. Measured on three
  independent arms: below ~5 MB a turn costs `42s + 11.2s per MB`; somewhere between 5.15
  and 6.15 MB it steps to a flat ~600 s and stays there however much further it grows. All
  three crossed at turn 11–18 and dropped to roughly one step per ten minutes — no errors,
  no log line, just 10× slower. A 12,000-step episode needs 1,500–2,000 turns, so anything
  that grows per turn is dead long before the end; at one turn per session the payload is a
  constant 0.48 MB and the wall is unreachable. Session accumulation itself is harmless:
  1,878 consecutive single-turn sessions showed no latency drift (53–71 s median
  throughout) and cost about 513 KB each on disk.

  Until 2026-09-09 every arm ran `--session-turns 1` — a constant 0.48 MB payload, the wall
  unreachable, and no conversation memory at all: every turn rebuilt its state from the
  filesystem. The ladder's VISTA arm keeps one thread and hands off to a fresh one on a
  byte budget, so the memory arms now run the same way: the default `--session-turns 0
  --session-bytes 4000000` keeps a thread for ~8 act turns and cold-starts it *before* the
  frame that would cross the budget. The audit reports `bytes_resets` and
  `session_max_bytes` when the budget is on; `age_resets` stays 0. Both agents are built to
  survive a handoff: `_discard_session` already drops a thread on any unclean ending,
  precisely because `logs.txt` and the episode store live on the filesystem. The direct arm ignores both knobs and keeps its
  forced 1-turn sessions. Scores under the two policies are different arms; pass
  `--session-turns 1` to reproduce the earlier waves, and do not average across them.

  Note the counters are token-based and this failure is byte-based: at the point the arms
  stalled, the token budget was 27 % used while the wire payload was already past the wall.
  `compactions` and `overflow_resets` will read zero through the whole thing.

- **The action space is a property of the host, not the arm.** `src/agent.py` builds
  `MinecraftSim` with `action_type="env"`, where a camera value reaches the game as written.
  Under MinecraftSim's `agent` default it round-trips through VPT's mu-law binning and only
  11 values per axis survive — measured on the live simulator, a request of 4.32° (one 18 px
  inventory slot) is delivered as 4.3200 in `env` and 3.2154 in `agent`. That is lossless
  for a neural policy whose head emits those bins and lossy for anything writing degrees.
  If you change it, `MCU_CAMERA_QUANTISED=1` puts the world model's compensation and the
  camera correction in `camera_contract.py` back.

### Reading the result

```
logs/<arm>_green.log     environment side, including the final score block
logs/<arm>_purple.log    agent side: turns, milestones, session and quota errors
logs/<arm>_client.log    the evaluation client
logs/<arm>_result.json   the score
output/<arm>/episode_001/
    logs.txt                 every action and the state that followed
    frames/                  the first-person view per step
    memory/                  the arm's memory: logs.txt, episodes/ (mfm), mine/ (--own)
    worldmodel_report.json   milestones with the step each landed, turn counts, codex audit
```

Two things worth checking before trusting a number:

```bash
# Milestones with the step each landed on -- the comparison that matters, since the score
# counts milestones reached and is blind to how many steps each took.
python3 -c "import json;print(json.load(open('output/dm_wm/episode_001/worldmodel_report.json'))['milestones'])"

# Failed turns are usually infrastructure, not the agent. Check before concluding anything.
grep -oE "wrote no actions.json \(rc=[0-9]+\); .{0,60}" logs/dm_wm_purple.log | sort | uniq -c
```

Video scoring needs `OPENAI_API_KEY`. Without it that component fails cleanly and
`Total Score` falls back to the milestone-derived `sim_score`, which is the intended mode
for these comparisons.

<!-- UPSTREAM README, hidden. This section is inherited from KWSMooBang/MCU-AgentBeats
     and is not about the agents in this fork. Kept verbatim rather than deleted so a
     merge from upstream still applies cleanly; unwrap this comment to read it.

## ⚙️ Configuration Parameters

### Required
- **participants.agent** (str): URL of the Purple Agent to evaluate
  - Example: `"http://green-agent:9009"` or `"http://purple-agent:9019"`
  - Must be A2A protocol compatible

### Optional
- **task_category** (str): Task category to evaluate
  - Examples: `"combat"`, `"crafting"`, `"building"`
  - Available categories: `building`, `combat`, `crafting`, `decoration`, `ender_dragon`, `explore`, `find`, `mine_diamond_from_scratch`, `mining_and_collecting`, `motion`, `tool_use`, `trapping`

- **max_steps** (int): Maximum steps per task
  - **Default for standard tasks**: 1200 steps
  - **Default for long-term tasks**: 12000 steps
    - Long-term tasks categories: `kill_ender_dragon`, `mine_diamond_from_scratch`
    - These tasks require extensive resource gathering, crafting chains, and exploration
  - Custom values: Can be set in config, but will be capped at 1200 for non-long-term tasks
  - Recommended ranges:
    - Quick tasks (motion, explore): 500-900 steps
    - Standard tasks (crafting, combat): 900-1500 steps
    - Long-term tasks: 10000-12000 steps

## 📁 Project Structure

```
MCU-AgentBeats/
├── scripts/
│   ├── run-arm.sh          # One comparison arm end to end
│   └── codex-home.sh       # Isolated CODEX_HOME for one arm
├── src/
│   ├── server.py           # A2A server entry point
│   ├── agent.py            # Main evaluation logic
│   ├── messenger.py        # Purple agent communication
│   ├── executor.py         # Task execution management
│   ├── model.py            # Pydantic data models
│   └── util.py             # Helper functions (task loading, video processing)
│
├── MCU_benchmark/
│   ├── task_configs/
│   │   └── tasks/          # Task definitions by category
│   │       ├── building/
│   │       ├── combat/
│   │       ├── crafting/
│   │       ├── decoration/
│   │       ├── ender_dragon/
│   │       ├── explore/
│   │       ├── find/
│   │       ├── mine_diamond_from_scratch/
│   │       ├── mining_and_collecting/
│   │       ├── motion/
│   │       ├── tool_use/
│   │       └── trapping/
│   │
│   └── auto_eval/
│       ├── prompt/         # Video evaluation prompts
│       └── criteria_files/ # Task-specific evaluation criteria
│
├── output/                 # Evaluation results and recordings
├── logs/                   # Server logs
└── pyproject.toml          # Project dependencies
```

## 🏆 Benchmark Design Quality

### Why Minecraft for Agent Evaluation?

Minecraft provides a rich, open-world environment that closely mirrors real-world agent challenges:

1. **Complex State Space**: Thousands of block types, items, and environmental states
2. **Emergent Complexity**: Simple actions combine into complex behaviors
3. **Grounded Multimodal Input**: Visual observation (RGB images) with spatial reasoning
4. **Diverse Skill Requirements**: Navigation, crafting, combat, exploration, construction
5. **Long-horizon Tasks**: Require over 12000 steps with intermediate goals

### Task Categories

Our benchmark includes **12 distinct categories**, each testing different capabilities:

#### Standard Tasks 

| Category | Skills Tested | Example Tasks |
|----------|---------------|---------------|
| **building** | Spatial reasoning, multi-step execution | Build house, tower, maze |
| **combat** | Real-time decision making, positioning | Combat zombies, skeletons, enderman |
| **crafting** | Sequential planning, recipe knowledge | Craft enchanting table, furnace, ladder |
| **decoration** | Creative placement, aesthetic judgment | Decorate wall/ground, lay carpet |
| **explore** | Pathfinding, environment interaction | Explore chest, boat, climb |
| **find** | Visual search, navigation | Find diamond, village, bedrock |
| **mining_and_collecting** | Efficient resource gathering | Collect wood/wool/dirt, mine ores |
| **motion** | Basic movement and interaction | Drop item, look at sky, stacking |
| **tool_use** | Tool understanding, context-aware actions | Use bow, shield, brew potion |
| **trapping** | Strategic planning, entity manipulation | Trap mobs |

#### Long-term Tasks

| Category | Skills Tested | Example Tasks |
|----------|---------------|---------------|
| **ender_dragon** | Advanced combat, long-term planning, resource pipeline | Kill ender dragon |
| **mine_diamond_from_scratch** | Complete resource gathering → crafting → mining pipeline | Mine diamond from scratch |

These tasks require extensive multi-stage planning: gathering initial resources → crafting tools → exploring → achieving final goal.

## 📊 Evaluation Methodology

### Scoring Logic

The evaluation system uses different scoring approaches based on task configuration:

#### 1. Tasks with `reward_cfg` (Standard MCU Benchmark Tasks)

For tasks with reward configurations (most standard tasks):

1. **Primary Score**: Simulation reward tracking during execution
   - MineStudio simulator monitors task events (e.g., craft_item, mine_block)
   - Rewards are accumulated based on achieved milestones
   - `sim_score = total_rewards_achieved`

2. **Video Enhancement**:
   - Video evaluation is performed only when `sim_score < max_score`
   - If sim_score already equals max_score (perfect completion), video evaluation is skipped
   - GPT-4 Vision analyzes the gameplay video and scores "Task Progress" (0-10)
   - `final_score = (sim_score + task_progress_score) / 2`
   - This helps capture partial progress not reflected in discrete reward events

**Example:**
```yaml
# craft_furnace.yaml
reward_cfg:
  - event: craft_item
    objects: 
    - furnace
    reward: 10.0
    max_reward_times: 1
```

#### 2. Tasks with `milestone_reward_cfg` (Long-term Tasks)

For complex, multi-stage, long horizon tasks (kill_ender_dragon, mine_diamond_from_scratch):

1. **Milestone Tracking**: Task broken into sequential milestones
2. **Continuous Scoring**: `continuous_score = completed_milestones + current_progress`
   - `completed_milestones`: Number of fully achieved milestones
   - `current_progress`: Progress on current incomplete milestone (0-1), evaluated by GPT-4 Vision
3. **Final Score**: `(continuous_score / total_milestones) * 100`

This provides fine-grained progress measurement for tasks requiring 12,000+ steps.

#### 3. Tasks without Reward Configurations

For tasks without reward_cfg or milestone_reward_cfg:

1. **Video-Only Evaluation**: GPT-4 Vision analyzes recorded gameplay
2. **Score**: Based solely on "Task Progress" dimension (0-10)
3. Use case: Tasks where success is subjective or difficult to define programmatically

### Video Evaluation Criteria

When video evaluation is used, GPT-4 Vision assesses gameplay across **6 dimensions**:

| Criterion | Description | Score Range |
|-----------|-------------|-------------|
| **Task Progress** | Goal achievement level | 0-10 |
| **Action Control** | Precision and appropriateness of actions | 0-10 |
| **Error Recognition** | Detection and correction of mistakes | 0-10 |
| **Creative Attempts** | Novel problem-solving approaches | 0-10 |
| **Task Efficiency** | Speed and resource optimization | 0-10 |
| **Material Selection** | Correctness of tool/item usage | 0-10 |

**Note**: Video evaluation requires OpenAI API key and is used strategically:
- For long-term tasks: evaluating progress on incomplete milestones
- For standard tasks: enhancing simulation scores when partial completion is detected
- For non-reward tasks: primary scoring method

### Scoring Summary

| Task Type | Primary Metric | Video Evaluation Role | Max Score |
|-----------|---------------|----------------------|-----------|
| Standard with `reward_cfg` | Simulation rewards | Enhancement when score < max | 10 |
| Long-term with `milestone_reward_cfg` | Milestone completion + progress | Current milestone progress | 100 |
| No reward config | Video "Task Progress" | Primary scoring method | 10 |

## 📈 Evaluation Result Example

### Result Format

Results are saved in `output/{timestamp}/result.json`:

```json
{
  "participants": {
    "agent": "019bc2e2-b44b-71f3-9fa5-e89901920e31"
  },
  "results": [
    {
      "task_category": "crafting",
      "num_tasks": 10,
      "total_max_score": 100.0,
      "total_score": 21.5,
      "avg_action_control": 3.4,
      "avg_error_recognition_and_correction": 0.9,
      "avg_creative_attempts": 0.2,
      "avg_task_completion_efficiency": 1.9,
      "avg_material_selection_and_usage": 4.3,
      "task_metrics": {
        "craft_oak_planks": {
          "max_score": 10.0,
          "sim_score": 0.0,
          "score": 4.0,
          "action_control": 9.0,
          "error_recognition_and_correction": 8.0,
          "creative_attempts": 2.0,
          "task_completion_efficiency": 8.0,
          "material_selection_and_usage": 9.0
        },
        "craft_the_crafting_table": {
          "max_score": 10.0,
          "sim_score": 0.0,
          "score": 1.5,
          "action_control": 8.0,
          "error_recognition_and_correction": 0.0,
          "creative_attempts": 0.0,
          "task_completion_efficiency": 0.0,
          "material_selection_and_usage": 4.0
        },
        "craft_diorite": {
          "max_score": 10.0,
          "sim_score": 0.0,
          "score": 2.0,
          "action_control": 2.0,
          "error_recognition_and_correction": 0.0,
          "creative_attempts": 0.0,
          "task_completion_efficiency": 1.0,
          "material_selection_and_usage": 3.0
        },
      
        ...

      }
    }
  ]
}
```

## 🔧 Purple Agent Requirements

Your Purple Agent must implement the following A2A message protocol. For detailed action space documentation, refer to [MineStudio Action Space](https://craftjarvis.github.io/MineStudio/simulator/general-information.html#action-space).

### 1. Initialization Message

**Request (InitPayload):**
```json
{
  "type": "init",
  "prompt": "You are an AI agent that can play Minecraft...",
  "text": "craft furnace from cobblestone"
}
```
- **prompt**: Basic instruction or context for the agent's role and behavior. Example: "You are an AI agent that can play Minecraft...". This defines the agent's overall style, goals, and constraints, action space, and serves as a decision-making guideline during action inference.
- **text**: The specific task or command to be performed. Example: "craft furnace from cobblestone". This clearly specifies the goal to be achieved and is a key input for determining the agent's purpose during action inference.

**Response (AckPayload):**
```json
{
  "type": "ack",
  "success": true,
  "message": "Agent initialized and ready"
}
```

### 2. Observation and Action Message

**Request (ObservationPayload):**
```json
{
  "type": "obs",
  "step": 42,
  "obs": "<base64_encoded_128x128_RGB_image>"
}
```
- **obs**: The current observation of the environment, typically a base64-encoded RGB image of Minecraft game screen. This allows the agent to perceive the environment and infer the most appropriate action for the current situation.

**Response (ActionPayload):**

The agent supports **three action formats**:

#### Format 1: Compact Agent Format (Recommended)
```json
{
  "type": "action",
  "action_type": "agent",
  "buttons": [123],
  "camera": [60]
}
```
- `buttons`: Single integer (0-8191) encoding all button states as a bitmask
- `camera`: Single integer (0-120) for discretized camera movement

#### Format 2: Expanded Agent Format
```json
{
  "type": "action",
  "action_type": "agent",
  "buttons": [0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
  "camera": [0.0, 90.0]
}
```
- `buttons`: 20-element binary array for individual button states
- `camera`: [yaw, pitch] in degrees

#### Format 3: Environment Format
```json
{
  "type": "action",
  "action_type": "env",
  "action": {
    "forward": 1,
    "back": 0,
    "left": 0,
    "right": 0,
    "jump": 0,
    "sneak": 0,
    "sprint": 0,
    "attack": 0,
    "use": 0,
    "drop": 0,
    "inventory": 0,
    "hotbar.1": 0,
    "hotbar.2": 0,
    "hotbar.3": 0,
    "hotbar.4": 0,
    "hotbar.5": 0,
    "hotbar.6": 0,
    "hotbar.7": 0,
    "hotbar.8": 0,
    "hotbar.9": 0,
    "camera": [0.0, 0.0]
  }
}
```

### Action Space Details

For complete action space specification, see the [MineStudio documentation](https://craftjarvis.github.io/MineStudio/simulator/general-information.html#action-space).

**Button Actions:**
- Movement: `forward`, `back`, `left`, `right`, `jump`, `sneak`, `sprint`
- Interaction: `attack`, `use`, `drop`, `inventory`
- Hotbar: `hotbar.1` through `hotbar.9`

**Camera Control:**
- Format: `[yaw, pitch]` or single discretized value
- Yaw range: -180° to 180° (horizontal rotation)
- Pitch range: -90° to 90° (vertical rotation)

**Note**: All three formats are automatically parsed and converted by the Green Agent. Choose the format that best suits your agent's architecture.

-->

## 🧰 The Actuation Floor

None of what follows is a memory protocol. It is the substrate any long-horizon agent needs
before two memory arms can differ by anything but noise: on a benchmark where a recipe is a
mouse cursor landing on a slot, an agent with a perfect memory and a sloppy actuator scores
zero.

### What the action space does not contain

**No craft action.** `CraftAction` and `SmeltAction` exist in the MineStudio tree but are
never installed on the `MinecraftSim` this benchmark builds. Crafting cannot be *issued* — it
can only be *performed*, by opening the inventory GUI and moving a mouse cursor over slots.
Every recipe in a long-horizon chain is therefore a pixel-accurate pointer problem, and
because the milestone chain is tool-tier gated — cobblestone needs a wooden pickaxe, iron ore
a stone pickaxe, the ingot a furnace and fuel, diamond an iron pickaxe, obsidian a diamond one
— a single missed craft near the top caps everything below it. The crafting GUI, not
exploration, is where these runs are won or lost.

**No `ESC`.** There is no action that ends an episode; it ends when the step budget runs out
and at no other moment. Anything that checks the agent's own claims therefore has to run
continuously, because there is no single point to gate at.

### Procedures are closed loops, not macros

Crafting and locomotion are parameterised routines over the primitive action space —
`aim_at_ore`, `chop_tree`, `mine_forward`, `stair_down`, `cursor_to_slot`, `stow_items`. Every
action they emit is an ordinary env action through the same `sim.step`, and a milestone still
fires only when MineRL's own statistic moves; the procedures buy no credit the agent did not
earn.

What makes them more than macros is that each reports **what actually changed, not what it
attempted**:

- `mine_forward` counts blocks broken *and blocks advanced*, and stops early with a diagnosis
  when it breaks blocks without gaining ground.
- `chop_tree` stops after two non-wood breaks and says you are on leaves.

A GUI sequence that lands is written down (the briefing, or `mine/` with `--own`), addressed
by slot number, so a recipe is solved once rather than every time.

### The GUI cursor is measured, never integrated

The cursor was originally dead-reckoned by summing camera deltas at 4.17 px per degree. Over
one long session it drifted 60 pixels — three slot widths — and every absolute address computed
from it missed. The error per move is small and the sum is unbounded, so the fix is not a
better constant: read the pointer out of **the frame the environment already sends every
tick**, and overwrite the sum.

The arrow sprite needs no template to match. Its outline sits below value 70 and its body above
235, while the GUI's greys occupy 139–204 — so a candidate position is scored by how many
outline pixels are dark and body pixels bright, whatever scene it floats over. Ore and
tree-trunk detectors follow the same closed-loop pattern.

`tools/zoom.py <frame.png> <x> <y> <w> <h> [out.png]` crops and magnifies any region of a
frame, so the model can adjudicate a detector flag itself when a full 640×360 view is too
coarse to answer the question. Camera compensation lives in `camera_contract.py`; if you move
the action space off `env`, `MCU_CAMERA_QUANTISED=1` puts it back.

See [What isolation actually means](#what-isolation-actually-means) and
[Choosing the settings that define an arm](#choosing-the-settings-that-define-an-arm) for the
run-level half of the same problem.

<!-- UPSTREAM README, hidden. This section is inherited from KWSMooBang/MCU-AgentBeats
     and is not about the agents in this fork. Kept verbatim rather than deleted so a
     merge from upstream still applies cleanly; unwrap this comment to read it.

## 🔬 Benchmark Extension

### Adding New Tasks

1. Create YAML file in appropriate category folder
2. Define init commands, task text, and reward config
3. Test with `run_task.py`

### Modifying Evaluation Logic

Main files to modify:
- `src/agent.py`: Core evaluation loop
- `src/util.py`: Task loading and video processing
- `MCU_benchmark/auto_eval/`: Video evaluation prompts

## 📚 References

- [AgentBeats Competition](https://rdi.berkeley.edu/agentx-agentbeats#custom-tracks)
- [A2A Protocol](https://a2a-protocol.org/)
- [MCU Benchmark](https://github.com/CraftJarvis/MCU)
- [MineStudio Framework](https://github.com/CraftJarvis/MineStudio)

-->

## 📄 License

MIT License

---

For questions or issues, please create an issue on GitHub or contact the maintainers.
