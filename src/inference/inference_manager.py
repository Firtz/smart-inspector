"""InferenceManager orchestrating model loading, preprocessing, sequential/parallel execution,
result normalization, and hardware performance telemetry.
"""

from __future__ import annotations

import logging
import os
import platform
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import psutil

from src.execution.execution_config import AppConfig, ModelConfig
from src.inference.inference_engine import BaseInferenceEngine
from src.inference.model_loader import ModelLoader
from src.inference.preprocessor import (
    BasePreprocessor,
    InputValidationError,
    StandardImagePreprocessor,
)
from src.inference.result_normalizer import ResultNormalizer

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Hardware and runtime telemetry recorded during an inference run."""

    hardware_platform: str
    processor_name: str
    is_raspberry_pi: bool
    runtime_mode: str
    execution_mode: str
    model_load_times_ms: Dict[str, float] = field(default_factory=dict)
    total_inference_time_ms: float = 0.0
    per_model_inference_ms: Dict[str, float] = field(default_factory=dict)
    memory_rss_mb: float = 0.0
    memory_percent: float = 0.0
    cpu_percent: float = 0.0
    input_dimensions: Dict[str, int] = field(default_factory=dict)
    total_detections: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hardware_platform": self.hardware_platform,
            "processor_name": self.processor_name,
            "is_raspberry_pi": self.is_raspberry_pi,
            "runtime_mode": self.runtime_mode,
            "execution_mode": self.execution_mode,
            "model_load_times_ms": dict(self.model_load_times_ms),
            "total_inference_time_ms": round(self.total_inference_time_ms, 3),
            "per_model_inference_ms": {
                k: round(v, 3) for k, v in self.per_model_inference_ms.items()
            },
            "memory_rss_mb": round(self.memory_rss_mb, 2),
            "memory_percent": round(self.memory_percent, 2),
            "cpu_percent": round(self.cpu_percent, 2),
            "input_dimensions": dict(self.input_dimensions),
            "total_detections": self.total_detections,
        }


def detect_hardware_context() -> tuple[str, str, bool]:
    """Identify host OS/architecture and explicitly distinguish Laptop host from Raspberry Pi 5."""
    sys_name = platform.system()
    release = platform.release()
    machine = platform.machine()
    proc = platform.processor() or machine
    platform_str = f"{sys_name} {release} ({machine})"

    is_rpi = False
    model_file = "/proc/device-tree/model"
    if os.path.exists(model_file):
        try:
            with open(model_file, "r", encoding="utf-8", errors="ignore") as f:
                model_text = f.read().strip("\x00").strip()
                if "Raspberry Pi" in model_text:
                    is_rpi = True
                    proc = model_text
        except OSError:
            pass

    return platform_str, proc, is_rpi


class InferenceManager:
    """Coordinates preprocessing, model execution (sequential/parallel), normalization, and telemetry."""

    def __init__(
        self,
        app_config: AppConfig,
        preprocessor: Optional[BasePreprocessor] = None,
        normalizer: Optional[ResultNormalizer] = None,
        loader: Optional[ModelLoader] = None,
    ) -> None:
        self.app_config = app_config
        self.preprocessor = preprocessor or StandardImagePreprocessor()
        self.normalizer = normalizer or ResultNormalizer()
        self.loader = loader or ModelLoader(
            runtime_mode=app_config.runtime_mode,
            project_root=app_config.project_root,
        )
        self._engines: Dict[str, BaseInferenceEngine] = {}
        self._process = psutil.Process(os.getpid())
        # Prime cpu_percent measurement
        self._process.cpu_percent(interval=None)

    @property
    def loaded_engines(self) -> Dict[str, BaseInferenceEngine]:
        return dict(self._engines)

    def load_active_models(self) -> Dict[str, float]:
        """Load all active models configured in `app_config` and return load times (ms)."""
        active_configs = self.app_config.get_active_models()
        load_times: Dict[str, float] = {}
        for cfg in active_configs:
            engine = self.loader.load_model(cfg)
            self._engines[cfg.model_id] = engine
            load_times[cfg.model_id] = round(engine.load_time_ms, 3)
        return load_times

    def run_single_model(self, model_id: str, image: np.ndarray) -> Dict[str, Any]:
        """Run validation, preprocessing, inference, and normalization for one model.

        Handles errors explicitly and returns a standardized error dictionary if input
        or runtime execution fails.
        """
        if model_id not in self.app_config.models:
            raise KeyError(f"Model '{model_id}' tidak terdaftar di konfigurasi.")

        cfg: ModelConfig = self.app_config.models[model_id]
        engine = self._engines.get(model_id)
        is_mock = True if engine is None else engine.is_mock

        t_start = time.perf_counter()
        raw_dims: Optional[Dict[str, int]] = None

        try:
            raw_dims = self.preprocessor.validate_image(image)
            if engine is None or not engine.is_loaded:
                raise RuntimeError(
                    f"Engine untuk model '{model_id}' belum dimuat. Panggil load_active_models() terlebih dahulu."
                )

            preprocessed = self.preprocessor.preprocess(image, cfg.input_spec)
            raw_predictions = engine.predict(preprocessed)
            elapsed_ms = (time.perf_counter() - t_start) * 1000.0

            return self.normalizer.normalize_success(
                model_id=cfg.model_id,
                task_type=cfg.task_type,
                output_type=cfg.output_type,
                is_mock=engine.is_mock,
                input_dimensions=raw_dims,
                raw_predictions=raw_predictions,
                inference_time_ms=elapsed_ms,
                confidence_threshold=cfg.confidence_threshold,
            )

        except InputValidationError as exc:
            elapsed_ms = (time.perf_counter() - t_start) * 1000.0
            logger.error("Validasi input gagal pada model '%s': %s", model_id, exc)
            return self.normalizer.normalize_error(
                model_id=cfg.model_id,
                task_type=cfg.task_type,
                output_type=cfg.output_type,
                is_mock=is_mock,
                input_dimensions=raw_dims,
                error_code="INVALID_INPUT_IMAGE",
                error_message=str(exc),
                inference_time_ms=elapsed_ms,
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - t_start) * 1000.0
            logger.error("Eksekusi inferensi gagal pada model '%s': %s", model_id, exc)
            return self.normalizer.normalize_error(
                model_id=cfg.model_id,
                task_type=cfg.task_type,
                output_type=cfg.output_type,
                is_mock=is_mock,
                input_dimensions=raw_dims,
                error_code="INFERENCE_EXECUTION_ERROR",
                error_message=str(exc),
                inference_time_ms=elapsed_ms,
            )

    def run_inspection_cycle(
        self, image: np.ndarray, model_ids: Optional[List[str]] = None
    ) -> tuple[List[Dict[str, Any]], PerformanceMetrics]:
        """Execute all target models in configured mode (`sequential` or `parallel`) and collect metrics."""
        target_ids = model_ids or [m.model_id for m in self.app_config.get_active_models()]
        mode = self.app_config.execution.mode

        t_cycle_start = time.perf_counter()

        if mode == "parallel" and len(target_ids) > 1:
            max_workers = min(self.app_config.execution.max_workers, len(target_ids))
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                results = list(pool.map(lambda mid: self.run_single_model(mid, image), target_ids))
        else:
            results = [self.run_single_model(mid, image) for mid in target_ids]

        total_cycle_ms = (time.perf_counter() - t_cycle_start) * 1000.0

        mem_info = self._process.memory_info()
        mem_rss_mb = mem_info.rss / (1024.0 * 1024.0)
        mem_pct = self._process.memory_percent()
        cpu_pct = psutil.cpu_percent(interval=None)

        hw_platform, proc_name, is_rpi = detect_hardware_context()
        load_times = {
            mid: round(eng.load_time_ms, 3) for mid, eng in self._engines.items()
        }
        per_model_ms = {
            res["model_id"]: float(res["inference_time_ms"]) for res in results
        }
        total_dets = sum(len(res.get("detections", [])) for res in results)
        input_dims = results[0]["input_dimensions"] if results else {"width": 0, "height": 0, "channels": 0}

        metrics = PerformanceMetrics(
            hardware_platform=hw_platform,
            processor_name=proc_name,
            is_raspberry_pi=is_rpi,
            runtime_mode=self.app_config.runtime_mode,
            execution_mode=mode,
            model_load_times_ms=load_times,
            total_inference_time_ms=total_cycle_ms,
            per_model_inference_ms=per_model_ms,
            memory_rss_mb=mem_rss_mb,
            memory_percent=mem_pct,
            cpu_percent=cpu_pct,
            input_dimensions=input_dims,
            total_detections=total_dets,
        )

        logger.info(
            "Siklus inspeksi selesai: mode=%s, models=%d, total_time=%.2f ms, detections=%d, RAM=%.1f MB",
            mode,
            len(results),
            total_cycle_ms,
            total_dets,
            mem_rss_mb,
        )
        return results, metrics

    def shutdown(self) -> None:
        """Unload all active engines cleanly."""
        for eng in self._engines.values():
            eng.unload()
        self._engines.clear()

