"""Unit tests for canary_check.py pure logic (no network)."""

import unittest

from canary_check import capability_hit, normalize, token_similarity, verdict


class TestNormalize(unittest.TestCase):
    def test_lowercase_collapse_strip_punct(self):
        self.assertEqual(normalize("  The  Ball: $0.05!! "), "the ball 005")

    def test_empty(self):
        self.assertEqual(normalize(""), "")
        self.assertEqual(normalize(None), "")


class TestTokenSimilarity(unittest.TestCase):
    def test_identical(self):
        self.assertEqual(token_similarity("the ball is 5", "the ball is 5"), 1.0)

    def test_disjoint(self):
        self.assertEqual(token_similarity("alpha beta", "gamma delta"), 0.0)

    def test_both_empty_is_one(self):
        self.assertEqual(token_similarity("", ""), 1.0)

    def test_one_empty_is_zero(self):
        self.assertEqual(token_similarity("hello", ""), 0.0)

    def test_partial_jaccard(self):
        # {a,b,c} vs {a,b,d} -> intersection 2 / union 4 = 0.5
        self.assertAlmostEqual(token_similarity("a b c", "a b d"), 0.5)

    def test_punctuation_ignored(self):
        self.assertEqual(token_similarity("0.05", "$0.05!"), 1.0)


class TestCapabilityHit(unittest.TestCase):
    def test_hit_substring_normalized(self):
        self.assertTrue(capability_hit("The ball costs $0.05.", "0.05"))

    def test_miss(self):
        self.assertFalse(capability_hit("The ball costs $0.10.", "0.05"))

    def test_compare_only_returns_none(self):
        self.assertIsNone(capability_hit("anything", None))


class TestVerdict(unittest.TestCase):
    def test_downgrade_when_relay_fails_a_probe_ref_passes(self):
        rows = [
            {"id": "reason", "similarity": 0.8, "relay_hit": False, "ref_hit": True},
            {"id": "echo", "similarity": 0.9, "relay_hit": True, "ref_hit": True},
        ]
        v = verdict(rows)
        self.assertIn("SUSPICIOUS", v["label"])
        self.assertEqual(v["downgrade_flags"], ["reason"])

    def test_suspicious_on_low_similarity(self):
        rows = [{"id": "a", "similarity": 0.2, "relay_hit": None, "ref_hit": None}]
        self.assertIn("SUSPICIOUS", verdict(rows)["label"])

    def test_inconclusive_mid_band(self):
        rows = [{"id": "a", "similarity": 0.6, "relay_hit": None, "ref_hit": None}]
        self.assertIn("INCONCLUSIVE", verdict(rows)["label"])

    def test_ok_high_similarity(self):
        rows = [
            {"id": "a", "similarity": 0.95, "relay_hit": True, "ref_hit": True},
            {"id": "b", "similarity": 0.85, "relay_hit": None, "ref_hit": None},
        ]
        v = verdict(rows)
        self.assertIn("OK", v["label"])
        self.assertEqual(v["downgrade_flags"], [])

    def test_mean_similarity_reported(self):
        rows = [{"id": "a", "similarity": 0.4, "relay_hit": None, "ref_hit": None},
                {"id": "b", "similarity": 0.6, "relay_hit": None, "ref_hit": None}]
        self.assertEqual(verdict(rows)["mean_similarity"], 0.5)


if __name__ == "__main__":
    unittest.main()
