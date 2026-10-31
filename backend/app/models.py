from pydantic import BaseModel, Field
from typing import Literal

class ConnectRequest(BaseModel):
    mode: Literal["simulation", "hardware"] = "simulation"
    interface: str = "can0"
    bitrate: int = Field(default=500000, ge=10000, le=1000000)

class TransmitRequest(BaseModel):
    can_id: int = Field(ge=0, le=0x1FFFFFFF)
    data: str = Field(default="", max_length=16)
    extended: bool = False
    is_fd: bool = False
