# -*- coding: utf-8 -*-
"""UI 契约回归：输出槽位 / 章节切换 / 锁定回退 / 成绩卡。"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import app                    # noqa: E402
import npc_engine as engine   # noqa: E402


class TestContracts(unittest.TestCase):
    def test_output_slots(self):
        self.assertEqual(len(app.OUT), 9)
        self.assertEqual(len(app.FULL), 21)

    def test_restart_locked_chapter_rolls_back(self):
        out = app.do_restart("第二章 · 狱中忏悔信失踪案", "普通", "0:0:0:0")
        self.assertEqual(len(out), 21)
        self.assertEqual(out[9]["value"], "第一章 · 自鸣钟机芯失窃案")

    def test_restart_locked_hard_rolls_back(self):
        out = app.do_restart("第一章 · 自鸣钟机芯失窃案", "困难", "0:0:0:0")
        self.assertEqual(out[10]["value"], "普通")

    def test_restart_chapter2_syncs_accuse_and_quick(self):
        out = app.do_restart("第二章 · 狱中忏悔信失踪案", "普通", "0:1:1:0")
        self.assertEqual(out[9]["value"], "第二章 · 狱中忏悔信失踪案")
        self.assertIn("🏪 贾万通（当铺老板）", out[13]["choices"])
        self.assertEqual(out[14]["value"], "忏悔信里写了什么？")
        self.assertEqual(out[17]["value"], "谁最可能截走它？")

    def test_final_chapter_gate_and_choices(self):
        locked = app.do_restart("终章 · 第七位证人", "普通", "0:1:1:0")
        self.assertEqual(locked[9]["value"], "第一章 · 自鸣钟机芯失窃案")
        out = app.do_restart("终章 · 第七位证人", "普通", "0:1:1:1")
        self.assertEqual(out[9]["value"], "终章 · 第七位证人")
        self.assertIn("🏛️ 严崇山（警局局长）", out[13]["choices"])
        self.assertEqual(out[14]["value"], "火灾那晚你在哪里？")
        self.assertEqual(len(out[19]["choices"]), 2)  # 两个对质点

    def test_restart_intro_contains_brief(self):
        out = app.do_restart("第一章 · 自鸣钟机芯失窃案", "普通", "0:0:0:0")
        self.assertIn("卷宗", out[0][0]["content"])
        self.assertIn("目标", out[0][0]["content"])

    def test_load_chapter2_syncs_accuse(self):
        st = engine.new_game("letter", "normal", 0)
        out = app.do_load(engine.to_json(st))
        self.assertEqual(len(out), 21)
        self.assertEqual(out[9]["value"], "第二章 · 狱中忏悔信失踪案")
        self.assertIn("🏪 贾万通（当铺老板）", out[13]["choices"])

    def test_handler_slot_counts(self):
        st = engine.new_game()
        self.assertEqual(len(app.do_ask("你好", [], st)), 9)
        self.assertEqual(len(app.do_present("📄 账本残页 — x", [], st)), 9)
        self.assertEqual(len(app.do_switch("🍵 苏眉（酒馆老板娘）", [], st)), 9)
        self.assertEqual(len(app.do_accuse("🔨 王大锤（铁匠）", [], st)), 10)
        st2 = engine.new_game("clock")
        self.assertEqual(len(app.do_confront("王大锤 × 苏眉 · 案发当晚", [], st2)), 10)
        self.assertEqual(len(app.do_resolve("王大锤", [], st2)), 10)

    def test_confront_roundtrip(self):
        st = engine.new_game("clock")
        out = app.do_confront("王大锤 × 苏眉 · 案发当晚", [], st)
        self.assertEqual(out[8]["choices"], ["王大锤", "苏眉"])
        resolved = app.do_resolve("王大锤", out[0], st)
        self.assertIn("L4", st["clues"])
        self.assertFalse(resolved[7].visible)

    def test_switch_same_npc_keeps_chat(self):
        # 切案/读档时程序化更新 npc_dd 不应把聊天区覆盖成问候
        st = engine.new_game()
        out = app.do_switch("🔨 王大锤（铁匠）", ["卷宗"], st)
        self.assertNotIsInstance(out[0], list)

    def test_card_requires_verdict(self):
        st = engine.new_game()
        out = app.do_card(st, "0:0:0:0")
        self.assertFalse(out["visible"])

    def test_card_generates_image(self):
        st = engine.new_game("clock", "normal", 0)
        engine.accuse(st, "⌚ 沈墨白（钟表匠·已出城）")
        out = app.do_card(st, "99:0:0:0")  # tier 越界应被 clamp
        self.assertTrue(out["visible"])
        self.assertEqual(out["value"].size, (1200, 630))


if __name__ == "__main__":
    unittest.main()
