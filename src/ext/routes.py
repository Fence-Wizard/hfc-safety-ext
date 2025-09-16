from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
import httpx, os

router = APIRouter(prefix="/ext", tags=["Extension"])

# --- Config from env ---
ORCH_SHARED_SECRET = os.getenv("ORCH_SHARED_SECRET", "")
SAFETY_API_BASE = os.getenv("SAFETY_API_BASE", "")
SAFETY_API_KEY  = os.getenv("SAFETY_API_KEY", "")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_DEFAULT_CHANNEL_ID = os.getenv("SLACK_DEFAULT_CHANNEL_ID", "")

# --- Auth helper ---
def _auth(bearer: str | None):
    if not bearer or not bearer.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    tok = bearer.split(" ",1)[1]
    if ORCH_SHARED_SECRET and tok != ORCH_SHARED_SECRET:
        raise HTTPException(401, "Invalid token")

# --- Models ---
class JHAReq(BaseModel):
    task: str
    location: str = "Job site"
    crew_size: int = 2

class SDSReq(BaseModel):
    query: str

class NotifyReq(BaseModel):
    kind: str
    payload: dict

# --- Routes ---
@router.post("/safety/jha")
async def ext_jha(req: JHAReq, authorization: str | None = Header(None)):
    _auth(authorization)
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{SAFETY_API_BASE}/api/safety/jha/generate",
                         headers={"x-api-key": SAFETY_API_KEY},
                         json=req.model_dump())
        r.raise_for_status()
        return r.json()

@router.post("/safety/sds")
async def ext_sds(req: SDSReq, authorization: str | None = Header(None)):
    _auth(authorization)
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{SAFETY_API_BASE}/api/sds/search",
                         headers={"x-api-key": SAFETY_API_KEY},
                         json={"query": req.query})
        r.raise_for_status()
        return r.json()

@router.post("/notify/slack")
async def ext_notify_slack(req: NotifyReq, authorization: str | None = Header(None)):
    _auth(authorization)
    if not SLACK_BOT_TOKEN or not SLACK_DEFAULT_CHANNEL_ID:
        raise HTTPException(400, "Slack not configured")
    text = f":memo: {req.kind.upper()} created\n- task: {req.payload.get('task','')}\n- location: {req.payload.get('location','')}"
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post("https://slack.com/api/chat.postMessage",
                         headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                                  "Content-Type": "application/json; charset=utf-8"},
                         json={"channel": SLACK_DEFAULT_CHANNEL_ID, "text": text})
        data = r.json()
    if not data.get("ok"):
        raise HTTPException(502, f"Slack error: {data.get('error')}")
    return {"ok": True, "ts": data.get("ts")}
