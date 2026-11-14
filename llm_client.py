# -*- coding: utf-8 -*-
"""LLM 客户端抽象（链式多供应商）：
- MockLLM        离线规则引擎（兜底，评审现场永不断线）
- OpenAICompatLLM 任意 OpenAI 兼容供应商（主/备链）
- ModelScopeLLM  魔搭 API-Inference（legacy，仍支持）
- get_llm()      读取环境变量组装：主 → 备 → (魔搭) → Mock 逐调用回退

环境变量：
  LLM_API_BASE / LLM_API_KEY / LLM_MODEL          主供应商
  LLM_API2_BASE / LLM_API2_KEY / LLM_API2_MODEL   备供应商
  LLM_NO_THINKING=1（对 Qwen3 系关闭思考模式）
"""

import json
import os
import re

import game_data as G


def _match_topic(question, rules=None):
    rules = rules if rules is not None else G.TOPIC_RULES
    q = question.strip()
    for topic, kws, _tone in rules:
        if any(kw in q for kw in kws):
            return topic, _tone
    return "default", 2


class MockLLM:
    """离线规则引擎：按话题命中 NPC 台词，信任度低时切换“被逼问”口吻。"""

    name = "MockLLM（离线规则）"

    def ask(self, npc, question, trust, memories=None, history=None,
            rules=None, consensus=None, fame=False):
        topic, tc = _match_topic(question, rules)
        lines = npc["lines"]
        line = lines.get(topic, lines["default"])
        if tc < 0 and trust < 25:
            line = npc["pressured"][0]
        return {"dialogue": line, "trust_change": tc, "clue": None, "emotion": None}


class _OpenAIBase:
    """公共：system prompt 组装 + JSON 解析。"""

    def _system(self, npc, trust, memories, consensus=None):
        mem_txt = "\n".join(f"- {m}" for m in memories[-8:]) or "- （尚未记住任何事）"
        facts = npc.get("facts") or []
        facts_txt = "\n".join(f"- {f}" for f in facts) or "- （无）"
        bg = consensus or (
            "背景共识：钟表匠沈师傅“上礼拜一出城去如意镇修大钟”（全镇都这么认为，你也这么说）。")
        return (
            "你正在扮演悬疑审讯游戏《第七位证人》中的角色，严格入戏。\n"
            f"角色：{npc['name']}，{npc['role']}。性格与说话方式：{npc['intro']}\n"
            f"你的秘密（绝不主动说出，除非玩家出示关键证据或逼问到你崩溃）：{npc['secret']}\n"
            f"你掌握的公共事实（回答必须与此一致，严禁编造与之矛盾的情节）：\n{facts_txt}\n"
            f"当前玩家信任度：{trust}/100。低于30时你戒备、回答简短回避；高于70时你愿意多说；"
            "被问及敏感话题时明显紧张。\n"
            f"你记住的玩家问过的事（回答时保持一致，不要自相矛盾）：\n{mem_txt}\n"
            f"背景共识：{bg}\n"
            "要求：台词 1~3 句，符合民国小镇口吻与你的性格，不要跳出角色，"
            "不要出现 JSON 以外的说明文字。\n"
            '严格输出 JSON：{"dialogue": "台词", "emotion": "一个词", "trust_change": -5到5的整数}'
        )

    @staticmethod
    def _parse(text):
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
        try:
            data = json.loads(re.sub(r"^```(json)?|```$", "", text).strip())
        except Exception:
            m = re.search(r"\{.*\}", text, re.S)
            if m:
                try:
                    data = json.loads(m.group(0))
                except Exception:
                    data = None
            else:
                data = None
        if not data or "dialogue" not in data:
            data = {"dialogue": text or "（他欲言又止，终究没有作答。）",
                    "emotion": "平静", "trust_change": 0}
        try:
            data["trust_change"] = max(-5, min(5, int(data.get("trust_change", 0))))
        except Exception:
            data["trust_change"] = 0
        data["dialogue"] = str(data["dialogue"]).strip()
        return data


