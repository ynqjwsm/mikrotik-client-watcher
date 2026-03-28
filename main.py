import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import timedelta, datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import uvicorn

from config import config_manager
from models import Config, RosRouter, ClientMonitor, ClientPushRule, PushRuleType
from feishu_notifier import feishu_notifier
from scheduler import scheduler

load_dotenv()

app = FastAPI(title="MikroTik Client Watcher")
app.mount("/static", StaticFiles(directory="html/static"), name="static")
templates = Jinja2Templates(directory="html/templates")


security = HTTPBearer()
SECRET_KEY = os.getenv('LOGIN_KEY', 'admin123')
WEB_HOST = os.getenv('WEB_HOST', '0.0.0.0')
WEB_PORT = int(os.getenv('WEB_PORT', '8000'))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')


def setup_logging():
    log_dir = Path(os.getenv('DATA_DIR', '.')) / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / 'app.log'
    
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, LOG_LEVEL.upper()))
    
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,
        backupCount=5,
        encoding='utf-8'
    )
    console_handler = logging.StreamHandler()
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


setup_logging()
logger = logging.getLogger(__name__)





def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    return True


@app.on_event("startup")
async def startup_event():
    logger.info("Starting MikroTik Client Watcher")
    feishu_notifier.set_webhook_url(config_manager.get_feishu_webhook_url() or '')
    scheduler.start()


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down MikroTik Client Watcher")
    scheduler.stop()


@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={"id": "login"})


@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    return templates.TemplateResponse(request=request, name="config.html", context={"id": "config"})


class LoginRequest(BaseModel):
    key: str


@app.post("/api/login")
async def login(login_req: LoginRequest):
    if login_req.key == SECRET_KEY:
        return {"success": True, "token": login_req.key}
    raise HTTPException(status_code=401, detail="Invalid key")


@app.get("/api/config")
async def get_config(authenticated: bool = Depends(verify_token)):
    return config_manager.config.model_dump(mode='json')


@app.put("/api/config/feishu")
async def update_feishu_webhook(url: str, authenticated: bool = Depends(verify_token)):
    config_manager.set_feishu_webhook_url(url)
    feishu_notifier.set_webhook_url(url)
    return {"success": True}


@app.post("/api/config/routers")
async def add_router(router: RosRouter, authenticated: bool = Depends(verify_token)):
    config_manager.add_router(router)
    scheduler.on_router_added(router)
    return {"success": True, "router_id": router.id}


@app.put("/api/config/routers/{router_id}")
async def update_router(router_id: str, router: RosRouter, authenticated: bool = Depends(verify_token)):
    config_manager.update_router(router_id, router)
    scheduler.on_router_updated(router)
    return {"success": True}


@app.delete("/api/config/routers/{router_id}")
async def delete_router(router_id: str, authenticated: bool = Depends(verify_token)):
    config_manager.delete_router(router_id)
    scheduler.on_router_deleted(router_id)
    return {"success": True}


@app.post("/api/config/routers/{router_id}/clients")
async def add_client(router_id: str, client: ClientMonitor, authenticated: bool = Depends(verify_token)):
    config_manager.add_client(router_id, client)
    return {"success": True, "client_id": client.id}


@app.put("/api/config/routers/{router_id}/clients/{client_id}")
async def update_client(router_id: str, client_id: str, client: ClientMonitor, authenticated: bool = Depends(verify_token)):
    config_manager.update_client(router_id, client_id, client)
    return {"success": True}


@app.delete("/api/config/routers/{router_id}/clients/{client_id}")
async def delete_client(router_id: str, client_id: str, authenticated: bool = Depends(verify_token)):
    config_manager.delete_client(router_id, client_id)
    return {"success": True}


@app.post("/api/test-feishu")
async def test_feishu(message: str, authenticated: bool = Depends(verify_token)):
    success = feishu_notifier.send_message(message)
    return {"success": success}


@app.get("/api/status")
async def get_status(authenticated: bool = Depends(verify_token)):
    routers = []
    for router in config_manager.get_routers():
        routers.append({
            "id": router.id,
            "name": router.name,
            "enabled": router.enabled,
            "clients": [
                {
                    "id": c.id,
                    "name": c.name,
                    "address": c.address,
                    "mac_address": c.mac_address,
                    "active_hostname": c.active_hostname,
                    "is_online": c.is_online,
                    "enabled": c.enabled,
                    "last_seen": c.last_seen.isoformat() if c.last_seen else None
                }
                for c in router.clients
            ]
        })
    return {"routers": routers}


@app.post("/api/refresh")
async def manual_refresh(authenticated: bool = Depends(verify_token)):
    scheduler.manual_refresh_all()
    return {"success": True}


@app.put("/api/config/routers/{router_id}/toggle")
async def toggle_router(router_id: str, enabled: bool, authenticated: bool = Depends(verify_token)):
    success = config_manager.toggle_router_enabled(router_id, enabled)
    if success:
        router = config_manager.get_router(router_id)
        if router:
            scheduler.on_router_updated(router)
        return {"success": True}
    raise HTTPException(status_code=404, detail="Router not found")


@app.put("/api/config/routers/{router_id}/clients/{client_id}/toggle")
async def toggle_client(router_id: str, client_id: str, enabled: bool, authenticated: bool = Depends(verify_token)):
    success = config_manager.toggle_client_enabled(router_id, client_id, enabled)
    if success:
        return {"success": True}
    raise HTTPException(status_code=404, detail="Client not found")


if __name__ == "__main__":
    uvicorn.run(app, host=WEB_HOST, port=WEB_PORT)
