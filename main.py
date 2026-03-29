import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import uvicorn

from config import config_manager
from models import RosRouter, ClientMonitor, FeishuConfig, EmailConfig
from feishu_notifier import feishu_notifier
from email_notifier import email_notifier
from scheduler import scheduler
from settings import settings


load_dotenv()


def setup_logging() -> None:
    log_dir = settings.data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "app.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    console_handler = logging.StreamHandler()

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


setup_logging()
logger = logging.getLogger(__name__)


security = HTTPBearer()


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> bool:
    if credentials.credentials != settings.login_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting MikroTik Client Watcher")
    feishu_notifier.set_config(config_manager.get_feishu_config())
    email_notifier.set_config(config_manager.get_email_config())
    scheduler.start()
    yield
    logger.info("Shutting down MikroTik Client Watcher")
    scheduler.stop()


app = FastAPI(title="MikroTik Client Watcher", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="html/static"), name="static")
templates = Jinja2Templates(directory="html/templates")


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
    if login_req.key == settings.login_key:
        return {"success": True, "token": login_req.key}
    raise HTTPException(status_code=401, detail="Invalid key")


@app.get("/api/config")
async def get_config(authenticated: bool = Depends(verify_token)):
    return config_manager.config.model_dump(mode="json")


@app.put("/api/config/feishu")
async def update_feishu_config(config: FeishuConfig, authenticated: bool = Depends(verify_token)):
    config_manager.set_feishu_config(config)
    feishu_notifier.set_config(config)
    return {"success": True}


@app.put("/api/config/email")
async def update_email_config(config: EmailConfig, authenticated: bool = Depends(verify_token)):
    config_manager.set_email_config(config)
    email_notifier.set_config(config)
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


@app.post("/api/test-email")
async def test_email(subject: str, body: str, authenticated: bool = Depends(verify_token)):
    success = email_notifier.send_message(subject, body)
    return {"success": success}


@app.get("/api/status")
async def get_status(authenticated: bool = Depends(verify_token)):
    routers = []
    for router in config_manager.get_routers():
        routers.append(
            {
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
                        "last_seen": c.last_seen.isoformat() if c.last_seen else None,
                    }
                    for c in router.clients
                ],
            }
        )
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
    uvicorn.run(app, host=settings.web_host, port=settings.web_port)
