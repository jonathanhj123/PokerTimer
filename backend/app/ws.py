from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from . import auth
from .manager import manager

router = APIRouter()


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
            message = await websocket.receive_json()
            if message.get("type") != "command":
                continue
            if not is_admin:
                await websocket.send_json(
                    {"type": "error", "message": "Not authorized"})
                continue
            await manager.handle_command(
                websocket, message.get("action", ""), message.get("payload") or {})
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in manager.clients:
            manager.clients.remove(websocket)
