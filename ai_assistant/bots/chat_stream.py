"""Keep the web connection alive while the existing chat service completes."""
import json
import logging
from queue import Empty, Queue
from threading import BoundedSemaphore, Thread

from django.db import close_old_connections, connections
from django.http import JsonResponse, StreamingHttpResponse

logger = logging.getLogger(__name__)
HEARTBEAT_SECONDS = 10
# Leave request threads available for history and other short requests. No queue
# of paid work: a disconnected request holds its slot until processing finishes.
_slots = BoundedSemaphore(2)


def stream_chat_response(process):
    if not _slots.acquire(blocking=False):
        return JsonResponse({"error": "Chat is busy. Please try again shortly."}, status=503)

    completed = Queue(maxsize=1)

    def run():
        try:
            close_old_connections()
            response = process()
            event = {"type": "result", "status": response.status_code,
                     "data": json.loads(response.content.decode("utf-8"))}
        except Exception:
            logger.exception("Streaming chat failed")
            event = {"type": "result", "status": 500,
                     "data": {"error": "AI processing failed."}}
        finally:
            try:
                connections.close_all()
            except Exception:
                logger.exception("Streaming chat connection cleanup failed")
            finally:
                _slots.release()
        completed.put(event)

    worker = Thread(target=run, name="web-chat", daemon=True)
    try:
        worker.start()
    except BaseException:
        _slots.release()
        raise

    def events():
        # No wait for retrieval or generation before flushing the first bytes.
        yield b'{"type":"heartbeat"}\n'
        while True:
            try:
                event = completed.get(timeout=HEARTBEAT_SECONDS)
            except Empty:
                yield b'{"type":"heartbeat"}\n'
                continue
            yield (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")
            return

    response = StreamingHttpResponse(events(), content_type="application/x-ndjson")
    response["Cache-Control"] = "no-cache, no-store, no-transform"
    response["X-Accel-Buffering"] = "no"
    return response
