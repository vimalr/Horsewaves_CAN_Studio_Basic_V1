import asyncio, csv, io, random, time, statistics
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Optional

try:
    import can
except Exception:
    can = None

class CANService:
    def __init__(self):
        self.bus = None
        self.mode = "disconnected"
        self.interface = "can0"
        self.bitrate = 500000
        self.connected = False
        self.frames = asyncio.Queue(maxsize=5000)
        self.sim_task: Optional[asyncio.Task] = None
        self.rx_task: Optional[asyncio.Task] = None
        self.periodic_tasks = {}
        self.logging = False
        self.log_rows = deque(maxlen=200000)
        self.total_rx = 0
        self.total_tx = 0
        self.started = None
        self.last_seen = {}
        self.cycle_samples = defaultdict(lambda: deque(maxlen=100))
        self.dropped_stream_frames = 0
        self.anomaly_events = deque(maxlen=500)
        self.payload_history = defaultdict(lambda: deque(maxlen=20))

    async def connect(self, mode, interface, bitrate):
        await self.disconnect()
        self.mode, self.interface, self.bitrate = mode, interface, bitrate
        self.total_rx = self.total_tx = 0
        self.started = time.time()
        if mode == "simulation":
            self.connected = True
            self.sim_task = asyncio.create_task(self._simulate())
        else:
            if can is None:
                raise RuntimeError("python-can is not installed")
            try:
                self.bus = can.Bus(interface="socketcan", channel=interface)
            except Exception as e:
                self.bus = None
                raise RuntimeError(f"Could not open {interface}: {e}")
            self.connected = True
            self.rx_task = asyncio.create_task(self._receive())
        return self.status()

    async def disconnect(self):
        self.connected = False
        for task in [self.sim_task, self.rx_task, *self.periodic_tasks.values()]:
            if task: task.cancel()
        self.sim_task = self.rx_task = None
        self.periodic_tasks = {}
        if self.bus:
            try: self.bus.shutdown()
            except Exception: pass
        self.bus = None
        self.mode = "disconnected"

    def status(self):
        return {
            "connected": self.connected, "mode": self.mode,
            "interface": self.interface, "bitrate": self.bitrate,
            "rx": self.total_rx, "tx": self.total_tx,
            "logging": self.logging,
            "uptime_s": round(time.time() - self.started, 1) if self.connected and self.started else 0,
            "stream_dropped": self.dropped_stream_frames
        }

    async def _publish(self, frame):
        self.total_rx += 1
        now = time.time()
        cid = frame["can_id"]
        hist = self.payload_history[cid]
        payload = frame.get("data", "")
        if hist and hist[-1] != payload:
            old_bytes, new_bytes = hist[-1].split(), payload.split()
            changed = sum(x != y for x, y in zip(old_bytes, new_bytes))
            if changed >= 6:
                self.anomaly_events.append({
                    "timestamp": frame["timestamp"], "can_id": cid,
                    "type": "large_payload_change", "severity": "medium",
                    "score": 55, "explanation": f"{changed} payload bytes changed since previous observed frame"
                })
        hist.append(payload)
        cid = frame["can_id"]
        prev = self.last_seen.get(cid)
        if prev is not None:
            self.cycle_samples[cid].append((now - prev) * 1000.0)
        self.last_seen[cid] = now
        if self.logging: self.log_rows.append(dict(frame))
        try:
            self.frames.put_nowait(frame)
        except asyncio.QueueFull:
            self.dropped_stream_frames += 1
            try: self.frames.get_nowait()
            except asyncio.QueueEmpty: pass
            try: self.frames.put_nowait(frame)
            except asyncio.QueueFull: pass

    async def _simulate(self):
        ids = [0x100, 0x181, 0x220, 0x305, 0x412, 0x520]
        while self.connected:
            can_id = random.choice(ids)
            data = bytes(random.randrange(256) for _ in range(random.randint(2, 8)))
            await self._publish({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "can_id": f"{can_id:03X}", "can_id_dec": can_id,
                "dlc": len(data), "data": data.hex(" ").upper(),
                "direction": "RX", "extended": False, "is_fd": False
            })
            await asyncio.sleep(random.uniform(0.035, 0.18))

    async def _receive(self):
        while self.connected and self.bus:
            try:
                msg = await asyncio.to_thread(self.bus.recv, 0.25)
                if msg is None: continue
                await self._publish({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "can_id": f"{msg.arbitration_id:08X}" if msg.is_extended_id else f"{msg.arbitration_id:03X}",
                    "can_id_dec": msg.arbitration_id, "dlc": msg.dlc,
                    "data": bytes(msg.data).hex(" ").upper(), "direction": "RX",
                    "extended": msg.is_extended_id, "is_fd": getattr(msg, "is_fd", False)
                })
            except asyncio.CancelledError: break
            except Exception: await asyncio.sleep(0.1)

    async def transmit(self, can_id, data_hex, extended=False, is_fd=False):
        try: payload = bytes.fromhex(data_hex.replace(" ", "").replace(":", ""))
        except ValueError: raise ValueError("Data must be hexadecimal bytes, e.g. 11 22 A0")
        if len(payload) > (64 if is_fd else 8): raise ValueError("Classic CAN payload maximum is 8 bytes")
        if not self.connected: raise RuntimeError("Connect to an interface before transmitting")
        if self.mode == "hardware":
            if not self.bus: raise RuntimeError("CAN bus is not open")
            msg = can.Message(arbitration_id=can_id, data=payload, is_extended_id=extended, is_fd=is_fd)
            await asyncio.to_thread(self.bus.send, msg, 1.0)
        self.total_tx += 1
        return {"sent": True, "can_id": f"{can_id:X}", "data": payload.hex(" ").upper()}

    async def start_periodic(self, can_id, data, interval_ms, extended=False):
        if not self.connected: raise RuntimeError("Connect before starting periodic transmission")
        if interval_ms < 10: raise ValueError("Minimum periodic interval is 10 ms")
        key = f"{can_id:X}"
        await self.stop_periodic(key)
        async def runner():
            while self.connected:
                await self.transmit(can_id, data, extended, False)
                await asyncio.sleep(interval_ms / 1000.0)
        self.periodic_tasks[key] = asyncio.create_task(runner())
        return {"active": True, "can_id": key, "interval_ms": interval_ms}

    async def stop_periodic(self, can_id):
        task = self.periodic_tasks.pop(str(can_id).upper(), None)
        if task: task.cancel()
        return {"active": False, "can_id": str(can_id).upper()}

    def analytics(self):
        rows = []
        for cid, samples in self.cycle_samples.items():
            if not samples: continue
            vals = list(samples)
            avg = sum(vals) / len(vals)
            rows.append({"can_id": cid, "samples": len(vals),
                         "avg_ms": round(avg, 2), "min_ms": round(min(vals), 2),
                         "max_ms": round(max(vals), 2),
                         "jitter_ms": round(max(vals)-min(vals), 2)})
        rows.sort(key=lambda x: x["can_id"])
        return {"cycle_times": rows, "tracked_ids": len(self.last_seen),
                "rx_frames": self.total_rx, "stream_dropped": self.dropped_stream_frames}

    def start_logging(self):
        self.log_rows.clear()
        self.logging = True
        return {"logging": True}

    def stop_logging(self):
        self.logging = False
        return {"logging": False, "frames": len(self.log_rows)}

    def csv_bytes(self):
        out = io.StringIO()
        fields = ["timestamp","can_id","can_id_dec","dlc","data","direction","extended","is_fd"]
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        writer.writerows(self.log_rows)
        return out.getvalue().encode()


    def ai_analysis(self):
        """Explainable heuristic anomaly screening; this is not a trained ML model."""
        risks = []
        for cid, samples in self.cycle_samples.items():
            vals = list(samples)
            if len(vals) < 5:
                continue
            avg = statistics.mean(vals)
            if avg <= 0:
                continue
            cv = statistics.pstdev(vals) / avg
            jitter = max(vals) - min(vals)
            if cv > 0.35:
                score = min(95, int(50 + cv * 50))
                risks.append({
                    "can_id": cid, "score": score,
                    "level": "high" if score >= 75 else "medium",
                    "type": "cycle_time_instability",
                    "explanation": f"Cycle interval CV {cv:.2f}; average {avg:.1f} ms; peak-to-peak jitter {jitter:.1f} ms.",
                    "recommendation": "Check bus load, ECU scheduling, gateway delays, wiring/noise and capture host load."
                })
        for event in list(self.anomaly_events)[-30:]:
            risks.append({
                "can_id": event["can_id"], "score": event["score"],
                "level": event["severity"], "type": event["type"],
                "explanation": event["explanation"],
                "recommendation": "Verify signal definitions and expected state transitions against ECU specifications."
            })
        risks.sort(key=lambda item: item["score"], reverse=True)
        overall = max([item["score"] for item in risks], default=0)
        return {
            "engine": "Explainable CAN anomaly screening v1",
            "mode": "heuristic",
            "overall_score": overall,
            "risk_level": "high" if overall >= 75 else "medium" if overall >= 45 else "low",
            "frames_analyzed": self.total_rx,
            "findings": risks[:50],
            "limitations": "Heuristic screening only; not trained AI/ML, intrusion detection, safety assessment or compliance evidence."
        }
