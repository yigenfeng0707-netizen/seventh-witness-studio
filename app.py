# -*- coding: utf-8 -*-
"""《第七位证人》—— AI 审讯推理游戏（奇案集 v3：警衔/章节/难度/存档）
AI+∞ 开发者创作大赛 ·「AI 造游戏」参赛作品
本地运行：python app.py  →  http://127.0.0.1:7860
"""

import os
import traceback
# 本地自检必须绕过系统代理，否则 gradio 会误判 localhost 不可访问
os.environ.setdefault("no_proxy", "127.0.0.1,localhost")
os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")


def _patch_gradio44_schema_bug():
    """gradio 4.44 已知 bug：JSON schema 中 additionalProperties 为 bool 时
    _json_schema_to_python_type 崩溃（TypeError），导致首页 GET / 返回 500。
    打补丁：bool schema 视为 Any，递归调用也会经由补丁分发。"""
    try:
        import gradio_client.utils as cu
        orig = cu._json_schema_to_python_type
        if getattr(orig, "_patched", False):
            return

        def patched(schema, defs=None):
            if isinstance(schema, bool):
                return "Any" if schema else "None"
            try:
                return orig(schema, defs)
            except TypeError:
                return "Any"

        patched._patched = True
        cu._json_schema_to_python_type = patched
    except Exception:
        pass


_patch_gradio44_schema_bug()

import gradio as gr
from PIL import Image as PILImage, ImageDraw, ImageFont

import npc_engine as engine
from game_data import CASES, GAME_TITLE, RANKS, XP_GAIN

LLM = engine.G and __import__("llm_client").get_llm()
print(f"[llm] 使用引擎：{LLM.name}")

CASE_ORDER = ["clock", "letter"]
CASE_LABELS = [CASES[cid]["case_label"] for cid in CASE_ORDER]
CASE_LABEL_TO_ID = {CASES[cid]["case_label"]: cid for cid in CASE_ORDER}
DIFF_LABELS = ["普通", "困难"]

SA_SET = ("S", "A")


def npc_labels_for(case_id):
    return {nid: f"{v['emoji']} {v['name']}（{v['role']}）"
            for nid, v in CASES[case_id]["npcs"].items()}


def ev_labels_for(case_id, difficulty):
    c = CASES[case_id]
    evs = list(c["evidence"]) + (list(c.get("hard_evidence", []))
                                 if difficulty == "hard" else [])
    return [f"{e['name']} — {e['desc']}" for e in evs]


def ev_map_for(case_id, difficulty):
    c = CASES[case_id]
    evs = list(c["evidence"]) + (list(c.get("hard_evidence", []))
                                 if difficulty == "hard" else [])
    return {f"{e['name']} — {e['desc']}": e["id"] for e in evs}


def quick_updates(case_id):
    """4 个快捷问题按钮随案件切换；不足 4 个时隐藏多余按钮。"""
    qs = CASES[case_id]["quick_qs"]
    return [gr.update(value=qs[i], visible=True) if i < len(qs)
            else gr.update(visible=False) for i in range(4)]


def parse_rank(code):
    """rank_code = "tier:winsAny:ch1SA:ch2SA"（由前端档案 JS 维护）。"""
    try:
        parts = str(code or "").split(":")
        tier = int(parts[0]) if parts and parts[0].isdigit() else 0
        wins = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        ch1 = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        ch2 = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
    except Exception:
        tier, wins, ch1, ch2 = 0, 0, 0, 0
    return tier, wins, ch1, ch2


