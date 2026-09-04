import io
import json
import logging
import unittest

from core.structured_logging import (
    configure_logging,
    correlation_context,
    get_logger,
    log_event,
    redact,
)


class StructuredLoggingTests(unittest.TestCase):
    # -.-.-.-
    def test_redact_hides_secrets_and_email(self):
        value = redact(
            {
                "gemini_api_key": "secret-value",
                "message": "Contact bruno@example.com with Bearer abc.def.ghi",
            }
        )

        self.assertEqual(value["gemini_api_key"], "[REDACTED]")
        self.assertNotIn("bruno@example.com", value["message"])
        self.assertNotIn("abc.def.ghi", value["message"])

    # -.-.-.-
    def test_json_log_contains_correlation_id_and_fields(self):
        stream = io.StringIO()
        configure_logging(stream=stream)
        logger = get_logger("tests")

        with correlation_context("run-123"):
            log_event(
                logger,
                logging.INFO,
                "dependency_check",
                module="requests",
                token="should-not-leak",
            )

        payload = json.loads(stream.getvalue().strip())
        self.assertEqual(payload["level"], "info")
        self.assertEqual(payload["correlation_id"], "run-123")
        self.assertEqual(payload["message"], "dependency_check")
        self.assertEqual(payload["fields"]["module"], "requests")
        self.assertEqual(payload["fields"]["token"], "[REDACTED]")

    # -.-.-.-
    def test_correlation_context_restores_previous_value(self):
        stream = io.StringIO()
        configure_logging(stream=stream)
        logger = get_logger("tests.restore")

        with correlation_context("outer"):
            log_event(logger, logging.INFO, "outer")
            with correlation_context("inner"):
                log_event(logger, logging.INFO, "inner")
            log_event(logger, logging.INFO, "outer-again")

        rows = [json.loads(line) for line in stream.getvalue().splitlines()]
        self.assertEqual(
            [row["correlation_id"] for row in rows],
            ["outer", "inner", "outer"],
        )


if __name__ == "__main__":
    unittest.main()
