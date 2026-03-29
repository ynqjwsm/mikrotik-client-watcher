import logging
import threading
import time
from typing import Dict, Optional

from models import RosRouter
from monitor import RouterMonitor
from config import config_manager


logger = logging.getLogger(__name__)


class RouterPollingThread(threading.Thread):
    def __init__(self, router: RosRouter, stop_event: threading.Event):
        super().__init__(daemon=True)
        self.router = router
        self.stop_event = stop_event
        self.monitor = RouterMonitor(router)

    def run(self) -> None:
        logger.info(f"Started polling thread for router: {self.router.name}")
        while not self.stop_event.is_set():
            try:
                self.monitor.poll()
            except Exception as e:
                logger.error(f"Error in polling thread for {self.router.name}: {e}")

            interval = self.router.poll_interval_seconds
            if self.stop_event.wait(timeout=interval):
                break
        logger.info(f"Stopped polling thread for router: {self.router.name}")


class Scheduler:
    def __init__(self):
        self.stop_event = threading.Event()
        self.threads: Dict[str, RouterPollingThread] = {}
        self.lock = threading.Lock()

    def start(self) -> None:
        logger.info("Starting scheduler")
        self.stop_event.clear()
        self._start_all_routers()

    def stop(self) -> None:
        logger.info("Stopping scheduler")
        self.stop_event.set()
        with self.lock:
            for thread in self.threads.values():
                if thread.is_alive():
                    thread.join(timeout=5)
            self.threads.clear()

    def restart(self) -> None:
        self.stop()
        time.sleep(0.5)
        self.start()

    def _start_all_routers(self) -> None:
        with self.lock:
            for router in config_manager.get_routers():
                self._start_router_thread(router)

    def _start_router_thread(self, router: RosRouter) -> None:
        if router.id in self.threads:
            logger.warning(f"Thread for router {router.id} already exists")
            return

        thread = RouterPollingThread(router, self.stop_event)
        self.threads[router.id] = thread
        thread.start()

    def _stop_router_thread(self, router_id: str) -> None:
        if router_id not in self.threads:
            return

        thread = self.threads.pop(router_id)
        if thread.is_alive():
            logger.info(f"Stopping thread for router {router_id}")

    def on_router_added(self, router: RosRouter) -> None:
        with self.lock:
            if not self.stop_event.is_set():
                self._start_router_thread(router)

    def on_router_updated(self, router: RosRouter) -> None:
        with self.lock:
            if router.id in self.threads:
                self._stop_router_thread(router.id)
                if not self.stop_event.is_set():
                    self._start_router_thread(router)

    def on_router_deleted(self, router_id: str) -> None:
        with self.lock:
            self._stop_router_thread(router_id)

    def manual_refresh_all(self) -> None:
        logger.info("Manual refresh triggered for all routers")
        with self.lock:
            for thread in self.threads.values():
                try:
                    thread.monitor.manual_refresh()
                except Exception as e:
                    logger.error(f"Error in manual refresh for router {thread.router.name}: {e}")


scheduler = Scheduler()