CSS = """
/* ================= 《第七位证人》雾隐镇 · 民国悬疑主题 v2 ================= */
/* v2: 实色面板（修复透明层鬼影）+ 高对比文字 + 入场动画 */
:root {
  --night-1: #070b14;
  --night-2: #0c1220;
  --panel: #101725;
  --panel-2: #131b2e;
  --bubble-bot: #1b2438;
  --bubble-user: #2a3018;
  --line-brass: rgba(212, 169, 78, 0.32);
  --brass: #d4a94e;
  --brass-hi: #ecd08a;
  --ink: #f2ecdc;
  --ink-2: #c2cbdb;
  --danger-1: #8e1f2b;
  --danger-2: #d43d3d;
}

/* 夜幕 + 烟雾氛围（纯 CSS，无外部资源） */
body, gradio-app, .gradio-container {
  background: var(--night-1) !important;
}
.gradio-container {
  max-width: 1280px !important;
  margin: 0 auto !important;
  font-family: "PingFang SC", "Microsoft YaHei", sans-serif !important;
  color: var(--ink) !important;
  position: relative;
}
.gradio-container::before {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  background:
    radial-gradient(60% 40% at 18% 8%, rgba(212, 169, 78, 0.07), transparent 60%),
    radial-gradient(50% 45% at 85% 15%, rgba(103, 138, 199, 0.08), transparent 65%),
    linear-gradient(180deg, var(--night-2) 0%, var(--night-1) 100%);
}
.gradio-container::after {
  content: "";
  position: fixed;
  inset: -20%;
  pointer-events: none;
  z-index: 0;
  opacity: 0.45;
  background:
    radial-gradient(28% 20% at 30% 40%, rgba(140, 160, 190, 0.05), transparent 70%),
    radial-gradient(32% 22% at 72% 68%, rgba(140, 160, 190, 0.045), transparent 70%);
  animation: fog-drift 46s ease-in-out infinite alternate;
}
@keyframes fog-drift {
  0%   { transform: translate3d(-2%, -1%, 0) scale(1); }
  100% { transform: translate3d(3%, 2%, 0) scale(1.06); }
}
.gradio-container > * { position: relative; z-index: 1; }

/* 标题：民国衬线 + 铜金 */
.gradio-container h1 {
  font-family: "Noto Serif SC", "STZhongsong", "SimSun", serif !important;
  color: var(--brass-hi) !important;
  letter-spacing: 0.06em;
  text-shadow: 0 0 22px rgba(212, 169, 78, 0.35), 0 2px 6px rgba(0, 0, 0, 0.6);
  border-bottom: 1px solid var(--line-brass);
  padding-bottom: 12px !important;
}
.gradio-container h1 em, .gradio-container h1 p { color: var(--ink-2) !important; }
.gradio-container h2, .gradio-container h3 {
  font-family: "Noto Serif SC", "STZhongsong", "SimSun", serif !important;
  color: var(--brass) !important;
  letter-spacing: 0.04em;
}
.gradio-container p, .gradio-container li { color: var(--ink) !important; }
.gradio-container sub, .gradio-container small { color: var(--ink-2) !important; }

/* 通用面板：实色玻璃感 */
.gradio-container .block, .gradio-container .form, .gradio-container .panel {
  background: var(--panel) !important;
  border: 1px solid rgba(212, 169, 78, 0.16) !important;
  border-radius: 14px !important;
  box-shadow: 0 10px 34px rgba(0, 0, 0, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.04) !important;
}
.gradio-container label > span, .gradio-container .label-wrap > span {
  color: var(--brass) !important;
  font-weight: 600 !important;
  letter-spacing: 0.03em;
}

/* 审讯对象 / 案件 / 难度：人物卡式单选 */
.npc-picker label, .case-picker label, .diff-picker label {
  background: var(--panel-2) !important;
  border: 1px solid rgba(170, 179, 197, 0.25) !important;
  border-radius: 12px !important;
  padding: 9px 14px !important;
  transition: all 0.25s ease !important;
  color: var(--ink) !important;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35) !important;
}
.npc-picker label:hover, .case-picker label:hover, .diff-picker label:hover {
  border-color: var(--line-brass) !important;
  transform: translateY(-1px);
}
.npc-picker label:has(input:checked),
.case-picker label:has(input:checked),
.diff-picker label:has(input:checked) {
  border-color: var(--brass) !important;
  background: linear-gradient(180deg, rgba(212, 169, 78, 0.2), rgba(212, 169, 78, 0.07)), var(--panel-2) !important;
  box-shadow: 0 0 0 1px var(--brass), 0 6px 22px rgba(212, 169, 78, 0.22) !important;
}
.npc-picker input[type="radio"], .case-picker input[type="radio"],
.diff-picker input[type="radio"] { accent-color: var(--brass) !important; }
.rank-code, .rank-apply { display: none !important; }

/* 审讯记录（对话）：实色深底 + 高对比亮字 */
.chat-panel {
  background: #0d1424 !important;
  border: 1px solid rgba(212, 169, 78, 0.18) !important;
  border-radius: 14px !important;
}
.chat-panel .message-row, .chat-panel [class*="message"] { background: transparent !important; }
.chat-panel [class*="bubble"], .chat-panel [class*="content"], .chat-panel [class*="message"] {
  color: var(--ink) !important;
}
.chat-panel [class*="bubble"], .chat-panel [class*="message"] > div {
  background: var(--bubble-bot) !important;
  border: 1px solid rgba(170, 179, 197, 0.16) !important;
  border-radius: 12px !important;
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.35) !important;
}
.chat-panel [class*="bubble"] *, .chat-panel .message-row * { color: var(--ink) !important; }
.chat-panel .message-row.user [class*="bubble"], .chat-panel [class*="user"] [class*="bubble"] {
  background: var(--bubble-user) !important;
  border-color: var(--line-brass) !important;
}
.chat-panel .message-row.user [class*="bubble"] *, .chat-panel [class*="user"] [class*="bubble"] * {
  color: #f5e9c8 !important;
}
.chat-panel .message-row { animation: msg-in 0.35s ease both; }
@keyframes msg-in {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* 提问框 / 下拉：实色深底 */
.ask-box textarea, .gradio-container input[type="text"], .gradio-container input[type="tel"],
.gradio-container input[type="email"], .gradio-container textarea {
  background: #0a0f1c !important;
  color: var(--ink) !important;
  border: 1px solid rgba(170, 179, 197, 0.22) !important;
  border-radius: 10px !important;
}
.ask-box textarea:focus, .gradio-container input:focus, .gradio-container textarea:focus {
  border-color: var(--brass) !important;
  box-shadow: 0 0 0 1px var(--brass), 0 0 18px rgba(212, 169, 78, 0.18) !important;
}
.gradio-container input::placeholder, .gradio-container textarea::placeholder { color: #6b7689 !important; }
.evidence-select, .accuse-dd {
  background: #0a0f1c !important;
  border-radius: 10px !important;
}

/* 按钮：铜金主调 */
.gradio-container button {
  border-radius: 10px !important;
  font-weight: 600 !important;
  letter-spacing: 0.04em;
  transition: all 0.22s ease !important;
}
.gradio-container button.primary, .gradio-container button[type="submit"],
.gradio-container .quick-btn {
  background: linear-gradient(180deg, #2a3552, #1c2440) !important;
  color: var(--brass-hi) !important;
  border: 1px solid var(--line-brass) !important;
}
.gradio-container button.primary:hover, .gradio-container .quick-btn:hover {
  background: linear-gradient(180deg, #33406a, #232c4e) !important;
  border-color: var(--brass) !important;
  box-shadow: 0 0 18px rgba(212, 169, 78, 0.25) !important;
  transform: translateY(-1px);
}
.evidence-btn {
  background: linear-gradient(180deg, rgba(212, 169, 78, 0.32), rgba(212, 169, 78, 0.14)), #1c2440 !important;
  color: var(--brass-hi) !important;
  border: 1px solid var(--brass) !important;
}
.evidence-btn:hover {
  box-shadow: 0 0 22px rgba(212, 169, 78, 0.35) !important;
  transform: translateY(-1px);
}

/* 结案指认：血色终局 */
.accuse-btn {
  background: linear-gradient(180deg, var(--danger-2), var(--danger-1)) !important;
  color: #fff2ec !important;
  border: 1px solid rgba(255, 120, 110, 0.5) !important;
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.5) !important;
  letter-spacing: 0.12em !important;
  animation: accuse-breathe 3.2s ease-in-out infinite;
}
@keyframes accuse-breathe {
  0%, 100% { box-shadow: 0 6px 24px rgba(140, 30, 40, 0.4); }
  50%      { box-shadow: 0 6px 34px rgba(212, 60, 60, 0.55); }
}
.accuse-btn:hover { transform: translateY(-1px); }
.accuse-dd { border: 1px solid rgba(212, 60, 60, 0.35) !important; }

/* HUD：时间 */
.hud-clock {
  background: var(--panel) !important;
  border: 1px solid var(--line-brass) !important;
  border-radius: 14px !important;
  padding: 14px 16px !important;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45) !important;
}
.hud-clock strong {
  color: var(--brass-hi) !important;
  font-size: 1.25em !important;
  animation: clock-pulse 2.6s ease-in-out infinite;
}
@keyframes clock-pulse {
  0%, 100% { text-shadow: 0 0 10px rgba(212, 169, 78, 0.3); }
  50%      { text-shadow: 0 0 22px rgba(212, 169, 78, 0.55); }
}

/* HUD：嫌疑人状态卡（实色） */
.status-card {
  background: var(--panel) !important;
  border: 1px solid var(--line-brass) !important;
  border-radius: 14px !important;
  padding: 16px 18px !important;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45) !important;
}
.status-card h3 {
  margin-top: 0 !important;
  border-bottom: 1px dashed var(--line-brass);
  padding-bottom: 8px;
}
.status-card blockquote {
  border-left: 2px solid var(--brass) !important;
  color: var(--ink-2) !important;
  font-style: italic;
  margin: 8px 0 !important;
}
.status-card li { color: var(--ink-2) !important; }
.status-card strong { color: var(--brass-hi) !important; }

/* 线索板 */
.clue-board {
  background: #171223 !important;
  border: 1px solid var(--line-brass) !important;
  border-radius: 12px !important;
  padding: 12px 14px !important;
}
.clue-board strong { color: var(--brass-hi) !important; }
.gradio-container .accordion, .gradio-container details {
  border: 1px solid rgba(212, 169, 78, 0.22) !important;
  border-radius: 12px !important;
  background: var(--panel-2) !important;
}
.gradio-container details summary, .gradio-container .accordion-header {
  color: var(--brass) !important;
  font-weight: 700 !important;
  letter-spacing: 0.05em;
}

/* 结局卷轴：入场动画 */
.verdict-card {
  border: 2px solid var(--brass) !important;
  border-radius: 18px !important;
  background:
    radial-gradient(80% 60% at 50% 0%, rgba(212, 169, 78, 0.14), transparent 70%),
    linear-gradient(180deg, #14100a, #0a0e18) !important;
  box-shadow: 0 18px 60px rgba(0, 0, 0, 0.6), 0 0 40px rgba(212, 169, 78, 0.12) !important;
  padding: 22px 26px !important;
  animation: verdict-in 0.9s cubic-bezier(0.2, 0.9, 0.3, 1.1) both;
}
@keyframes verdict-in {
  0%   { opacity: 0; transform: translateY(28px) scale(0.96); filter: brightness(0.4); }
  60%  { opacity: 1; filter: brightness(1.25); }
  100% { opacity: 1; transform: translateY(0) scale(1); filter: brightness(1); }
}
.verdict-card h2 {
  font-size: 1.6em !important;
  text-align: center;
  text-shadow: 0 0 26px rgba(212, 169, 78, 0.45) !important;
}

/* 警衔徽章栏 */
.rank-bar {
  background: var(--panel-2) !important;
  border: 1px solid var(--line-brass) !important;
  border-radius: 12px !important;
  min-height: 20px;
}
.rank-bar b { letter-spacing: 0.04em; }

/* 细节 */
.gradio-container a { color: var(--brass-hi) !important; }
.gradio-container ::selection { background: rgba(212, 169, 78, 0.35); }
.gradio-container ::-webkit-scrollbar { width: 9px; height: 9px; }
.gradio-container ::-webkit-scrollbar-thumb { background: rgba(212, 169, 78, 0.3); border-radius: 6px; }
.gradio-container ::-webkit-scrollbar-track { background: rgba(255, 255, 255, 0.03); }

/* 手机端 */
@media (max-width: 640px) {
  .chat-panel { height: 300px !important; }
  .gradio-container { padding: 0 4px !important; }
}
"""