class OpenAICompatLLM(_OpenAIBase):
    """任意 OpenAI 兼容供应商。no_thinking=True 时对 Qwen3 系关闭思考模式。"""

    def __init__(self, name, base, model, key, no_thinking=False,
                 temperature=0.85, max_tokens=300):
        from openai import OpenAI
        self.client = OpenAI(api_key=key, base_url=base, timeout=30, max_retries=1)
        self.model = model
        self.name = name
        self._kw = dict(temperature=temperature, max_tokens=max_tokens)
        if no_thinking:
            self._kw["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}

    def ask(self, npc, question, trust, memories=None, history=None, rules=None, consensus=None):
        msgs = [{"role": "system", "content": self._system(npc, trust, memories or [], consensus)}]
        for h in (history or [])[-6:]:
            msgs.append({"role": h["role"], "content": h["content"]})
        msgs.append({"role": "user", "content": f"玩家（侦探）问：{question}"})
        try:
            resp = self.client.chat.completions.create(
                model=self.model, messages=msgs, **self._kw)
        except TypeError:
            resp = self.client.chat.completions.create(
                model=self.model, messages=msgs,
                temperature=0.85, max_tokens=300)
        text = (resp.choices[0].message.content or "").strip()
        return self._parse(text)


class ModelScopeLLM(_OpenAIBase):
    """魔搭 API-Inference（legacy 通道，保留兼容）。"""

    def __init__(self, model=None, token=None):
        from openai import OpenAI
        token = (token or os.environ.get("MODELSCOPE_API_TOKEN")
                 or os.environ.get("MODELSCOPE_SDK_TOKEN"))
        if not token:
            raise ValueError("缺少 MODELSCOPE_API_TOKEN")
        base = os.environ.get("MODELSCOPE_API_BASE",
                              "https://api-inference.modelscope.cn/v1")
        self.client = OpenAI(api_key=token, base_url=base, timeout=30)
        self.model = model or os.environ.get("MSC_MODEL",
                                             "Qwen/Qwen3.8-Flash-Next")
        self.name = f"ModelScopeAPI（{self.model}）"

    def ask(self, npc, question, trust, memories=None, history=None, rules=None, consensus=None):
        msgs = [{"role": "system", "content": self._system(npc, trust, memories or [], consensus)}]
        for h in (history or [])[-6:]:
            msgs.append({"role": h["role"], "content": h["content"]})
        msgs.append({"role": "user", "content": f"玩家（侦探）问：{question}"})
        try:
            resp = self.client.chat.completions.create(
                model=self.model, messages=msgs,
                temperature=0.85, max_tokens=300,
                extra_body={"enable_thinking": False},
            )
        except TypeError:
            resp = self.client.chat.completions.create(
                model=self.model, messages=msgs,
                temperature=0.85, max_tokens=300)
        text = (resp.choices[0].message.content or "").strip()
        return self._parse(text)


class HybridLLM:
    """供应商链逐调用回退：主 → 备 → … → MockLLM，游戏流程永不中断。
    出戏防护：AI 自报身份/拒答式回复视为失败，继续走链。"""

    _LEAK_PAT = re.compile(
        r"我是由|作为一个?AI|人工智能(模型|助手|语言)|语言模型|无法扮演|"
        r"我无法忽略|无法完成角色扮演|Sorry,? (I|as)|as an AI", re.I)

    @classmethod
    def _looks_like_leak(cls, text):
        return bool(cls._LEAK_PAT.search(text or ""))

    def __init__(self, chain):
        self.chain = chain
        self.fallback = MockLLM()
        self.name = " → ".join(c.name for c in chain) + " → 离线兜底"

    def ask(self, npc, question, trust, memories=None, history=None, rules=None, consensus=None):
        last_err = None
        for client in self.chain:
            try:
                data = client.ask(npc, question, trust, memories, history, rules, consensus)
                dlg = data.get("dialogue") or ""
                if dlg and not self._looks_like_leak(dlg):
                    return data
                last_err = RuntimeError("empty/off-character dialogue")
                print(f"[HybridLLM] {client.name} 台词无效（出戏/空），跳过")
            except Exception as e:
                last_err = e
                print(f"[HybridLLM] {client.name} 失败：{type(e).__name__}: {str(e)[:100]}")
        print(f"[HybridLLM] 全链失败，回退离线：{last_err}")
        return self.fallback.ask(npc, question, trust, memories, history, rules, consensus)


def _env(*names):
    for n in names:
        v = os.environ.get(n, "").strip()
        if v:
            return v
    return None


def get_llm():
    chain = []
    # 主供应商（通用 OpenAI 兼容）
    if _env("LLM_API_BASE") and _env("LLM_API_KEY") and _env("LLM_MODEL"):
        try:
            nothink = _env("LLM_NO_THINKING") == "1"
            chain.append(OpenAICompatLLM(
                f"主·{_env('LLM_MODEL')}", _env("LLM_API_BASE"),
                _env("LLM_MODEL"), _env("LLM_API_KEY"), no_thinking=nothink))
        except Exception as e:
            print(f"[llm_client] 主供应商初始化失败：{e}")
    # 备供应商
    if _env("LLM_API2_BASE") and _env("LLM_API2_KEY") and _env("LLM_API2_MODEL"):
        try:
            chain.append(OpenAICompatLLM(
                f"备·{_env('LLM_API2_MODEL')}", _env("LLM_API2_BASE"),
                _env("LLM_API2_MODEL"), _env("LLM_API2_KEY")))
        except Exception as e:
            print(f"[llm_client] 备供应商初始化失败：{e}")
    # 魔搭 legacy 通道
    if _env("MODELSCOPE_API_TOKEN", "MODELSCOPE_SDK_TOKEN"):
        try:
            chain.append(ModelScopeLLM())
        except Exception as e:
            print(f"[llm_client] 魔搭通道不可用：{e}")
    if chain:
        return HybridLLM(chain)
    return MockLLM()
