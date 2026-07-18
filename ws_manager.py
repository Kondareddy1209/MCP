import asyncio
from fastapi import WebSocket
from typing import Dict, Tuple

class ConnectionManager:
    def __init__(self):
        # Map WebSocket to its message queue and background sender task
        self.active_connections: Dict[WebSocket, Tuple[asyncio.Queue, asyncio.Task]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        queue = asyncio.Queue(maxsize=100)  # limit queue size to prevent memory leaks
        task = asyncio.create_task(self._writer_loop(websocket, queue))
        self.active_connections[websocket] = (queue, task)
        print(f"[WebSocket] Client connected. Total active connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            queue, task = self.active_connections.pop(websocket)
            task.cancel()
            print(f"[WebSocket] Client disconnected. Total active connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        # Non-blocking broadcast: enqueue message for each client asynchronously (Task 10)
        for ws, (queue, _) in list(self.active_connections.items()):
            try:
                if queue.full():
                    try:
                        queue.get_nowait()  # discard oldest if full
                    except asyncio.QueueEmpty:
                        pass
                queue.put_nowait(message)
            except Exception as e:
                print(f"[WebSocket] Failed to enqueue message for connection {ws}: {e}")

    async def _writer_loop(self, websocket: WebSocket, queue: asyncio.Queue):
        """Dedicated per-client background loop to drain queues without blocking (Task 10)"""
        try:
            heartbeat_interval = 20.0  # send a ping heartbeat every 20 seconds of silence
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)
                    await websocket.send_json(message)
                    queue.task_done()
                except asyncio.TimeoutError:
                    # Heartbeat ping
                    await websocket.send_json({"type": "ping"})
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[WebSocket] Writer loop connection closed: {e}")
        finally:
            # Ensure cleanup on disconnect or failure
            self.disconnect(websocket)

manager = ConnectionManager()
