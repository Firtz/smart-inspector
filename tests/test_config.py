"""Unit tests for configuration loading and validation (Week 1 & Week 2)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from src.execution.execution_config import (
    ConfigurationError,
    ModelInputSpec,
    load_app_config,
)


class TestConfigurationLoading(unittest.TestCase):
    """Verify `settings.yaml` and `models.yaml` loading, defaults, and error handling."""

    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[1]

    def test_load_default_configs_succeeds(self) -> None:
        config = load_app_config(project_root=self.project_root)
        self.assertEqual(config.runtime_mode, "mock")
        self.assertEqual(config.execution.mode, "sequential")
        self.assertEqual(len(config.models), 5)

        expected_ids = {
            "health_inspector",
            "pest_detector",
            "disease_detector",
            "flower_pollination",
            "ripeness_ffb",
        }
        self.assertEqual(set(config.models.keys()), expected_ids)

        active = config.get_active_models()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].model_id, "ripeness_ffb")
        self.assertTrue(active[0].is_placeholder)

    def test_environment_variable_overrides(self) -> None:
        old_mode = os.environ.get("SMART_INSPECTOR_EXECUTION_MODE")
        old_port = os.environ.get("SMART_INSPECTOR_API_PORT")
        try:
            os.environ["SMART_INSPECTOR_EXECUTION_MODE"] = "parallel"
            os.environ["SMART_INSPECTOR_API_PORT"] = "9090"
            config = load_app_config(project_root=self.project_root)
            self.assertEqual(config.execution.mode, "parallel")
            self.assertEqual(config.api.port, 9090)
        finally:
            if old_mode is None:
                os.environ.pop("SMART_INSPECTOR_EXECUTION_MODE", None)
            else:
                os.environ["SMART_INSPECTOR_EXECUTION_MODE"] = old_mode
            if old_port is None:
                os.environ.pop("SMART_INSPECTOR_API_PORT", None)
            else:
                os.environ["SMART_INSPECTOR_API_PORT"] = old_port

    def test_missing_config_file_raises_configuration_error(self) -> None:
        with self.assertRaises(ConfigurationError):
            load_app_config(
                settings_path="config/non_existent_settings.yaml",
                project_root=self.project_root,
            )

    def test_invalid_execution_mode_raises_configuration_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_settings = Path(tmpdir) / "bad_settings.yaml"
            bad_settings.write_text(
                "system:\n  runtime_mode: mock\nexecution:\n  mode: invalid_mode\n",
                encoding="utf-8",
            )
            with self.assertRaises(ConfigurationError):
                load_app_config(
                    settings_path=bad_settings,
                    project_root=self.project_root,
                )

    def test_invalid_input_spec_dimensions_raises_error(self) -> None:
        spec = ModelInputSpec(width=-10, height=640, channels=3)
        with self.assertRaises(ConfigurationError):
            spec.validate("broken_model")


if __name__ == "__main__":
    unittest.main()

