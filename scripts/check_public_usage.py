"""Explicit external acceptance; fictional numeric data only, never imported by app/tests."""

import concurrent.futures
import datetime
import ipaddress
import json
import os
from pathlib import Path
import socket
import ssl
import urllib.error
import urllib.request
import uuid

HOST = "orangepiaipro-us.taile2de37.ts.net"
BASE = f"https://{HOST}"
CONTEXT = ssl.create_default_context()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = urllib.request.build_opener(urllib.request.HTTPSHandler(context=CONTEXT), NoRedirect())


def request(path, body=None, content_type="application/json"):
    headers = {"Content-Type": content_type} if body is not None else {}
    req = urllib.request.Request(BASE + path, data=body, headers=headers)
    try:
        with OPENER.open(req, timeout=20) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read()


def batch(events):
    return json.dumps({"schema_version": 1, "events": events}).encode()


def main():
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted":
        raise SystemExit("requires_independent_github_hosted_runner")
    if any("tailscale" in name.lower() for _, name in socket.if_nameindex()):
        raise SystemExit("tailnet_interface_detected")
    addresses = sorted({result[4][0] for result in socket.getaddrinfo(HOST, 443, type=socket.SOCK_STREAM)})
    assert addresses and all(ipaddress.ip_address(address).is_global for address in addresses), addresses
    evidence = {
        "checked_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "runner_environment": os.environ["RUNNER_ENVIRONMENT"],
        "run_url": f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}",
        "hostname": HOST,
        "public_dns_addresses": addresses,
        "tests": [],
    }

    def expect(status, path, body=None, content_type="application/json"):
        result = request(path, body, content_type)
        assert result[0] == status, (path, result[0], result[2][:100])
        return result

    assert json.loads(expect(200, "/healthz")[2]) == {"status": "ok"}
    event = {
        "event_id": str(uuid.uuid4()),
        "revision": 1,
        "day_utc": "2000-01-01",
        "recording_count": 1,
        "duration_ms": 125000,
        "source_words": 320,
        "source_chars": 1450,
        "translated_words": 18,
        "translated_chars": 760,
    }
    other = dict(event, event_id=str(uuid.uuid4()))
    evidence["fictional_event_id"] = event["event_id"]
    evidence["conflict_batch_other_event_id"] = other["event_id"]
    ack = {"schema_version": 1, "acknowledged": [{"event_id": event["event_id"], "revision": 1}]}
    for _ in range(10):
        assert json.loads(expect(200, "/v1/usage/batch", batch([event]))[2]) == ack
    evidence["tests"].append("legal_post_and_ten_identical_retries")
    event.update(revision=3, source_chars=1500)
    expect(200, "/v1/usage/batch", batch([event]))
    ack["acknowledged"][0]["revision"] = 3
    assert json.loads(expect(200, "/v1/usage/batch", batch([dict(event, revision=2)]))[2]) == ack
    event.update(revision=4, source_chars=1200)
    ack["acknowledged"][0]["revision"] = 4
    assert json.loads(expect(200, "/v1/usage/batch", batch([event]))[2]) == ack
    evidence["tests"].append("higher_revision_lower_correction_and_out_of_order_ack")
    expect(409, "/v1/usage/batch", batch([other, dict(event, source_chars=1300)]))
    evidence["tests"].append("same_revision_conflict_rejected")
    # Receive HTTP headers but discard the legal JSON acknowledgment, then retry.
    with OPENER.open(
        urllib.request.Request(
            BASE + "/v1/usage/batch", data=batch([event]), headers={"Content-Type": "application/json"}
        ),
        timeout=20,
    ) as lost:
        assert lost.status == 200
    assert json.loads(expect(200, "/v1/usage/batch", batch([event]))[2]) == ack
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: request("/v1/usage/batch", batch([event])), range(8)))
    assert all(status == 200 and json.loads(body) == ack for status, _, body in results)
    evidence["tests"].append("discarded_ack_retry_and_eight_concurrent_duplicates")
    for name in ["audio", "text", "api_key"]:
        expect(400, "/v1/usage/batch", batch([dict(event, **{name: "fictional_rejected_value"})]))
    expect(400, "/v1/usage/batch", b'{"schema_version":1,"schema_version":1,"events":[]}')
    expect(400, "/v1/usage/batch", batch([dict(event, duration_ms=True)]))
    expect(413, "/v1/usage/batch", b" " * (128 * 1024 + 1))
    expect(415, "/v1/usage/batch", b"{}", "text/plain")
    restricted = [
        "/",
        "/admin",
        "/docs",
        "/openapi.json",
        "/usage.sqlite3",
        "/var/lib/lecture-usage/",
        "/v1/usage/batch/",
    ]
    for path in restricted:
        expect(404, path)
    evidence["restricted_routes"] = {path: 404 for path in restricted}
    evidence["tests"].append("validation_body_limit_and_restricted_routes")
    limited = False
    for _ in range(70):
        status, headers, _ = request("/healthz")
        if status == 429:
            value = next(value for name, value in headers.items() if name.lower() == "retry-after")
            assert int(value) > 0
            evidence["retry_after_seconds"] = int(value)
            limited = True
            break
        assert status == 200
    assert limited, "rate_limit_not_observed"
    evidence["tests"].append("rate_limit_429_with_retry_after")
    evidence["final_acknowledgment"] = ack
    evidence["expected_snapshot"] = event
    evidence["persistence_and_atomic_rollback"] = "requires_private_readonly_database_confirmation"
    Path("public-usage-evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
