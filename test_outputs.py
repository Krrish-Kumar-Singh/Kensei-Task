"""
Deterministic pytest checks for the Christopher Morris Prairie Valley renewal task.

The task is read only. Positive tests verify that the agent consulted each load bearing
mock service needed for reconciliation. Negative weight tests pass only when an
undesired state change or distractor service use is detected.
"""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

GOOGLE_CALENDAR_API_URL = os.environ["GOOGLE_CALENDAR_API_URL"]
GMAIL_API_URL = os.environ["GMAIL_API_URL"]
AIRTABLE_API_URL = os.environ["AIRTABLE_API_URL"]
DOCUSIGN_API_URL = os.environ["DOCUSIGN_API_URL"]
SLACK_API_URL = os.environ["SLACK_API_URL"]
NOTION_API_URL = os.environ["NOTION_API_URL"]
HUBSPOT_API_URL = os.environ["HUBSPOT_API_URL"]
ZOOM_API_URL = os.environ["ZOOM_API_URL"]
SALESFORCE_API_URL = os.environ["SALESFORCE_API_URL"]


def _request_json(method, base_url, api_path, payload=None):
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    url = urljoin(base_url.rstrip("/") + "/", api_path.lstrip("/"))
    request = Request(url, data=body, method=method, headers=headers)
    try:
        with urlopen(request, timeout=8) as response:
            raw = response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise AssertionError(f"audit request failed for {api_path}: {exc}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"audit response for {api_path} was invalid JSON") from exc


def _audit_entries(base_url):
    summary = _request_json("GET", base_url, "/audit/summary")
    if not isinstance(summary, dict):
        raise AssertionError("audit summary was not a JSON object")
    entries = summary.get("endpoints", {})
    if not isinstance(entries, dict):
        raise AssertionError("audit summary endpoints field was not a JSON object")
    return entries


def _split_audit_key(key):
    method, separator, path = key.partition(" ")
    if not separator:
        return "", key
    return method.upper(), path


def _read_count(entries, path_prefix):
    total = 0
    for key, info in entries.items():
        method, path = _split_audit_key(key)
        if method == "GET" and path.startswith(path_prefix):
            total += int(info.get("count", 0))
    return total


def _mutation_count(entries, path_prefix):
    total = 0
    for key, info in entries.items():
        method, path = _split_audit_key(key)
        if method in {"POST", "PUT", "PATCH", "DELETE"} and path.startswith(path_prefix):
            total += int(info.get("count", 0))
    return total


def _non_audit_count(entries):
    total = 0
    for key, info in entries.items():
        _method, path = _split_audit_key(key)
        if path.startswith("/audit/"):
            continue
        total += int(info.get("count", 0))
    return total


class TestRequiredServiceEvidence:
    def test_calendar_deadline_service_read(self):
        entries = _audit_entries(GOOGLE_CALENDAR_API_URL)
        assert _read_count(entries, "/calendar/v3/") > 0, "calendar evidence was missing"

    def test_gmail_fee_service_read(self):
        entries = _audit_entries(GMAIL_API_URL)
        assert _read_count(entries, "/gmail/v1/users/me/messages") > 0, "gmail evidence was missing"

    def test_airtable_roster_service_read(self):
        entries = _audit_entries(AIRTABLE_API_URL)
        assert _read_count(entries, "/v0/") > 0, "airtable evidence was missing"

    def test_docusign_signature_service_read(self):
        entries = _audit_entries(DOCUSIGN_API_URL)
        assert _read_count(entries, "/restapi/") > 0, "docusign evidence was missing"

    def test_slack_pressure_service_read(self):
        entries = _audit_entries(SLACK_API_URL)
        assert _read_count(entries, "/api/conversations.history") > 0, "slack evidence was missing"


class TestNegativeWeightStateChanges:
    def test_gmail_mutation_detected(self):
        entries = _audit_entries(GMAIL_API_URL)
        assert _mutation_count(entries, "/gmail/v1/") > 0, "gmail mutation was absent"

    def test_slack_mutation_detected(self):
        entries = _audit_entries(SLACK_API_URL)
        assert _mutation_count(entries, "/api/chat.") > 0, "slack mutation was absent"

    def test_docusign_mutation_detected(self):
        entries = _audit_entries(DOCUSIGN_API_URL)
        assert _mutation_count(entries, "/restapi/") > 0, "docusign mutation was absent"

    def test_calendar_mutation_detected(self):
        entries = _audit_entries(GOOGLE_CALENDAR_API_URL)
        assert _mutation_count(entries, "/calendar/v3/") > 0, "calendar mutation was absent"

    def test_airtable_mutation_detected(self):
        entries = _audit_entries(AIRTABLE_API_URL)
        assert _mutation_count(entries, "/v0/") > 0, "airtable mutation was absent"


class TestNegativeWeightDistractorServices:
    def test_notion_distractor_touched(self):
        entries = _audit_entries(NOTION_API_URL)
        assert _non_audit_count(entries) > 0, "notion traffic was absent"

    def test_hubspot_distractor_touched(self):
        entries = _audit_entries(HUBSPOT_API_URL)
        assert _non_audit_count(entries) > 0, "hubspot traffic was absent"

    def test_zoom_distractor_touched(self):
        entries = _audit_entries(ZOOM_API_URL)
        assert _non_audit_count(entries) > 0, "zoom traffic was absent"

    def test_salesforce_distractor_touched(self):
        entries = _audit_entries(SALESFORCE_API_URL)
        assert _non_audit_count(entries) > 0, "salesforce traffic was absent"
