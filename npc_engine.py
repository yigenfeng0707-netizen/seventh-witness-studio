# -*- coding: utf-8 -*-
"""NPC 引擎 v2：多案件感知 + 信任阈值规则层 + 存档分享码"""

import game_data as G
from game_data import (CASES, HARD_MINUTES, HARD_TRUST_PENALTY,
                       COST_TALK, COST_EVIDENCE, START_MINUTES)


def CD(state):
    """当前案件数据。"""
    return G.CASES[state["case_id"]]


def new_game(case_id="clock", difficulty="normal", rank_tier=0):
    """开新局：案件 × 难度 × 警衔特权。"""
    c = G.CASES[case_id]
    hard = difficulty == "hard"
    minutes = (G.HARD_MINUTES if hard else c.get("start_minutes", G.START_MINUTES))
    if rank_tier >= 2:
        minutes += 5  # 二级探员特权：开局时间 +5
    trust_bonus = 5 if rank_tier >= 4 else 0  # 高级探员特权：全员信任 +5
    penalty = G.HARD_TRUST_PENALTY if hard else 0
    ev_list = list(c["evidence"]) + (list(c.get("hard_evidence", [])) if hard else [])
    return {
        "case_id": case_id,
        "difficulty": difficulty,
        "cur": c["default_npc"],
        "npc": {nid: {"trust": max(5, v["trust0"] + trust_bonus - penalty),
                      "emotion": v["emotion0"],
                      "memories": [],
                      "history": [],
                      "confessed": False}
                for nid, v in c["npcs"].items()},
        "evidence_ids": [e["id"] for e in ev_list],
        "evidence_shown": {},
        "time": minutes,
        "clues": [],
        "ended": False,
        "verdict": None,
        "last_choice": "",
    }


def switch(state, npc_id):
    state["cur"] = npc_id
    return greeting(state, npc_id)


def greeting(state, npc_id):
    return CD(state)["npcs"][npc_id]["greeting"]


def _tick(state):
    if state["time"] <= 0 and not state["ended"]:
        state["ended"] = True
        state["verdict"] = "TIMEUP"
        return True
    return False


def _add_clue(state, clue_id):
    if clue_id and clue_id not in state["clues"]:
        state["clues"].append(clue_id)
        return clue_id
    return None


# ---------------- 提问 ----------------

def ask(state, npc_id, question, llm):
    if state["ended"]:
        return {"reply": "（本案已结。点击“重新开始”再开一局。）", "clue": None, "timeup": False}
    c = CD(state)
    st = state["npc"][npc_id]
    npc = c["npcs"][npc_id]
    q = (question or "").strip()

    # 规则层校验①：信任 <15 且未供述 → 下逐客令（额外流失 2 分钟）
    if st["trust"] < 15 and not st["confessed"]:
        state["time"] = max(0, state["time"] - COST_TALK - 2)
        st["emotion"] = "逐客"
        reply = (f"（{npc['name']} 把手里的活一撂，转身下了逐客令："
                 f"“话不投机半句多。你走吧，今天什么都别问。”"
                 f"——信任过低被拒之门外，时间额外流逝 2 分钟）")
        return {"reply": reply, "clue": None, "timeup": _tick(state)}

    # 规则层校验②：信任 <25 且问及关键案情 → 拒绝细谈（确定性规则输出）
    if st["trust"] < 25 and not st["confessed"] and any(k in q for k in c["key_topics"]):
        state["time"] = max(0, state["time"] - COST_TALK)
        st["emotion"] = "戒备"
        reply = (f"（{npc['name']} 面色一沉，把话头掐断："
                 f"“这话我不敢接。你先做点让人信得过的事，再来问这些。”"
                 f"——信任不足，关键问题被拒绝）")
        return {"reply": reply, "clue": None, "timeup": _tick(state)}

    reply = llm.ask(npc, question, st["trust"],
                    st["memories"], st["history"],
                    rules=c["topic_rules"], consensus=c.get("consensus"))

    state["time"] = max(0, state["time"] - COST_TALK)
    st["trust"] = max(5, min(100, st["trust"] + reply.get("trust_change", 0)))
    if not st["confessed"]:
        if reply.get("emotion"):
            st["emotion"] = reply["emotion"]
        elif st["trust"] < 30:
            st["emotion"] = "戒备"
        else:
            st["emotion"] = npc["emotion0"]

    q = q if q else "（沉默）"
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
    if not isinstance(st, dict) or "npc" not in st or "time" not in st or "clues" not in st \
            or "case_id" not in st:
        raise ValueError("存档码无效")
    if st["case_id"] not in G.CASES:
        raise ValueError("存档码所属案件不存在")
    return st


# ---------------- 出示证据 ----------------

def present_evidence(state, npc_id, ev_id):
    if state["ended"]:
        return {"reply": "（本案已结。点击“重新开始”再开一局。）", "clue": None, "timeup": False}
    c = CD(state)
    ev = next((e for e in c["evidence"] + c.get("hard_evidence", [])
               if e["id"] == ev_id), None)
    if ev is None:
        return {"reply": "（这件证物不属于当前案件。）", "clue": None, "timeup": False}
    npc, st = c["npcs"][npc_id], state["npc"][npc_id]

    if state["evidence_shown"].get(ev_id) == npc_id:
        return {"reply": f"（{npc['name']}别过头去）这件东西，刚才不是看过了吗……", "clue": None, "timeup": False}
    state["evidence_shown"][ev_id] = npc_id
    state["time"] = max(0, state["time"] - COST_EVIDENCE)

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
    c = CD(state)
    n = len(state["clues"])
    if c["truth_key"] in choice:
        state["verdict"] = "WIN_S" if n >= 4 else "WIN_A" if n == 3 else "WIN_B"
    else:
        state["verdict"] = "LOSE"
    return end_markdown(state)


# ---------------- 渲染 ----------------

def end_markdown(state):
    c = CD(state)
    v = state["verdict"] or "TIMEUP"
    titles = {
        "WIN_S": "⭐ S 级破案 · 完美结案",
        "WIN_A": "⭐ A 级破案 · 成功结案",
        "WIN_B": "✔️ 结案 · 险胜",
        "LOSE": "❌ 冤案 · 真凶逍遥",
        "TIMEUP": "⏳ 时间耗尽",
    }
    body = c["endings"][v].format(choice=state.get("last_choice", ""))
    recap = clue_board(state)
    return (f"## {titles[v]}\n\n{body}\n\n---\n\n"
            f"**🔎 已解锁关键线索：{len(state['clues'])}/{len(c['key_clues'])}**\n\n{recap}\n\n{c['truth_text']}")


def clock_md(state):
    c = CD(state)
    hint = ""
    if state["time"] <= c.get("start_minutes", START_MINUTES) - 18:
        hint = "\n\n💡 *证物各有其主——对的人面前，才有用。*"
    tag = " · 困难" if state.get("difficulty") == "hard" else ""
    return f"⏱️ **剩余审讯时间：{state['time']} 分钟**{tag}{hint}"


def status_card(state, npc_id):
    c = CD(state)
    npc, st = c["npcs"][npc_id], state["npc"][npc_id]
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
    c = CD(state)
    if not state["clues"]:
        return "（尚未解锁任何关键线索。审讯 + 出示证据，才能拼出真相。）"
    lines = []
    for i, cid in enumerate(state["clues"], 1):
        cl = c["key_clues"][cid]
        lines.append(f"**{i}. {cl['name']}**（来源：{cl['src']}）— {cl['text']}")
    return "\n\n".join(lines)
