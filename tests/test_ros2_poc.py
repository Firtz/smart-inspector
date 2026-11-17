"""Unit tests for Week 1 ROS 2 Publisher / Subscriber Proof of Concept."""

from __future__ import annotations

import unittest

from src.ros2.publisher import InferenceResultPublisher, build_sample_poc_message
from src.ros2.subscriber import InferenceResultSubscriber


class TestROS2ProofOfConcept(unittest.TestCase):
    """Verify Publisher and Subscriber behavior and isolation when ROS 2 is mocked/unavailable."""

    def test_publisher_and_subscriber_loop_in_mock_mode(self) -> None:
        pub = InferenceResultPublisher(
            node_name="test_pub_node",
            topic_name="/smart_inspector/inference/results",
            use_mock=True,
        )
        received_list = []
        sub = InferenceResultSubscriber(
            node_name="test_sub_node",
            topic_name="/smart_inspector/inference/results",
            use_mock=True,
            on_message=lambda msg: received_list.append(msg),
        )
        pub.register_local_callback(sub.handle_raw_message)

        payload = build_sample_poc_message(sequence_id=7)
        raw_json = pub.publish_result(payload)

        self.assertEqual(len(pub.published_messages), 1)
        self.assertIn('"sequence_id": 7', raw_json)
        self.assertEqual(len(sub.received_messages), 1)
        self.assertEqual(len(received_list), 1)
        self.assertEqual(received_list[0]["model_id"], "ripeness_ffb")
        self.assertEqual(received_list[0]["status"], "success")

        pub.close()
        sub.close()

    def test_subscriber_rejects_malformed_json(self) -> None:
        sub = InferenceResultSubscriber(use_mock=True)
        with self.assertRaises(ValueError):
            sub.handle_raw_message("{not_valid_json")
        sub.close()


if __name__ == "__main__":
    unittest.main()

