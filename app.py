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
.gradio-container {max-width: 1200px !important; margin: 0 auto;}
.status-card {border: 1px solid #d9d4f0 !important; border-radius: 12px !important;
              padding: 12px !important; background: #faf9ff !important;}
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


with gr.Blocks(title=CASE_TITLE) as demo:
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
                              label="审讯对象（随时切换，不耗时）")
            chat = gr.Chatbot(label="审讯记录", height=380)
            q_box = gr.Textbox(placeholder="向当前对象提问…（点击 ➤ 发送，每次 -1 分钟）",
                               show_label=False, container=False, submit_btn=True)
            with gr.Row():
                quick_btns = [gr.Button(qq, size="sm") for qq in QUICK_QS]
            with gr.Row():
                ev_dd = gr.Dropdown(choices=EV_OPTIONS, label="证物（现场勘查所得）", value=None)
                ev_btn = gr.Button("出示证据（-2 分钟）", variant="secondary")
        with gr.Column(scale=3):
            clock_md = gr.Markdown()
            status_md = gr.Markdown(elem_classes=["status-card"])
            with gr.Accordion("🔎 线索板", open=True):
                clue_md = gr.Markdown()
            accuse_dd = gr.Dropdown(choices=ACCUSE_OPTIONS,
                                    label="指认真凶（一锤定音，慎重！）")
            accuse_btn = gr.Button("🚨 结案指认", variant="stop")

    verdict_grp = gr.Group(visible=False)
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
