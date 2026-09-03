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
    stop_event = threading.Event()

    def handle_exit():
        stop_event.set()
        import os
        os._exit(0)

    def handle_restart():
        stop_event.set()
        import os
        import sys
        print("[Main] Restarting application via os.execv...")
        os.execv(sys.executable, [sys.executable] + sys.argv)

    daemon = VoiceTypingDaemon(
        engine=engine,
        db=db,
        show_tray=True,
        on_exit=handle_exit,
        on_restart=handle_restart
    )
    from web.api import set_daemon_instance
    set_daemon_instance(daemon)
    
    try:
        daemon.start(blocking=True)
        while not stop_event.is_set():
            time.sleep(0.5)
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
