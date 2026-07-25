# Implements the authenticated gRPC decision service and streamed-file validation.
import argparse, asyncio, hmac, logging, os, tempfile, grpc
from collections.abc import Callable
from pathlib import Path
from typing import Literal
from grpc import aio

from backend.api.config import settings
from backend.api.gRPC.stubs import pb2, pbg
from backend.engine.adapters.sandbox import SandboxAdapter, create_sandbox_adapter
from backend.engine.quarantine import QuarantineManager
from backend.observability.metrics import record_quarantine, record_verdict, track_request
from backend.observability.request_id import configure_json_logging
from backend.orchestrator.decision import Event, Router

API_KEY_HEADER = "x-api-key"
DEFAULT_GRPC_HOST = "127.0.0.1"
DEFAULT_GRPC_PORT = 50055
MAX_FILE_BYTES = settings.max_file_bytes
EARLY_DECISION_BYTES = 200 * 1024
# real bwrap-isolated analysis (not the placeholder adapter) needs more than
# the 0.25s budget that was tuned for the no-op static adapter
SANDBOX_TIMEOUT_S = 5.0
GRPC_MESSAGE_BYTES = 16 * 1024 * 1024

logger = logging.getLogger(__name__)

# matches Router.decide()'s own confidence bar for a definitive verdict
QUARANTINE_CONFIDENCE_MIN = 0.5

def _response(decision):
    return pb2.DecideResponse(decision=pb2.Decision(
        score=decision.score,
        confidence=decision.confidence,
        verdict=decision.verdict,
        used=decision.used,
    ))


async def _authorize(context) -> None:
    if not settings.require_api_key:
        return

    provided = ""
    for key, value in context.invocation_metadata():
        if key.lower() == API_KEY_HEADER:
            provided = value
            break
    if not provided or not hmac.compare_digest(provided, settings.api_key):
        await context.abort(grpc.StatusCode.UNAUTHENTICATED, "invalid API key")


class DeciderService(pbg.DeciderServicer):  # type: ignore[misc]
    def __init__(
        self,
        router: Router | None = None,
        sandbox_factory: Callable[[], SandboxAdapter] = create_sandbox_adapter,
        max_file_bytes: int = MAX_FILE_BYTES,
        early_decision_bytes: int = EARLY_DECISION_BYTES,
        sandbox_timeout_s: float = SANDBOX_TIMEOUT_S,
    ):
        self.router = router or Router()
        self.quarantine = QuarantineManager(settings.quarantine_dir)
        self.sandbox_factory = sandbox_factory
        self.max_file_bytes = max_file_bytes
        self.early_decision_bytes = early_decision_bytes
        self.sandbox_timeout_s = sandbox_timeout_s

    def _maybe_quarantine(self, data: bytes, filename: str, score: float) -> tuple[bool, str | None]:
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, prefix="rk_grpc_", suffix=".bin") as f:
                f.write(data)
                tmp_path = Path(f.name)
            entry = self.quarantine.quarantine_file(
                tmp_path, reason=f"malicious scan, client filename={filename!r}, score={score:.3f}"
            )
            if entry is None:
                return False, None
            return True, entry.quarantine_id
        except Exception:
            logger.exception("quarantine attempt failed for %s", filename)
            return False, None
        finally:
            if tmp_path is not None and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    @staticmethod
    def _to_event(raw_event) -> Event:
        kind: Literal["log", "file"]
        kind_value = int(raw_event.kind)
        if kind_value == pb2.Event.LOG:
            kind, payload = "log", raw_event.text
        elif kind_value == pb2.Event.FILE:
            kind, payload = "file", bytes(raw_event.bytes)
        else:
            raise ValueError(f"unsupported event kind: {kind_value}")

        event_context: dict[str, object] = dict(raw_event.context)
        if raw_event.path:
            event_context["path"] = raw_event.path
        return Event(kind=kind, payload=payload, context=event_context)

    async def _sandbox_context(self, payload: bytes) -> dict[str, str]:
        sandbox = None
        try:
            sandbox = self.sandbox_factory()
            signals = await asyncio.wait_for(
                sandbox.analyze(payload, timeout_s=self.sandbox_timeout_s),
                timeout=self.sandbox_timeout_s,
            )
            return signals.as_context()
        except TimeoutError:
            logging.warning("Sandbox enrichment timed out after %.2fs", self.sandbox_timeout_s)
            return {"sandbox_bytes": str(len(payload)), "sandbox_timed_out": "1"}
        except Exception as exc:
            logging.warning("Sandbox enrichment failed: %s", exc)
            return {}
        finally:
            if sandbox is not None:
                try:
                    sandbox.close()
                except Exception as exc:
                    logging.warning("Sandbox cleanup failed: %s", exc)

    async def Decide(self, request, context):
        with track_request("grpc", "Decide") as outcome:
            await _authorize(context)
            try:
                event = self._to_event(request.event)
            except ValueError as exc:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))

            if not event.payload:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "event payload is empty")
            decision = await self.router.decide(event)
            record_verdict(event.kind, decision.verdict)
            outcome["status"] = "ok"
            return _response(decision)

    async def StreamLogs(self, request_iterator, context):
        with track_request("grpc", "StreamLogs") as outcome:
            await _authorize(context)
            async for message in request_iterator:
                if not message.text.strip():
                    await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "log line is empty")
                decision = await self.router.decide(
                    Event(kind="log", payload=message.text, context=dict(message.context))
                )
                record_verdict("log", decision.verdict)
                yield pb2.LogDecision(id=message.id, decision=_response(decision).decision)
            outcome["status"] = "ok"

    async def UploadAndDecide(self, request_iterator, context):
        with track_request("grpc", "UploadAndDecide") as outcome:
            await _authorize(context)
            total = 0
            buffer = bytearray()
            first_path = ""
            first_context: dict[str, object] = {}
            saw_chunk = False
            saw_eof = False

            async for chunk in request_iterator:
                data = bytes(chunk.data)
                if int(chunk.offset) != total:
                    await context.abort(
                        grpc.StatusCode.INVALID_ARGUMENT,
                        f"invalid chunk offset: expected {total}, received {chunk.offset}",
                    )

                if not saw_chunk:
                    saw_chunk = True
                    first_path = chunk.path or "unknown.bin"
                    first_context = dict(chunk.context)

                total += len(data)
                if total > self.max_file_bytes:
                    await context.abort(
                        grpc.StatusCode.RESOURCE_EXHAUSTED,
                        f"file exceeds {self.max_file_bytes} byte limit",
                    )
                buffer.extend(data)

                crossed_early_boundary = (
                    len(buffer) >= self.early_decision_bytes
                    and len(buffer) - len(data) < self.early_decision_bytes
                )
                if crossed_early_boundary:
                    early = await self.router.decide(Event(
                        kind="file",
                        payload=bytes(buffer),
                        context={**first_context, "path": first_path},
                    ))
                    borderline = self.router.thr.BORDERLINE_LOW <= early.score <= self.router.thr.BORDERLINE_HIGH
                    if not borderline and early.confidence >= 0.5:
                        record_verdict("file", early.verdict)
                        if early.verdict == "malicious" and early.confidence >= QUARANTINE_CONFIDENCE_MIN:
                            quarantined, _ = self._maybe_quarantine(bytes(buffer), first_path, early.score)
                            if quarantined:
                                record_quarantine()
                        outcome["status"] = "ok"
                        return _response(early)

                if chunk.eof:
                    saw_eof = True
                    break

            if not saw_chunk:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "file stream is empty")
            if not saw_eof:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "file stream is missing EOF")
            if not buffer:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "file payload is empty")

            sandbox_context = await self._sandbox_context(bytes(buffer))
            final = await self.router.decide(Event(
                kind="file",
                payload=bytes(buffer),
                context={**first_context, "path": first_path, **sandbox_context},
            ))
            record_verdict("file", final.verdict)
            if final.verdict == "malicious" and final.confidence >= QUARANTINE_CONFIDENCE_MIN:
                quarantined, _ = self._maybe_quarantine(bytes(buffer), first_path, final.score)
                if quarantined:
                    record_quarantine()
            outcome["status"] = "ok"
            return _response(final)


