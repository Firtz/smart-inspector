"""ROS 2 Publisher wrapper and Proof of Concept for Smart Inspector System.

Isolates `rclpy` imports so the project can run in Mock/Standalone mode on Windows
or environments where ROS 2 is not yet installed.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String

    ROS2_AVAILABLE = True
except ImportError:
    rclpy = None  # type: ignore[assignment]
    Node = object  # type: ignore[assignment,misc]
    String = None  # type: ignore[assignment]
    ROS2_AVAILABLE = False


def is_ros2_available() -> bool:
    """Return True if `rclpy` and `std_msgs` are importable in the current environment."""
    return ROS2_AVAILABLE


class InferenceResultPublisher:
    """Publishes standardized inference result JSON payloads over ROS 2 or mock callback.

    When `use_mock=True` or when `rclpy` is unavailable (unless `require_ros2=True`),
    messages are recorded in an internal buffer and optionally forwarded to local callbacks.
    """

    def __init__(
        self,
        node_name: str = "smart_inspector_inference_node",
        topic_name: str = "/smart_inspector/inference/results",
        qos_depth: int = 10,
        use_mock: bool = True,
        require_ros2: bool = False,
    ) -> None:
        self.node_name = node_name
        self.topic_name = topic_name
        self.qos_depth = qos_depth
        self.use_mock = use_mock or (not ROS2_AVAILABLE)
        self._published_history: List[str] = []
        self._callbacks: List[Callable[[str], None]] = []
        self._ros_node: Optional[Any] = None
        self._ros_publisher: Optional[Any] = None
        self._owns_rclpy_context = False

        if require_ros2 and not ROS2_AVAILABLE:
            raise RuntimeError(
                "ROS 2 (rclpy) tidak ditemukan di lingkungan ini. "
                "Pastikan ROS 2 telah di-source (contoh: `source /opt/ros/jazzy/setup.bash`) "
                "atau jalankan dalam mode mock."
            )

        if not self.use_mock and ROS2_AVAILABLE:
            self._init_ros2()
        else:
            logger.info(
                "InferenceResultPublisher aktif dalam mode MOCK (ROS2_AVAILABLE=%s) pada topik '%s'.",
                ROS2_AVAILABLE,
                self.topic_name,
            )

    def _init_ros2(self) -> None:
        if not rclpy.ok():
            rclpy.init()
            self._owns_rclpy_context = True
        self._ros_node = rclpy.create_node(self.node_name)
        self._ros_publisher = self._ros_node.create_publisher(
            String, self.topic_name, self.qos_depth
        )
        logger.info(
            "Node ROS 2 '%s' siap mempublikasikan ke topik '%s' (qos=%d).",
            self.node_name,
            self.topic_name,
            self.qos_depth,
        )

    def register_local_callback(self, callback: Callable[[str], None]) -> None:
        """Register an in-process listener (useful for testing and mock pub/sub verification)."""
        self._callbacks.append(callback)

    @property
    def published_messages(self) -> List[str]:
        """Return list of serialized JSON strings published during this session."""
        return list(self._published_history)

    def publish_result(self, payload: Dict[str, Any]) -> str:
        """Serialize dictionary payload to JSON and publish to ROS 2 topic (or mock bus)."""
        serialized = json.dumps(payload, ensure_ascii=False)
        self._published_history.append(serialized)

        if not self.use_mock and self._ros_publisher is not None and String is not None:
            msg = String()
            msg.data = serialized
            self._ros_publisher.publish(msg)
            logger.debug("ROS 2 message published to %s (%d bytes)", self.topic_name, len(serialized))
        else:
            logger.debug("Mock ROS 2 message recorded on %s (%d bytes)", self.topic_name, len(serialized))

        for cb in self._callbacks:
            cb(serialized)

        return serialized

    def close(self) -> None:
        """Cleanly destroy the ROS 2 node and shut down context if owned."""
        if self._ros_node is not None:
            self._ros_node.destroy_node()
            self._ros_node = None
        if self._owns_rclpy_context and ROS2_AVAILABLE and rclpy.ok():
            rclpy.shutdown()
            self._owns_rclpy_context = False


def build_sample_poc_message(sequence_id: int = 1) -> Dict[str, Any]:
    """Create a realistic sample inference-result-like message for the Week 1 ROS 2 POC."""
    return {
        "schema_version": "1.0",
        "sequence_id": sequence_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model_id": "ripeness_ffb",
        "task_type": "ffb_ripeness",
        "is_mock": True,
        "status": "success",
        "input_dimensions": {"width": 640, "height": 640, "channels": 3},
        "detections": [
            {
                "label": "PLACEHOLDER_FFB_RIPE",
                "confidence": 0.91,
                "bounding_box": {"x_min": 120, "y_min": 80, "x_max": 420, "y_max": 390},
            }
        ],
        "confidence": 0.91,
        "bounding_box": {"x_min": 120, "y_min": 80, "x_max": 420, "y_max": 390},
        "inference_time_ms": 14.5,
        "error": None,
    }


def main() -> int:
    """CLI entrypoint for standalone ROS 2 Publisher Proof of Concept."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    if not ROS2_AVAILABLE:
        logger.warning(
            "ROS 2 (rclpy) TIDAK tersedia di mesin ini. Menjalankan Publisher POC dalam mode simulasi lokal."
        )
        pub = InferenceResultPublisher(use_mock=True)
        sample = build_sample_poc_message(sequence_id=1)
        raw_json = pub.publish_result(sample)
        logger.info("Pesan POC (Simulasi): %s", raw_json)
        pub.close()
        return 0

    logger.info("Memulai ROS 2 Publisher POC (Tekan Ctrl+C untuk berhenti)...")
    pub = InferenceResultPublisher(use_mock=False, require_ros2=True)
    seq = 1
    try:
        import time

        while rclpy.ok():
            sample = build_sample_poc_message(sequence_id=seq)
            raw_json = pub.publish_result(sample)
            logger.info("[ROS 2 Published #%d] %s", seq, raw_json)
            seq += 1
            time.sleep(1.0)
    except KeyboardInterrupt:
        logger.info("Publisher dihentikan oleh pengguna.")
    finally:
        pub.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

