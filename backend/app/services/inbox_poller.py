import logging
import threading
import time

logger = logging.getLogger(__name__)


def start_inbox_poller(app):
    """Run EmailIngestionService.poll_inbox() on a background thread on a timer.

    Only starts if IMAP is configured and IMAP_AUTO_POLL is enabled, so 'Sync
    Email Inbox' keeps working as a manual override either way.
    """
    if not app.config.get("IMAP_AUTO_POLL", True):
        return
    if not (app.config.get("IMAP_HOST") and app.config.get("IMAP_USER") and app.config.get("IMAP_PASSWORD")):
        logger.info("IMAP not configured — automatic inbox polling disabled")
        return

    interval = app.config.get("IMAP_POLL_INTERVAL_SECONDS", 300)

    def _loop():
        from app.services.email_ingestion import EmailIngestionService
        from app.services.llm.factory import get_llm_client
        from app.services.llm.base import LLMUnavailableError
        from app.services.storage import LocalStorageService

        while True:
            time.sleep(interval)
            try:
                with app.app_context():
                    llm = get_llm_client(app.config["LLM_PROVIDER"], app.config)
                    storage = LocalStorageService(app.config["UPLOAD_FOLDER"])
                    service = EmailIngestionService(app.config, storage, llm)
                    results = service.poll_inbox()
                    attached = sum(1 for r in results if r.get("status") == "attached")
                    if attached:
                        logger.info("Auto inbox poll: attached documents for %s candidate(s)", attached)
            except LLMUnavailableError as exc:
                logger.warning("Auto inbox poll skipped — LLM unavailable: %s", exc)
            except Exception:
                logger.exception("Auto inbox poll failed")

    thread = threading.Thread(target=_loop, name="imap-inbox-poller", daemon=True)
    thread.start()
    logger.info("Started automatic IMAP inbox polling every %ss", interval)
