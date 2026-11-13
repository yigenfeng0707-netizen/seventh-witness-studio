---
title: 第七位证人
emoji: 🕰️
sdk: docker
app_file: app.py
pinned: false
---

# 🕰️ 第七位证人

> AI+∞ 开发者创作大赛 第三期「AI 造游戏」参赛作品
> **把 AI 的记忆做成核心玩法的限时审讯推理游戏。**

## 玩法

- 你是外来侦探，限时 **60 分钟**（游戏内时间）审讯 4 名嫌疑人
- 每名 NPC 由大模型驱动：**持久记忆 / 性格 / 隐藏秘密 / 信任度与情绪**
- 右侧"记忆图谱"实时可视化 NPC 记得什么、隐瞒什么
- 出示证据 → 命中对的人 → 撬开秘密、解锁关键线索（共 4 条）
- 时间耗尽前从 5 人中指认真凶，线索数决定结局评级（S/A/B）

## 本地运行

```bash
pip install -r requirements.txt
python app.py
# → http://127.0.0.1:7860
```

## LLM 链式多供应商 + 离线兜底

按环境变量逐级组装调用链：**主供应商 → 备供应商 → (魔搭) → MockLLM**，任何一环失败当次自动切到下一环，**逐调用回退**，游戏流程永不中断。

| 环节 | 触发条件 | 说明 |
|---|---|---|
| 主供应商 | `LLM_API_BASE` / `LLM_API_KEY` / `LLM_MODEL` | 任意 OpenAI 兼容接口（线上实测：`qwen3.8-27b`） |
| 备供应商 | `LLM_API2_BASE` / `LLM_API2_KEY` / `LLM_API2_MODEL` | 第二家 OpenAI 兼容接口（线上实测：`sensenova-6.8-flash`） |
| 魔搭（legacy） | `MODELSCOPE_API_TOKEN` | API-Inference，默认 `Qwen/Qwen3.8-Flash-Next`，可用 `MSC_MODEL` / `MODELSCOPE_API_BASE` 调整 |
| MockLLM（默认） | 无任何环境变量 | 离线规则引擎，覆盖全部话题与 4 条坦白线，**纯离线也能完整通关** |

可选：`LLM_NO_THINKING=1`（对 Qwen3 系关闭思考模式）。密钥只走环境变量，不进代码库。

## 通关提示（剧透慎读）

5 件证物各有其主：账本→王大锤、怀表→苏眉、湿手套→陆离、蜡烛→老周。
真相藏在证词的缝隙里——"第七位证人"不在审讯名单上。