SOUND_JS = r"""
() => {
  let actx = null, muted = false;
  const ac = () => (actx = actx || new (window.AudioContext || window.webkitAudioContext)());
  function tone(freq, dur, type, gain, delay, slide) {
    if (muted) return;
    try {
      const c = ac();
      const o = c.createOscillator(), g = c.createGain();
      o.type = type || 'sine';
      o.frequency.setValueAtTime(freq, c.currentTime + (delay || 0));
      if (slide) o.frequency.exponentialRampToValueAtTime(slide, c.currentTime + (delay || 0) + dur);
      g.gain.setValueAtTime(gain || 0.06, c.currentTime + (delay || 0));
      g.gain.exponentialRampToValueAtTime(0.0001, c.currentTime + (delay || 0) + dur);
      o.connect(g); g.connect(c.destination);
      o.start(c.currentTime + (delay || 0)); o.stop(c.currentTime + (delay || 0) + dur + 0.02);
    } catch (e) {}
  }
  const sfx = {
    click:    () => tone(1100, 0.05, 'sine', 0.05),
    send:     () => tone(520, 0.12, 'sine', 0.06, 0, 880),
    reply:    () => { tone(660, 0.16, 'sine', 0.06); tone(880, 0.22, 'sine', 0.05, 0.12); },
    clue:     () => { [523, 659, 784, 1047].forEach((f, i) => tone(f, 0.18, 'triangle', 0.07, i * 0.09)); },
    evidence: () => { tone(1400, 0.08, 'square', 0.04); tone(900, 0.12, 'triangle', 0.05, 0.06); },
    accuse:   () => { tone(160, 0.5, 'sawtooth', 0.08); tone(220, 0.6, 'sawtooth', 0.06, 0.05); tone(110, 0.9, 'sine', 0.08, 0.1); },
    verdict:  () => { [392, 523, 659].forEach((f, i) => tone(f, 0.4, 'triangle', 0.06, i * 0.12)); },
    rankup:   () => { [523, 659, 784, 1047, 1319].forEach((f, i) => tone(f, 0.22, 'triangle', 0.07, i * 0.11)); }
  };

  // 静音开关（右上角悬浮）
  const btn = document.createElement('button');
  btn.textContent = '🔊';
  btn.title = '游戏音效开关';
  btn.style.cssText = 'position:fixed;top:8px;right:8px;z-index:9999;background:rgba(16,23,37,.92);border:1px solid rgba(212,169,78,.4);color:#ecd08a;border-radius:50%;width:36px;height:36px;font-size:15px;cursor:pointer;';
  btn.onclick = () => { muted = !muted; btn.textContent = muted ? '🔇' : '🔊'; if (!muted) sfx.click(); };
  document.body.appendChild(btn);

  // 按钮点击音（事件委托，捕获阶段）
  document.addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b || b === btn) return;
    const t = (b.innerText || '').replace(/\s+/g, '');
    if (t.includes('结案指认')) { sfx.accuse(); setTimeout(() => sfx.verdict(), 700); }
    else if (t.includes('出示证据')) sfx.evidence();
    else if (t.includes('发送') || b.getAttribute('type') === 'submit') sfx.send();
    else sfx.click();
  }, true);

  // 新消息侦听：气泡数量变化 → 对应音效
  let prevCount = -1;
  const hook = () => {
    const chat = document.querySelector('.chat-panel, [class*="chatbot"]');
    if (!chat) return;
    const bubbles = chat.querySelectorAll('[class*="bubble"], [class*="message"]');
    const key = bubbles.length;
    if (prevCount >= 0 && key > prevCount) {
      const last = bubbles[bubbles.length - 1];
      const txt = (last.innerText || '');
      if (txt.includes('关键线索解锁')) sfx.clue();
      else if (txt.includes('侦探：')) sfx.send();
      else if (txt.trim()) sfx.reply();
    }
    prevCount = key;
  };
  const mo = new MutationObserver(() => setTimeout(hook, 60));
  const mount = () => {
    const chat = document.querySelector('.chat-panel, [class*="chatbot"]');
    if (chat) { mo.observe(chat, {childList: true, subtree: true}); hook(); }
    else setTimeout(mount, 800);
  };
  mount();

  // ===== 侦探档案：警衔 / 章节 / 难度解锁（localStorage） =====
  const PKEY = 'd7w_profile_v1';
  const RANKS = [[0, '见习侦探'], [100, '三级探员'], [250, '二级探员'], [450, '一级探员'], [700, '高级探员'], [1000, '首席侦探']];
  const CASE_KEYS = ['clock', 'letter'];
  const CASE_NAMES = {'clock': '第一章', 'letter': '第二章'};
  const GAINS = {'S': 100, 'A': 70, 'B': 40, 'LOSE': 10, 'TIMEUP': 10};
  const loadProf = () => { try { return JSON.parse(localStorage.getItem(PKEY)) || {xp: 0, wins: 0, best: {}, hardBest: {}}; } catch (e) { return {xp: 0, wins: 0, best: {}, hardBest: {}}; } };
  const saveProf = (p) => { try { localStorage.setItem(PKEY, JSON.stringify(p)); } catch (e) {} };
  const tierOf = (xp) => { let t = 0; RANKS.forEach(([th], i) => { if (xp >= th) t = i; }); return t; };
  const rankName = (t) => RANKS[t][1];
  const nextTh = (t) => (t + 1 < RANKS.length ? RANKS[t + 1][0] : RANKS[RANKS.length - 1][0]);

  function parseRating(txt) {
    txt = txt || '';
    if (txt.indexOf('S 级') >= 0) return 'S';
    if (txt.indexOf('A 级') >= 0) return 'A';
    if (txt.indexOf('险胜') >= 0) return 'B';
    if (txt.indexOf('冤案') >= 0) return 'LOSE';
    if (txt.indexOf('时间耗尽') >= 0) return 'TIMEUP';
    return null;
  }

  function currentCaseKey() {
    const inp = document.querySelector('.case-picker input:checked');
    const v = inp ? inp.value : '';
    for (const k of CASE_KEYS) { if (v.indexOf(CASE_NAMES[k]) >= 0) return k; }
    return 'clock';
  }
  function isHard() {
    const inp = document.querySelector('.diff-picker input:checked');
    return !!inp && inp.value === '困难';
  }

  function syncRankCode() {
    const prof = loadProf();
    const tier = tierOf(prof.xp);
    const ch1 = prof.best.clock || '';
    const ch2 = prof.best.letter || '';
    const code = [tier, prof.wins || 0,
                  (ch1 === 'S' || ch1 === 'A') ? 1 : 0,
                  (ch2 === 'S' || ch2 === 'A') ? 1 : 0].join(':');
    const inp = document.querySelector('.rank-code input, .rank-code textarea');
    if (inp) {
      inp.value = code;
      inp.dispatchEvent(new Event('input', {bubbles: true}));
      inp.dispatchEvent(new Event('change', {bubbles: true}));
    }
  }

  function renderRankBar() {
    const prof = loadProf();
    const t = tierOf(prof.xp);
    const bar = document.querySelector('.rank-bar');
    if (!bar) return;
    const stars = CASE_KEYS.map(k => {
      const nm = CASE_NAMES[k];
      const r = prof.best[k];
      const hr = prof.hardBest[k];
      return nm + ' ' + (r ? '⭐' + r : '🌑') + (hr ? ' ★' + hr : '');
    }).join('　');
    const lock = (prof.best.clock === 'S' || prof.best.clock === 'A');
    bar.innerHTML = '<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:10px 14px;">' +
      '<span style="border:1px solid rgba(212,169,78,.4);border-radius:999px;padding:4px 12px;background:rgba(212,169,78,.12);">🎖️ <b style="color:#ecd08a">' + rankName(t) + '</b></span>' +
      '<span style="color:#c2cbdb;font-size:.9em;">声望 ' + prof.xp + ' / 下一级 ' + nextTh(t) + '</span>' +
      '<span style="color:#c2cbdb;font-size:.9em;">' + stars + '</span>' +
      (lock ? '<span style="color:#4cc38a;font-size:.9em;">第二章 ✓ ｜ 困难模式 ✓</span>'
            : '<span style="color:#8b93a5;font-size:.9em;">🔒 第二章 / 困难模式：以 S/A 通关第一章解锁</span>') +
      '</div>';
    document.querySelectorAll('.case-picker label').forEach(lb => {
      const inp = lb.querySelector('input');
      if (inp && (inp.value || '').indexOf('第二章') >= 0) {
        lb.style.opacity = lock ? 1 : 0.45;
        lb.style.cursor = lock ? 'pointer' : 'not-allowed';
      }
    });
    syncRankCode();
  }

  function registerVerdict() {
    const vc = document.querySelector('.verdict-card');
    const visible = vc && vc.getBoundingClientRect().height > 0;
    if (!visible) { window._d7w_flag = false; return; }
    if (window._d7w_flag) return;
    window._d7w_flag = true;
    const rating = parseRating((vc.querySelector('h2') || {}).innerText);
    if (!rating) return;
    const prof = loadProf();
    prof.xp += GAINS[rating] || 10;
    if (rating === 'S' || rating === 'A') prof.wins = (prof.wins || 0) + 1;
    const ckey = currentCaseKey();
    const store = isHard() ? prof.hardBest : prof.best;
    const prev = store[ckey];
    if (!prev || (GAINS[rating] || 0) >= (GAINS[prev] || 0)) store[ckey] = rating;
    saveProf(prof);
    sfx.verdict();
    if (tierOf(prof.xp) > tierOf(prof.xp - (GAINS[rating] || 0))) setTimeout(() => sfx.rankup(), 500);
    renderRankBar();
  }
  setInterval(registerVerdict, 1500);
  renderRankBar();
  setTimeout(() => {
    if (tierOf(loadProf().xp) >= 2) {
      const ap = document.querySelector('.rank-apply button');
      if (ap) ap.click();
    }
  }, 1200);
}
"""