def _listen_address(host: str, port: int) -> str:
    normalized_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
    return f"{normalized_host}:{port}"


def create_server(host: str, port: int, service: DeciderService | None = None):
    server = aio.server(options=[
        ("grpc.max_send_message_length", GRPC_MESSAGE_BYTES),
        ("grpc.max_receive_message_length", GRPC_MESSAGE_BYTES),
    ])
    pbg.add_DeciderServicer_to_server(service or DeciderService(), server)  # type: ignore[arg-type]

    address = _listen_address(host, port)
    if os.getenv("RAKSHAK_TLS", "0") == "1":
        cert_path = Path(os.getenv("RAKSHAK_TLS_CERT", "server.crt"))
        key_path = Path(os.getenv("RAKSHAK_TLS_KEY", "server.key"))
        credentials = grpc.ssl_server_credentials(((key_path.read_bytes(), cert_path.read_bytes()),))
        bound_port = server.add_secure_port(address, credentials)
    else:
        bound_port = server.add_insecure_port(address)

    if not bound_port:
        raise RuntimeError(f"could not bind gRPC server to {address}")
    return server, bound_port


async def serve(host: str = DEFAULT_GRPC_HOST, port: int = DEFAULT_GRPC_PORT) -> None:
    server, bound_port = create_server(host, port)
    await server.start()
    logging.info("Decider gRPC listening on %s", _listen_address(host, bound_port))

    metrics_port = int(os.getenv("RAKSHAK_METRICS_PORT", "0"))
    if metrics_port:
        from prometheus_client import start_http_server

        start_http_server(metrics_port)
        logging.info("Metrics listening on :%d", metrics_port)

    await server.wait_for_termination()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.getenv("RAKSHAK_GRPC_HOST", DEFAULT_GRPC_HOST))
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("RAKSHAK_GRPC_PORT", str(DEFAULT_GRPC_PORT))),
    )
    args = parser.parse_args()
    configure_json_logging()
    asyncio.run(serve(args.host, args.port))


if __name__ == "__main__":
    main()
