"""ROS 2 Subscriber wrapper and Proof of Concept for Smart Inspector System.

Receives standardized JSON inference messages from `/smart_inspector/inference/results`,
validates the JSON payload, and logs/stores the parsed results.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Optional

from src.ros2.publisher import ROS2_AVAILABLE

logger = logging.getLogger(__name__)

if ROS2_AVAILABLE:
    import rclpy
    from std_msgs.msg import String
else:
    rclpy = None  # type: ignore[assignment]
    String = None  # type: ignore[assignment]


class InferenceResultSubscriber:
    """Subscribes to inference result JSON messages over ROS 2 or mock callback channel."""

    def __init__(
        self,
        node_name: str = "smart_inspector_subscriber_poc",
        topic_name: str = "/smart_inspector/inference/results",
        qos_depth: int = 10,
        use_mock: bool = True,
        require_ros2: bool = False,
        on_message: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self.node_name = node_name
        self.topic_name = topic_name
        self.qos_depth = qos_depth
        self.use_mock = use_mock or (not ROS2_AVAILABLE)
        self.on_message = on_message
        self._received_messages: List[Dict[str, Any]] = []
        self._ros_node: Optional[Any] = None
        self._ros_subscription: Optional[Any] = None
        self._owns_rclpy_context = False

        if require_ros2 and not ROS2_AVAILABLE:
            raise RuntimeError(
                "ROS 2 (rclpy) tidak ditemukan di lingkungan ini. "
                "Pastikan ROS 2 telah di-source pada Linux/Raspberry Pi."
            )

        if not self.use_mock and ROS2_AVAILABLE:
            self._init_ros2()
        else:
            logger.info(
                "InferenceResultSubscriber aktif dalam mode MOCK (ROS2_AVAILABLE=%s) pada topik '%s'.",
                ROS2_AVAILABLE,
                self.topic_name,
            )

    def _init_ros2(self) -> None:
        if not rclpy.ok():
            rclpy.init()
            self._owns_rclpy_context = True
        self._ros_node = rclpy.create_node(self.node_name)
        self._ros_subscription = self._ros_node.create_subscription(
            String,
            self.topic_name,
            self._ros_callback,
            self.qos_depth,
        )
        logger.info(
            "Node Subscriber ROS 2 '%s' mendengarkan topik '%s'.",
            self.node_name,
            self.topic_name,
        )

    def _ros_callback(self, msg: Any) -> None:
        self.handle_raw_message(str(msg.data))

    def handle_raw_message(self, raw_json: str) -> Dict[str, Any]:
        """Parse incoming JSON string, store it, and invoke user callback if configured."""
        try:
            parsed = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            logger.error("Gagal mem-parsing pesan JSON pada topik %s: %s", self.topic_name, exc)
            raise ValueError(f"Payload bukan JSON valid: {exc}") from exc

        if not isinstance(parsed, dict):
            raise ValueError("Payload JSON harus berupa objek/dictionary.")

        self._received_messages.append(parsed)
        logger.info(
            "Pesan diterima pada %s: model_id=%s, status=%s, detections=%d",
            self.topic_name,
            parsed.get("model_id", "unknown"),
            parsed.get("status", "unknown"),
            len(parsed.get("detections", [])),
        )

        if self.on_message is not None:
            self.on_message(parsed)

        return parsed

    @property
    def received_messages(self) -> List[Dict[str, Any]]:
        """Return list of all parsed dictionary payloads received."""
        return list(self._received_messages)

    def spin(self) -> None:
        """Block and spin the ROS 2 node until interrupted."""
        if self.use_mock or self._ros_node is None:
            raise RuntimeError("spin() hanya dapat dipanggil saat ROS 2 aktif (bukan mode mock).")
        rclpy.spin(self._ros_node)

    def close(self) -> None:
        """Destroy the ROS 2 node and shut down context if owned."""
        if self._ros_node is not None:
            self._ros_node.destroy_node()
            self._ros_node = None
        if self._owns_rclpy_context and ROS2_AVAILABLE and rclpy.ok():
            rclpy.shutdown()
            self._owns_rclpy_context = False


def main() -> int:
    """CLI entrypoint for standalone ROS 2 Subscriber Proof of Concept."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    if not ROS2_AVAILABLE:
        logger.warning(
            "ROS 2 (rclpy) TIDAK tersedia di mesin ini. "
            "Mendemonstrasikan loop Publisher -> Subscriber dalam mode Mock lokal."
        )
        from src.ros2.publisher import InferenceResultPublisher, build_sample_poc_message

        pub = InferenceResultPublisher(use_mock=True)
        sub = InferenceResultSubscriber(use_mock=True)
        pub.register_local_callback(sub.handle_raw_message)

        sample = build_sample_poc_message(sequence_id=1)
        pub.publish_result(sample)

        pub.close()
        sub.close()
        return 0

    logger.info("Memulai ROS 2 Subscriber POC (Tekan Ctrl+C untuk berhenti)...")
    sub = InferenceResultSubscriber(use_mock=False, require_ros2=True)
    try:
        sub.spin()
    except KeyboardInterrupt:
        logger.info("Subscriber dihentikan oleh pengguna.")
    finally:
        sub.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

