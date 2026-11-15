# -*- coding: utf-8 -*-
"""引擎层回归：开新局 / 提问 / 信任阈值 / 证据 / 指认 / 存档。"""
import base64
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import game_data as G          # noqa: E402
import llm_client as L         # noqa: E402
import npc_engine as engine    # noqa: E402


class TestNewGame(unittest.TestCase):
    def test_normal(self):
        st = engine.new_game("clock", "normal", 0)
        self.assertEqual(st["time"], 60)
        self.assertEqual(st["start_time"], 60)
        self.assertEqual(st["npc"]["wang"]["trust"], 45)
        self.assertFalse(st["ended"])

    def test_hard(self):
        st = engine.new_game("clock", "hard", 0)
        self.assertEqual(st["time"], 45)
        self.assertEqual(st["npc"]["wang"]["trust"], 35)  # 45 - 10
        self.assertIn("threat", st["evidence_ids"])

    def test_rank_perks(self):
        st = engine.new_game("clock", "normal", 2)
        self.assertEqual(st["time"], 65)                  # 二级：+5 分钟
        st = engine.new_game("clock", "normal", 4)
        self.assertEqual(st["npc"]["wang"]["trust"], 50)  # 高级：+5 信任

    def test_chapter2(self):
        st = engine.new_game("letter", "normal", 0)
        self.assertEqual(st["case_id"], "letter")
        self.assertEqual(len(st["npc"]), 4)
        self.assertEqual(len(st["evidence_ids"]), 5)


class TestAsk(unittest.TestCase):
    def setUp(self):
        self.llm = L.MockLLM()
        self.st = engine.new_game("clock", "normal", 0)

    def test_time_and_trust(self):
        r = engine.ask(self.st, "wang", "案发当晚你在哪里？", self.llm)
        self.assertEqual(self.st["time"], 59)
        self.assertIn("打铁", r["reply"])
        self.assertEqual(self.st["npc"]["wang"]["trust"], 42)  # 45 - 3
        self.assertTrue(any("案发当晚" in m for m in self.st["npc"]["wang"]["memories"]))

    def test_kick_out_below_15(self):
        self.st["npc"]["wang"]["trust"] = 10
        r = engine.ask(self.st, "wang", "你好", self.llm)
        self.assertIn("逐客令", r["reply"])
        self.assertEqual(self.st["time"], 57)  # 60 - 1 - 2

    def test_refuse_key_topic_below_25(self):
        self.st["npc"]["wang"]["trust"] = 20
        r = engine.ask(self.st, "wang", "案发当晚你在哪里？", self.llm)
        self.assertIn("拒绝", r["reply"])
        self.assertEqual(self.st["time"], 59)

    def test_whisper_at_85(self):
        self.st["npc"]["wang"]["trust"] = 90
        r = engine.ask(self.st, "wang", "你好", self.llm)
        self.assertIn("压低声音", r["reply"])

    def test_timeup(self):
        self.st["time"] = 1
        r = engine.ask(self.st, "wang", "你好", self.llm)
        self.assertTrue(r["timeup"])
        self.assertEqual(self.st["verdict"], "TIMEUP")
        self.assertTrue(self.st["ended"])


class TestEvidence(unittest.TestCase):
    def setUp(self):
        self.st = engine.new_game("clock", "normal", 0)

    def test_correct_evidence(self):
        r = engine.present_evidence(self.st, "wang", "ledger")
        self.assertEqual(r["clue"], "L4")
        self.assertEqual(self.st["time"], 58)
        self.assertTrue(self.st["npc"]["wang"]["confessed"])

    def test_wrong_evidence(self):
        r = engine.present_evidence(self.st, "wang", "glove")
        self.assertIsNone(r["clue"])
        self.assertEqual(self.st["time"], 58)

    def test_duplicate_per_npc(self):
        engine.present_evidence(self.st, "wang", "ledger")   # 60 -> 58
        engine.present_evidence(self.st, "su", "ledger")     # 58 -> 56
        t = self.st["time"]
        r = engine.present_evidence(self.st, "wang", "ledger")
        self.assertIn("看过了", r["reply"])
        self.assertEqual(self.st["time"], t)                 # 不重复扣时


class TestAccuse(unittest.TestCase):
    def setUp(self):
        self.st = engine.new_game("clock", "normal", 0)
        self.c = G.CASES["clock"]
        self.truth = "⌚ 沈墨白（钟表匠·已出城）"

    def _with_clues(self, n):
        self.st["clues"] = list(self.c["key_clues"].keys())[:n]

    def test_s_rank(self):
        self._with_clues(4)
        engine.accuse(self.st, self.truth)
        self.assertEqual(self.st["verdict"], "WIN_S")

    def test_a_rank(self):
        self._with_clues(3)
        engine.accuse(self.st, self.truth)
        self.assertEqual(self.st["verdict"], "WIN_A")

    def test_b_rank(self):
        self._with_clues(1)
        engine.accuse(self.st, self.truth)
        self.assertEqual(self.st["verdict"], "WIN_B")

    def test_wrong_person(self):
        engine.accuse(self.st, "🔨 王大锤（铁匠）")
        self.assertEqual(self.st["verdict"], "LOSE")


