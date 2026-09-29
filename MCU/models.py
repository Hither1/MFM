from typing import Any, Literal, Optional, Dict
from pydantic import BaseModel, HttpUrl, Field, model_validator

class EvalRequest(BaseModel):
    participants: dict[str, HttpUrl] # role-endpoint mapping
    config: dict[str, Any]

class EvalResult(BaseModel):
    winner: str # role of winner
    detail: dict[str, Any]

# Protocols between Green and Purple agents
# From Green Agent to Purple Agent
class InitPayload(BaseModel):
    """Initial task description sent to purple agent."""
    type: Literal["init"] = "init"
    text: str = Field(..., description="Task description")

class ObservationPayload(BaseModel):
    """Observation sent to purple agent at each step."""
    type: Literal["obs"] = "obs"
    step: int = Field(..., ge=0, description="Current step number")
    obs: str = Field(..., description="Base64 encoded image")


# From Purple Agent to Green Agent
class AckPayload(BaseModel):
    """Acknowledgment from purple agent."""
    type: Literal["ack"] = "ack"
    success: bool = False
    message: str = ""

class ActionPayload(BaseModel):
    """Action response from purple agent.
    
    Supports three formats:
    1. Compact agent format: {"type": "action", "action_type": "agent", "buttons": [123], "camera": [60]}
    2. Expanded agent format: {"type": "action", "action_type": "agent", "buttons": [0,0,0,1,...], "camera": [0.0, 90.0]}
    3. Env format: {"type": "action", "action_type": "env", "action": {"forward": 0, "back": 0, ..., "camera": [...]}}
    """
    type: Literal["action"] = "action"
    action_type: Literal["agent", "env"] = "agent"
    # agent action type fields (formats 1 & 2)
    buttons: Optional[list] = Field(None, description="Button action (agent action space)")
    camera: Optional[list] = Field(None, description="Camera movements (agent action space)")
    # env action type field (format 3)
    action: Optional[Dict[str, Any]] = Field(None, description="Detailed action dict (env action space)")
    
    @model_validator(mode='after')
    def validate_format(self):
        """Validate action format based on action_type."""
        
        if self.action_type == "agent":
            # Validate agent action format
            if self.buttons is None:
                raise ValueError("buttons field is required for action_type='agent'")
            if self.camera is None:
                raise ValueError("camera field is required for action_type='agent'")
            
            if not isinstance(self.buttons, list):
                raise ValueError("buttons field must be a list")
            if len(self.buttons) != 1 and len(self.buttons) != 20:
                raise ValueError(f"buttons must have length 1 or 20, got {len(self.buttons)}")
            
            if not isinstance(self.camera, (list, tuple)):
                raise ValueError("camera field must be a list or tuple")
            if len(self.camera) != 1 and len(self.camera) != 2:
                raise ValueError(f"camera must have length 1 or 2, got {len(self.camera)}")
                
        elif self.action_type == "env":
            # Validate env action format
            if self.action is None:
                raise ValueError("action field is required for action_type='env'")
            
            if not isinstance(self.action, dict):
                raise ValueError("action field must be a dictionary")
            
            # Validate required keys for env action
            required_keys = {
                'forward', 'back', 'left', 'right', 
                'jump', 'sneak', 'sprint',
                'attack', 'use', 'drop', 'inventory',
                'camera'
            }
            required_keys.update({f'hotbar.{i}' for i in range(1, 10)})
            
            missing_keys = required_keys - set(self.action.keys())
            if missing_keys:
                # Auto-fill missing keys with defaults
                for key in missing_keys:
                    if key == 'camera':
                        self.action['camera'] = [0.0, 0.0]
                    else:
                        self.action[key] = 0
            
            # Validate camera format
            camera = self.action.get('camera')
            if camera is not None:
                if not isinstance(camera, (list, tuple)):
                    raise ValueError(f"camera must be a list or tuple, got {type(camera)}")
                if len(camera) != 2:
                    raise ValueError(f"camera must have length 2, got {len(camera)}")
        
        return self
    