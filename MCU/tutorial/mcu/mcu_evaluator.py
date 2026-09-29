"""
MCU Evaluator - Green agent that evaluates MCU benchmark on purple agents.

This agent:
1. Sets up MCU simulation environment
2. Send task prompts to the purple agent
3. Parses the purple agent responses
4. Steps through the simulation environment and collects metrics
"""

import os
import argparse
import uvicorn
import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

import re
import json
import numpy as np
import base64
import cv2 
import torch
from pathlib import Path

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    DataPart,
    Part,
    TaskState,
    TextPart,
)
from a2a.utils import new_agent_text_message

from agentbeats.green_executor import GreenAgent, GreenExecutor
from agentbeats.models import EvalRequest, EvalResult
from agentbeats.tool_provider import ToolProvider

from minestudio.simulator import MinecraftSim
from minestudio.simulator.callbacks import CommandsCallback, RecordCallback, SpeedTestCallback, SummonMobsCallback, MaskActionsCallback, RewardsCallback, JudgeResetCallback, FastResetCallback

from model import InitPayload, ObservationPayload, AckPayload, ActionPayload
from util import get_tasks, assess_video, process_video

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcu_evaluator")


def create_agent_card(name: str, url: str) -> AgentCard:
    """Create the agent card for the MCU evaluator agent."""
    skill = AgentSkill(
        id="mcu_evaluation",
        name="MCU Evaluation",
        description="Evaluates MCU benchmark tasks",
        tags=["benchmark", "mcu", "evaluation"],
        examples=[],
    )
    return AgentCard(
        name=name,
        description="MCU Evaluator Agent",
        url=url,
        version="1.0.0",
        default_input_modes=["application/json"],
        default_output_modes=["application/json"],
        capabilities=AgentCapabilities(),
        skills=[skill],
    )
    