# 统一输出槽位（见 Blocks 内定义）
OUT = None      # 9 项：常规刷新
FULL = None     # 19 项：全量刷新（含案件/难度/状态/存档/指认/快捷问题/成绩卡）


def _msgs(text):
    return [{"role": "assistant", "content": text}]


def do_restart(case_label, diff_label, rank_code):
    cid = CASE_LABEL_TO_ID.get(case_label, "clock")
    diff_label = diff_label if diff_label in DIFF_LABELS else "普通"
    difficulty = "hard" if diff_label == "困难" else "normal"
    tier, wins_any, ch1_sa, ch2_sa = parse_rank(rank_code)

    if difficulty == "hard" and wins_any < 1:
        gr.Warning("🔒 困难模式需先以 S/A 评级通关任意一章")
        difficulty = "normal"
        diff_label = "普通"
    if cid == "letter" and ch1_sa != 1:
        gr.Warning("🔒 第二章需先以 S/A 评级通关第一章")
        cid = "clock"
        case_label = CASES["clock"]["case_label"]

    c = CASES[cid]
    st = engine.new_game(cid, difficulty, tier)
    greet = engine.switch(st, st["cur"])
    intro = (f"📜 **【卷宗 · {c['case_label']}】**\n\n{c['brief']}\n\n"
             f"🎯 **目标**：在 {st['time']} 分钟内集齐 {len(c['key_clues'])} 条关键线索，"
             f"从 {len(c['accuse_options'])} 人中指认真凶。\n\n"
             f"—— {greet}")
    npc_l = npc_labels_for(cid)
    ev_l = ev_labels_for(cid, difficulty)
    return (_msgs(intro), engine.clock_md(st), engine.status_card(st, st["cur"]),
            engine.clue_board(st), gr.Group(visible=False), gr.skip(), "",
            gr.update(choices=list(npc_l.values()), value=npc_l[st["cur"]]),
            gr.update(choices=ev_l, value=None),
            gr.update(value=case_label), gr.update(value=diff_label), st, gr.skip(),
            gr.update(choices=c["accuse_options"], value=None),
            *quick_updates(cid), gr.update(value=None, visible=False))


