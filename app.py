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
/* ================= 《第七位证人》雾隐镇 · 民国悬疑主题 ================= */
:root {
  --night-1: #070b14;
  --night-2: #0c1220;
  --panel: rgba(15, 22, 37, 0.86);
  --panel-2: rgba(18, 27, 45, 0.72);
  --line-brass: rgba(212, 169, 78, 0.32);
  --brass: #d4a94e;
  --brass-hi: #ecd08a;
  --brass-dim: rgba(212, 169, 78, 0.14);
  --ink: #e9e3d3;
  --ink-2: #aab3c5;
  --danger-1: #8e1f2b;
  --danger-2: #d43d3d;
}

/* —— 夜幕 + 烟雾氛围（纯 CSS，无外部资源） —— */
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
    radial-gradient(70% 55% at 50% 110%, rgba(10, 16, 28, 0.9), transparent 70%),
    linear-gradient(180deg, var(--night-2) 0%, var(--night-1) 100%);
}
.gradio-container::after {
  content: "";
  position: fixed;
  inset: -20%;
  pointer-events: none;
  z-index: 0;
  opacity: 0.5;
  background:
    radial-gradient(28% 20% at 30% 40%, rgba(140, 160, 190, 0.05), transparent 70%),
    radial-gradient(32% 22% at 72% 68%, rgba(140, 160, 190, 0.045), transparent 70%);
  animation: fog-drift 46s ease-in-out infinite alternate;
}
@keyframes fog-drift {
  0%   { transform: translate3d(-2%, -1%, 0) scale(1); }
  100% { transform: translate3d(3%, 2%, 0) scale(1.06); }
}
/* 内容层抬到氛围之上 */
.gradio-container > * { position: relative; z-index: 1; }

/* —— 标题：民国衬线 + 铜金 —— */
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

/* —— 通用面板玻璃化 —— */
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

/* —— 审讯对象：人物卡式单选 —— */
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
  background: linear-gradient(180deg, rgba(212, 169, 78, 0.16), rgba(212, 169, 78, 0.05)) !important;
  box-shadow: 0 0 0 1px var(--brass), 0 6px 22px rgba(212, 169, 78, 0.22) !important;
}
.npc-picker input[type="radio"] { accent-color: var(--brass) !important; }

/* —— 审讯记录（对话） —— */
.chat-panel {
  background: linear-gradient(180deg, rgba(10, 15, 26, 0.65), rgba(12, 18, 32, 0.5)) !important;
  border: 1px solid rgba(212, 169, 78, 0.18) !important;
  border-radius: 14px !important;
}
.chat-panel .message-row { background: transparent !important; }
.chat-panel .bubble {
  border-radius: 12px !important;
  border: 1px solid rgba(170, 179, 197, 0.14) !important;
  background: rgba(22, 31, 50, 0.85) !important;
  color: var(--ink) !important;
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.3) !important;
}
.chat-panel .bubble.user, .chat-panel .message-row.user .bubble {
  background: linear-gradient(180deg, rgba(212, 169, 78, 0.2), rgba(212, 169, 78, 0.08)) !important;
  border-color: var(--line-brass) !important;
}

/* —— 提问框 / 下拉 —— */
.ask-box textarea, .gradio-container input[type="text"], .gradio-container input[type="tel"],
.gradio-container input[type="email"], .gradio-container textarea {
  background: rgba(8, 12, 22, 0.75) !important;
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
  background: rgba(8, 12, 22, 0.75) !important;
  border-radius: 10px !important;
}
.gradio-container .secondary-wrap, .gradio-container .wrap.default.full {
  background: transparent !important;
}

/* —— 按钮：铜金主调 —— */
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
  background: linear-gradient(180deg, rgba(212, 169, 78, 0.28), rgba(212, 169, 78, 0.12)) !important;
  color: var(--brass-hi) !important;
  border: 1px solid var(--brass) !important;
}
.evidence-btn:hover {
  box-shadow: 0 0 22px rgba(212, 169, 78, 0.35) !important;
  transform: translateY(-1px);
}

/* —— 结案指认：血色终局 —— */
.accuse-btn {
  background: linear-gradient(180deg, var(--danger-2), var(--danger-1)) !important;
  color: #fff2ec !important;
  border: 1px solid rgba(255, 120, 110, 0.5) !important;
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.5) !important;
  box-shadow: 0 6px 24px rgba(140, 30, 40, 0.4) !important;
  letter-spacing: 0.12em !important;
}
.accuse-btn:hover {
  box-shadow: 0 8px 34px rgba(212, 60, 60, 0.55) !important;
  transform: translateY(-1px);
}
.accuse-dd { border: 1px solid rgba(212, 60, 60, 0.35) !important; }

/* —— HUD：时间 —— */
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
  text-shadow: 0 0 14px rgba(212, 169, 78, 0.4);
  animation: clock-pulse 2.6s ease-in-out infinite;
}
@keyframes clock-pulse {
  0%, 100% { text-shadow: 0 0 10px rgba(212, 169, 78, 0.3); }
  50%      { text-shadow: 0 0 22px rgba(212, 169, 78, 0.55); }
}

/* —— HUD：嫌疑人状态卡 —— */
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

/* —— 线索板 —— */
.clue-board {
  background: linear-gradient(180deg, rgba(30, 24, 12, 0.55), rgba(16, 22, 37, 0.6)) !important;
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

/* —— 结局卷轴 —— */
.verdict-card {
  border: 2px solid var(--brass) !important;
  border-radius: 18px !important;
  background:
    radial-gradient(80% 60% at 50% 0%, rgba(212, 169, 78, 0.14), transparent 70%),
    linear-gradient(180deg, rgba(20, 16, 10, 0.92), rgba(10, 14, 24, 0.95)) !important;
  box-shadow: 0 18px 60px rgba(0, 0, 0, 0.6), 0 0 40px rgba(212, 169, 78, 0.12) !important;
  padding: 22px 26px !important;
}
.verdict-card h2 {
  font-size: 1.6em !important;
  text-align: center;
  text-shadow: 0 0 26px rgba(212, 169, 78, 0.45) !important;
}
.verdict-card button { margin-top: 10px; }

/* —— 细节 —— */
.gradio-container a { color: var(--brass-hi) !important; }
.gradio-container ::selection { background: rgba(212, 169, 78, 0.35); }
.gradio-container ::-webkit-scrollbar { width: 9px; height: 9px; }
.gradio-container ::-webkit-scrollbar-thumb {
  background: rgba(212, 169, 78, 0.3);
  border-radius: 6px;
}
.gradio-container ::-webkit-scrollbar-track { background: rgba(255, 255, 255, 0.03); }
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


with gr.Blocks(title=CASE_TITLE, css=CSS) as demo:
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