class MCUEvaluator(GreenAgent):
    def __init__(self):
        self._required_roles = ["agent"]
        self._required_config_keys = ["difficulty"]
        self._tool_provider = ToolProvider()
        
        self.root_dir = Path(__file__).resolve().parents[2]
        
    def validate_request(self, request: EvalRequest) -> tuple[bool, str]:
        missing_roles = set(self._required_roles) - set(request.participants.keys())
        if missing_roles:
            return False, f"Missing roles: {missing_roles}"

        missing_config_keys = set(self._required_config_keys) - set(request.config.keys())
        if missing_config_keys:
            return False, f"Missing config keys: {missing_config_keys}"

        # Validate difficulty
        difficulty = request.config.get("difficulty")
        if difficulty not in ['simple', 'hard']:
            return False, f"Invalid difficulty: {difficulty}. Must be 'simple' or 'hard'"

        return True, "ok"
    
    async def run_eval(self, req: EvalRequest, updater: TaskUpdater) -> None:
        logger.info(f"   Starting MCU evaluation: {req}")
        start_time = time.time()
        
        difficulty = req.config["difficulty"]
        if difficulty not in ['simple', 'hard']:
            print("Invalid difficulty level. Please choose 'simple' or 'hard'.")
            exit()
        task_list = req.config.get("task_list", None)
        num_tasks = req.config.get("num_tasks", None)
        max_steps = req.config.get("max_steps", 900)
        
        # Get the purple agent URL
        agent_url = str(req.participants["agent"])
        
        # Get task
        tasks = get_tasks(difficulty, task_list, num_tasks)
        logger.info(f"Running {len(tasks)} {difficulty} tasks")
        
        await updater.update_status(
            TaskState.working,
            new_agent_text_message(f"Starting MCU evaluation with {len(tasks)} {difficulty} tasks.")
        )
        
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        record_dir = f"./record/{difficulty}/{date_str}"
        os.makedirs(record_dir, exist_ok=True)
        metrics: dict = {}

        try:
            for (task, commands, text) in tasks:
                logger.info(f"Running task '{task}'...")
                await updater.update_status(
                    TaskState.working,
                    new_agent_text_message(f"Running task '{task}'...")
                )
                
                metrics[task] = {}
                
                try:
                    reward = await self._run_single_task(
                        agent_url=agent_url,
                        commands=commands,
                        text=text,
                        max_steps=max_steps,
                        record_path=os.path.join(record_dir, task.replace(' ', '_'))
                    )
                    metrics[task]["reward"] = reward
                    
                    criteria_dir = self.root_dir / "MCU_benchmark" / "auto_eval" / "criteria_files"
                    rule_file_path = os.path.join(criteria_dir, f"{task.replace(' ', '_')}.txt")
                    video_path = os.path.join(record_dir, f"{task.replace(' ', '_')}", "episode_1.mp4")
                    
                    video_score = await self._run_video_eval(
                        task=task,
                        rule_file_path=rule_file_path,
                        video_path=video_path
                    )
                    metrics[task]["video_score"] = video_score
                    
                    logger.info(f"Task '{task}' ended with reward: {reward}")
                except Exception as e:
                    logger.error(f"Task '{task}' failed: {e}")
                    metrics[task]["reward"] = None
                    metrics[task]["video_score"] = None
                
            task_rewards = [m["reward"] for m in metrics.values() if m.get("reward") is not None]
            total_reward = sum(task_rewards)
            num_completed = len(task_rewards)
            pass_rate = (total_reward / num_completed * 100) if num_completed > 0 else 0.0
            
            result = {
                "difficulty": difficulty,
                "score": total_reward,
                "pass_rate": pass_rate,
                "num_tasks": len(metrics),
                "num_completed": num_completed,
                "task_metrics": {task: m["reward"] for task, m in metrics.items()},
            }
            
            result["video_scores"] = {task: m.get("video_score") for task, m in metrics.items()}
            
            task_result_str = "\n".join(
                f"Task '{task_name}': {'✓' if m['reward'] == 1.0 else '✗'} ({m['reward']})"
                for task_name, m in metrics.items()
            )
            
            summary = f"""MCU Evaluation Result
    Difficulty: {difficulty}
    Tasks: {num_completed}
    Pass Rate: {pass_rate:.2f}% ({int(total_reward)}/{num_completed})

    Task Results:
    {task_result_str}"""

            await updater.add_artifact(
                parts=[
                    Part(root=TextPart(text=summary)),
                    Part(root=DataPart(data=result))
                ],
                name="Result"
            )

            # Save results to txt file
            result_file = os.path.join(record_dir, "result.txt")
            with open(result_file, 'w', encoding='utf-8') as f:
                f.write(summary)
            logger.info(f"Results saved to {result_file}")

            await updater.add_artifact(
                parts=[
                    Part(root=TextPart(text=summary)),
                    Part(root=DataPart(data=result))
                ],
                name="Result"
            )
            
        finally:
            self._tool_provider.reset()
        
        
    async def _run_single_task(
        self,
        agent_url: str,
        commands: list[str],
        text: str,
        max_steps: int,
        record_path: str
    ):
        """Run a single MCU task and return the reward."""
        env = MinecraftSim(
            obs_size=(128, 128),
            callbacks=[
                CommandsCallback(commands),
                JudgeResetCallback(max_steps),
                RecordCallback(record_path=record_path, fps=30, frame_type="pov"),
            ]
        )
        
        def encode_image(image: np.ndarray, fmt: str = '.jpeg') -> str:
            success, buffer = cv2.imencode(fmt, image)
            if not success:
                raise ValueError("Image encoding failed")

            enc_image = base64.b64encode(buffer).decode("utf-8")
            return enc_image

        total_reward = 0.0
        terminated = False
        
        try:
            init_payload = InitPayload(text=text)
            res = await self._tool_provider.talk_to_agent(
                message=init_payload.model_dump_json(),
                url=agent_url,
                new_conversation=True,
            )
            ack_payload = AckPayload.model_validate_json(res)
            logger.info(f"Sent init message to agent, received response: {ack_payload}")
            
            obs, info = env.reset()

            for step in range(max_steps):
                obs_img = obs['image']
            
                obs_payload = ObservationPayload(
                    step=step,
                    obs=encode_image(obs_img)
                )
                res = await self._tool_provider.talk_to_agent(
                    message=obs_payload.model_dump_json(),
                    url=agent_url,
                    new_conversation=False,
                )
                
                action = self._parse_agent_response(res)
                obs, reward, terminated, truncated, info = env.step(action)
                total_reward += reward
                
                if terminated:
                    break
        finally:
            env.close()

        return total_reward
    
    async def _run_video_eval(self, task: str, rule_file_path: str, video_path: str) -> dict[str, Any]:
        try:
            video_frames = process_video(video_path)
            result = assess_video(task, rule_file_path, video_frames, video_path)
            return result
        except Exception as e:
            print(f"Video evaluation failed for {task}: {e}")
            return {"error": str(e)}

    def _parse_agent_response(self, response: str):
        """
        Parse the purple agent's response string and convert it into an action dict acceptable by `env.step(action)`.
        """

        if not response:
            return {
                "buttons": np.array([0]),
                "camera": np.array([60]),
            }

        try:
            action_payload = ActionPayload.model_validate_json(response)
            buttons = np.array(action_payload.buttons, dtype=np.int32)
            camera = np.array(action_payload.camera, dtype=np.int32)
            return {"buttons": buttons, "camera": camera}
        except Exception as e:
            print(f"Failed to parse agent response as ActionPayload: {e}")
            
            try:
                data = json.loads(response)
                buttons = data.get("buttons")
                camera = data.get("camera")
                
                buttons = np.array(buttons, dtype=np.int32) if buttons is not None else np.array([0])
                camera = np.array(camera, dtype=np.int32) if camera is not None else np.array([60])
                return {"buttons": buttons, "camera": camera}
            except Exception as e2:
                print(f"Failed to parse agent response as JSON: {e2}")
                return {
                    "buttons": np.array([0]),
                    "camera": np.array([60]),
                }
                
    
async def main():
    parser = argparse.ArgumentParser(description="Run the A2A MCU Evaluate")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind the server")
    parser.add_argument("--port", type=int, default=9019, help="Port to bind the server")
    parser.add_argument("--card-url", type=str, help="External URL to provide in the agent card")
    args = parser.parse_args()

    logger.info("Starting MCU Evaluator agent...")
    agent_url = args.card_url or f"http://{args.host}:{args.port}/"

    agent = MCUEvaluator()
    executor = GreenExecutor(agent)
    agent_card = create_agent_card("MCUEvaluator", agent_url)
    
    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
    )
    
    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )
    
    uvicorn_config = uvicorn.Config(server.build(), host=args.host, port=args.port)
    uvicorn_server = uvicorn.Server(uvicorn_config)
    await uvicorn_server.serve()

if __name__ == '__main__':
    asyncio.run(main())