def do_switch(label, chat, state):
    npc_id = engine.CD(state)["default_npc"]
    labels = npc_labels_for(state["case_id"])
    npc_id = next((k for k, v in labels.items() if v == label), state["cur"])
    if state["ended"]:
        return (chat, engine.clock_md(state), engine.status_card(state, state["cur"]),
                engine.clue_board(state), gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip())
    greet = engine.switch(state, npc_id)
    return (_msgs(greet), engine.clock_md(state), engine.status_card(state, npc_id),
            engine.clue_board(state), gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip())


def do_ask(question, chat, state):
    chat = list(chat)
    q = (question or "").strip()
    clock = engine.clock_md(state)
    status = engine.status_card(state, state["cur"])
    clue = engine.clue_board(state)
    grp, md = gr.skip(), gr.skip()
    if state["ended"]:
        return (chat, clock, status, clue, gr.Group(visible=True),
                engine.end_markdown(state), q, gr.skip(), gr.skip())
    if q:
        before_trust = state["npc"][state["cur"]]["trust"]
        try:
            res = engine.ask(state, state["cur"], q, LLM)
        except Exception:
            # 任何 LLM/引擎异常都不外露给玩家：记录日志，回一句角色化兜底。
            traceback.print_exc()
            res = {"reply": "（他沉默了片刻，似乎在斟酌措辞，终究没有作答。）",
                   "clue": None, "timeup": False}
        npc_name = engine.CD(state)["npcs"][state["cur"]]["name"]
        delta = state["npc"][state["cur"]]["trust"] - before_trust
        chat.append({"role": "user", "content": f"🧑‍✈️ 侦探：{q}"})
        chat.append({"role": "assistant", "content": f"{npc_name}：{res['reply']}"})
        if delta:
            chat.append({"role": "assistant", "content": f"（{npc_name} 的信任 {delta:+d}）"})
        if res["clue"]:
            chat.append({"role": "assistant", "content": "🔎 【关键线索解锁！查看右侧线索板】"})
        clock = engine.clock_md(state)
        status = engine.status_card(state, state["cur"])
        clue = engine.clue_board(state)
        if res["timeup"]:
            grp, md = gr.Group(visible=True), engine.end_markdown(state)
    return (chat, clock, status, clue, grp, md, "", gr.skip(), gr.skip())


