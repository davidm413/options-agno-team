"""Audit-backed alert dispatch for live trading safety events."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from options_agno_team.config import AppConfig
from options_agno_team.execution import ProposalRepository
from options_agno_team.models import AlertEvent, AlertSeverity, to_jsonable


class AlertDispatcher:
    def __init__(self, repository: ProposalRepository, config: AppConfig | None = None) -> None:
        self.repository = repository
        self.config = config or AppConfig()

    def publish(
        self,
        severity: AlertSeverity,
        category: str,
        message: str,
        *,
        proposal_id: str | None = None,
        symbol: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AlertEvent:
        timestamp = datetime.now(timezone.utc)
        event = AlertEvent(
            alert_id=str(uuid4()),
            timestamp=timestamp,
            severity=severity,
            category=category,
            message=message,
            proposal_id=proposal_id,
            symbol=symbol,
            payload=payload or {},
        )
        self.repository.save_alert_event(event)
        self._emit(event)
        return event

    def _emit(self, event: AlertEvent) -> None:
        payload = json.dumps(to_jsonable(event), sort_keys=True)
        if self.config.alert_stdout_enabled:
            print(payload, file=sys.stderr)
        if self.config.alert_webhook_url:
            self._post_webhook(payload, event)

    def _post_webhook(self, payload: str, event: AlertEvent) -> None:
        request = urllib.request.Request(
            self.config.alert_webhook_url or "",
            data=payload.encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(  # nosec B310 - URL is explicit operator configuration.
                request,
                timeout=self.config.alert_webhook_timeout_seconds,
            ):
                return
        except (OSError, urllib.error.URLError) as exc:
            failure = AlertEvent(
                alert_id=str(uuid5(NAMESPACE_URL, f"alert-delivery-failed:{event.alert_id}")),
                timestamp=datetime.now(timezone.utc),
                severity=AlertSeverity.WARNING,
                category="alert_delivery_failed",
                message="Alert webhook delivery failed",
                proposal_id=event.proposal_id,
                symbol=event.symbol,
                payload={"failed_alert_id": event.alert_id, "error": str(exc)},
            )
            self.repository.save_alert_event(failure)
            if self.config.alert_stdout_enabled:
                print(json.dumps(to_jsonable(failure), sort_keys=True), file=sys.stderr)
