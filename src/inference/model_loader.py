"""ModelLoader factory for instantiating and loading Mock or Real inference engines."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional

from src.execution.execution_config import ModelConfig
from src.inference.inference_engine import (
    BaseInferenceEngine,
    MockInferenceEngine,
    ModelLoadError,
    RealModelEngineAdapter,
)

logger = logging.getLogger(__name__)


class ModelLoader:
    """Creates and loads `BaseInferenceEngine` instances according to runtime mode and model config."""

    def __init__(self, runtime_mode: str = "mock", project_root: Optional[Path] = None) -> None:
        if runtime_mode not in ("mock", "real"):
            raise ValueError(f"runtime_mode '{runtime_mode}' tidak valid (harus 'mock' atau 'real').")
        self.runtime_mode = runtime_mode
        self.project_root = project_root or Path(__file__).resolve().parents[2]

    def create_engine(self, model_config: ModelConfig) -> BaseInferenceEngine:
        """Instantiate the appropriate engine without loading weights yet."""
        if self.runtime_mode == "mock" or model_config.framework == "mock":
            if self.runtime_mode == "real" and model_config.framework == "mock":
                raise ModelLoadError(
                    f"Sistem berjalan dengan runtime_mode='real', tetapi model '{model_config.model_id}' "
                    "masih memiliki framework='mock' (placeholder). Ubah framework dan weights_path di models.yaml."
                )
            return MockInferenceEngine(config=model_config, project_root=self.project_root)

        return RealModelEngineAdapter(config=model_config, project_root=self.project_root)

    def load_model(self, model_config: ModelConfig) -> BaseInferenceEngine:
        """Instantiate and load the engine for a single `ModelConfig`."""
        engine = self.create_engine(model_config)
        engine.load()
        return engine

    def load_models(self, models: list[ModelConfig]) -> Dict[str, BaseInferenceEngine]:
        """Load a collection of models and return a mapping of `model_id -> BaseInferenceEngine`."""
        loaded: Dict[str, BaseInferenceEngine] = {}
        for cfg in models:
            loaded[cfg.model_id] = self.load_model(cfg)
        return loaded