def do_present(ev_label, chat, state):
    chat = list(chat)
    clock = engine.clock_md(state)
    status = engine.status_card(state, state["cur"])
    clue = engine.clue_board(state)
    grp, md = gr.skip(), gr.skip()
    if state["ended"]:
        return (chat, clock, status, clue, gr.Group(visible=True),
                engine.end_markdown(state), "", gr.skip(), gr.skip())
    ev_map = ev_map_for(state["case_id"], state.get("difficulty", "normal"))
    npc = engine.CD(state)["npcs"][state["cur"]]
    ev_id = ev_map.get(ev_label or "")
    if not ev_id:
        chat.append({"role": "assistant", "content": "（先在证物栏里选一件证物，再出示。）"})
        return (chat, clock, status, clue, grp, md, "", gr.skip(), gr.skip())
    ev_name = ev_label.split(" — ")[0]
    before_trust = state["npc"][state["cur"]]["trust"]
    chat.append({"role": "user", "content": f"🧑‍✈️ 侦探出示了证物：{ev_name}"})
    try:
        res = engine.present_evidence(state, state["cur"], ev_id)
    except Exception:
        traceback.print_exc()
        res = {"reply": "（他瞥了一眼，没有接话。）", "clue": None, "timeup": False}
    delta = state["npc"][state["cur"]]["trust"] - before_trust
    chat.append({"role": "assistant", "content": f"{npc['name']}：{res['reply']}"})
    if delta:
        chat.append({"role": "assistant", "content": f"（{npc['name']} 的信任 {delta:+d}）"})
    if res["clue"]:
        chat.append({"role": "assistant", "content": "🔎 【关键线索解锁！查看右侧线索板】"})
    clock = engine.clock_md(state)
    status = engine.status_card(state, state["cur"])
    clue = engine.clue_board(state)
    if res["timeup"]:
        grp, md = gr.Group(visible=True), engine.end_markdown(state)
    return (chat, clock, status, clue, grp, md, "", gr.skip(), gr.skip())


def do_accuse(choice, chat, state):
    chat = list(chat)
    clock = engine.clock_md(state)
    status = engine.status_card(state, state["cur"])
    clue = engine.clue_board(state)
    card_reset = gr.update(value=None, visible=False)
    if not choice:
        chat.append({"role": "assistant",
                     "content": "（请先从名单中选择一个名字，再按下结案指认。）"})
        return (chat, clock, status, clue, gr.skip(), gr.skip(), gr.skip(), gr.skip(),
                gr.skip(), card_reset)
    if not state["ended"]:
        try:
            engine.accuse(state, choice)
        except Exception:
            traceback.print_exc()
            chat.append({"role": "assistant",
                         "content": "（结案文书出了点岔子，请再按一次指认。）"})
            return (chat, clock, status, clue, gr.skip(), gr.skip(), gr.skip(), gr.skip(),
                    gr.skip(), card_reset)
    return (chat, clock, status, clue, gr.Group(visible=True),
            engine.end_markdown(state), gr.skip(), gr.skip(), gr.skip(), card_reset)


