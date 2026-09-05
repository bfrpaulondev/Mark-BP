import unittest

from core.computer_use.perception_cache import (
    FrameSignature,
    LocalFrameCache,
    hamming_distance64,
)


class _Clock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def advance(self, seconds: float):
        self.value += seconds


class LocalFrameCacheTests(unittest.TestCase):
    def test_first_observation_is_keyframe(self):
        clock = _Clock()
        cache = LocalFrameCache(monotonic_clock=clock)
        decision = cache.observe(
            FrameSignature("a" * 24, 0b1010, 10),
            scope="monitor-1",
        )
        self.assertTrue(decision.keyframe)
        self.assertFalse(decision.duplicate)
        self.assertEqual(decision.reason, "new_scope")

    def test_exact_duplicate_is_classified_without_pixels(self):
        clock = _Clock()
        cache = LocalFrameCache(
            monotonic_clock=clock,
            keyframe_interval_seconds=5.0,
        )
        signature = FrameSignature("b" * 24, 0x1234, 12)
        cache.observe(signature, scope="window-A")
        clock.advance(0.2)
        decision = cache.observe(signature, scope="window-A")

        self.assertTrue(decision.duplicate)
        self.assertTrue(decision.near_duplicate)
        self.assertFalse(decision.keyframe)
        self.assertEqual(decision.reason, "exact_duplicate")
        self.assertEqual(decision.hamming_distance, 0)

        entry = next(iter(cache._entries.values()))
        self.assertFalse(hasattr(entry, "jpeg_bytes"))
        self.assertFalse(hasattr(entry, "pixels"))
        self.assertFalse(hasattr(entry, "image"))

    def test_near_match_never_claims_exact_duplicate(self):
        clock = _Clock()
        cache = LocalFrameCache(
            monotonic_clock=clock,
            near_hamming_distance=2,
        )
        cache.observe(FrameSignature("a" * 24, 0b0000, 8), scope="same")
        clock.advance(0.1)
        decision = cache.observe(
            FrameSignature("c" * 24, 0b0011, 8),
            scope="same",
        )
        self.assertFalse(decision.duplicate)
        self.assertTrue(decision.near_duplicate)
        self.assertEqual(decision.hamming_distance, 2)

    def test_periodic_keyframe_prevents_permanent_duplicate_blindness(self):
        clock = _Clock()
        cache = LocalFrameCache(
            monotonic_clock=clock,
            keyframe_interval_seconds=1.0,
        )
        signature = FrameSignature("d" * 24, 77, 4)
        cache.observe(signature, scope="same")
        clock.advance(1.1)
        decision = cache.observe(signature, scope="same")
        self.assertTrue(decision.duplicate)
        self.assertTrue(decision.keyframe)
        self.assertEqual(decision.reason, "periodic_keyframe")

    def test_scope_change_forces_new_keyframe(self):
        cache = LocalFrameCache()
        signature = FrameSignature("e" * 24, 11, 3)
        cache.observe(signature, scope="monitor:1")
        decision = cache.observe(signature, scope="monitor:2")
        self.assertTrue(decision.keyframe)
        self.assertFalse(decision.duplicate)

    def test_cache_is_bounded_and_ttl_evicted(self):
        clock = _Clock()
        cache = LocalFrameCache(
            max_entries=4,
            ttl_seconds=1.0,
            monotonic_clock=clock,
        )
        for index in range(8):
            cache.observe(
                FrameSignature(f"{index:024d}", index, index % 31),
                scope=f"scope-{index}",
            )
            clock.advance(0.05)
        self.assertLessEqual(cache.stats()["entries"], 4)

        clock.advance(2.0)
        cache.observe(FrameSignature("f" * 24, 1, 1), scope="fresh")
        self.assertEqual(cache.stats()["entries"], 1)

    def test_hamming_distance_is_64_bit_bounded(self):
        self.assertEqual(hamming_distance64(0, 0), 0)
        self.assertEqual(hamming_distance64(0, (1 << 64) - 1), 64)
        self.assertEqual(hamming_distance64(0, 1 << 80), 0)


if __name__ == "__main__":
    unittest.main()
