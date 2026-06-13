"""Unit tests for make_coding_chart.py pure functions.

These exercise only the data layer (build_coding_data / value_headline), which
imports no PIL — so the suite passes on the CI runner, where Pillow is absent.
The rendering path (render/main) is intentionally not imported here.
"""

import unittest

from make_coding_chart import build_coding_data, value_headline

# Coding scenario = input 50k, output 20k, +30k thinking for reasoning models.
# Costs below are hand-checkable against those token counts.
MODELS = [
    # reasoning: 50k@10 + 50k@50 /1M = 0.5 + 2.5 = $3.00 ; top capability → flagship
    {"name": "Flagship", "provider": "A", "open": False, "reasoning": True,
     "benchmarks": {"swe_bench_verified": 0.95}, "pricing_usd_per_mtok": {"input": 10.0, "output": 50.0}},
    # non-reasoning: 50k@0.95 + 20k@4 /1M = 0.0475 + 0.08 = $0.1275 ; open
    {"name": "OpenCheap", "provider": "B", "open": True, "reasoning": False,
     "benchmarks": {"swe_bench_verified": 0.80}, "pricing_usd_per_mtok": {"input": 0.95, "output": 4.0}},
    # has a price but no SWE-bench score → excluded
    {"name": "NoScore", "provider": "C", "open": True, "reasoning": False,
     "benchmarks": {"swe_bench_verified": None}, "pricing_usd_per_mtok": {"input": 1.0, "output": 1.0}},
    # has a SWE-bench score but no price → excluded
    {"name": "NoPrice", "provider": "D", "open": False, "reasoning": False,
     "benchmarks": {"swe_bench_verified": 0.70}},
    # missing benchmarks dict entirely → excluded, must not raise
    {"name": "NoBench", "provider": "E", "open": False, "reasoning": False,
     "pricing_usd_per_mtok": {"input": 1.0, "output": 1.0}},
]


class TestBuildCodingData(unittest.TestCase):
    def setUp(self):
        self.rows = build_coding_data(MODELS)

    def test_only_models_with_both_score_and_price(self):
        self.assertEqual({r["name"] for r in self.rows}, {"Flagship", "OpenCheap"})

    def test_sorted_cheapest_first(self):
        self.assertEqual([r["name"] for r in self.rows], ["OpenCheap", "Flagship"])

    def test_costs_use_coding_engine(self):
        by = {r["name"]: r for r in self.rows}
        self.assertAlmostEqual(by["Flagship"]["cost"], 3.00, places=6)
        self.assertAlmostEqual(by["OpenCheap"]["cost"], 0.1275, places=6)

    def test_flagship_is_top_capability(self):
        flags = [r["name"] for r in self.rows if r["flagship"]]
        self.assertEqual(flags, ["Flagship"])

    def test_open_flag_preserved(self):
        by = {r["name"]: r for r in self.rows}
        self.assertTrue(by["OpenCheap"]["open"])
        self.assertFalse(by["Flagship"]["open"])

    def test_empty_input_is_safe(self):
        self.assertEqual(build_coding_data([]), [])


class TestValueHeadline(unittest.TestCase):
    def test_no_peer_when_open_model_matches_no_pricier_closed(self):
        # OpenCheap (0.80) — the only closed model within ±2 pts is none
        # (Flagship is 0.95, 15 pts away). So there is no qualifying peer.
        self.assertIsNone(value_headline(build_coding_data(MODELS)))

    def test_open_model_ties_pricier_closed_peer(self):
        rows = build_coding_data(
            MODELS
            + [  # closed peer at the same 0.80 score but pricier than OpenCheap
                {"name": "ClosedPeer", "provider": "F", "open": False, "reasoning": True,
                 "benchmarks": {"swe_bench_verified": 0.80},
                 "pricing_usd_per_mtok": {"input": 2.0, "output": 12.0}},
            ]
        )
        hd = value_headline(rows)
        self.assertIsNotNone(hd)
        self.assertEqual(hd["name"], "OpenCheap")
        self.assertEqual(hd["peer"], "ClosedPeer")
        # ClosedPeer reasoning cost (50k@2 + 50k@12)/1M = 0.1 + 0.6 = $0.70
        # OpenCheap $0.1275 → 0.70 / 0.1275 ≈ 5.49x
        self.assertAlmostEqual(hd["cheaper_x"], 0.70 / 0.1275, places=2)
        # gap to the 0.95 ceiling = 15 points
        self.assertAlmostEqual(hd["gap_pts"], 15.0, places=4)

    def test_no_peer_when_no_closed_models(self):
        rows = build_coding_data(
            [{"name": "OnlyOpen", "provider": "G", "open": True, "reasoning": False,
              "benchmarks": {"swe_bench_verified": 0.80},
              "pricing_usd_per_mtok": {"input": 1.0, "output": 1.0}}]
        )
        self.assertIsNone(value_headline(rows))

    def test_none_on_empty(self):
        self.assertIsNone(value_headline([]))


if __name__ == "__main__":
    unittest.main()
