# -*- coding: utf-8 -*-
"""《第七位证人》—— AI 审讯推理游戏
AI+∞ 开发者创作大赛 ·「AI 造游戏」参赛作品
本地运行：python app.py  →  http://127.0.0.1:7860
"""

import os
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

import npc_engine as engine
from game_data import (ACCUSE_OPTIONS, CASE_BRIEF, CASE_TITLE, DEFAULT_NPC,
                       EVIDENCE, NPCS, QUICK_QS)
from llm_client import get_llm

LLM = get_llm()
print(f"[llm] 使用引擎：{LLM.name}")

NPC_LABELS = {nid: f"{v['emoji']} {v['name']}（{v['role']}）" for nid, v in NPCS.items()}
ID_BY_LABEL = {v: k for k, v in NPC_LABELS.items()}
EV_OPTIONS = [f"{e['name']} — {e['desc']}" for e in EVIDENCE]
EV_ID_BY_LABEL = {f"{e['name']} — {e['desc']}": e["id"] for e in EVIDENCE}

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

/* 审讯对象：人物卡式单选 */
.npc-picker label {
  background: var(--panel-2) !important;
  border: 1px solid rgba(170, 179, 197, 0.25) !important;
  border-radius: 12px !important;
  padding: 9px 14px !important;
  transition: all 0.25s ease !important;
  color: var(--ink) !important;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35) !important;
}
.npc-picker label:hover { border-color: var(--line-brass) !important; transform: translateY(-1px); }
.npc-picker label:has(input:checked) {
  border-color: var(--brass) !important;
  background: linear-gradient(180deg, rgba(212, 169, 78, 0.2), rgba(212, 169, 78, 0.07)), var(--panel-2) !important;
  box-shadow: 0 0 0 1px var(--brass), 0 6px 22px rgba(212, 169, 78, 0.22) !important;
}
.npc-picker input[type="radio"] { accent-color: var(--brass) !important; }

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

/* 细节 */
.gradio-container a { color: var(--brass-hi) !important; }
.gradio-container ::selection { background: rgba(212, 169, 78, 0.35); }
.gradio-container ::-webkit-scrollbar { width: 9px; height: 9px; }
.gradio-container ::-webkit-scrollbar-thumb { background: rgba(212, 169, 78, 0.3); border-radius: 6px; }
.gradio-container ::-webkit-scrollbar-track { background: rgba(255, 255, 255, 0.03); }


/* ================= 响应式：手机 / 平板 / 桌面 ================= */
/* 平板竖屏与手机（≤900px）：双栏堆叠为单列，审讯流在上、HUD 在下 */
@media (max-width: 900px) {
  .gradio-container .row {
    flex-wrap: wrap !important;
  }
  .gradio-container .row > [class*="column"], .gradio-container .row > div[class*="col"],
  .gradio-container .row > .col, .gradio-container .row > div {
    flex: 1 1 100% !important;
    max-width: 100% !important;
    min-width: 100% !important;
  }
  .gradio-container { padding: 0 10px !important; }
  .gradio-container h1 { font-size: 1.5em !important; }

  /* 人物卡：双列网格，触控目标加大 */
  .npc-picker {
    display: flex !important;
    flex-wrap: wrap !important;
    gap: 8px !important;
  }
  .npc-picker label {
    flex: 1 1 46% !important;
    padding: 12px 10px !important;
    font-size: 0.95em !important;
    text-align: center;
  }
  .gradio-container button {
    min-height: 44px !important;
  }
  .accuse-btn { font-size: 1.05em !important; }
}

/* 手机（≤640px）：进一步压缩 */
@media (max-width: 640px) {
  .chat-panel { height: 300px !important; }
  .gradio-container h1 { font-size: 1.3em !important; letter-spacing: 0.03em; }
  .hud-clock strong { font-size: 1.15em !important; }
  .npc-picker label { flex: 1 1 100% !important; }
  .verdict-card { padding: 16px 14px !important; }
  .verdict-card h2 { font-size: 1.3em !important; }
}

/* 平板横屏 / 小桌面（901-1279px）：保持双栏，压缩留白 */
@media (min-width: 901px) and (max-width: 1279px) {
  .gradio-container { padding: 0 10px !important; }
  .chat-panel { height: 340px !important; }
}

