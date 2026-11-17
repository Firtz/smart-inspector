"""Unit tests for Week 2 AI Inference vertical slice:
- Input validation
- Preprocessing
- Mock inference (Object Detection & Classification)
- Output normalization & JSON Schema validation
- Error handling (missing real weights, invalid input, unloaded model)
- Inference timing & performance metrics
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.execution.execution_config import ModelInputSpec, load_app_config
from src.inference.inference_engine import (
    MockInferenceEngine,
    ModelLoadError,
    ModelNotLoadedError,
    RealModelEngineAdapter,
)
from src.inference.inference_manager import InferenceManager
from src.inference.model_loader import ModelLoader
from src.inference.preprocessor import (
    InputValidationError,
    StandardImagePreprocessor,
    create_synthetic_palm_image,
    load_image_from_path,
    save_ppm_image,
)
from src.inference.result_normalizer import (
    RawPrediction,
    ResultNormalizer,
    ResultValidationError,
    validate_inference_result,
)


class TestInferencePipeline(unittest.TestCase):
    """Comprehensive tests for Week 2 reusable inference components."""

    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[1]
        self.app_config = load_app_config(project_root=self.project_root)
        self.preprocessor = StandardImagePreprocessor()
        self.normalizer = ResultNormalizer()

    def test_input_validation_rejects_invalid_arrays(self) -> None:
        # Non-ndarray input
        with self.assertRaises(InputValidationError):
            self.preprocessor.validate_image("not_an_image")  # type: ignore[arg-type]

        # Empty array
        with self.assertRaises(InputValidationError):
            self.preprocessor.validate_image(np.array([], dtype=np.uint8))

        # Invalid 4-channel RGBA image
        with self.assertRaises(InputValidationError):
            self.preprocessor.validate_image(np.zeros((100, 100, 4), dtype=np.uint8))

    def test_preprocessing_resizes_and_normalizes_to_nchw(self) -> None:
        raw_img = create_synthetic_palm_image(width=800, height=600, channels=3)
        spec = ModelInputSpec(
            width=640,
            height=640,
            channels=3,
            color_format="RGB",
            scale="0_to_1",
            mean=(0.0, 0.0, 0.0),
            std=(1.0, 1.0, 1.0),
        )
        result = self.preprocessor.preprocess(raw_img, spec)
        self.assertEqual(result.original_dimensions, {"width": 800, "height": 600, "channels": 3})
        self.assertEqual(result.model_dimensions, {"width": 640, "height": 640, "channels": 3})
        self.assertEqual(result.tensor.shape, (1, 3, 640, 640))
        self.assertEqual(result.tensor.dtype, np.float32)
        self.assertGreaterEqual(float(result.tensor.min()), 0.0)
        self.assertLessEqual(float(result.tensor.max()), 1.0)

    def test_ppm_image_save_and_load_roundtrip(self) -> None:
        img = create_synthetic_palm_image(width=120, height=80, channels=3)
        with tempfile.TemporaryDirectory() as tmpdir:
            ppm_path = Path(tmpdir) / "sample.ppm"
            save_ppm_image(ppm_path, img)
            loaded = load_image_from_path(ppm_path)
            self.assertEqual(loaded.shape, (80, 120, 3))
            np.testing.assert_array_equal(img, loaded)

    def test_mock_inference_object_detection_vs_classification(self) -> None:
        raw_img = create_synthetic_palm_image(width=640, height=640, channels=3)

        # 1. Object detection model (ripeness_ffb) -> has bounding_box
        ripeness_cfg = self.app_config.models["ripeness_ffb"]
        ripeness_engine = MockInferenceEngine(ripeness_cfg, project_root=self.project_root)
        load_ms = ripeness_engine.load()
        self.assertTrue(ripeness_engine.is_loaded)
        self.assertGreaterEqual(load_ms, 0.0)

        pre_ripeness = self.preprocessor.preprocess(raw_img, ripeness_cfg.input_spec)
        preds_ripeness = ripeness_engine.predict(pre_ripeness)
        norm_ripeness = self.normalizer.normalize_success(
            model_id=ripeness_cfg.model_id,
            task_type=ripeness_cfg.task_type,
            output_type=ripeness_cfg.output_type,
            is_mock=True,
            input_dimensions=pre_ripeness.original_dimensions,
            raw_predictions=preds_ripeness,
            inference_time_ms=5.2,
            confidence_threshold=ripeness_cfg.confidence_threshold,
        )
        validate_inference_result(norm_ripeness)
        self.assertEqual(norm_ripeness["status"], "success")
        self.assertIsNotNone(norm_ripeness["bounding_box"])
        self.assertEqual(len(norm_ripeness["detections"]), 1)

        # 2. Classification model (health_inspector) -> bounding_box MUST be None
        health_cfg = self.app_config.models["health_inspector"]
        health_engine = MockInferenceEngine(health_cfg, project_root=self.project_root)
        health_engine.load()
        pre_health = self.preprocessor.preprocess(raw_img, health_cfg.input_spec)
        preds_health = health_engine.predict(pre_health)
        norm_health = self.normalizer.normalize_success(
            model_id=health_cfg.model_id,
            task_type=health_cfg.task_type,
            output_type=health_cfg.output_type,
            is_mock=True,
            input_dimensions=pre_health.original_dimensions,
            raw_predictions=preds_health,
            inference_time_ms=3.1,
            confidence_threshold=health_cfg.confidence_threshold,
        )
        validate_inference_result(norm_health)
        self.assertIsNone(norm_health["bounding_box"])
        self.assertIsNone(norm_health["detections"][0]["bounding_box"])

    def test_output_normalization_schema_rejects_invalid_bbox(self) -> None:
        bad_pred = RawPrediction(
            label="PLACEHOLDER_FFB_RIPE",
            class_id=1,
            confidence=0.85,
            bounding_box={"x_min": 500, "y_min": 500, "x_max": 100, "y_max": 100},
        )
        with self.assertRaises(ResultValidationError):
            self.normalizer.normalize_success(
                model_id="ripeness_ffb",
                task_type="ffb_ripeness",
                output_type="object_detection",
                is_mock=True,
                input_dimensions={"width": 640, "height": 640, "channels": 3},
                raw_predictions=[bad_pred],
                inference_time_ms=4.0,
            )

    def test_error_handling_unloaded_engine_and_missing_real_weights(self) -> None:
        ripeness_cfg = self.app_config.models["ripeness_ffb"]
        unloaded_engine = MockInferenceEngine(ripeness_cfg)
        raw_img = create_synthetic_palm_image(width=320, height=320, channels=3)
        pre = self.preprocessor.preprocess(raw_img, ripeness_cfg.input_spec)

        with self.assertRaises(ModelNotLoadedError):
            unloaded_engine.predict(pre)

        # Real adapter must fail explicitly if weight file does not exist
        real_adapter = RealModelEngineAdapter(ripeness_cfg, project_root=self.project_root)
        with self.assertRaises(ModelLoadError):
            real_adapter.load()

        # ModelLoader in 'real' mode must reject placeholder 'mock' framework configs
        real_loader = ModelLoader(runtime_mode="real", project_root=self.project_root)
        with self.assertRaises(ModelLoadError):
            real_loader.load_model(ripeness_cfg)

    def test_inference_manager_cycle_timing_and_error_recovery(self) -> None:
        manager = InferenceManager(self.app_config)
        load_times = manager.load_active_models()
        self.assertIn("ripeness_ffb", load_times)
        self.assertGreaterEqual(load_times["ripeness_ffb"], 0.0)

        img = create_synthetic_palm_image(width=640, height=640, channels=3)
        results, metrics = manager.run_inspection_cycle(img)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "success")
        self.assertGreater(results[0]["inference_time_ms"], 0.0)
        self.assertGreater(metrics.total_inference_time_ms, 0.0)
        self.assertGreater(metrics.memory_rss_mb, 0.0)
        self.assertFalse(metrics.is_raspberry_pi)

        # Error recovery on invalid empty image returns standardized error dictionary without crashing
        bad_res = manager.run_single_model("ripeness_ffb", np.array([], dtype=np.uint8))
        validate_inference_result(bad_res)
        self.assertEqual(bad_res["status"], "error")
        self.assertEqual(bad_res["error"]["code"], "INVALID_INPUT_IMAGE")

        manager.shutdown()

    def test_inference_manager_parallel_execution_mode(self) -> None:
        # Enable two models and test parallel execution
        object.__setattr__(self.app_config.execution, "mode", "parallel")
        object.__setattr__(
            self.app_config.execution,
            "enabled_models",
            ["ripeness_ffb", "health_inspector"],
        )
        manager = InferenceManager(self.app_config)
        manager.load_active_models()

        img = create_synthetic_palm_image(width=640, height=640, channels=3)
        results, metrics = manager.run_inspection_cycle(img)
        self.assertEqual(len(results), 2)
        self.assertEqual(metrics.execution_mode, "parallel")
        for res in results:
            validate_inference_result(res)
            self.assertEqual(res["status"], "success")
        manager.shutdown()


if __name__ == "__main__":
    unittest.main()

