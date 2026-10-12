import sys, os
import json
import numpy as np
import base64
import cv2
import asyncio

from pathlib import Path
from datetime import datetime
from typing import Any
from pydantic import ValidationError

from a2a.server.tasks import TaskUpdater
from a2a.types import Message, TaskState, Part, TextPart, DataPart
from a2a.utils import get_message_text, new_agent_text_message

# `python src/server.py` puts `src/` on sys.path but not the project root, where
# `MCU_benchmark` (the milestone tracker) lives. MineStudio is the installed package
# (pyproject.toml, pinned in uv.lock).
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from minestudio.simulator import MinecraftSim
from minestudio.utils.vpt_lib.actions import Buttons
from minestudio.simulator.callbacks import RecordCallback, JudgeResetCallback, CommandsCallback, RewardsCallback, TaskCallback, FastResetCallback

from MCU_benchmark.utility.milestone_tracker import MilestoneTrackerCallback

from messenger import Messenger
from model import EvalRequest, InitPayload, ObservationPayload, AckPayload, ActionPayload
from util import (get_tasks, load_world_spec, load_portal_probe,
                  assess_video, process_video, evaluate_longterm_result)


class Agent:
    # Fill in: list of required participant roles, e.g. ["pro_debater", "con_debater"]
    required_roles: list[str] = ["agent"]
    # Fill in: list of required config keys, e.g. ["topic", "num_rounds"]
    required_config_keys: list[str] = ["task_category"]
    
    # Valid task categories (the folders under MCU_benchmark/task_configs/tasks): the
    # three tasks of the paper.
    valid_categories: set[str] = {
        "mine_diamond_from_scratch", "ender_dragon",
        # The nether-portal case study: the dragon chain's one purely geometric goal,
        # cut out of the chain with the blocks already in hand and nothing scarce, so
        # the only thing measured is whether the shape comes out right.
        "nether_portal",
    }
    
    # Task step limits
    DEFAULT_MAX_STEPS: int = 1200
    LONG_TASK_MAX_STEPS: int = 12000
    #: Tasks allowed past DEFAULT_MAX_STEPS. A task missing from here has its
    #: --max-steps silently clamped to 1200 (see _run).
    LONG_TASKS: set[str] = {"kill_ender_dragon", "mine_diamond_from_scratch", "nether_portal"}

    # How long a purple agent may take to answer one observation before the step is
    # filled with a noop. Reactive policies answer in milliseconds, but a planning
    # agent spends a whole model turn on the step where it re-plans, so this is
    # overridable per evaluation via config["step_timeout"].
    DEFAULT_STEP_TIMEOUT: float = 60.0
    
    # No class-level noop: the simulator runs in the `env` action space, whose no-op is
    # a full button dict rather than the `{buttons: [0], camera: [60]}` pair the `agent`
    # space uses, and only the live simulator can produce it. Every site calls
    # `env.noop_action()`.

    def __init__(self):
        self.messenger = Messenger()
        # Initialize other state here
        self.root_dir = Path(__file__).resolve().parents[1]
        # Load prompt template
        prompt_path = self.root_dir / "src" / "prompt.txt"
        with open(prompt_path, 'r', encoding='utf-8') as f:
            self.prompt_template = f.read()

    def validate_request(self, request: EvalRequest) -> tuple[bool, str]:
        missing_roles = set(self.required_roles) - set(request.participants.keys())
        if missing_roles:
            return False, f"Missing roles: {missing_roles}"

        missing_config_keys = set(self.required_config_keys) - set(request.config.keys())
        if missing_config_keys:
            return False, f"Missing config keys: {missing_config_keys}"

        # Validate task_category
        task_category = request.config.get("task_category")
        if task_category and task_category not in self.valid_categories:
            return False, f"Invalid task_category: '{task_category}'. Valid categories: {sorted(self.valid_categories)}"

        return True, "ok"
    
    def _calculate_task_score(self, reward_cfg, milestone_reward_cfg) -> float:
        task_score = 0.0
        
        # Use milestone_reward_cfg if available, otherwise use reward_cfg
        cfg = milestone_reward_cfg if milestone_reward_cfg else reward_cfg
        
        if cfg:
            for item in cfg:
                reward = item.get('reward', 0.0)
                max_times = item.get('max_reward_times', 1)
                task_score += reward * max_times
        
        return task_score

    async def run(self, message: Message, updater: TaskUpdater) -> None:
        """Implement your agent logic here.

        Args:
            message: The incoming message
            updater: Report progress (update_status) and results (add_artifact)

        Use self.messenger.talk_to_agent(message, url) to call other agents.
        """
        input_text = get_message_text(message)

        try:
            request: EvalRequest = EvalRequest.model_validate_json(input_text)
            ok, msg = self.validate_request(request)
            if not ok:
                await updater.reject(new_agent_text_message(msg))
                return
        except ValidationError as e:
            await updater.reject(new_agent_text_message(f"Invalid request: {e}"))
            return
        
        # Get the purple agent URL
        agent_url = str(request.participants["agent"])
        
        # Get config parameters
        task_category = request.config.get("task_category", "overall")
        max_steps = request.config.get("max_steps", None)
        step_timeout = float(request.config.get("step_timeout", self.DEFAULT_STEP_TIMEOUT))
        
        # Get tasks
        tasks = get_tasks(task_category)
        num_tasks = len(tasks)
        
        await updater.update_status(
            TaskState.working, 
            new_agent_text_message(f"Starting MCU evaluation with {num_tasks} tasks from {task_category}")
        )
        
        # Prepare output directory
        # The pid, not just the clock: a paired run puts two green agents behind two
        # ports and they receive their requests in the same second, so a second-resolution
        # name collides and both write `<task>/episode_1.mp4`, `milestone_tracking.json`
        # and `result.txt` to the same place. One arm's results silently overwrite the
        # other's, and the surviving file looks like a complete result for both. Observed
        # on the 2026-08-24 ender_dragon smoke. The pid also says which server log a
        # result directory belongs to.
        date_str = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
        output_dir = self.root_dir / "output" / date_str
        os.makedirs(output_dir, exist_ok=True)
        metrics: dict = {}
        
        try: 
            for task, commands, text, reward_cfg, milestone_reward_cfg in tasks:
                print(f"Running task: {task.replace('_', ' ')}")
                await updater.update_status(
                    TaskState.working, 
                    new_agent_text_message(f"Running task: {task.replace('_', ' ')}")
                )
                
                metrics[task] = {}
                # Determine max score for this task
                if task in self.LONG_TASKS:
                    max_score = 100.0
                else:
                    max_score = 10.0
                metrics[task]["max_score"] = max_score
                
                try:       
                    record_path = os.path.join(output_dir, task) 
                    sim_score = await self._run_single_task(
                        agent_url,
                        task, 
                        commands,
                        text,
                        reward_cfg,
                        milestone_reward_cfg,
                        max_steps,
                        record_path=record_path,
                        step_timeout=step_timeout,
                        task_category=task_category,
                    )
                    metrics[task]["sim_score"] = sim_score
                    
                    criteria_dir = self.root_dir / "MCU_benchmark" /"auto_eval" / "criteria_files"
                    rule_file_path = os.path.join(criteria_dir, f"{task}.txt")
                    video_path = os.path.join(record_path, "episode_1.mp4")
                    
                    # Initialize video evaluation results
                    video_eval_result = None
                    
                    # Validate video files
                    if not os.path.exists(video_path):
                        print(f"Warning: Video file not found for {task}")
                        metrics[task]["video_eval_scores"] = {}
                    else:
                        video_eval_result = await self._run_video_eval(
                            task=task,
                            rule_file_path=rule_file_path,
                            video_path=video_path
                        )
                        
                    if reward_cfg is None and milestone_reward_cfg is None:
                        score = 0.0
                        if video_eval_result is not None:
                            scores = video_eval_result.get('scores', {})
                            score = scores.get('Task Progress', 0.0)
                        score = (score / 10) * max_score
                    else:
                        # Calculate max score from reward configuration
                        task_score = self._calculate_task_score(reward_cfg, milestone_reward_cfg)
                        score = sim_score 
                        
                        if milestone_reward_cfg is not None:
                            # Long Horizon Task (kill_ender_dragon, mine_diamond_from_scratch)
                            score = evaluate_longterm_result(Path(record_path))
                            score = (score / task_score) * max_score
                        else: 
                            # Short Horizon Task with reward_cfg (origin MCU benchmark tasks)
                            score = (score / task_score) * max_score
                            
                            if score < max_score and video_eval_result is not None:
                                scores = video_eval_result.get('scores', {})
                                task_progress_score = scores.get('Task Progress', 0.0)
                                score = (score + task_progress_score) / 2
                                
                    metrics[task]["score"] = round(score, 2)  
                    
                    if video_eval_result is not None:
                        scores = video_eval_result.get('scores', {})
                        metrics[task]["action_control"] = scores.get('Action Control', 'N/A')
                        metrics[task]["error_recognition_and_correction"] = scores.get("Error Recognition and Correction", 'N/A')
                        metrics[task]["creative_attempts"] = scores.get("Creative Attempts", 'N/A')
                        metrics[task]["task_completion_efficiency"] = scores.get("Task Completion Efficiency", 'N/A')
                        metrics[task]["material_selection_and_usage"] = scores.get("Material Selection and Usage", 'N/A')
                        

                    if metrics[task].get("score") is not None:
                        result_msg = f"""Task {task}
- Max Score: {max_score}
- Score: {metrics[task]['score']:.2f}
- Action Control: {metrics[task].get("action_control", "N/A")}
- Error Recognition: {metrics[task].get("error_recognition_and_correction", "N/A")}
- Creative Attempts: {metrics[task].get("creative_attempts", "N/A")}
- Task Efficiency: {metrics[task].get("task_completion_efficiency", "N/A")}
- Material Usage: {metrics[task].get("material_selection_and_usage", "N/A")} """
                        print(result_msg)
                        await updater.update_status(
                            TaskState.working,
                            new_agent_text_message(result_msg)
                        )
                except Exception as e:
                    print(f"Error running task {task}: {e}")
                    metrics[task]["score"] = 0.0
                    metrics[task]["action_control"] = 'N/A'
                    metrics[task]["error_recognition_and_correction"] = 'N/A'
                    metrics[task]["creative_attempts"] = 'N/A'
                    metrics[task]["task_completion_efficiency"] = 'N/A'
                    metrics[task]["material_selection_and_usage"] = 'N/A'
                    metrics[task]["error"] = str(e)
                    metrics[task]["error_type"] = type(e).__name__
        
            # Calculate metrics
            score_list = [m["score"] for m in metrics.values() if m.get("score") is not None]
            total_score = sum(score_list)
            total_max_score = sum(m.get("max_score", 10.0) for m in metrics.values())
            
            # Calculate average scores for video evaluation criteria
            criteria_scores = {
                "action_control": [],
                "error_recognition_and_correction": [],
                "creative_attempts": [],
                "task_completion_efficiency": [],
                "material_selection_and_usage": []
            }
            
            for m in metrics.values():
                for criterion in criteria_scores.keys():
                    value = m.get(criterion, 'N/A')
                    if value != 'N/A' and isinstance(value, (int, float)):
                        criteria_scores[criterion].append(value)
            
            avg_criteria = {
                criterion: round(sum(scores) / len(scores), 2) if scores else "N/A"
                for criterion, scores in criteria_scores.items()
            }
            
            result = {
                "task_category": task_category,
                "num_tasks": num_tasks,
                "total_max_score": total_max_score,
                "total_score": total_score,
                "avg_action_control": avg_criteria['action_control'],
                "avg_error_recognition_and_correction": avg_criteria['error_recognition_and_correction'],
                "avg_creative_attempts": avg_criteria['creative_attempts'],
                "avg_task_completion_efficiency": avg_criteria['task_completion_efficiency'],
                "avg_material_selection_and_usage": avg_criteria['material_selection_and_usage'],
                "task_metrics": metrics
            }
            
            task_result_str = "\n".join(
                f"""    Task '{task_name}':
        - max_score: {m.get('max_score', 10.0)}
        - score: {m.get('score', 0.0):.2f} / {m.get('max_score', 10.0)}
        - sim_score: {m.get('sim_score', 0.0):.2f} / {m.get('max_score', 10.0)}
        - action_control: {m.get('action_control', 'N/A')}
        - error_recognition: {m.get('error_recognition_and_correction', 'N/A')}
        - creative_attempts: {m.get('creative_attempts', 'N/A')}
        - task_efficiency: {m.get('task_completion_efficiency', 'N/A')}
        - material_usage: {m.get('material_selection_and_usage', 'N/A')}"""
                for task_name, m in metrics.items() 
            )
            
            summary = f"""MCU Evaluation Result
- Categories: {task_category}
- Number of Tasks: {num_tasks}
- Total Score: {total_score:.2f} / {total_max_score}
- Action Control: {avg_criteria['action_control']}
- Error Recognition and Correction: {avg_criteria['error_recognition_and_correction']}
- Creative Attempts: {avg_criteria['creative_attempts']}
- Task Completion Efficiency: {avg_criteria['task_completion_efficiency']}
- Material Selection and Usage: {avg_criteria['material_selection_and_usage']}

- Task Results:
{task_result_str}"""
    
            # Save results to txt file
            result_file = os.path.join(output_dir, "result.txt")
            with open(result_file, 'w', encoding='utf-8') as f:
                f.write(summary)

            await updater.add_artifact(
                parts=[
                    Part(root=TextPart(text=summary)),
                    Part(root=DataPart(data=result))
                ],
                name="Result"
            )
            print("========== Evaluation completed. ==========")
            print(summary)
            
        except Exception as e:
            error_msg = f"Critical error during evaluation: {type(e).__name__} - {e}"
            print(error_msg)
            await updater.reject(new_agent_text_message(error_msg))
            raise
        
        finally:
            self.messenger.reset()
    
    #: Keys forwarded verbatim from the `info` MineStudio returns from `env.step`.
    #: An allowlist held to HUMAN PARITY: everything here has a direct on-screen
    #: equivalent for a human player -- coordinates/pitch/yaw on the F3 debug screen
    #: (`player_pos`, `location_stats`), the inventory and held item in the GUI/HUD,
    #: health and food on the HUD, and the cumulative statistics on the pause menu's
    #: Statistics screen. Deliberately NOT here: `mobs` (an off-screen radar no player
    #: has), the live per-milestone completion bits (the scoring callback's private
    #: verdict) and `milestone_spec` (the scoring config itself) -- a participant can
    #: read the public task configs, so the checklist is agent-side knowledge
    #: (`task_milestones.py`), and completion is something an agent derives from the
    #: statistics rather than is told.
    INFO_PASSTHROUGH: tuple[str, ...] = (
        "player_pos", "location_stats", "inventory", "equipped_items",
        "isGuiOpen", "health", "food_level",
        # The cumulative event statistics. An agent that keeps its own milestone ledger
        # diffs these; they are also what RewardsCallback scores on, so a purple agent can
        # reach the same verdict by the same route rather than trusting ours.
        "mine_block", "craft_item", "pickup", "kill_entity", "break_item",
        "use_item", "damage_dealt",
    )

    @classmethod
    def _jsonable_info(cls, value):
        """numpy scalars and 0-d arrays do not survive `model_dump_json`."""
        if isinstance(value, dict):
            return {str(k): cls._jsonable_info(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._jsonable_info(v) for v in value]
        if isinstance(value, np.ndarray):
            return cls._jsonable_info(value.item() if value.ndim == 0 else value.tolist())
        if isinstance(value, np.generic):
            return value.item()
        return value

    @classmethod
    def _observation_info(cls, info: dict) -> dict:
        """The non-visual slice of simulator state handed to the purple agent.

        Forwarded in the simulator's own shapes rather than reshaped into any one agent's
        preferred rendering -- `inventory` stays slot-keyed, `location_stats` stays the
        stringified stat block -- so an agent brought in with its own readers keeps working
        unchanged. Reshaping is the purple agent's job; this is plumbing.

        It matters because without it a purely visual agent has to read its own item counts
        off a JPEG, and 9 of the 10 `mine_diamond_from_scratch` milestones are gated behind
        the inventory GUI, where that is the difference between a closed loop and an open
        one. The allowlist is the whole policy: nothing scoring-side (milestone bits,
        milestone spec) is published here any more.
        """
        return {key: cls._jsonable_info(info[key])
                for key in cls.INFO_PASSTHROUGH if key in info}

    async def _run_single_task(
        self,
        agent_url: str,
        task: str,
        commands: list[str] | None,
        text: str,
        reward_cfg: list[dict] | None,
        milestone_reward_cfg: list[dict] | None,
        max_steps: int | None,
        record_path: str,
        step_timeout: float = DEFAULT_STEP_TIMEOUT,
        task_category: str | None = None,
    ) -> float:
        """ 
        Run a single MCU task and return the reward.
        """
        # The world seed and the portal probe are read from the task category's config
        # directory, which is not always named like the task (ender_dragon holds
        # kill_ender_dragon.yaml).
        category = task_category or task
        
        # Determine max_steps based on task and input
        if max_steps is None:
            max_steps = self.LONG_TASK_MAX_STEPS if task in self.LONG_TASKS else self.DEFAULT_MAX_STEPS
        elif max_steps > self.DEFAULT_MAX_STEPS and task not in self.LONG_TASKS:
            max_steps = self.DEFAULT_MAX_STEPS
         
        world_spec = load_world_spec(category)
        if world_spec:
            print(f"[green] {task}: world pinned {world_spec}", flush=True)

        # Set up the MinecraftSim environment with appropriate callbacks
        task_dict = {
            'name': task.replace('_', ' '),
            'text': text
        }
        
        callbacks = [
            TaskCallback([task_dict]),  
            FastResetCallback(
                biomes=['plains', 'forest'],
                random_tp_range=1000,
            ),
            RecordCallback(
                record_path=record_path,
                fps=20,
                frame_type='pov',
            )
        ]
        
        if reward_cfg:
            callbacks.insert(1, RewardsCallback(reward_cfg=reward_cfg))
            
        if milestone_reward_cfg:
            callbacks.insert(1, MilestoneTrackerCallback(
                reward_cfg=milestone_reward_cfg,
                output_path=record_path,
                task_name=task
            ))
            
        if commands:
            callbacks.insert(0, CommandsCallback(commands))

        # Host-side geometry ground truth for the nether-portal case study. Absent from
        # every other task, so no callback is added there. It asks the engine for the
        # blocks around the player and writes portal_report.json; nothing it learns is
        # published into `info`, and `voxels` is not in INFO_PASSTHROUGH, so the
        # privileged view stops at the green process.
        probe = load_portal_probe(category)
        if probe:
            from mcu_worldmodel.portal_probe import PortalProbeCallback
            callbacks.append(PortalProbeCallback(output_dir=record_path, **probe))
            print(f"[green] {task}: portal probe {probe}", flush=True)
            
        env = MinecraftSim(
            # `env`, not MinecraftSim's `agent` default. The default routes every action
            # through `env_action_to_agent_action`, whose camera leg is VPT's mu-law
            # binning: 11 reachable values per axis. That is lossless for a policy whose
            # head emits those bins, and lossy for anything that writes degrees -- one
            # 18px GUI slot is 4.32 degrees and arrives as 3.215, a quarter short, while
            # any correction under ~0.31 degrees is quantised to zero. Both LLM arms
            # write degrees. In `env` the camera is Box(-180, 180) and `step` passes the
            # dict straight through; the conversion moves to the reactive-policy path,
            # where indices map back to their own bin values exactly.
            action_type="env",
            obs_size=(640, 360),
            callbacks=callbacks,
            # Empty for every task that does not pin them, which leaves MinecraftSim's
            # own defaults in place.
            **world_spec,
        )
        
        def encode_image(image: np.ndarray, fmt: str = '.jpeg') -> str:
            success, buffer = cv2.imencode(fmt, image)
            if not success:
                raise ValueError("Image encoding failed")

            enc_image = base64.b64encode(buffer).decode("utf-8")
            return enc_image
        
        sim_score = 0.0
        try:            
            # Send initial payload to purple agent containing prompt and task description
            init_payload = InitPayload(
                prompt=self.prompt_template, 
                text=text
            )
            init_response = await asyncio.wait_for(
                self.messenger.talk_to_agent(
                    message=init_payload.model_dump_json(),
                    url=agent_url,
                    new_conversation=True,
                ),
                timeout=60.0
            )
            ack_payload = AckPayload.model_validate_json(init_response)
            assert ack_payload.success, f"Agent initialization failed: {ack_payload.message}"
            
            obs, info = env.reset()
            # MCU_STOP_AFTER_COMPLETE=N ends a milestone task N steps after its last
            # milestone was banked, instead of playing out the budget. Unset (every
            # recorded run), the loop is what it was. N > 0 leaves the purple agent
            # its periodic report after the last milestone.
            stop_after = os.environ.get("MCU_STOP_AFTER_COMPLETE")
            stop_after = int(stop_after) if stop_after else None
            tracker = next((c for c in callbacks if isinstance(c, MilestoneTrackerCallback)), None)
            complete_at = None
            for step in range(max_steps):
                # Send observation payload to purple agent
                obs_img = obs['image']
                obs_info = self._observation_info(info)
                if step == 0:
                    # Once per task: says what the observation extension actually
                    # carries. A missing key here is a callback wiring problem, and
                    # without this line it is only visible as an agent that behaves
                    # as if it were blind to its own position.
                    print(f"obs info for {task}: keys={sorted(obs_info)} "
                          f"obs_keys={sorted(obs)}")
                obs_payload = ObservationPayload(
                    step=step,
                    obs=encode_image(obs_img),
                    info=obs_info,
                )

                # Receive action from purple agent
                try:
                    response = await asyncio.wait_for(
                        self.messenger.talk_to_agent(
                            message=obs_payload.model_dump_json(),
                            url=agent_url,
                            new_conversation=False,
                            # Strictly longer than `step_timeout`, so the deadline that
                            # fires is always the asyncio one. httpx's ReadTimeout is not
                            # an asyncio.TimeoutError, so it escapes the handler below and
                            # ends the episode instead of costing one noop step.
                            timeout=int(step_timeout) + 60,
                        ),
                        timeout=step_timeout
                    )
                    action = self._parse_action_response(env, response)
                except asyncio.TimeoutError:
                    print(f"Agent timeout at step {step}, using noop action")
                    action = env.noop_action()
                    
                # Take a step in the environment with the received action
                obs, reward, terminated, truncated, info = env.step(action)
                sim_score += reward
                
                if terminated:
                    break
                if stop_after is not None and tracker is not None:
                    if complete_at is None and len(tracker.milestone_log) >= len(milestone_reward_cfg):
                        complete_at = step
                        print(f"[green] {task}: every milestone banked at step {step}; "
                              f"stopping {stop_after} steps on", flush=True)
                    if complete_at is not None and step >= complete_at + stop_after:
                        break
                
        except Exception as e:
            print(f"Error during task '{task}': {type(e).__name__} - {e}")
        finally:
            try:
                env.close()
            except Exception as e:
                print(f"Error closing environment: {type(e).__name__} - {e}")

        return sim_score
    
    async def _run_video_eval(self, task: str, rule_file_path: str, video_path: str) -> dict | None:
        """Run video evaluation and return detailed results.
        
        Returns:
            dict: {
                'scores': dict
                'criterias': list
            }
        """
        try:
            video_frames = process_video(video_path)
            result = assess_video(task, rule_file_path, video_frames, video_path)
            return result
        except (FileNotFoundError, ValueError, RuntimeError) as e:
            print(f"Video evaluation failed for {task}: {type(e).__name__} - {e}")
            return None
        except Exception as e:
            # Catch OpenAI API errors, network errors, etc.
            print(f"Unexpected error during video evaluation for {task}: {type(e).__name__} - {e}")
            return None
    
    def _parse_agent_action_type(self, env: MinecraftSim, buttons: list, camera: list) -> dict:
        """Parse agent action type format.
        
        Handles two agent formats:
        1. Compact: buttons=[123], camera=[60] (MultiDiscrete)
        2. Expanded: buttons=[0,0,0,1,...] (len=20), camera=[0.0, 90.0] (len=2)
        """
        if len(buttons) == 1 and len(camera) == 1:
            # Format 1: the policy head's own indices. The simulator runs in `env`, so
            # they are mapped back here instead of inside `step`. `to_factored` wants a
            # trailing axis of 1 and squeezes it, and `policy2env` returns a batch that
            # is unwrapped again. Lossless: an index resolves to the exact bin value the
            # `agent` space would have used.
            packed = {"buttons": np.asarray(buttons, dtype=np.int64).reshape(1, 1),
                      "camera": np.asarray(camera, dtype=np.int64).reshape(1, 1)}
            return self._unbatch(env, env.agent_action_to_env_action(packed))
        elif len(buttons) == 20 and len(camera) == 2:
            # Format 2: already one entry per button, already degrees. That is the env
            # space spelled differently, so it needs naming rather than converting.
            action_dict = {btn: int(buttons[i]) for i, btn in enumerate(Buttons.ALL)}
            action_dict['camera'] = camera
            return self._parse_env_action_type(env, action_dict)
        else:
            raise ValueError(f"Invalid button/camera dimensions: buttons={len(buttons)}, camera={len(camera)}")

    @staticmethod
    def _unbatch(env: MinecraftSim, action: dict) -> dict:
        """Drop the leading batch axis MineStudio's converters add, onto a full noop so
        every key the env action space requires is present."""
        out = env.noop_action()
        for key, value in action.items():
            if key not in out:
                continue
            arr = np.asarray(value)
            out[key] = arr[0] if arr.ndim > np.asarray(out[key]).ndim else arr
        return out
    
    def _parse_env_action_type(self, env: MinecraftSim, action_dict: dict) -> dict:
        """Parse env action type format: the simulator's own space, so no conversion.

        Built on `env.noop_action()` rather than on the incoming dict, because the env
        action space is a `Dict` and `step` needs every key present -- an agent that
        sends only `{"attack": 1}` would otherwise fail on the first missing button.
        Unknown keys are dropped rather than passed on: they cannot reach the simulator
        and a silent typo in a purple agent's action name should not look like a button
        that simply did nothing.
        """
        action = env.noop_action()
        for key, value in (action_dict or {}).items():
            if key not in action:
                continue
            if key == 'camera':
                action[key] = np.asarray(value, dtype=np.float32).reshape(2)
            else:
                action[key] = np.asarray(value, dtype=np.asarray(action[key]).dtype).reshape(
                    np.asarray(action[key]).shape)
        return action
    
    def _fallback_parse_action(self, env: MinecraftSim, response: str) -> dict:
        """Fallback parser for legacy/malformed action responses.

        Takes `env` because the simulator runs in the `env` action space now: a bare
        `{"buttons": .., "camera": ..}` pair is the reactive-policy encoding and has to
        be mapped, and anything unparseable falls back to the env-space noop rather than
        to the agent-space one, which `step` would no longer understand.
        """
        try:
            data = json.loads(response)
            buttons = data.get("buttons")
            camera = data.get("camera")
            if (buttons is not None and len(buttons) == 1
                    and camera is not None and len(camera) == 1):
                return self._parse_agent_action_type(env, buttons, camera)
            print("Fallback parse found no usable buttons/camera pair; using noop")
            return env.noop_action()
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            print(f"Failed to parse agent response as JSON: {type(e).__name__} - {e}")
            return env.noop_action()
    
    def _parse_action_response(self, env: MinecraftSim, response: str) -> dict:
        """
        Parse the purple agent's response string and convert it into an action dict.
        
        Supports three formats:
        1. Compact agent: {"type": "action", "action_type": "agent", "buttons": [123], "camera": [60]}
        2. Expanded agent: {"type": "action", "action_type": "agent", "buttons": [0,0,0,1,...], "camera": [0.0, 90.0]}
        3. Env format: {"type": "action", "action_type": "env", "action": {"forward": 1, "camera": [...], ...}}
        
        All formats are converted to compact agent format for env.step().
        """
        if not response:
            return env.noop_action()
        
        try:
            action_payload = ActionPayload.model_validate_json(response)
            
            if action_payload.action_type == "agent":
                return self._parse_agent_action_type(env, action_payload.buttons, action_payload.camera)
            elif action_payload.action_type == "env":
                return self._parse_env_action_type(env, action_payload.action)
            else:
                raise ValueError(f"Unknown action_type: {action_payload.action_type}")
            
        except (ValidationError, ValueError, KeyError, json.JSONDecodeError) as e:
            print(f"Failed to parse as ActionPayload ({type(e).__name__}), trying fallback parsing")
            return self._fallback_parse_action(env, response)