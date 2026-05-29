from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from regime_trader.config.models import FeatureConfig, RegimeConfig
from regime_trader.features.builder import FeatureVectorBuilder
from regime_trader.regimes.classifier import RegimeClassifier
from regime_trader.regimes.clustering import DeterministicKMeans
from regime_trader.regimes.transitions import TransitionModel
from regime_trader.schemas.market import Bar, OptionChain
from regime_trader.schemas.regime import FeatureVector, RegimeOutput


class RegimeService:
    def __init__(self, feature_config: FeatureConfig, regime_config: RegimeConfig) -> None:
        self.builder = FeatureVectorBuilder(feature_config)
        self.classifier = RegimeClassifier(regime_config)
        self.transitions = TransitionModel()
        self.cluster_model = DeterministicKMeans(regime_config.cluster_count, model_version=regime_config.model_version)

    def build_features(
        self,
        symbol: str,
        bars: Sequence[Bar],
        *,
        option_chain: OptionChain | None = None,
    ) -> FeatureVector:
        return self.builder.build(
            symbol,
            bars,
            option_chain=option_chain,
            model_version=self.cluster_model.model_version,
        )

    def detect(
        self,
        symbol: str,
        bars: Sequence[Bar],
        *,
        option_chain: OptionChain | None = None,
        history: Sequence[RegimeOutput] = (),
    ) -> RegimeOutput:
        vector = self.build_features(symbol, bars, option_chain=option_chain)
        cluster_id: int | None = None
        cluster_confidence: float | None = None
        if self.cluster_model.centroids is not None:
            feature_values = np.asarray([feature.value for feature in vector.features], dtype=float)
            assignment = self.cluster_model.assign(feature_values)
            cluster_id = assignment.cluster_id
            cluster_confidence = assignment.confidence
        output = self.classifier.classify(vector, cluster_id=cluster_id, cluster_confidence=cluster_confidence)
        if history:
            output = output.model_copy(
                update={"transition_probabilities": self.transitions.probabilities((*history, output))}
            )
        return output

    def fit_clusters(self, vectors: Sequence[FeatureVector]) -> None:
        if not vectors:
            raise ValueError("no feature vectors supplied")
        feature_names = tuple(feature.name for feature in vectors[0].features)
        matrix = np.asarray([[feature.value for feature in vector.features] for vector in vectors], dtype=float)
        self.cluster_model.fit(matrix, feature_names)
