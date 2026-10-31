# Horsewaves CAN Studio — B+C Engineering Foundation (v1.1)

A Linux-first web and desktop CAN engineering tool for bench development and validation workflows.

## Included in this release
- Web UI (React + Vite)
- Desktop UI (PySide6 WebEngine wrapper)
- FastAPI backend and WebSocket live frame stream
- Simulation mode and Linux SocketCAN hardware mode
- Classic CAN monitor, manual transmit and CSV logger
- CAN Intelligence: observed per-ID cycle-time min/average/max/jitter
- Periodic CAN transmit API (minimum 10 ms interval)
- Five themes including Horsewaves Red & Gold
- API health/status/interface/analytics endpoints

## Quick start — Ubuntu 22.04+
Install prerequisites:
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nodejs npm can-utils
```
For a web session:
```bash
chmod +x run_web.sh
./run_web.sh
```
Open `http://localhost:5173`. API docs: `http://127.0.0.1:8765/docs`.

For the desktop application:
```bash
chmod +x run_desktop.sh
./run_desktop.sh
```
The script starts the API and Vite server, then opens the desktop window.

## Manual start
Backend:
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8765
```
Frontend (new terminal):
```bash
cd frontend
npm install
npm run dev
```
Desktop dependencies:
```bash
cd desktop
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```
Manual desktop start assumes API and web UI are already running.

## SocketCAN bench setup
Check the adapter:
```bash
lsusb
ip -br link
```
Configure an already-installed SocketCAN adapter for 500 kbit/s:
```bash
sudo ip link set can0 down
sudo ip link set can0 type can bitrate 500000
sudo ip link set can0 up
ip -details link show can0
```
Select Hardware mode and interface `can0` in the UI. Adapter drivers/firmware and privileged interface configuration remain OS/manufacturer responsibilities.

## API
- `GET /api/health`
- `GET /api/status`
- `GET /api/interfaces`
- `GET /api/analytics`
- `POST /api/connect`
- `POST /api/disconnect`
- `POST /api/transmit`
- `POST /api/transmit/periodic`
- `POST /api/transmit/periodic/stop`
- `POST /api/logging/start`
- `POST /api/logging/stop`
- `GET /api/logging/download`
- `WS /ws/frames`

## Release scope / limitations
This is a functional engineering foundation, not a Vector CANalyzer replacement and not yet a complete B+C product. This release implements Classic CAN, simulation, SocketCAN RX/TX, periodic transmit API, CSV logging, and observed cycle-time analytics. ECU Virtual Lab profiles, DBC decode/edit, ISO-TP/UDS, J1939, CAN FD validation, automated test authoring, fault injection, signed test evidence, user management and remote test bench are not implemented in this build. They are roadmap items.
Cycle-time values are measured from frames observed by this application. They do not prove that a message is missing; define expected periods and test windows in a future validation module before reporting timeout faults.
Hardware transmission can affect a live vehicle. Use an isolated bench, approved IDs/payloads, correct bitrate and termination. Do not transmit to a production vehicle without authorization.

## USB serial detection and AI analysis
The dashboard discovers `/dev/ttyUSB*`, `/dev/ttyACM*`, and `/dev/ttyS*` ports. It does not automatically open serial devices. Native SocketCAN adapters generally appear as `can0`/`can1`; SLCAN devices require separate serial-to-CAN configuration.

The AI Analysis tab is an explainable heuristic anomaly screener for cycle-time variability and large payload changes. It is not a trained ML model, intrusion detector, safety assessor, or compliance verdict.
# Horsewaves_CAN_Studio_Basic_V1
