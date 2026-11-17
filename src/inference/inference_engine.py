"""InferenceEngine base class, MockInferenceEngine, and RealModelEngineAdapter.

Separates generic inference orchestration from framework-specific runtime execution
so all five oil palm AI detection models share a uniform lifecycle (`load`, `predict`, `unload`).
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, List, Optional

import numpy as np

from src.execution.execution_config import ModelConfig
from src.inference.preprocessor import PreprocessedInput
from src.inference.result_normalizer import RawPrediction

logger = logging.getLogger(__name__)


class ModelNotLoadedError(RuntimeError):
    """Raised when `predict()` is invoked before `load()` succeeds."""


class ModelLoadError(FileNotFoundError):
    """Raised when a real model file is missing or cannot be initialized by its framework."""


class BaseInferenceEngine(ABC):
    """Abstract base class for all model inference engines (Mock and Real)."""

    def __init__(self, config: ModelConfig, project_root: Optional[Path] = None) -> None:
        self.config = config
        self.project_root = project_root or Path(__file__).resolve().parents[2]
        self._is_loaded: bool = False
        self._load_time_ms: float = 0.0

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    @property
    def load_time_ms(self) -> float:
        return self._load_time_ms

    @property
    @abstractmethod
    def is_mock(self) -> bool:
        """Return True if this engine generates simulated/mock predictions."""

    @abstractmethod
    def load(self) -> float:
        """Load model weights into memory and return load duration in milliseconds."""

    @abstractmethod
    def predict(self, preprocessed: PreprocessedInput) -> List[RawPrediction]:
        """Run forward pass on preprocessed input and return raw predictions."""

    def unload(self) -> None:
        """Release model resources."""
        self._is_loaded = False


class MockInferenceEngine(BaseInferenceEngine):
    """Deterministic MockInferenceEngine for testing pipeline, ROS 2, and API without real weights.

    Produces task-appropriate outputs (e.g., bounding boxes for `object_detection` models
    and `bounding_box=None` for `classification` models like `health_inspector`).
    """

    @property
    def is_mock(self) -> bool:
        return True

    def load(self) -> float:
        t0 = time.perf_counter()
        # Simulate lightweight initialization
        self._is_loaded = True
        self._load_time_ms = (time.perf_counter() - t0) * 1000.0
        logger.info(
            "[MOCK ENGINE] Model '%s' (%s) berhasil diinisialisasi dalam %.3f ms (is_placeholder=%s).",
            self.config.model_id,
            self.config.task_type,
            self._load_time_ms,
            self.config.is_placeholder,
        )
        return self._load_time_ms

    def predict(self, preprocessed: PreprocessedInput) -> List[RawPrediction]:
        if not self._is_loaded:
            raise ModelNotLoadedError(
                f"MockInferenceEngine untuk model '{self.config.model_id}' belum dimuat (panggil load() terlebih dahulu)."
            )

        tensor = preprocessed.tensor
        if tensor.size == 0:
            raise ValueError("Preprocessed tensor kosong.")

        # Compute deterministic signal from image content so output reacts to input tensor
        mean_val = float(np.clip(np.abs(tensor).mean(), 0.0, 1.0))
        labels = self.config.labels
        primary_class_idx = int((mean_val * 100) % len(labels))
        primary_label = labels[primary_class_idx]
        primary_conf = round(min(0.98, max(self.config.confidence_threshold + 0.15, 0.72 + 0.15 * mean_val)), 4)

        orig_w = preprocessed.original_dimensions["width"]
        orig_h = preprocessed.original_dimensions["height"]

        if self.config.output_type == "classification":
            # Classification models do NOT emit bounding boxes
            return [
                RawPrediction(
                    label=primary_label,
                    class_id=primary_class_idx,
                    confidence=primary_conf,
                    bounding_box=None,
                    metadata={"engine": "MockInferenceEngine", "note": "classification_no_bbox"},
                )
            ]

        # Object detection / segmentation models emit pixel bounding boxes scaled to input image
        x_min = max(0, int(orig_w * 0.20))
        y_min = max(0, int(orig_h * 0.18))
        x_max = min(orig_w, int(orig_w * 0.75))
        y_max = min(orig_h, int(orig_h * 0.80))

        predictions = [
            RawPrediction(
                label=primary_label,
                class_id=primary_class_idx,
                confidence=primary_conf,
                bounding_box={
                    "x_min": x_min,
                    "y_min": y_min,
                    "x_max": x_max,
                    "y_max": y_max,
                },
                metadata={"engine": "MockInferenceEngine"},
            )
        ]

        # Add a secondary lower-confidence candidate to test threshold filtering
        if len(labels) > 1:
            sec_idx = (primary_class_idx + 1) % len(labels)
            predictions.append(
                RawPrediction(
                    label=labels[sec_idx],
                    class_id=sec_idx,
                    confidence=0.32,  # Below default 0.50 threshold unless threshold is lowered
                    bounding_box={
                        "x_min": max(0, int(orig_w * 0.05)),
                        "y_min": max(0, int(orig_h * 0.05)),
                        "x_max": min(orig_w, int(orig_w * 0.30)),
                        "y_max": min(orig_h, int(orig_h * 0.30)),
                    },
                    metadata={"engine": "MockInferenceEngine", "candidate": "secondary_low_conf"},
                )
            )

        return predictions


class RealModelEngineAdapter(BaseInferenceEngine):
    """Template adapter for integrating real trained AI models (ONNX / PyTorch / TFLite).

    Verifies that the model weights file actually exists on disk and initializes the
    selected runtime backend when available. Does NOT fabricate model weights or fake
    real inference when files are absent.
    """

    def __init__(self, config: ModelConfig, project_root: Optional[Path] = None) -> None:
        super().__init__(config, project_root)
        self._session: Optional[Any] = None

    @property
    def is_mock(self) -> bool:
        return False

    def resolve_weights_path(self) -> Path:
        raw_path = Path(self.config.weights_path)
        if raw_path.is_absolute():
            return raw_path
        return self.project_root / raw_path

    def load(self) -> float:
        t0 = time.perf_counter()
        weights_file = self.resolve_weights_path()
        if not weights_file.exists():
            raise ModelLoadError(
                f"File bobot model asli untuk '{self.config.model_id}' tidak ditemukan di: {weights_file}. "
                "Tempatkan file model yang sudah dilatih di direktori tersebut atau gunakan runtime_mode='mock'."
            )

        framework = self.config.framework.lower()
        if framework == "onnx":
            try:
                import onnxruntime as ort  # type: ignore[import-not-found]
            except ImportError as exc:
                raise ModelLoadError(
                    "Paket 'onnxruntime' belum terinstal. Instal dengan `pip install onnxruntime`."
                ) from exc
            self._session = ort.InferenceSession(
                str(weights_file), providers=["CPUExecutionProvider"]
            )
        elif framework == "tflite":
            try:
                import tflite_runtime.interpreter as tflite  # type: ignore[import-not-found]
            except ImportError as exc:
                raise ModelLoadError(
                    "Paket 'tflite-runtime' belum terinstal di lingkungan ini."
                ) from exc
            self._session = tflite.Interpreter(model_path=str(weights_file))
            self._session.allocate_tensors()
        elif framework == "pytorch":
            try:
                import torch  # type: ignore[import-not-found]
            except ImportError as exc:
                raise ModelLoadError(
                    "Paket 'torch' / 'ultralytics' belum terinstal di lingkungan ini."
                ) from exc
            self._session = torch.jit.load(str(weights_file), map_location="cpu")
        else:
            raise ModelLoadError(
                f"Model '{self.config.model_id}' dikonfigurasi dengan framework='{framework}'. "
                "Untuk model asli, ubah framework di config/models.yaml menjadi 'onnx', 'pytorch', atau 'tflite'."
            )

        self._is_loaded = True
        self._load_time_ms = (time.perf_counter() - t0) * 1000.0
        logger.info(
            "[REAL ENGINE] Model '%s' (%s) berhasil dimuat dari '%s' dalam %.2f ms.",
            self.config.model_id,
            framework,
            weights_file,
            self._load_time_ms,
        )
        return self._load_time_ms

    def predict(self, preprocessed: PreprocessedInput) -> List[RawPrediction]:
        if not self._is_loaded or self._session is None:
            raise ModelNotLoadedError(
                f"RealModelEngineAdapter untuk '{self.config.model_id}' belum dimuat."
            )
        # Note: Task-specific tensor post-processing (e.g. YOLO NMS vs Softmax classification)
        # depends on the exact output tensor shape of the trained model to be provided by the AI training team.
        raise NotImplementedError(
            f"Post-processing spesifik model untuk '{self.config.model_id}' menunggu spesifikasi "
            "output tensor dari file model asli (lihat docs/MODEL_INTEGRATION.md)."
        )

