from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Form, Depends, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from datetime import datetime
from database import get_db, Base, engine
from models import User, Message
from auth_util import hash_password, verify_password, create_access_token, decode_token

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
Base.metadata.create_all(bind=engine)

@app.get("/signup", response_class=HTMLResponse)
def signup_form(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

@app.post("/signup", response_class=HTMLResponse)
def signup(request: Request, uname: str = Form(...), email: str = Form(...), pwd: str = Form(...), db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == email).first():
        return templates.TemplateResponse("signup.html", {"request": request, "error": "User already exists"})
    db.add(User(username=uname, email=email, password=hash_password(pwd)))
    db.commit()
    return templates.TemplateResponse("login.html", {"request": request, "success": "Signup successful"})

@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(email: str = Form(...), pwd: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(pwd, user.password):
        return templates.TemplateResponse("login.html", {"request": {}, "error": "Invalid credentials"})
    token = create_access_token({"sub": user.email})
    res = RedirectResponse("/main", status_code=302)
    res.set_cookie("access_token", token, httponly=True)
    return res

@app.get("/logout")
def logout():
    res = RedirectResponse("/login", status_code=302)
    res.delete_cookie("access_token")
    return res

@app.get("/main", response_class=HTMLResponse)
def chat_home(request: Request, db: Session = Depends(get_db), access_token: str = Cookie(None)):
    user = decode_token(access_token)
    current_user = db.query(User).filter_by(email=user["sub"]).first()
    users = db.query(User).filter(User.id != current_user.id).all()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": current_user.username,
        "sender_id": current_user.id,
        "receiver_id": "",
        "users": users
    })

@app.get("/main/{receiver_id}", response_class=HTMLResponse)
def chat_with(request: Request, receiver_id: int, db: Session = Depends(get_db), access_token: str = Cookie(None)):
    user = decode_token(access_token)
    sender = db.query(User).filter_by(email=user["sub"]).first()
    receiver = db.query(User).get(receiver_id)
    users = db.query(User).filter(User.id != sender.id).all()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": sender.username,
        "sender_id": sender.id,
        "receiver_id": receiver.id,
        "chat_receiver_name": receiver.username,
        "users": users
    })



# ---------------- WebSocket ----------------
class ConnectionManager:
    def __init__(self):
        self.connections: dict[int, WebSocket] = {}

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.connections[user_id] = websocket
        await self.broadcast_online_users()

    async def disconnect(self, user_id: int):
        self.connections.pop(user_id, None)
        await self.broadcast_online_users()

    async def broadcast_online_users(self):
        data = {"type": "status_update", "online_users": list(self.connections.keys())}
        for ws in list(self.connections.values()):
            await ws.send_json(data)

    async def send_to(self, user_id: int, data: dict):
        ws = self.connections.get(user_id)
        if ws:
            await ws.send_json(data)

manager = ConnectionManager()

@app.websocket("/ws/{sender_id}/{receiver_id}")
async def chat_ws(websocket: WebSocket, sender_id: int, receiver_id: int, db: Session = Depends(get_db)):
    await manager.connect(sender_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            text = data.get("message")
            is_broadcast = data.get("is_broadcast", False)
            now = datetime.now()

            if not text:
                continue

            if is_broadcast:
                for uid in manager.connections:
                    if uid != sender_id:
                        await manager.send_to(uid, {
                            "type": "message",
                            "username": db.query(User).get(sender_id).username,
                            "message": text,
                            "time": now.strftime('%I:%M %p')
                        })
                continue

            db.add(Message(sender_id=sender_id, receiver_id=receiver_id, message=text, time=now, is_read=False))
            db.commit()

            msg = {
                "type": "message",
                "username": db.query(User).get(sender_id).username,
                "message": text,
                "time": now.strftime('%I:%M %p')
            }

            await manager.send_to(sender_id, msg)
            await manager.send_to(receiver_id, msg)

            if receiver_id in manager.connections:
                await manager.send_to(receiver_id, {
                    "type": "notification",
                    "from_user": db.query(User).get(sender_id).username
                })
    except WebSocketDisconnect:
        await manager.disconnect(sender_id)
