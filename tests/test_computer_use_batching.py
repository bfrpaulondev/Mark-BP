import json
import unittest

from core.computer_use.batching import can_chain_without_reobserve, sanitize_action_batch
from core.computer_use.contracts import ComputerAction, SessionState
from core.computer_use.planner import _parse_actions


class ComputerUseBatchingTests(unittest.TestCase):
    def test_click_then_type_can_run_without_intermediate_model_call(self):
        actions = [
            ComputerAction(
                action="click",
                description="Focus the username field",
                x=100,
                y=200,
                risk="low",
                reobserve=False,
            ),
            ComputerAction(
                action="smart_type",
                description="Type the username",
                text="bruno",
                risk="low",
            ),
        ]

        safe = sanitize_action_batch(actions)

        self.assertEqual(len(safe), 2)
        self.assertFalse(safe[0].reobserve)
        self.assertTrue(safe[1].reobserve)
        self.assertTrue(can_chain_without_reobserve(safe[0], safe[1]))

    def test_two_coordinate_clicks_are_never_batched(self):
        actions = [
            ComputerAction(action="click", x=100, y=100, reobserve=False),
            ComputerAction(action="click", x=300, y=300),
        ]

        safe = sanitize_action_batch(actions)

        self.assertEqual(len(safe), 1)
        self.assertTrue(safe[0].reobserve)

    def test_high_risk_action_breaks_batch_before_following_action(self):
        actions = [
            ComputerAction(
                action="click",
                description="Click save permissions",
                x=100,
                y=100,
                risk="high",
                reobserve=False,
            ),
            ComputerAction(action="smart_type", text="ignored"),
        ]

        safe = sanitize_action_batch(actions)

        self.assertEqual(len(safe), 1)
        self.assertTrue(safe[0].reobserve)

    def test_planner_parser_accepts_micro_batch_and_caps_it(self):
        raw = json.dumps(
            {
                "actions": [
                    {
                        "action": "click",
                        "description": "Focus field",
                        "x": 100,
                        "y": 200,
                        "risk": "low",
                        "reobserve": False,
                    },
                    {
                        "action": "type",
                        "description": "Type value",
                        "text": "hello",
                        "risk": "low",
                        "reobserve": True,
                    },
                    {"action": "wait", "seconds": 1},
                    {"action": "wait", "seconds": 1},
                ]
            }
        )

        actions = _parse_actions(raw)

        self.assertEqual([item.action for item in actions], ["click", "type"])
        self.assertFalse(actions[0].reobserve)
        self.assertTrue(actions[1].reobserve)

    def test_legacy_single_action_response_still_works(self):
        actions = _parse_actions(
            json.dumps(
                {
                    "action": "scroll",
                    "direction": "down",
                    "amount": 3,
                }
            )
        )

        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].action, "scroll")
        self.assertTrue(actions[0].reobserve)

    def test_session_state_reports_model_call_savings(self):
        state = SessionState(batched_actions=3, saved_model_calls=3)
        snapshot = state.as_dict()

        self.assertEqual(snapshot["batched_actions"], 3)
        self.assertEqual(snapshot["saved_model_calls"], 3)


if __name__ == "__main__":
    unittest.main()
