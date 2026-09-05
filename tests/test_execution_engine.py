import asyncio
import unittest

from core.execution_engine import ExecutionEngine
from core.tool_router import RouteTier, ToolRoute


class ExecutionEngineTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = ExecutionEngine()
        self.route = ToolRoute(
            tool_name="system_monitor",
            action="status",
            tier=RouteTier.DIRECT_LOCAL,
            reason="deterministic_local_tool",
        )

    async def test_dispatches_synchronous_executor(self):
        dispatch = await self.engine.execute(self.route, lambda: {"ok": True})

        self.assertEqual(dispatch.raw_response, {"ok": True})
        self.assertIs(dispatch.route, self.route)
        self.assertGreaterEqual(dispatch.duration_ms, 0)

    async def test_dispatches_asynchronous_executor(self):
        async def execute():
            await asyncio.sleep(0)
            return "done"

        dispatch = await self.engine.execute(self.route, execute)

        self.assertEqual(dispatch.raw_response, "done")

    async def test_executor_exception_is_not_swallowed(self):
        def explode():
            raise RuntimeError("boom")

        with self.assertRaisesRegex(RuntimeError, "boom"):
            await self.engine.execute(self.route, explode)

    async def test_cancellation_is_not_converted_to_success(self):
        async def cancel():
            raise asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.engine.execute(self.route, cancel)


if __name__ == "__main__":
    unittest.main()
