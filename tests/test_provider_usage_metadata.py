import unittest
from types import SimpleNamespace

from core.providers.gemini_generate import extract_gemini_usage
from core.providers.openai_responses import extract_openai_usage


class ProviderUsageExtractionTests(unittest.TestCase):
    def test_openai_usage_extracts_cached_and_reasoning_tokens(self):
        usage = extract_openai_usage(
            {
                "usage": {
                    "input_tokens": 120,
                    "output_tokens": 35,
                    "total_tokens": 155,
                    "input_tokens_details": {"cached_tokens": 40},
                    "output_tokens_details": {"reasoning_tokens": 12},
                }
            }
        )

        self.assertEqual(usage.input_tokens, 120)
        self.assertEqual(usage.cached_input_tokens, 40)
        self.assertEqual(usage.output_tokens, 35)
        self.assertEqual(usage.reasoning_tokens, 12)
        self.assertEqual(usage.total_tokens, 155)

    def test_openai_usage_derives_total_when_api_omits_it(self):
        usage = extract_openai_usage(
            {"usage": {"input_tokens": 10, "output_tokens": 4}}
        )
        self.assertEqual(usage.total_tokens, 14)

    def test_gemini_usage_supports_sdk_attribute_shape(self):
        metadata = SimpleNamespace(
            prompt_token_count=200,
            candidates_token_count=50,
            total_token_count=250,
            cached_content_token_count=75,
            thoughts_token_count=20,
        )
        usage = extract_gemini_usage(metadata)

        self.assertEqual(usage.input_tokens, 200)
        self.assertEqual(usage.output_tokens, 50)
        self.assertEqual(usage.cached_input_tokens, 75)
        self.assertEqual(usage.reasoning_tokens, 20)
        self.assertEqual(usage.total_tokens, 250)

    def test_gemini_usage_supports_serialized_camel_case_shape(self):
        usage = extract_gemini_usage(
            {
                "promptTokenCount": 30,
                "candidatesTokenCount": 10,
                "cachedContentTokenCount": 5,
                "thoughtsTokenCount": 3,
            }
        )

        self.assertEqual(usage.input_tokens, 30)
        self.assertEqual(usage.output_tokens, 10)
        self.assertEqual(usage.cached_input_tokens, 5)
        self.assertEqual(usage.reasoning_tokens, 3)
        self.assertEqual(usage.total_tokens, 40)

    def test_missing_usage_is_explicitly_empty(self):
        self.assertFalse(extract_openai_usage({}).has_usage)
        self.assertFalse(extract_gemini_usage(None).has_usage)


if __name__ == "__main__":
    unittest.main()
