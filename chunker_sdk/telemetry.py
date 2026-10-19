"""Small dependency-light structured logging, tracing and process metrics."""
import json, logging, time, uuid
from contextlib import contextmanager
from threading import Lock

class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)), "level": record.levelname,
                   "logger": record.name, "message": record.getMessage()}
        for key in ("trace_id", "span", "duration_ms", "document_name", "strategy", "chunk_count", "file_bytes", "error_type"):
            if hasattr(record, key): payload[key] = getattr(record, key)
        return json.dumps(payload, ensure_ascii=False, default=str)

logger = logging.getLogger("document_chunker")
if not logger.handlers:
    handler = logging.StreamHandler(); handler.setFormatter(JsonFormatter()); logger.addHandler(handler); logger.setLevel(logging.INFO); logger.propagate = False
_lock = Lock(); _metrics = {"calls_total": 0, "errors_total": 0, "preview_calls_total": 0, "chunks_total": 0, "bytes_total": 0, "duration_ms_total": 0.0}
@contextmanager
def span(name, trace_id=None, **attrs):
    tid = trace_id or uuid.uuid4().hex[:16]; started = time.perf_counter(); logger.info("span.start", extra={"trace_id":tid,"span":name,**attrs})
    try:
        yield {"trace_id":tid,"span":name}
        logger.info("span.end", extra={"trace_id":tid,"span":name,"duration_ms":round((time.perf_counter()-started)*1000,3),**attrs})
    except Exception as exc:
        logger.error("span.error", extra={"trace_id":tid,"span":name,"duration_ms":round((time.perf_counter()-started)*1000,3),"error_type":type(exc).__name__,**attrs})
        raise
def record_call(duration_ms, file_bytes=0, chunks=0, error=False, preview=False):
    with _lock:
        _metrics["calls_total"] += 1; _metrics["errors_total"] += int(error); _metrics["preview_calls_total"] += int(preview)
        _metrics["chunks_total"] += chunks; _metrics["bytes_total"] += file_bytes; _metrics["duration_ms_total"] += duration_ms
def get_metrics():
    with _lock: return {**_metrics, "average_duration_ms": round(_metrics["duration_ms_total"] / max(1,_metrics["calls_total"]),3)}
def prometheus_metrics():
    m=get_metrics(); return "\n".join(f"document_chunker_{k} {v}" for k,v in m.items()) + "\n"
