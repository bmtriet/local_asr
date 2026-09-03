import argparse
import sys
import threading
import time
import uvicorn
from config import get_settings
from storage.database import Database
from asr_engine.engine import ASREngine
from daemon.service import VoiceTypingDaemon
from web.api import app

def run_web(settings):
    print(f"[Main] Starting Web UI Server on http://{settings.HOST}:{settings.PORT}")
    uvicorn.run(app, host=settings.HOST, port=settings.PORT, log_level="info")

def run_daemon(engine, db):
    print("[Main] Starting Voice Typing Daemon with Tray Icon...")
    daemon = VoiceTypingDaemon(engine=engine, db=db, show_tray=True)
    daemon.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        daemon.stop()

def main():
    parser = argparse.ArgumentParser(description="Local ASR System with Qwen3-ASR and Continual Learning")
    parser.add_argument(
        "--service",
        choices=["all", "daemon", "web"],
        default="all",
        help="Service to start: 'all' (daemon + web), 'daemon', or 'web'"
    )
    args = parser.parse_args()

    settings = get_settings()
    db = Database()
    db.init_db()

    if args.service == "web":
        run_web(settings)
    elif args.service == "daemon":
        engine = ASREngine(lazy_load=False)
        run_daemon(engine, db)
    elif args.service == "all":
        # Preload engine on GPU first so model is immediately ready
        engine = ASREngine(lazy_load=False)

        # Run Web Server in background thread
        web_thread = threading.Thread(target=run_web, args=(settings,), daemon=True)
        web_thread.start()

        # Run Daemon in main thread
        run_daemon(engine, db)

if __name__ == "__main__":
    main()
