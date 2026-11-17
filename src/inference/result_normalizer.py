"""Standardized inference output schema and ResultNormalizer.

Ensures every AI model (whether classification, object detection, or segmentation,
and whether mock or real) produces a consistent JSON-serializable structure
ready for ROS 2 publishing and the local Dashboard API.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import jsonschema

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1.0"

INFERENCE_RESULT_JSON_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "SmartInspectorInferenceResult",
    "type": "object",
    "required": [
        "schema_version",
        "timestamp",
        "model_id",
        "task_type",
        "output_type",
        "is_mock",
        "status",
        "input_dimensions",
        "detections",
        "confidence",
        "bounding_box",
        "inference_time_ms",
        "error",
    ],
    "properties": {
        "schema_version": {"type": "string"},
        "timestamp": {"type": "string", "minLength": 10},
        "model_id": {"type": "string", "minLength": 1},
        "task_type": {
            "type": "string",
            "enum": [
                "plant_health",
                "pest_indication",
                "disease_indication",
                "flower_pollination",
                "ffb_ripeness",
            ],
        },
        "output_type": {
            "type": "string",
            "enum": ["classification", "object_detection", "segmentation"],
        },
        "is_mock": {"type": "boolean"},
        "status": {"type": "string", "enum": ["success", "error"]},
        "input_dimensions": {
            "type": "object",
            "required": ["width", "height", "channels"],
            "properties": {
                "width": {"type": "integer", "minimum": 1},
                "height": {"type": "integer", "minimum": 1},
                "channels": {"type": "integer", "enum": [1, 3]},
            },
        },
        "detections": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["label", "class_id", "confidence", "bounding_box"],
                "properties": {
                    "label": {"type": "string", "minLength": 1},
                    "class_id": {"type": "integer", "minimum": 0},
                    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "bounding_box": {
                        "oneOf": [
                            {"type": "null"},
                            {
                                "type": "object",
                                "required": ["x_min", "y_min", "x_max", "y_max"],
                                "properties": {
                                    "x_min": {"type": "integer", "minimum": 0},
                                    "y_min": {"type": "integer", "minimum": 0},
                                    "x_max": {"type": "integer", "minimum": 0},
                                    "y_max": {"type": "integer", "minimum": 0},
                                },
                            },
                        ]
                    },
                },
            },
        },
        "confidence": {
            "oneOf": [
                {"type": "null"},
                {"type": "number", "minimum": 0.0, "maximum": 1.0},
            ]
        },
        "bounding_box": {
            "oneOf": [
                {"type": "null"},
                {
                    "type": "object",
                    "required": ["x_min", "y_min", "x_max", "y_max"],
                    "properties": {
                        "x_min": {"type": "integer", "minimum": 0},
                        "y_min": {"type": "integer", "minimum": 0},
                        "x_max": {"type": "integer", "minimum": 0},
                        "y_max": {"type": "integer", "minimum": 0},
                    },
                },
            ]
        },
        "inference_time_ms": {"type": "number", "minimum": 0.0},
        "error": {
            "oneOf": [
                {"type": "null"},
                {
                    "type": "object",
                    "required": ["code", "message"],
                    "properties": {
                        "code": {"type": "string", "minLength": 1},
                        "message": {"type": "string", "minLength": 1},
                    },
                },
            ]
        },
    },
    "additionalProperties": True,
}


@dataclass
class RawPrediction:
    """Raw prediction item emitted by an InferenceEngine before normalization."""

    label: str
    class_id: int
    confidence: float
    bounding_box: Optional[Dict[str, int]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ResultValidationError(ValueError):
    """Raised when a normalized inference result violates the standardized JSON schema."""


def validate_inference_result(result_dict: Dict[str, Any]) -> None:
    """Validate an inference result dictionary against `INFERENCE_RESULT_JSON_SCHEMA`."""
    try:
        jsonschema.validate(instance=result_dict, schema=INFERENCE_RESULT_JSON_SCHEMA)
    except jsonschema.ValidationError as exc:
        raise ResultValidationError(
            f"Hasil inferensi tidak sesuai skema standar: {exc.message}"
        ) from exc

    # Additional semantic check: bounding box coordinates order
    for det in result_dict.get("detections", []):
        bbox = det.get("bounding_box")
        if bbox is not None:
            if bbox["x_max"] < bbox["x_min"] or bbox["y_max"] < bbox["y_min"]:
                raise ResultValidationError(
                    f"Koordinat bounding_box tidak valid (max < min): {bbox}"
                )


class ResultNormalizer:
    """Normalizes raw model predictions or errors into the standardized schema."""

    def normalize_success(
        self,
        model_id: str,
        task_type: str,
        output_type: str,
        is_mock: bool,
        input_dimensions: Dict[str, int],
        raw_predictions: List[RawPrediction],
        inference_time_ms: float,
        confidence_threshold: float = 0.0,
    ) -> Dict[str, Any]:
        """Convert raw predictions into a validated standardized dictionary."""
        filtered = [
            pred for pred in raw_predictions if pred.confidence >= confidence_threshold
        ]
        # Sort highest confidence first
        filtered.sort(key=lambda item: item.confidence, reverse=True)

        normalized_detections: List[Dict[str, Any]] = []
        for pred in filtered:
            bbox_out: Optional[Dict[str, int]] = None
            if output_type != "classification" and pred.bounding_box is not None:
                bbox_out = {
                    "x_min": int(max(0, pred.bounding_box["x_min"])),
                    "y_min": int(max(0, pred.bounding_box["y_min"])),
                    "x_max": int(max(0, pred.bounding_box["x_max"])),
                    "y_max": int(max(0, pred.bounding_box["y_max"])),
                }

            normalized_detections.append(
                {
                    "label": str(pred.label),
                    "class_id": int(pred.class_id),
                    "confidence": round(float(pred.confidence), 4),
                    "bounding_box": bbox_out,
                }
            )

        top_confidence: Optional[float] = None
        top_bbox: Optional[Dict[str, int]] = None
        if normalized_detections:
            top_confidence = normalized_detections[0]["confidence"]
            top_bbox = normalized_detections[0]["bounding_box"]

        result = {
            "schema_version": SCHEMA_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model_id": model_id,
            "task_type": task_type,
            "output_type": output_type,
            "is_mock": bool(is_mock),
            "status": "success",
            "input_dimensions": {
                "width": int(input_dimensions["width"]),
                "height": int(input_dimensions["height"]),
                "channels": int(input_dimensions["channels"]),
            },
            "detections": normalized_detections,
            "confidence": top_confidence,
            "bounding_box": top_bbox,
            "inference_time_ms": round(max(0.0, float(inference_time_ms)), 3),
            "error": None,
        }

        validate_inference_result(result)
        return result

    def normalize_error(
        self,
        model_id: str,
        task_type: str,
        output_type: str,
        is_mock: bool,
        input_dimensions: Optional[Dict[str, int]],
        error_code: str,
        error_message: str,
        inference_time_ms: float = 0.0,
    ) -> Dict[str, Any]:
        """Build a standardized error payload when preprocessing or inference fails."""
        dims = input_dimensions or {"width": 1, "height": 1, "channels": 3}
        result = {
            "schema_version": SCHEMA_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model_id": model_id,
            "task_type": task_type,
            "output_type": output_type,
            "is_mock": bool(is_mock),
            "status": "error",
            "input_dimensions": {
                "width": max(1, int(dims.get("width", 1))),
                "height": max(1, int(dims.get("height", 1))),
                "channels": int(dims.get("channels", 3)) if dims.get("channels") in (1, 3) else 3,
            },
            "detections": [],
            "confidence": None,
            "bounding_box": None,
            "inference_time_ms": round(max(0.0, float(inference_time_ms)), 3),
            "error": {
                "code": str(error_code),
                "message": str(error_message),
            },
        }

        validate_inference_result(result)
        return result

