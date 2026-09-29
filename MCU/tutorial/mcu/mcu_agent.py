"""
MCU Agent - Purple agent that solves MCU benchmark tasks.

This is the agent being tested. It:
1. Receives task descriptions with available tools from the green agent
2. Decides which tool to call or how to respond
3. Returns responses in the expected JSON format wrapped in <json>...</json> tags
"""
import argparse
import sys
import os
import uvicorn
import logging
from dotenv import load_dotenv

load_dotenv()

import json
import base64
import cv2
import numpy as np
import torch

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from a2a.utils import new_agent_text_message
from loguru import logger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcu_agent")

from minestudio.models.steve_one import SteveOnePolicy
from model import InitPayload, ObservationPayload, AckPayload, ActionPayload, ErrorPayload


def prepare_agent_card(url: str) -> AgentCard:
    """Create the agent card for the MCU purple agent."""
    skill = AgentSkill(
        id="task_fulfillment",
        name="Task Fulfillment",
        description="Solves tasks for MCU benchmark evaluation",
        tags=["benchmark", "mcu"],
        examples=[],
    )
    return AgentCard(
        name="mcu_agent",
        description="Minecraft tasks solving agent for MCU benchmark evaluation",
        url=url,
        version="1.0.0",
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        capabilities=AgentCapabilities(),
        skills=[skill],
    )
    
    
class MCUAgentExecutor(AgentExecutor):
    """Executor for the MCU purple agent."""
    def __init__(self):
        self.model = SteveOnePolicy.from_pretrained("CraftJarvis/MineStudio_STEVE-1.official").to("cuda")
        self.model.eval()
        self.ctx_id_to_messages: dict[str, list[dict]] = {}
        

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        ctx_id = context.context_id
        user_input = context.get_user_input()
        
        try:
            payload = json.loads(user_input)
        except Exception as e:
            logger.error(f"Failed to parse user input as JSON: {e}")
            await event_queue.enqueue_event(
                new_agent_text_message(
                    json.dumps({
                        "type": "error",
                        "message": "Invalid input format. Please provide a valid JSON."
                    }),
                    context_id=ctx_id,
                )
            )
            return
        
        if context.context_id not in self.ctx_id_to_messages:
            self.ctx_id_to_messages[context.context_id] = [payload]
        
        type = payload.get("type")
        
        if type == "init":
            text = payload.get("text", "")
            self.condition = self.model.prepare_condition(
                {
                    'cond_scale': 4.0,
                    'text': text
                }
            )
            self.state_in = self.model.initial_state(1, self.condition)
            
            ack_payload = AckPayload(success=True, message="Initialization successful.")
            await event_queue.enqueue_event(
                new_agent_text_message(
                    ack_payload.model_dump_json(),
                    context_id=ctx_id,
                )
            )
            return 
        elif type == "obs":
            obs = payload.get("obs", None)
            if obs is None:
                logger.error("No observation provided in 'obs' message.")
                
                error_payload = ErrorPayload(message="No observation provided.")
                await event_queue.enqueue_event(
                    new_agent_text_message(
                        error_payload.model_dump_json(),
                        context_id=ctx_id,
                    )
                )
                return
            
            obs_img = self._decode_image(obs)
            obs = torch.tensor(obs_img, dtype=torch.uint8, device='cuda')
            if obs.dim() == 3:
                obs = obs.unsqueeze(0).unsqueeze(0) 
            elif obs.dim() == 4:
                obs = obs.unsqueeze(0)
                
            action, self.state_in = self.model.get_action(
                input={
                    'image': obs,
                    'condition': self.condition
                },
                state_in=self.state_in
            )
            
            action_payload = ActionPayload(
                buttons=action['buttons'].cpu().numpy().tolist(),
                camera=action['camera'].cpu().numpy().tolist()
            )
            await event_queue.enqueue_event(
                new_agent_text_message(
                    action_payload.model_dump_json(),
                    context_id=ctx_id,
                )
            )
            return 
        else: 
            logger.error(f"Unknown message type: {type}")
            
            error_payload = ErrorPayload(message=f"Unknown message type: {type}")
            await event_queue.enqueue_event(
                new_agent_text_message(
                    error_payload.model_dump_json(),
                    context_id=ctx_id,
                )
            )
            return

        
    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError
    
    
    def _decode_image(self, enc_image: str) -> np.ndarray:
        """Decode a base64-encoded image string to a numpy array."""
        bytes_image = base64.b64decode(enc_image)
        buffer = np.frombuffer(bytes_image, dtype=np.uint8)
        image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        if image is None: 
            raise ValueError("Image decoding failed.")
        
        return image 
        
        
        
def main():
    parser = argparse.ArgumentParser(description="Run the tau2 agent (purple agent).")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind the server")
    parser.add_argument("--port", type=int, default=9019, help="Port to bind the server")
    parser.add_argument("--card-url", type=str, help="External URL for the agent card")
    args = parser.parse_args()

    logger.info("Starting mcu agent...")
    card = prepare_agent_card(args.card_url or f"http://{args.host}:{args.port}/")

    request_handler = DefaultRequestHandler(
        agent_executor=MCUAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    app = A2AStarletteApplication(
        agent_card=card,
        http_handler=request_handler,
    )

    uvicorn.run(
        app.build(),
        host=args.host,
        port=args.port,
        timeout_keep_alive=300,
    )


if __name__ == "__main__":
    main()
