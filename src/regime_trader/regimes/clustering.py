from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ClusterModelMetadata:
    model_version: str
    n_clusters: int
    feature_names: tuple[str, ...]
    seed: int


@dataclass(frozen=True)
class ClusterAssignment:
    cluster_id: int
    distance: float
    confidence: float
    metadata: ClusterModelMetadata


class DeterministicKMeans:
    def __init__(self, n_clusters: int, *, seed: int = 17, model_version: str = "kmeans-v1") -> None:
        self.n_clusters = n_clusters
        self.seed = seed
        self.model_version = model_version
        self.centroids: np.ndarray | None = None
        self.feature_names: tuple[str, ...] = ()

    def fit(self, vectors: np.ndarray, feature_names: tuple[str, ...]) -> DeterministicKMeans:
        if len(vectors) < self.n_clusters:
            raise ValueError("not enough observations for requested clusters")
        self.feature_names = feature_names
        ordered = vectors[np.argsort(vectors[:, 0])]
        indices = np.linspace(0, len(ordered) - 1, self.n_clusters, dtype=int)
        centroids = ordered[indices].astype(float)
        for _ in range(50):
            distances = np.linalg.norm(vectors[:, None, :] - centroids[None, :, :], axis=2)
            labels = np.argmin(distances, axis=1)
            updated = np.vstack(
                [
                    vectors[labels == cluster].mean(axis=0) if np.any(labels == cluster) else centroids[cluster]
                    for cluster in range(self.n_clusters)
                ]
            )
            if np.allclose(updated, centroids):
                break
            centroids = updated
        self.centroids = centroids
        return self

    def assign(self, vector: np.ndarray) -> ClusterAssignment:
        if self.centroids is None:
            raise ValueError("cluster model has not been fit")
        distances = np.linalg.norm(self.centroids - vector, axis=1)
        cluster_id = int(np.argmin(distances))
        ordered = np.sort(distances)
        nearest = float(ordered[0])
        second = float(ordered[1]) if len(ordered) > 1 else nearest + 1.0
        confidence = 1.0 if second == 0 else max(0.0, min(1.0, 1.0 - nearest / second))
        return ClusterAssignment(
            cluster_id=cluster_id,
            distance=nearest,
            confidence=confidence,
            metadata=ClusterModelMetadata(
                model_version=self.model_version,
                n_clusters=self.n_clusters,
                feature_names=self.feature_names,
                seed=self.seed,
            ),
        )
