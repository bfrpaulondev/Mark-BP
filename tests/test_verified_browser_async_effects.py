import json
import unittest

from actions.verified_browser_automation import _verify_scroll, _verify_type


class FakeLocator:
    def __init__(self):
        self.first = self
        self.value = ""

    async def count(self):
        return 1

    async def clear(self):
        self.value = ""

    async def type(self, text, delay=0):
        self.value += str(text)

    async def input_value(self):
        return self.value

    async def evaluate(self, _script):
        return {
            "checked": None,
            "expanded": None,
            "pressed": None,
            "selected": None,
            "disabled": False,
            "valueLength": len(self.value),
        }


class FakeMouse:
    def __init__(self, page):
        self.page = page

    async def wheel(self, _x, y):
        self.page.scroll_y = max(0, self.page.scroll_y + int(y))


class FakeContext:
    def __init__(self, page):
        self.pages = [page]


class FakePage:
    def __init__(self):
        self.url = "https://example.com/docs"
        self.scroll_y = 0
        self.input = FakeLocator()
        self.mouse = FakeMouse(self)
        self.context = FakeContext(self)

    async def title(self):
        return "Docs"

    async def evaluate(self, script):
        if "scrollX" in script:
            return [0, self.scroll_y]
        if "activeElement" in script:
            return {"tag": "input", "id": "query"}
        return None

    def locator(self, _selector):
        return self.input


class FakeSession:
    def __init__(self):
        self.page = FakePage()

    async def _get_page(self):
        return self.page


class VerifiedBrowserAsyncEffectsTests(unittest.IsolatedAsyncioTestCase):
    async def test_scroll_verifies_real_page_scroll_position_change(self):
        session = FakeSession()
        payload = json.loads(await _verify_scroll(session, {"direction": "down", "amount": 400}))

        self.assertTrue(payload["verified"])
        self.assertEqual(payload["evidence"]["before"]["scroll"], [0, 0])
        self.assertEqual(payload["evidence"]["after"]["scroll"], [0, 400])

    async def test_scroll_at_boundary_remains_unverified(self):
        session = FakeSession()
        payload = json.loads(await _verify_scroll(session, {"direction": "up", "amount": 400}))

        self.assertFalse(payload["verified"])
        self.assertTrue(payload["delivered"])

    async def test_type_verifies_value_but_does_not_echo_typed_text_in_evidence(self):
        session = FakeSession()
        typed = "sample-entry-456"
        payload = json.loads(
            await _verify_type(
                session,
                {"selector": "#query", "text": typed, "clear_first": True},
            )
        )

        self.assertTrue(payload["verified"])
        self.assertEqual(payload["evidence"]["actual_length"], len(typed))
        self.assertNotIn(typed, json.dumps(payload["evidence"], ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
