import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from . import auth
from .manager import manager

router = APIRouter()

_INVALID_MESSAGE = {"type": "error", "message": "Invalid message"}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    is_admin = auth.verify_session_token(websocket.cookies.get("session"))
    manager.clients.append(websocket)
    try:
        await websocket.send_json({
            "type": "state",
            "state": manager.state.to_dict(),
            "is_admin": is_admin,
        })
        while True:
            try:
                message = await websocket.receive_json()
            except (json.JSONDecodeError, KeyError):
                # Non-JSON text frame, or a binary frame (which lacks the
                # "text" key receive_json expects) — e.g. a stray heartbeat
                # ping. Reply with a diagnostic instead of killing the
                # connection.
                await websocket.send_json(_INVALID_MESSAGE)
                continue
            if not isinstance(message, dict):
                # Top-level JSON that isn't an object (e.g. a bare number
                # or a list) has no "type"/"payload" to read from.
                await websocket.send_json(_INVALID_MESSAGE)
                continue
            if message.get("type") != "command":
                continue
            if not is_admin:
                await websocket.send_json(
                    {"type": "error", "message": "Not authorized"})
                continue
            payload = message.get("payload") or {}
            if not isinstance(payload, dict):
                await websocket.send_json(_INVALID_MESSAGE)
                continue
            await manager.handle_command(
                websocket, message.get("action", ""), payload)
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in manager.clients:
            manager.clients.remove(websocket)
