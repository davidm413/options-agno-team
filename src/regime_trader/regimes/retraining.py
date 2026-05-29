from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

from regime_trader.regimes.service import RegimeService
from regime_trader.schemas.learning import RetrainingJob
from regime_trader.schemas.regime import FeatureVector


class ClusterRetrainingService:
    def __init__(self, service: RegimeService) -> None:
        self.service = service

    def retrain(
        self,
        vectors: Sequence[FeatureVector],
        *,
        dataset_scope: str,
        trigger: str,
        rollback_model_version: str,
    ) -> RetrainingJob:
        self.service.fit_clusters(vectors)
        candidate = f"{self.service.cluster_model.model_version}-{uuid4().hex[:8]}"
        self.service.cluster_model.model_version = candidate
        return RetrainingJob(
            job_id=f"retrain-{uuid4().hex}",
            trigger=trigger,
            evidence=(f"{len(vectors)} feature vectors",),
            dataset_scope=dataset_scope,
            status="candidate_created",
            candidate_model_version=candidate,
            comparison_metrics={"training_vectors": float(len(vectors))},
            rollback_model_version=rollback_model_version,
        )
