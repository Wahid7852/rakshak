# Fuzzes the live FastAPI app against its own OpenAPI schema (DAST).
import pytest

pytest.importorskip("schemathesis")
pytest.importorskip("fastapi")

import schemathesis
from hypothesis import HealthCheck, settings

from backend.api.main import app

schema = schemathesis.openapi.from_asgi("/openapi.json", app)


@schema.parametrize()
@settings(
    max_examples=25,
    deadline=None,
    # filter_too_much: the feedback endpoint's narrow schema filters out most fuzz inputs.
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
def test_api_fuzz(case):
    # dev-key: verify_api_key isn't modeled as an OpenAPI security scheme (it's a
    # plain Header dependency), so schemathesis wouldn't otherwise know to send it -
    # without this every fuzzed request would just hit 401 and never reach real
    # handler logic.
    #
    # Only checking for server errors (crashes), not full schema/response
    # conformance: schemathesis's multipart generation for /v1/scan/file produces
    # schema-valid-but-semantically-empty file parts that FastAPI's UploadFile
    # rightly 422s on, which the stricter checks flag as false positives. Crash
    # detection is the actual DAST value here.
    case.call_and_validate(
        headers={"x-api-key": "dev-key"},
        checks=[schemathesis.checks.not_a_server_error],
    )