/* 大桌面（≥1600px）：放宽版心 */
@media (min-width: 1600px) {
  .gradio-container { max-width: 1400px !important; }
}

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
    verdict:  () => { [392, 523, 659].forEach((f, i) => tone(f, 0.4, 'triangle', 0.06, i * 0.12)); }
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
}
"""

# 统一输出槽位：chat, clock, status, clue, verdict_grp, verdict_md, q_box, npc_dd
OUT8 = None  # 在 Blocks 内定义后填充


def _msgs(text):
    return [{"role": "assistant", "content": text}]


def do_restart():
    state = engine.new_game()
    greet = engine.switch(state, DEFAULT_NPC)
    return (_msgs(greet), engine.clock_md(state), engine.status_card(state, DEFAULT_NPC),
            engine.clue_board(state), gr.Group(visible=False), "", "",
            NPC_LABELS[DEFAULT_NPC])


def do_switch(label, chat_hist, state):
    npc_id = ID_BY_LABEL.get(label, DEFAULT_NPC)
    if state["ended"]:
        return (chat_hist, engine.clock_md(state), engine.status_card(state, npc_id),
                engine.clue_board(state), gr.skip(), gr.skip(), gr.skip(), gr.skip())
    greet = engine.switch(state, npc_id)
    return (_msgs(greet), engine.clock_md(state), engine.status_card(state, npc_id),
            engine.clue_board(state), gr.skip(), gr.skip(), gr.skip(), gr.skip())


def do_ask(question, chat_hist, state):
    chat = list(chat_hist)
    q = (question or "").strip()
    clock = engine.clock_md(state)
    status = engine.status_card(state, state["cur"])
    clue = engine.clue_board(state)
    grp, md = gr.skip(), gr.skip()
    if state["ended"]:
        return (chat, clock, status, clue, gr.Group(visible=True),
                engine.end_markdown(state), q, gr.skip())
    if q:
        res = engine.ask(state, state["cur"], q, LLM)
        chat.append({"role": "user", "content": f"🧑‍✈️ 侦探：{q}"})
        chat.append({"role": "assistant", "content": f"{NPCS[state['cur']]['name']}：{res['reply']}"})
        if res["clue"]:
            chat.append({"role": "assistant", "content": "🔎 【关键线索解锁！查看右侧线索板】"})
        clock = engine.clock_md(state)
        status = engine.status_card(state, state["cur"])
        clue = engine.clue_board(state)
        if res["timeup"]:
            grp, md = gr.Group(visible=True), engine.end_markdown(state)
    return (chat, clock, status, clue, grp, md, "", gr.skip())


def do_present(ev_label, chat_hist, state):
    chat = list(chat_hist)
    clock = engine.clock_md(state)
    status = engine.status_card(state, state["cur"])
    clue = engine.clue_board(state)
    grp, md = gr.skip(), gr.skip()
    if state["ended"]:
        return (chat, clock, status, clue, gr.Group(visible=True),
                engine.end_markdown(state), "", gr.skip())
    npc = NPCS[state["cur"]]
    ev_id = EV_ID_BY_LABEL.get(ev_label or "")
    if not ev_id:
        chat.append({"role": "assistant", "content": "（先在证物栏里选一件证物，再出示。）"})
        return (chat, clock, status, clue, grp, md, "", gr.skip())
    ev_name = ev_label.split(" — ")[0]
    chat.append({"role": "user", "content": f"🧑‍✈️ 侦探出示了证物：{ev_name}"})
    res = engine.present_evidence(state, state["cur"], ev_id)
    chat.append({"role": "assistant", "content": f"{npc['name']}：{res['reply']}"})
    if res["clue"]:
        chat.append({"role": "assistant", "content": "🔎 【关键线索解锁！查看右侧线索板】"})
    clock = engine.clock_md(state)
    status = engine.status_card(state, state["cur"])
    clue = engine.clue_board(state)
    if res["timeup"]:
        grp, md = gr.Group(visible=True), engine.end_markdown(state)
    return (chat, clock, status, clue, grp, md, "", gr.skip())


def do_accuse(choice, chat_hist, state):
    chat = list(chat_hist)
    clock = engine.clock_md(state)
    status = engine.status_card(state, state["cur"])
    clue = engine.clue_board(state)
    if not choice:
        chat.append({"role": "assistant",
                     "content": "（请先从名单中选择一个名字，再按下结案指认。）"})
        return (chat, clock, status, clue, gr.skip(), gr.skip(), gr.skip(), gr.skip())
    if not state["ended"]:
        engine.accuse(state, choice)
    return (chat, clock, status, clue, gr.Group(visible=True),
            engine.end_markdown(state), gr.skip(), gr.skip())


with gr.Blocks(title=CASE_TITLE, css=CSS, js=SOUND_JS) as demo:
    gr.Markdown(
        f"# 🕰️ 第七位证人\n"
        f"*「AI 造游戏」参赛作品 · 把 AI 的记忆做成玩法的审讯推理游戏*\n\n{CASE_BRIEF}\n\n"
        f"<sub>🤖 当前 AI 引擎：**{LLM.name}**</sub>"
    )
    state = gr.State(engine.new_game())

    with gr.Row():
        with gr.Column(scale=7):
            npc_dd = gr.Radio(choices=list(NPC_LABELS.values()),
                              value=NPC_LABELS[DEFAULT_NPC],
                              label="审讯对象（随时切换，不耗时）",
                              elem_classes=["npc-picker"])
            chat = gr.Chatbot(label="审讯记录", height=380, elem_classes=["chat-panel"])
            q_box = gr.Textbox(placeholder="向当前对象提问…（点击 ➤ 发送，每次 -1 分钟）",
                               show_label=False, container=False, submit_btn=True,
                               elem_classes=["ask-box"])
            with gr.Row():
                quick_btns = [gr.Button(qq, size="sm", elem_classes=["quick-btn"]) for qq in QUICK_QS]
            with gr.Row():
                ev_dd = gr.Dropdown(choices=EV_OPTIONS, label="证物（现场勘查所得）", value=None,
                                    elem_classes=["evidence-select"])
                ev_btn = gr.Button("出示证据（-2 分钟）", variant="secondary", elem_classes=["evidence-btn"])
        with gr.Column(scale=3):
            clock_md = gr.Markdown(elem_classes=["hud-clock"])
            status_md = gr.Markdown(elem_classes=["status-card"])
            with gr.Accordion("🔎 线索板", open=True):
                clue_md = gr.Markdown(elem_classes=["clue-board"])
            accuse_dd = gr.Dropdown(choices=ACCUSE_OPTIONS,
                                    label="指认真凶（一锤定音，慎重！）",
                                    elem_classes=["accuse-dd"])
            accuse_btn = gr.Button("🚨 结案指认", variant="stop", elem_classes=["accuse-btn"])

    verdict_grp = gr.Group(visible=False, elem_classes=["verdict-card"])
    with verdict_grp:
        verdict_md = gr.Markdown()
        restart_btn = gr.Button("🔄 重新开始")

    OUT8 = [chat, clock_md, status_md, clue_md, verdict_grp, verdict_md, q_box, npc_dd]

    demo.load(do_restart, None, OUT8)
    npc_dd.change(do_switch, [npc_dd, chat, state], OUT8)
    q_box.submit(do_ask, [q_box, chat, state], OUT8)
    ev_btn.click(do_present, [ev_dd, chat, state], OUT8)
    accuse_btn.click(do_accuse, [accuse_dd, chat, state], OUT8)
    restart_btn.click(do_restart, None, OUT8)
    for b, qq in zip(quick_btns, QUICK_QS):
        # 快捷提问：点击即直接发送该问题（不再只填充输入框）
        b.click(lambda chat_hist, st, t=qq: do_ask(t, chat_hist, st), [chat, state], OUT8)

if __name__ == "__main__":
    # 创空间容器必须监听 0.0.0.0:7860；本地默认同配置，无副作用
    demo.launch(server_name=os.environ.get("GRADIO_SERVER_NAME", "0.0.0.0"),
                server_port=7860, share=False, show_error=True)
