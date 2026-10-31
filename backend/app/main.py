import asyncio, io, glob
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Literal
from .can_service import CANService

class ConnectRequest(BaseModel):
    mode: Literal["simulation", "hardware"] = "simulation"
    interface: str = "can0"
    bitrate: int = Field(default=500000, ge=10000, le=1000000)
class TransmitRequest(BaseModel):
    can_id: int = Field(ge=0, le=0x1FFFFFFF)
    data: str = Field(default="", max_length=16)
    extended: bool = False
    is_fd: bool = False
class PeriodicRequest(BaseModel):
    can_id: int = Field(ge=0, le=0x1FFFFFFF)
    data: str = Field(default="", max_length=16)
    interval_ms: int = Field(default=100, ge=10, le=60000)
    extended: bool = False
class StopPeriodicRequest(BaseModel):
    can_id: str

app = FastAPI(title="Horsewaves CAN Studio API", version="1.1.0",
              description="Horsewaves CAN Studio — Classic CAN monitor, transmit, logger and basic bus intelligence.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
service = CANService()

@app.get("/api/health")
async def health(): return {"status":"ok","product":"Horsewaves CAN Studio","version":"1.1.0"}
@app.get("/api/status")
async def status(): return service.status()
@app.get("/api/interfaces")
async def interfaces():
    import os
    try: names = [n for n in os.listdir("/sys/class/net") if n.startswith(("can","slcan"))]
    except Exception: names = []
    return {"interfaces": names}
@app.get("/api/analytics")
async def analytics(): return service.analytics()
@app.post("/api/connect")
async def connect(req: ConnectRequest):
    try: return await service.connect(req.mode, req.interface, req.bitrate)
    except Exception as e: raise HTTPException(400, str(e))
@app.post("/api/disconnect")
async def disconnect():
    await service.disconnect()
    return service.status()
@app.post("/api/transmit")
async def transmit(req: TransmitRequest):
    try: return await service.transmit(req.can_id, req.data, req.extended, req.is_fd)
    except Exception as e: raise HTTPException(400, str(e))
@app.post("/api/transmit/periodic")
async def periodic(req: PeriodicRequest):
    try: return await service.start_periodic(req.can_id, req.data, req.interval_ms, req.extended)
    except Exception as e: raise HTTPException(400, str(e))
@app.post("/api/transmit/periodic/stop")
async def periodic_stop(req: StopPeriodicRequest):
    return await service.stop_periodic(req.can_id)
@app.post("/api/logging/start")
async def logging_start(): return service.start_logging()
@app.post("/api/logging/stop")
async def logging_stop(): return service.stop_logging()
@app.get("/api/logging/download")
async def logging_download():
    return StreamingResponse(io.BytesIO(service.csv_bytes()), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="horsewaves_can_log.csv"'})
@app.websocket("/ws/frames")
async def frames_socket(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            try: frame = await asyncio.wait_for(service.frames.get(), timeout=20)
            except asyncio.TimeoutError:
                await ws.send_json({"type":"heartbeat"}); continue
            await ws.send_json(frame)
    except WebSocketDisconnect: pass
    except Exception:
        try: await ws.close()
        except Exception: pass


@app.get("/api/ai/analyze")
async def ai_analyze():
    return service.ai_analysis()

@app.get("/api/serial/ports")
async def serial_ports():
    ports = []
    try:
        from serial.tools import list_ports
        for port in list_ports.comports():
            ports.append({
                "device": port.device, "description": port.description,
                "manufacturer": port.manufacturer, "product": port.product,
                "serial_number": port.serial_number, "vid": port.vid, "pid": port.pid
            })
    except Exception:
        pass
    known = {item["device"] for item in ports}
    for pattern in ("/dev/ttyUSB*", "/dev/ttyACM*", "/dev/ttyS*"):
        for device in glob.glob(pattern):
            if device not in known:
                ports.append({
                    "device": device, "description": "Serial device (metadata unavailable)",
                    "manufacturer": None, "product": None, "serial_number": None,
                    "vid": None, "pid": None
                })
    return {
        "ports": sorted(ports, key=lambda item: item["device"]),
        "note": "Discovery only; serial ports are not automatically opened."
    }
