from typing import Any, Literal
from pydantic import BaseModel, HttpUrl, Field
    
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
    """Action response from purple agent."""
    type: Literal["action"] = "action"
    buttons: list = Field(..., description="Button states")
    camera: list = Field(..., description="Camera movements")
    
class ErrorPayload(BaseModel):
    """Error message from purple agent."""
    type: Literal["error"] = "error"
    message: str = Field(..., description="Error message")