def do_quick_ask(question, chat, state):
    return do_ask(question, chat, state)


def do_export(state):
    try:
        return engine.to_json(state)
    except Exception:
        return "（导出失败）"


def do_load(code):
    try:
        st = engine.from_json(code or "")
    except ValueError as e:
        raise gr.Error(str(e))
    cid = st["case_id"]
    c = CASES[cid]
    diff_label = "困难" if st.get("difficulty") == "hard" else "普通"
    cur = st.get("cur") or c["default_npc"]
    npc_l = npc_labels_for(cid)
    ev_l = ev_labels_for(cid, st.get("difficulty", "normal"))
    greet = engine.switch(st, cur)
    greet = (f"📂 **已读取存档：{c['case_label']}**"
             f"（剩余 {st['time']} 分钟，线索 {len(st['clues'])}/{len(c['key_clues'])}）\n\n{greet}")
    ended = bool(st.get("ended", False))
    return (_msgs(greet), engine.clock_md(st), engine.status_card(st, cur),
            engine.clue_board(st), gr.Group(visible=ended),
            engine.end_markdown(st) if ended else gr.skip(),
            "", gr.update(choices=list(npc_l.values()), value=npc_l[cur]),
            gr.update(choices=ev_l, value=None),
            gr.update(value=c["case_label"]), gr.update(value=diff_label),
            st, "",
            gr.update(choices=c["accuse_options"], value=None),
            *quick_updates(cid), gr.update(value=None, visible=False))


