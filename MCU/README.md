> **This directory in the MFM release.** It is MCU-AgentBeats (the benchmark, below) with
> the Minecraft chassis of the paper's four arms added: `mcu_worldmodel/`,
> `worldmodel_purple_agent.py`, `scripts/`, `camera_contract.py`, `task_milestones.py`,
> the task `MCU_benchmark/task_configs/tasks/nether_portal/`, and the world seed
> (`world_seed` in a task config, `MCU_WORLD_SEED`) in `src/util.py` and `src/agent.py`.
> Start with [`mcu_worldmodel/README.md`](mcu_worldmodel/README.md); one life of one arm
> is `scripts/run-arm.sh`; installing the simulator is
> [`mcu_worldmodel/SETUP.md`](mcu_worldmodel/SETUP.md).

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

## 📄 License

MIT License

---

For questions or issues, please create an issue on GitHub or contact the maintainers.