class TestConfront(unittest.TestCase):
    def setUp(self):
        self.llm = L.MockLLM()

    def test_correct_liar_unlocks_clue(self):
        st = engine.new_game("clock", "normal", 0)
        r = engine.start_confrontation(st, "clock_conf_1", self.llm)
        self.assertTrue(r["started"])
        self.assertEqual(r["choices"], ["王大锤", "苏眉"])
        self.assertEqual(st["time"], 57)
        rr = engine.resolve_confrontation(st, "王大锤")
        self.assertTrue(rr["correct"])
        self.assertEqual(rr["clue"], "L4")
        self.assertIn("L4", st["clues"])

    def test_wrong_choice_penalizes_and_no_clue(self):
        st = engine.new_game("clock", "normal", 0)
        engine.start_confrontation(st, "clock_conf_1", self.llm)
        rr = engine.resolve_confrontation(st, "苏眉")
        self.assertFalse(rr["correct"])
        self.assertEqual(st["clues"], [])
        self.assertLess(st["npc"]["su"]["trust"], 60)

    def test_chapter2_confrontation(self):
        st = engine.new_game("letter", "normal", 0)
        engine.start_confrontation(st, "letter_conf_1", self.llm)
        rr = engine.resolve_confrontation(st, "贾万通")
        self.assertTrue(rr["correct"])
        self.assertEqual(rr["clue"], "L7")

    def test_duplicate_and_pending_guards(self):
        st = engine.new_game("clock", "normal", 0)
        engine.start_confrontation(st, "clock_conf_1", self.llm)
        self.assertFalse(engine.start_confrontation(st, "clock_conf_1", self.llm)["started"])
        engine.resolve_confrontation(st, "王大锤")
        self.assertFalse(engine.start_confrontation(st, "clock_conf_1", self.llm)["started"])


class TestChapter2S(unittest.TestCase):
    def test_full_s_path(self):
        st = engine.new_game("letter", "normal", 0)
        plan = [("jia", "pawnnote"), ("shunzi", "envelope"),
                ("liu", "nib"), ("fei", "shoebox")]
        for npc, ev in plan:
            r = engine.present_evidence(st, npc, ev)
            self.assertIsNotNone(r["clue"])
        self.assertEqual(len(st["clues"]), 4)
        engine.accuse(st, "🏪 贾万通（当铺老板）")
        self.assertEqual(st["verdict"], "WIN_S")


class TestChapter3(unittest.TestCase):
    def test_s_path(self):
        st = engine.new_game("final", "normal", 0)
        plan = [("wen", "kerosene"), ("aheng", "drawing"),
                ("he", "autopsy"), ("yan", "key")]
        for npc, ev in plan:
            r = engine.present_evidence(st, npc, ev)
            self.assertIsNotNone(r["clue"])
        self.assertEqual(len(st["clues"]), 4)
        engine.accuse(st, "🏛️ 严崇山（警局局长）")
        self.assertEqual(st["verdict"], "WIN_S")

    def test_confrontations(self):
        st = engine.new_game("final", "normal", 0)
        llm = L.MockLLM()
        for pid, liar in [("final_conf_1", "严崇山"), ("final_conf_2", "严崇山")]:
            r = engine.start_confrontation(st, pid, llm)
            self.assertTrue(r["started"])
            rr = engine.resolve_confrontation(st, liar)
            self.assertTrue(rr["correct"])
        self.assertIn("L9", st["clues"])
        self.assertIn("L11", st["clues"])

    def test_wrong_liar(self):
        st = engine.new_game("final", "normal", 0)
        llm = L.MockLLM()
        engine.start_confrontation(st, "final_conf_1", llm)
        rr = engine.resolve_confrontation(st, "温书仪")
        self.assertFalse(rr["correct"])
        self.assertEqual(st["clues"], [])


class TestSave(unittest.TestCase):
    def test_roundtrip(self):
        st = engine.new_game("letter", "hard", 0)
        st["clues"] = ["L8"]
        code = engine.to_json(st)
        st2 = engine.from_json(code)
        self.assertEqual(st2["case_id"], "letter")
        self.assertEqual(st2["clues"], ["L8"])
        self.assertEqual(st2["difficulty"], "hard")

    def test_legacy_evidence_migration(self):
        st = engine.new_game("clock", "normal", 0)
        st["evidence_shown"] = {"ledger": "wang"}
        code = base64.b64encode(json.dumps(st).encode("utf-8")).decode("ascii")
        st2 = engine.from_json(code)
        self.assertTrue(st2["evidence_shown"]["ledger:wang"])

    def test_invalid_code(self):
        with self.assertRaises(ValueError):
            engine.from_json("not-a-valid-code")


if __name__ == "__main__":
    unittest.main()
