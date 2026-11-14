# -*- coding: utf-8 -*-
"""游戏引擎：状态机 + NPC 记忆/信任/情绪 + 证据质询 + 指认结算"""

import game_data as G


def new_game():
    return {
        "time": G.START_MINUTES,
        "ended": False,
        "verdict": None,
        "last_choice": "",
        "cur": G.DEFAULT_NPC,
        "clues": [],            # 已解锁关键线索 id 列表
        "evidence_shown": {},   # 证据 id -> 出示过的 npc id
        "npc": {
            nid: {"trust": v["trust0"], "emotion": v["emotion0"],
                  "memories": [], "history": [], "confessed": False}
            for nid, v in G.NPCS.items()
        },
    }


# ---------------- 切换 / 开场 ----------------

def switch(state, npc_id):
    state["cur"] = npc_id
    return greeting(state, npc_id)


def greeting(state, npc_id):
    npc, st = G.NPCS[npc_id], state["npc"][npc_id]
    if st["confessed"]:
        return f"（{npc['name']}垂着头）……你还有话要问？"
    if st["memories"]:
        return f"（{npc['name']}抬眼看你）又回来了？……说吧，还想问什么。"
    return npc["greeting"]


# ---------------- 提问 ----------------

# 关键案情关键词：低信任时拒绝细谈（规则层校验，确定性输出）
KEY_TOPICS = ("案发", "当晚", "那晚", "凶器", "钥匙", "钟楼", "钟声", "沈师傅", "沈墨白",
              "沈", "指纹", "账本", "怀表", "手套", "蜡烛", "第三把", "钩爪", "机芯", "侧门")


def ask(state, npc_id, question, llm):
    if state["ended"]:
        return {"reply": "（本案已结。点击“重新开始”再开一局。）", "clue": None, "timeup": False}
    st = state["npc"][npc_id]
    npc = G.NPCS[npc_id]
    q = (question or "").strip()

    # 规则层校验①：信任 <15 且未供述 → 下逐客令（额外流失 2 分钟）
    if st["trust"] < 15 and not st["confessed"]:
        state["time"] = max(0, state["time"] - G.COST_TALK - 2)
        st["emotion"] = "逐客"
        reply = (f"（{npc['name']} 把手里的活一撂，转身下了逐客令："
                 f"“话不投机半句多。你走吧，今天什么都别问。”"
                 f"——信任过低被拒之门外，时间额外流逝 2 分钟）")
        return {"reply": reply, "clue": None, "timeup": _tick(state)}

    # 规则层校验②：信任 <25 且问及关键案情 → 拒绝细谈（确定性规则输出）
    if st["trust"] < 25 and not st["confessed"] and any(k in q for k in KEY_TOPICS):
        state["time"] = max(0, state["time"] - G.COST_TALK)
        st["emotion"] = "戒备"
        reply = (f"（{npc['name']} 面色一沉，把话头掐断："
                 f"“这话我不敢接。你先做点让人信得过的事，再来问这些。”"
                 f"——信任不足，关键问题被拒绝）")
        return {"reply": reply, "clue": None, "timeup": _tick(state)}

    reply = llm.ask(G.NPCS[npc_id], question, st["trust"],
                    st["memories"], st["history"])

    state["time"] = max(0, state["time"] - G.COST_TALK)
    st["trust"] = max(5, min(100, st["trust"] + reply.get("trust_change", 0)))
    if not st["confessed"]:
        if reply.get("emotion"):
            st["emotion"] = reply["emotion"]
        elif st["trust"] < 30:
            st["emotion"] = "戒备"
        else:
            st["emotion"] = G.NPCS[npc_id]["emotion0"]

    q = question.strip()
    mem = f"你问过：{q[:14]}{'…' if len(q) > 14 else ''}"
    if mem not in st["memories"]:
        st["memories"].append(mem)
    st["history"].append({"role": "user", "content": f"玩家问：{q}"})
    st["history"].append({"role": "assistant", "content": str(reply.get("dialogue", ""))[:120]})

    clue = reply.get("clue")
    if clue:
        clue = _add_clue(state, clue)

    # 规则层增益③：信任 ≥85 且未供述 → 主动多透露半句真话（确定性提示）
    if st["trust"] >= 85 and not st["confessed"]:
        whisper = npc.get("whisper")
        if whisper:
            reply["dialogue"] = (str(reply.get("dialogue", "")) +
                                 f"\n（他犹豫了一下，压低声音补了一句：“{whisper}”）")

    return {"reply": reply["dialogue"], "clue": clue, "timeup": _tick(state)}


# ---------------- 存档（分享码） ----------------

def to_json(state):
    import json as _json, base64 as _b64
    return _b64.b64encode(_json.dumps(state, ensure_ascii=False).encode("utf-8")).decode("ascii")


