"""Configuration loader and validation module for Smart Inspector System.

Loads and validates `config/settings.yaml` and `config/models.yaml` with
support for environment variable overrides.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)

VALID_RUNTIME_MODES = {"mock", "real"}
VALID_EXECUTION_MODES = {"sequential", "parallel"}
VALID_INPUT_TYPES = {"image_file", "synthetic", "usb_camera", "drone_stream"}
VALID_TASK_TYPES = {
    "plant_health",
    "pest_indication",
    "disease_indication",
    "flower_pollination",
    "ffb_ripeness",
}
VALID_OUTPUT_TYPES = {"classification", "object_detection", "segmentation"}
VALID_FRAMEWORKS = {"mock", "onnx", "pytorch", "tflite"}


class ConfigurationError(ValueError):
    """Raised when configuration files are missing, malformed, or invalid."""


@dataclass(frozen=True)
class ModelInputSpec:
    """Input tensor specification for an AI model."""

    width: int = 640
    height: int = 640
    channels: int = 3
    color_format: str = "RGB"
    scale: str = "0_to_1"
    mean: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    std: Tuple[float, float, float] = (1.0, 1.0, 1.0)

    def validate(self, model_id: str) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ConfigurationError(
                f"Model '{model_id}' memiliki dimensi input tidak valid: "
                f"{self.width}x{self.height} (harus > 0)."
            )
        if self.channels not in (1, 3):
            raise ConfigurationError(
                f"Model '{model_id}' memiliki jumlah channel tidak valid: "
                f"{self.channels} (harus 1 atau 3)."
            )
        if self.color_format not in ("RGB", "BGR", "GRAY"):
            raise ConfigurationError(
                f"Model '{model_id}' memiliki color_format tidak valid: {self.color_format}."
            )
        if self.scale not in ("0_to_1", "0_to_255"):
            raise ConfigurationError(
                f"Model '{model_id}' memiliki scale tidak valid: {self.scale}."
            )


@dataclass(frozen=True)
class ModelConfig:
    """Configuration for a single AI detection task model."""

    model_id: str
    name: str
    task_type: str
    output_type: str
    enabled: bool
    is_placeholder: bool
    framework: str
    weights_path: str
    input_spec: ModelInputSpec
    confidence_threshold: float = 0.50
    iou_threshold: float = 0.45
    labels: List[str] = field(default_factory=list)
    description: str = ""

    def validate(self) -> None:
        if not self.model_id:
            raise ConfigurationError("model_id tidak boleh kosong.")
        if self.task_type not in VALID_TASK_TYPES:
            raise ConfigurationError(
                f"Model '{self.model_id}' memiliki task_type '{self.task_type}' yang tidak dikenal. "
                f"Pilihan valid: {sorted(VALID_TASK_TYPES)}"
            )
        if self.output_type not in VALID_OUTPUT_TYPES:
            raise ConfigurationError(
                f"Model '{self.model_id}' memiliki output_type '{self.output_type}' yang tidak valid. "
                f"Pilihan valid: {sorted(VALID_OUTPUT_TYPES)}"
            )
        if self.framework not in VALID_FRAMEWORKS:
            raise ConfigurationError(
                f"Model '{self.model_id}' memiliki framework '{self.framework}' yang tidak valid. "
                f"Pilihan valid: {sorted(VALID_FRAMEWORKS)}"
            )
        if not (0.0 <= self.confidence_threshold <= 1.0):
            raise ConfigurationError(
                f"Model '{self.model_id}' memiliki confidence_threshold={self.confidence_threshold} "
                "(harus di antara 0.0 dan 1.0)."
            )
        if not self.labels:
            raise ConfigurationError(
                f"Model '{self.model_id}' harus memiliki minimal satu label kelas."
            )
        self.input_spec.validate(self.model_id)


@dataclass(frozen=True)
class ExecutionSettings:
    """Settings controlling model execution mode and concurrency."""

    mode: str = "sequential"
    max_workers: int = 2
    timeout_ms: int = 5000
    enabled_models: List[str] = field(default_factory=list)

    def validate(self) -> None:
        if self.mode not in VALID_EXECUTION_MODES:
            raise ConfigurationError(
                f"Mode eksekusi '{self.mode}' tidak valid. Pilihan valid: {sorted(VALID_EXECUTION_MODES)}"
            )
        if self.max_workers < 1:
            raise ConfigurationError("max_workers harus >= 1.")
        if self.timeout_ms <= 0:
            raise ConfigurationError("timeout_ms harus > 0.")


@dataclass(frozen=True)
class InputSourceSettings:
    """Settings controlling image/camera input source."""

    type: str = "image_file"
    sample_image_path: str = "tests/assets/sample_palm.ppm"
    default_resolution: Tuple[int, int] = (640, 640)
    camera_device_id: int = 0

    def validate(self) -> None:
        if self.type not in VALID_INPUT_TYPES:
            raise ConfigurationError(
                f"Input source type '{self.type}' tidak valid. Pilihan valid: {sorted(VALID_INPUT_TYPES)}"
            )
        if self.default_resolution[0] <= 0 or self.default_resolution[1] <= 0:
            raise ConfigurationError("default_resolution harus memiliki lebar dan tinggi > 0.")


@dataclass(frozen=True)
class ROS2Settings:
    """Settings for ROS 2 node and topic names."""

    enabled: bool = False
    node_name: str = "smart_inspector_inference_node"
    topics: Dict[str, str] = field(
        default_factory=lambda: {
            "inference_results": "/smart_inspector/inference/results",
            "system_status": "/smart_inspector/system/status",
            "heartbeat": "/smart_inspector/system/heartbeat",
        }
    )
    qos_depth: int = 10
    publish_rate_hz: float = 1.0

    def validate(self) -> None:
        if not self.node_name:
            raise ConfigurationError("ros2.node_name tidak boleh kosong.")
        if self.qos_depth < 1:
            raise ConfigurationError("ros2.qos_depth harus >= 1.")
        if self.publish_rate_hz <= 0:
            raise ConfigurationError("ros2.publish_rate_hz harus > 0.")


@dataclass(frozen=True)
class APISettings:
    """Settings for local intranet API server."""

    enabled: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    version_prefix: str = "/api/v1"
    max_history_size: int = 100

    def validate(self) -> None:
        if not (1 <= self.port <= 65535):
            raise ConfigurationError(f"api.port={self.port} tidak valid (harus 1..65535).")
        if self.max_history_size < 1:
            raise ConfigurationError("api.max_history_size harus >= 1.")


@dataclass(frozen=True)
class AppConfig:
    """Complete validated application configuration."""

    node_name: str
    environment: str
    runtime_mode: str
    log_level: str
    execution: ExecutionSettings
    input_source: InputSourceSettings
    ros2: ROS2Settings
    api: APISettings
    models: Dict[str, ModelConfig]
    project_root: Path

    def validate(self) -> None:
        if self.runtime_mode not in VALID_RUNTIME_MODES:
            raise ConfigurationError(
                f"runtime_mode '{self.runtime_mode}' tidak valid. Pilihan valid: {sorted(VALID_RUNTIME_MODES)}"
            )
        self.execution.validate()
        self.input_source.validate()
        self.ros2.validate()
        self.api.validate()

        if not self.models:
            raise ConfigurationError("Registri model kosong; minimal 1 model harus terdaftar.")

        for model_id, model_cfg in self.models.items():
            model_cfg.validate()

        for enabled_id in self.execution.enabled_models:
            if enabled_id not in self.models:
                raise ConfigurationError(
                    f"Model '{enabled_id}' di execution.enabled_models tidak ditemukan di models.yaml. "
                    f"Model yang tersedia: {sorted(self.models.keys())}"
                )

    def get_active_models(self) -> List[ModelConfig]:
        """Return the ordered list of active ModelConfig objects for execution."""
        if self.execution.enabled_models:
            return [self.models[m_id] for m_id in self.execution.enabled_models]
        return [m for m in self.models.values() if m.enabled]


def _load_yaml_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise ConfigurationError(f"File konfigurasi tidak ditemukan: {path}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            content = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Gagal mem-parsing YAML pada {path}: {exc}") from exc

    if not isinstance(content, dict):
        raise ConfigurationError(f"Format YAML pada {path} harus berupa dictionary/mapping di level root.")
    return content


def _parse_model_config(model_key: str, raw: Dict[str, Any]) -> ModelConfig:
    raw_spec = raw.get("input_spec", {}) or {}
    mean_raw = raw_spec.get("mean", [0.0, 0.0, 0.0])
    std_raw = raw_spec.get("std", [1.0, 1.0, 1.0])

    input_spec = ModelInputSpec(
        width=int(raw_spec.get("width", 640)),
        height=int(raw_spec.get("height", 640)),
        channels=int(raw_spec.get("channels", 3)),
        color_format=str(raw_spec.get("color_format", "RGB")),
        scale=str(raw_spec.get("scale", "0_to_1")),
        mean=(float(mean_raw[0]), float(mean_raw[1]), float(mean_raw[2])),
        std=(float(std_raw[0]), float(std_raw[1]), float(std_raw[2])),
    )

    return ModelConfig(
        model_id=str(raw.get("model_id", model_key)),
        name=str(raw.get("name", model_key)),
        task_type=str(raw.get("task_type", "")),
        output_type=str(raw.get("output_type", "object_detection")),
        enabled=bool(raw.get("enabled", False)),
        is_placeholder=bool(raw.get("is_placeholder", True)),
        framework=str(raw.get("framework", "mock")),
        weights_path=str(raw.get("weights_path", "")),
        input_spec=input_spec,
        confidence_threshold=float(raw.get("confidence_threshold", 0.50)),
        iou_threshold=float(raw.get("iou_threshold", 0.45)),
        labels=[str(lbl) for lbl in raw.get("labels", [])],
        description=str(raw.get("description", "")),
    )


def load_app_config(
    settings_path: Optional[Path | str] = None,
    models_path: Optional[Path | str] = None,
    project_root: Optional[Path | str] = None,
) -> AppConfig:
    """Load and validate application configuration from YAML files and environment variables."""
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[2]

    env_settings = os.environ.get("SMART_INSPECTOR_SETTINGS_PATH")
    env_models = os.environ.get("SMART_INSPECTOR_MODELS_PATH")

    resolved_settings_path = Path(settings_path or env_settings or (root / "config" / "settings.yaml"))
    if not resolved_settings_path.is_absolute():
        resolved_settings_path = root / resolved_settings_path

    resolved_models_path = Path(models_path or env_models or (root / "config" / "models.yaml"))
    if not resolved_models_path.is_absolute():
        resolved_models_path = root / resolved_models_path

    settings_raw = _load_yaml_file(resolved_settings_path)
    models_raw = _load_yaml_file(resolved_models_path)

    sys_raw = settings_raw.get("system", {}) or {}
    exec_raw = settings_raw.get("execution", {}) or {}
    input_raw = settings_raw.get("input_source", {}) or {}
    ros2_raw = settings_raw.get("ros2", {}) or {}
    api_raw = settings_raw.get("api", {}) or {}

    runtime_mode = os.environ.get(
        "SMART_INSPECTOR_RUNTIME_MODE", str(sys_raw.get("runtime_mode", "mock"))
    ).lower()
    exec_mode = os.environ.get(
        "SMART_INSPECTOR_EXECUTION_MODE", str(exec_raw.get("mode", "sequential"))
    ).lower()
    log_level = os.environ.get(
        "SMART_INSPECTOR_LOG_LEVEL", str(sys_raw.get("log_level", "INFO"))
    ).upper()

    ros2_enabled_env = os.environ.get("SMART_INSPECTOR_ROS2_ENABLED")
    if ros2_enabled_env is not None:
        ros2_enabled = ros2_enabled_env.strip().lower() in ("1", "true", "yes")
    else:
        ros2_enabled = bool(ros2_raw.get("enabled", False))

    api_host = os.environ.get("SMART_INSPECTOR_API_HOST", str(api_raw.get("host", "0.0.0.0")))
    api_port = int(os.environ.get("SMART_INSPECTOR_API_PORT", api_raw.get("port", 8000)))

    res_list = input_raw.get("default_resolution", [640, 640])
    default_resolution = (int(res_list[0]), int(res_list[1]))

    execution_settings = ExecutionSettings(
        mode=exec_mode,
        max_workers=int(exec_raw.get("max_workers", 2)),
        timeout_ms=int(exec_raw.get("timeout_ms", 5000)),
        enabled_models=[str(m) for m in exec_raw.get("enabled_models", [])],
    )

    input_settings = InputSourceSettings(
        type=str(input_raw.get("type", "image_file")),
        sample_image_path=str(input_raw.get("sample_image_path", "tests/assets/sample_palm.ppm")),
        default_resolution=default_resolution,
        camera_device_id=int(input_raw.get("camera_device_id", 0)),
    )

    ros2_settings = ROS2Settings(
        enabled=ros2_enabled,
        node_name=str(ros2_raw.get("node_name", "smart_inspector_inference_node")),
        topics=dict(ros2_raw.get("topics", {})),
        qos_depth=int(ros2_raw.get("qos_depth", 10)),
        publish_rate_hz=float(ros2_raw.get("publish_rate_hz", 1.0)),
    )

    api_settings = APISettings(
        enabled=bool(api_raw.get("enabled", False)),
        host=api_host,
        port=api_port,
        version_prefix=str(api_raw.get("version_prefix", "/api/v1")),
        max_history_size=int(api_raw.get("max_history_size", 100)),
    )

    models_dict_raw = models_raw.get("models", {})
    if not isinstance(models_dict_raw, dict):
        raise ConfigurationError("Bagian 'models' di models.yaml harus berupa mapping/dictionary.")

    parsed_models: Dict[str, ModelConfig] = {}
    for model_key, model_entry in models_dict_raw.items():
        if not isinstance(model_entry, dict):
            raise ConfigurationError(f"Entri model '{model_key}' harus berupa mapping/dictionary.")
        cfg = _parse_model_config(model_key, model_entry)
        parsed_models[cfg.model_id] = cfg

    app_config = AppConfig(
        node_name=str(sys_raw.get("node_name", "smart_inspector_companion")),
        environment=str(sys_raw.get("environment", "development")),
        runtime_mode=runtime_mode,
        log_level=log_level,
        execution=execution_settings,
        input_source=input_settings,
        ros2=ros2_settings,
        api=api_settings,
        models=parsed_models,
        project_root=root,
    )
    app_config.validate()
    logger.debug(
        "Berhasil memuat konfigurasi: mode=%s, execution=%s, total_models=%d, active_models=%s",
        app_config.runtime_mode,
        app_config.execution.mode,
        len(app_config.models),
        [m.model_id for m in app_config.get_active_models()],
    )
    return app_config

