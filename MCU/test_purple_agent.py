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

from minestudio.models.steve_one import SteveOnePolicy
from minestudio.models.vpt import VPTPolicy
from models import InitPayload, ObservationPayload, AckPayload, ActionPayload


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
    def __init__(self, model_name: str = "steve1"):
        self.model_name = model_name
        if model_name == "steve1":
            self.model = SteveOnePolicy.from_pretrained("CraftJarvis/MineStudio_STEVE-1.official").to("cuda")
        elif model_name == "vpt":
            # Placeholder for VPT model initialization
            self.model = VPTPolicy.from_pretrained("CraftJarvis/MineStudio_VPT.rl_from_early_game_2x").to("cuda")
        else:
            raise ValueError(f"Unsupported model: {model_name}")
        if self.model is not None:
            self.model.eval()
        self.ctx_id_to_messages: dict[str, list[dict]] = {}
        

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        ctx_id = context.context_id
        user_input = context.get_user_input()
        
        try:
            payload = json.loads(user_input)
        except Exception as e:
            print(f"Failed to parse user input as JSON: {e}")
            ack_payload = AckPayload(success=False, message="Invalid input format. Please provide a valid JSON.")
            await event_queue.enqueue_event(
                new_agent_text_message(
                    ack_payload.model_dump_json(),
                    context_id=ctx_id,
                )
            )
            return
        
        if context.context_id not in self.ctx_id_to_messages:
            self.ctx_id_to_messages[context.context_id] = [payload]
        
        type = payload.get("type")
        
        if type == "init":
            if self.model_name == "vpt":
                self.state_in = None
            else:
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
                ack_payload = AckPayload(success=False, message="No observation provided.")
                await event_queue.enqueue_event(
                    new_agent_text_message(
                        ack_payload.model_dump_json(),
                        context_id=ctx_id,
                    )
                )
                return
            
            img = self._decode_image(obs)
            # The green agent streams observations at the recording resolution
            # (640x360), but STEVE-1/VPT expect the 128x128 frames they were
            # trained on, so downscale before inference.
            img = cv2.resize(img, (128, 128), interpolation=cv2.INTER_LINEAR)

            if self.model_name == "vpt":
                img = np.array(img, dtype=np.uint8)
                action, self.state_in = self.model.get_action(
                    input={
                        'image': img,
                    },
                    state_in=self.state_in,
                    input_shape='*'
                )
            else: 
                img = torch.tensor(img, dtype=torch.uint8, device='cuda')
                if img.ndim == 3:
                    img = img[None, None, ...] 
                elif img.ndim == 4:
                    img = img[None, ...]
                    
                action, self.state_in = self.model.get_action(
                    input={
                        'image': img,
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
            print(f"Unknown message type received: {type}")
            ack_payload = AckPayload(success=False, message=f"Unknown message type: {type}")
            await event_queue.enqueue_event(
                new_agent_text_message(
                    ack_payload.model_dump_json(),
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
    parser.add_argument("--model", type=str, default="steve1", choices=["steve1", "vpt"], help="Model to use: steve1 or vpt (default: steve1)")
    args = parser.parse_args()

    print("Starting mcu purple agent...")
    card = prepare_agent_card(args.card_url or f"http://{args.host}:{args.port}/")

    request_handler = DefaultRequestHandler(
        agent_executor=MCUAgentExecutor(model_name=args.model),
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