def _card_font(size):
    """成绩卡字体：容器内 Noto CJK 优先（Dockerfile 安装），Windows 字体兜底。"""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "assets", "fonts", "NotoSansSC-Regular.otf"),
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
    ]
    for path in candidates:
        try:
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def do_card(state, rank_code):
    if not state.get("ended"):
        gr.Warning("结案后才能生成成绩卡")
        return gr.update(value=None, visible=False)
    try:
        c = engine.CD(state)
        tier, _w, _c1, _c2 = parse_rank(rank_code)
        tier = max(0, min(tier, len(RANKS) - 1))
        rank_name = RANKS[tier][1]
        v = state.get("verdict") or "TIMEUP"
        rating_txt = {"WIN_S": "★★★ S 级破案", "WIN_A": "★★ A 级破案",
                      "WIN_B": "★ B 级结案", "LOSE": "X 冤案", "TIMEUP": "超时"}[v]
        W, H = 1200, 630
        img = PILImage.new("RGB", (W, H), (10, 14, 23))
        d = ImageDraw.Draw(img)
        for y in range(H):
            t = y / H
            d.line([(0, y), (W, y)],
                   fill=(int(13 + 8 * (1 - t)), int(19 + 6 * (1 - t)), int(32 + 4 * (1 - t))))
        font_big, font_mid, font_sm, font_xs = (
            _card_font(72), _card_font(40), _card_font(28), _card_font(22))
        d.rectangle([14, 14, W - 15, H - 15], outline=(212, 169, 78), width=4)
        d.rectangle([26, 26, W - 27, H - 27], outline=(120, 100, 55), width=1)
        d.text((W // 2, 92), "侦探成绩卡", font=font_big, fill=(236, 208, 138), anchor="mm")
        d.text((W // 2, 190), rating_txt, font=font_big, fill=(255, 242, 236), anchor="mm")
        d.text((W // 2, 290), f"《{c['title']}》", font=font_mid, fill=(236, 208, 138), anchor="mm")
        d.text((W // 2 - 10, 370), f"剩余审讯时间：{state['time']} 分钟",
               font=font_sm, fill=(236, 208, 138), anchor="mm")
        d.text((W // 2 - 10, 420), f"关键线索：{len(state['clues'])}/{len(c['key_clues'])}",
               font=font_sm, fill=(236, 208, 138), anchor="mm")
        d.text((W // 2 - 10, 470), f"侦探警衔：{rank_name}",
               font=font_sm, fill=(236, 208, 138), anchor="mm")
        d.text((W // 2, 560), "试玩：https://gsym236998-seventh-witness.ms.show",
               font=font_sm, fill=(236, 208, 138), anchor="mm")
        d.text((W // 2, 596), "AI+∞ 开发者创作大赛 · 第三期「AI 造游戏」",
               font=font_xs, fill=(170, 179, 197), anchor="mm")
        return gr.update(value=img, visible=True)
    except Exception:
        traceback.print_exc()
        gr.Warning("成绩卡生成失败，请稍后再试")
        return gr.update(value=None, visible=False)


with gr.Blocks(title=GAME_TITLE, css=CSS, js=SOUND_JS) as demo:
    gr.Markdown(
        f"# 🕰️ {GAME_TITLE}\n"
        f"*「AI 造游戏」参赛作品 · 把 AI 的记忆做成玩法的审讯推理游戏*\n\n"
        f"**雾隐镇奇案集** —— 每一案，都藏着一位会撒谎、会记仇、会被打动的 AI。\n\n"
        f"<sub>🤖 当前 AI 引擎：**{LLM.name}**</sub>"
    )
    rank_md = gr.Markdown(elem_classes=["rank-bar"])
    rank_code = gr.Textbox(elem_classes=["rank-code"], show_label=False, container=False)
    state = gr.State(engine.new_game())

    with gr.Row():
        case_dd = gr.Radio(choices=CASE_LABELS,
                           value=CASE_LABELS[0],
                           label="奇案集（切换案件将开启新局，进度可用存档码保存）",
                           elem_classes=["case-picker"])
        diff_radio = gr.Radio(choices=DIFF_LABELS, value="普通",
                              label="难度（困难模式需 S/A 通关解锁）",
                              elem_classes=["diff-picker"])

    with gr.Row():
        with gr.Column(scale=7):
            npc_dd = gr.Radio(choices=list(npc_labels_for("clock").values()),
                              value=npc_labels_for("clock")[CASES["clock"]["default_npc"]],
                              label="审讯对象（随时切换，不耗时）",
                              elem_classes=["npc-picker"])
            chat = gr.Chatbot(label="审讯记录", height=380, elem_classes=["chat-panel"])
            q_box = gr.Textbox(placeholder="向当前对象提问…（点击 ➤ 发送，每次 -1 分钟）",
                               show_label=False, container=False, submit_btn=True,
                               elem_classes=["ask-box"])
            with gr.Row():
                quick_btns = [gr.Button(qq, size="sm", elem_classes=["quick-btn"])
                              for qq in CASES["clock"]["quick_qs"]]
            with gr.Row():
                ev_dd = gr.Dropdown(choices=ev_labels_for("clock", "normal"),
                                    label="证物（现场勘查所得）", value=None,
                                    elem_classes=["evidence-select"])
                ev_btn = gr.Button("出示证据（-2 分钟）", variant="secondary",
                                   elem_classes=["evidence-btn"])
        with gr.Column(scale=3):
            clock_md = gr.Markdown(elem_classes=["hud-clock"])
            status_md = gr.Markdown(elem_classes=["status-card"])
            with gr.Accordion("🔎 线索板", open=True):
                clue_md = gr.Markdown(elem_classes=["clue-board"])
            with gr.Accordion("❓ 怎么玩（30 秒上手）", open=False):
                gr.Markdown(
                    "1. **提问**：每次 -1 分钟；快捷问题同样扣时。\n"
                    "2. **出示证据**：每次 -2 分钟；对的证据 × 对的人 = 坦白 + 关键线索。\n"
                    "3. **指认**：集齐线索后随时可指认；线索数决定 S/A/B，指认错误是冤案。\n"
                    "4. **信任**：<15 被逐客（额外 -2 分钟）；<25 拒答关键案情；≥85 会主动透话。"
                )
            accuse_dd = gr.Dropdown(choices=CASES["clock"]["accuse_options"],
                                    label="指认真凶（一锤定音，慎重！）",
                                    elem_classes=["accuse-dd"])
            accuse_btn = gr.Button("🚨 结案指认", variant="stop", elem_classes=["accuse-btn"])
            with gr.Accordion("💾 存档 / 续玩", open=False):
                save_box = gr.Textbox(label="存档码（导出后复制保存；续玩时粘贴→读取并继续）",
                                      lines=3, max_lines=5)
                with gr.Row():
                    save_btn = gr.Button("📤 生成存档码", size="sm", elem_classes=["quick-btn"])
                    load_btn = gr.Button("📥 读取并继续", size="sm", elem_classes=["quick-btn"])
            apply_btn = gr.Button("应用警衔", visible=False, elem_classes=["rank-apply"])

    verdict_grp = gr.Group(visible=False, elem_classes=["verdict-card"])
    with verdict_grp:
        verdict_md = gr.Markdown()
        card_btn = gr.Button("📸 生成侦探成绩卡（可保存分享）", elem_classes=["quick-btn"])
        card_img = gr.Image(interactive=False, show_label=False, visible=False,
                            elem_classes=["card-img"])
        restart_btn = gr.Button("🔄 重新开始")

    OUT = [chat, clock_md, status_md, clue_md, verdict_grp, verdict_md, q_box, npc_dd, ev_dd]
    FULL = (OUT + [case_dd, diff_radio, state, save_box, accuse_dd]
            + quick_btns + [card_img])

    demo.load(do_restart, [case_dd, diff_radio, rank_code], FULL)
    apply_btn.click(do_restart, [case_dd, diff_radio, rank_code], FULL)
    case_dd.change(do_restart, [case_dd, diff_radio, rank_code], FULL)
    diff_radio.change(do_restart, [case_dd, diff_radio, rank_code], FULL)
    npc_dd.change(do_switch, [npc_dd, chat, state], OUT)
    q_box.submit(do_ask, [q_box, chat, state], OUT)
    ev_btn.click(do_present, [ev_dd, chat, state], OUT)
    accuse_btn.click(do_accuse, [accuse_dd, chat, state], OUT + [card_img])
    restart_btn.click(do_restart, [case_dd, diff_radio, rank_code], FULL)
    card_btn.click(do_card, [state, rank_code], [card_img])
    save_btn.click(do_export, [state], [save_box])
    load_btn.click(do_load, [save_box], FULL)
    for b, qq in zip(quick_btns, CASES["clock"]["quick_qs"]):
        b.click(do_quick_ask, [b, chat, state], OUT)

if __name__ == "__main__":
    # 创空间容器必须监听 0.0.0.0:7860；本地默认同配置，无副作用
    demo.launch(server_name=os.environ.get("GRADIO_SERVER_NAME", "0.0.0.0"),
                server_port=7860, share=False, show_error=False)
