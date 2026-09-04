import unittest

from core.computer_use.contracts import ComputerAction, FrameSnapshot
from core.computer_use.safety import evaluate_action
from core.providers.openai_responses import extract_output_text


class ComputerUseContractTests(unittest.TestCase):
    def test_relative_coordinates_map_to_negative_monitor_space(self):
        frame = FrameSnapshot(
            sequence=1,
            timestamp=0.0,
            left=-1920,
            top=0,
            monitor_width=1920,
            monitor_height=1080,
            image_width=1280,
            image_height=720,
            monitor_index=2,
            change_score=1.0,
            jpeg_bytes=b"x",
        )

        self.assertEqual(frame.to_screen_coordinates(0, 0), (-1920, 0))
        self.assertEqual(frame.to_screen_coordinates(1280, 720), (-1, 1079))
        self.assertEqual(frame.to_screen_coordinates(640, 360), (-960, 540))

    def test_destructive_or_external_action_requires_approval(self):
        action = ComputerAction(
            action="click",
            description="Click Save Changes for user permissions",
            x=100,
            y=100,
        )

        decision = evaluate_action(action)

        self.assertFalse(decision.allowed)
        self.assertTrue(decision.requires_approval)

    def test_low_risk_scroll_is_allowed(self):
        decision = evaluate_action(
            ComputerAction(
                action="scroll",
                description="Scroll down to continue reading the table",
            )
        )

        self.assertTrue(decision.allowed)
        self.assertFalse(decision.requires_approval)

    def test_openai_output_text_extractor_handles_responses_payload(self):
        payload = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": '{"action":"done"}'}
                    ],
                }
            ]
        }

        self.assertEqual(extract_output_text(payload), '{"action":"done"}')


if __name__ == "__main__":
    unittest.main()
