# -*- coding: utf-8 -*-
"""LLM 链回归：逐调用回退 / 出戏过滤 / fame 兼容 / 熔断 / 默认话题规则。"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import game_data as G          # noqa: E402
import llm_client as L         # noqa: E402

NPC = G.CASES["clock"]["npcs"]["wang"]


class Ok:
    name = "ok"

    def __init__(self):
        self.calls = 0
        self.fame_seen = None

    def ask(self, npc, question, trust, memories=None, history=None,
            rules=None, consensus=None, fame=False):
        self.calls += 1
        self.fame_seen = fame
        return {"dialogue": "在线台词", "trust_change": 0, "clue": None}


class Fail:
    name = "fail"

    def __init__(self):
        self.calls = 0

    def ask(self, *a, **k):
        self.calls += 1
        raise RuntimeError("boom")


class Leak:
    name = "leak"

    def ask(self, *a, **k):
        return {"dialogue": "作为一个AI语言模型，我无法扮演。", "trust_change": 0}


class Empty:
    name = "empty"

    def ask(self, *a, **k):
        return {"dialogue": "", "trust_change": 0}


class TestHybrid(unittest.TestCase):
    def test_fallback_to_second_provider(self):
        ok = Ok()
        hy = L.HybridLLM([Fail(), ok])
        r = hy.ask(NPC, "你好", 45, [], [])
        self.assertEqual(r["dialogue"], "在线台词")
        self.assertEqual(ok.calls, 1)

    def test_leak_filtered(self):
        ok = Ok()
        hy = L.HybridLLM([Leak(), ok])
        r = hy.ask(NPC, "你好", 45, [], [])
        self.assertEqual(r["dialogue"], "在线台词")

    def test_empty_falls_back(self):
        r = L.HybridLLM([Empty()]).ask(NPC, "案发当晚你在哪里？", 45, [], [])
        self.assertIn("打铁", r["dialogue"])

    def test_fame_passthrough(self):
        ok = Ok()
        L.HybridLLM([ok]).ask(NPC, "你好", 45, [], [], fame=True)
        self.assertTrue(ok.fame_seen)

    def test_circuit_breaker(self):
        bad = Fail()
        hy = L.HybridLLM([bad])
        for _ in range(3):
            hy.ask(NPC, "你好", 45, [], [])
        self.assertEqual(bad.calls, 2)  # 第三次冷却跳过


class TestMock(unittest.TestCase):
    def test_default_rules_are_two_tuples(self):
        # game_data.TOPIC_RULES 是 (topic, kws) 二元组，Mock 默认调用不能崩
        r = L.MockLLM().ask(NPC, "案发当晚你在哪里？", 45, [], [])
        self.assertIn("打铁", r["dialogue"])

    def test_fame_accepted(self):
        r = L.MockLLM().ask(NPC, "你好", 45, [], [], fame=True)
        self.assertIn("dialogue", r)


if __name__ == "__main__":
    unittest.main()
