from fastapi import FastAPI, WebSocket
from fastapi.websockets import WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .models import TripStatus

from llm.process import process_user_speech
from .models import TripStatus
from .t2v import synthesize_text
import asyncio
from .maps import Location
import json

app = FastAPI()


class GlobalState:
    def __init__(self):
        self.current_status = None
        self.lock = asyncio.Lock()
        self.messages = [
            {
                "role": "system",
                "content": "You are a fun driving bestie. If you are asked a question about driving, you will use one of the tool calls to find the answer. Or, you will summarize the trip information as broadly as possible without repeating it word for word",
            }
        ]

    async def set_status(self, status: TripStatus):
        async with self.lock:
            self.current_status = status

    async def get_status(self):
        async with self.lock:
            return self.current_status

    async def set_messages(self, new_messages):
        async with self.lock:
            self.messages = new_messages

    async def get_messages(self):
        async with self.lock:
            return self.messages


state = GlobalState()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/destination")
async def handle_destination(data: TripStatus):
    await state.set_status(data)
    return JSONResponse(
        content={"status": "success", "message": "Data received successfully!"},
        status_code=200,
    )

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    import traceback
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "detail": traceback.format_exc()},
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            current_status = await state.get_status()
            if current_status is None:
                await websocket.send_text(json.dumps({"text": "Please set a destination first.", "route": None}))
                try:
                    await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
                except asyncio.TimeoutError:
                    pass
                continue
            try:
                current_status.update_status()
                messages = await state.get_messages()
                response, new_messages, status, extras = process_user_speech(
                    data, current_status, messages
                )
                await state.set_messages(new_messages)
                await state.set_status(status)
                route_coords = [
                    {"lat": step.start_location.lat, "lng": step.start_location.lng}
                    for step in reversed(status.route)
                ] if status.route else None
                payload = {"text": response, "route": route_coords}
                if "new_dest" in extras:
                    payload["new_dest"] = extras["new_dest"]
                if "stop" in extras and extras["stop"]:
                    payload["stop"] = extras["stop"]
                await websocket.send_text(json.dumps(payload))
            except Exception as e:
                import traceback
                print(f"WS handler error: {traceback.format_exc()}")
                await websocket.send_text(json.dumps({"text": f"Error: {e}", "route": None}))
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                pass  # frontend missed sending "done" — continue anyway
    except WebSocketDisconnect:
        pass


@app.websocket("/navigation")
async def navigation_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            current_status = await state.get_status()
            if current_status is None:
                continue
            data = json.loads(data)
            current_status.curr = Location(**data)
            try:
                response = current_status.check_route_instruction()
            except Exception as e:
                print(f"Nav instruction error: {e}")
                response = None
            await state.set_status(current_status)
            if response:
                await websocket.send_text(response)
    except WebSocketDisconnect:
        pass
