"""Main entrypoint for the Low-Cost Multi-Task Smart Inspector System (Weeks 1-2 Foundation).

Demonstrates:
1. Loading and validating system & 5-model registry configurations (`config/settings.yaml`, `config/models.yaml`).
2. Preparing or loading a sample input image (`tests/assets/sample_palm.ppm`).
3. Initializing the Week 2 vertical-slice inference pipeline (`InferenceManager`).
4. Publishing standardized inference results through the ROS 2 Publisher / Subscriber layer (or Mock ROS 2 bus).
5. Reporting hardware performance telemetry explicitly labeled with the host platform.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional, Sequence

from src.execution.execution_config import ConfigurationError, load_app_config
from src.inference.inference_manager import InferenceManager
from src.inference.preprocessor import (
    create_synthetic_palm_image,
    load_image_from_path,
    save_ppm_image,
)
from src.ros2.publisher import InferenceResultPublisher, is_ros2_available
from src.ros2.subscriber import InferenceResultSubscriber

logger = logging.getLogger("smart_inspector.main")


def setup_logging(level_name: str = "INFO") -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        force=True,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Smart Inspector System - Runner (Fondasi Minggu 1 & Minggu 2)"
    )
    parser.add_argument(
        "--settings",
        type=str,
        default=None,
        help="Path ke file settings.yaml (default: config/settings.yaml)",
    )
    parser.add_argument(
        "--models",
        type=str,
        default=None,
        help="Path ke file models.yaml (default: config/models.yaml)",
    )
    parser.add_argument(
        "--image",
        type=str,
        default=None,
        help="Path ke file gambar sampel untuk diuji (opsional)",
    )
    parser.add_argument(
        "--mode",
        choices=["sequential", "parallel"],
        default=None,
        help="Override mode eksekusi model (sequential / parallel)",
    )
    return parser


def run_application(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        app_config = load_app_config(
            settings_path=args.settings,
            models_path=args.models,
        )
    except ConfigurationError as exc:
        logging.basicConfig(level=logging.ERROR)
        logger.error("Konfigurasi tidak valid: %s", exc)
        return 2

    setup_logging(app_config.log_level)

    if args.mode:
        object.__setattr__(app_config.execution, "mode", args.mode)

    logger.info("==============================================================")
    logger.info("LOW-COST MULTI-TASK SMART INSPECTOR SYSTEM (v0.2.0 - Week 1&2)")
    logger.info("Node Name      : %s", app_config.node_name)
    logger.info("Environment    : %s", app_config.environment)
    logger.info("Runtime Mode   : %s (Mock=%s)", app_config.runtime_mode, app_config.runtime_mode == "mock")
    logger.info("Execution Mode : %s", app_config.execution.mode)
    logger.info("ROS 2 Native   : %s (Enabled in config=%s)", is_ros2_available(), app_config.ros2.enabled)
    logger.info("Registered AI  : %d models (%s)", len(app_config.models), ", ".join(app_config.models.keys()))
    logger.info("Active Models  : %s", [m.model_id for m in app_config.get_active_models()])
    logger.info("==============================================================")

    # Prepare input image
    image_rel = args.image or app_config.input_source.sample_image_path
    image_path = Path(image_rel)
    if not image_path.is_absolute():
        image_path = app_config.project_root / image_path

    if not image_path.exists():
        w, h = app_config.input_source.default_resolution
        logger.info(
            "File sampel gambar belum ada di '%s'. Membuat citra sintetis kelapa sawit (%dx%d)...",
            image_path,
            w,
            h,
        )
        synthetic_img = create_synthetic_palm_image(width=w, height=h, channels=3)
        if image_path.suffix.lower() == ".ppm":
            save_ppm_image(image_path, synthetic_img)
            image = load_image_from_path(image_path)
        else:
            image = synthetic_img
    else:
        logger.info("Memuat citra input dari: %s", image_path)
        image = load_image_from_path(image_path)

    # Initialize InferenceManager & load active models
    manager = InferenceManager(app_config=app_config)
    load_times = manager.load_active_models()
    logger.info("Waktu inisialisasi/pemuatan model (ms): %s", load_times)

    # Initialize ROS 2 Publisher & Subscriber (uses Mock bus automatically if ROS 2 is unavailable/disabled)
    use_mock_ros = (not app_config.ros2.enabled) or (not is_ros2_available())
    topic_results = app_config.ros2.topics.get(
        "inference_results", "/smart_inspector/inference/results"
    )
    publisher = InferenceResultPublisher(
        node_name=app_config.ros2.node_name,
        topic_name=topic_results,
        qos_depth=app_config.ros2.qos_depth,
        use_mock=use_mock_ros,
    )
    subscriber = InferenceResultSubscriber(
        node_name=f"{app_config.ros2.node_name}_verifier",
        topic_name=topic_results,
        qos_depth=app_config.ros2.qos_depth,
        use_mock=use_mock_ros,
    )
    if use_mock_ros:
        publisher.register_local_callback(subscriber.handle_raw_message)

    try:
        results, metrics = manager.run_inspection_cycle(image=image)
        for res in results:
            publisher.publish_result(res)

        logger.info("--- HASIL INFERENSI TERSTANDARISASI (JSON) ---")
        print(json.dumps(results, indent=2, ensure_ascii=False))

        logger.info("--- METRIK PERFORMA & PERANGKAT KERAS ---")
        print(json.dumps(metrics.to_dict(), indent=2, ensure_ascii=False))

    finally:
        publisher.close()
        subscriber.close()
        manager.shutdown()

    return 0


if __name__ == "__main__":
    sys.exit(run_application())