def from_json(code):
    import json as _json, base64 as _b64
    try:
        st = _json.loads(_b64.b64decode(code.strip()).decode("utf-8"))
    except Exception:
        raise ValueError("存档码无效")
    if not isinstance(st, dict) or "npc" not in st or "time" not in st or "clues" not in st:
        raise ValueError("存档码无效")
    return st


# ---------------- 出示证据 ----------------

def present_evidence(state, npc_id, ev_id):
    if state["ended"]:
        return {"reply": "（本案已结。点击“重新开始”再开一局。）", "clue": None, "timeup": False}
    ev = next(e for e in G.EVIDENCE if e["id"] == ev_id)
    npc, st = G.NPCS[npc_id], state["npc"][npc_id]

    if state["evidence_shown"].get(ev_id) == npc_id:
        return {"reply": f"（{npc['name']}别过头去）这件东西，刚才不是看过了吗……", "clue": None, "timeup": False}
    state["evidence_shown"][ev_id] = npc_id
    state["time"] = max(0, state["time"] - G.COST_EVIDENCE)

    conf = npc["confessions"].get(ev_id)
    if conf:
        st["confessed"] = True
        st["emotion"] = "慌乱"
        st["trust"] = max(5, st["trust"] - 8)
        st["memories"].append(f"他在「{ev['name']}」面前吐露了秘密")
        clue = _add_clue(state, npc["clue_on_confession"])
        return {"reply": conf, "clue": clue, "timeup": _tick(state)}

    return {"reply": npc["react_miss"], "clue": None, "timeup": _tick(state)}


# ---------------- 指认 ----------------

def accuse(state, choice):
    state["ended"] = True
    state["last_choice"] = choice
    n = len(state["clues"])
    if "沈墨白" in choice:
        state["verdict"] = "WIN_S" if n >= 4 else "WIN_A" if n == 3 else "WIN_B"
    else:
        state["verdict"] = "LOSE"
    return end_markdown(state)


def end_markdown(state):
    v = state["verdict"] or "TIMEUP"
    titles = {
        "WIN_S": "⭐ S 级破案 · 完美结案",
        "WIN_A": "⭐ A 级破案 · 成功结案",
        "WIN_B": "✔️ 结案 · 险胜",
        "LOSE": "❌ 冤案 · 真凶逍遥",
        "TIMEUP": "⏳ 时间耗尽",
    }
    body = G.ENDINGS[v].format(choice=state.get("last_choice", ""))
    recap = clue_board(state)
    return (f"## {titles[v]}\n\n{body}\n\n---\n\n"
            f"**🔎 已解锁关键线索：{len(state['clues'])}/4**\n\n{recap}\n\n{G.TRUTH_TEXT}")


# ---------------- 渲染 ----------------

def clock_md(state):
    hint = ""
    if state["time"] <= G.START_MINUTES - 18:
        hint = "\n\n💡 *证物各有其主——对的人面前，才有用。*"
    return f"⏱️ **剩余审讯时间：{state['time']} 分钟**{hint}"


def status_card(state, npc_id):
    npc, st = G.NPCS[npc_id], state["npc"][npc_id]
    filled = round(st["trust"] / 10)
    bar = "█" * filled + "░" * (10 - filled)
    mems = st["memories"][-6:][::-1] or ["（还什么都没记住）"]
    mem_lines = "\n".join(f"- {m}" for m in mems)
    secret_line = (f"- 🔓 {npc['secret']}" if st["confessed"]
                   else "- 🔒 ？？？（出示有效证据可撬开）")
    return (
        f"### {npc['emoji']} {npc['name']} · {npc['role']}\n"
        f"> {npc['intro']}\n\n"
        f"**情绪**：{st['emotion']}　**信任度**：{bar} {st['trust']}\n\n"
        f"**📝 记忆图谱（他记住的事）**\n{mem_lines}\n\n"
        f"**🔒 记忆深处**\n{secret_line}"
    )


def clue_board(state):
    if not state["clues"]:
        return "（尚未解锁任何关键线索。审讯 + 出示证据，才能拼出真相。）"
    lines = []
    for i, cid in enumerate(state["clues"], 1):
        c = G.KEY_CLUES[cid]
        lines.append(f"**{i}. {c['name']}**（来源：{c['src']}）— {c['text']}")
    return "\n\n".join(lines)


# ---------------- 内部 ----------------

def _add_clue(state, clue_id):
    if clue_id and clue_id not in state["clues"]:
        state["clues"].append(clue_id)
        return clue_id
    return None


def _tick(state):
    if state["time"] <= 0 and not state["ended"]:
        state["ended"] = True
        state["verdict"] = "TIMEUP"
        return True
    return False
