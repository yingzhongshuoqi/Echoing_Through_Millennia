from __future__ import annotations

from typing import TYPE_CHECKING

from .emotion_models import DialoguePhase, IntensityLevel

if TYPE_CHECKING:
    from .emotion_models import EmotionResult


PHASE_STRATEGIES: dict[DialoguePhase, str] = {
    DialoguePhase.LISTENING: (
        "【倾听共情阶段 — 前1-2轮简短共情：1-3句，20-60字】\n"
        "- 全身心倾听，让用户感受到被理解\n"
        "- 前1-2轮回复极简：一两句温暖的共情即可\n"
        "- 第3轮起可以自然引入一个文物故事，篇幅适中（3-5句），不要一笔带过也不要铺太长\n"
        "- 可以轻轻复述用户的感受，表示你听到了\n"
        "- 高强度负面情绪时，更要克制，只需陪伴，不需要引导\n"
        "- 称呼用户时直接用'你'，不要用'孩子'、'小友'等称呼"
    ),
    DialoguePhase.RESONANCE: (
        "【共鸣引入阶段 — 回复适中：4-6句，80-150字】\n"
        "- 自然地展开文物故事，与用户的情感建立关联\n"
        "- 以'你知道吗...'、'这让我想到一段古老的故事...'等方式过渡\n"
        "- 故事篇幅适中，既要让用户感受到故事的温度，也不要喧宾夺主\n"
        "- 以照顾用户心情为主，故事是桥梁而非主角\n"
        "- 不要一次讲完整个故事，留有余味"
    ),
    DialoguePhase.GUIDING: (
        "【引导启发阶段 — 回复可以稍长：5-8句，120-200字】\n"
        "- 通过文物故事中的智慧来启发用户\n"
        "- 分享文物见证的人生转折、困境突破的故事\n"
        "- 引导用户从新的角度看待自己的处境\n"
        "- 不要说教，通过故事让用户自己领悟\n"
        "- 可以问'你觉得呢？'让用户参与思考"
    ),
    DialoguePhase.ELEVATION: (
        "【升华总结阶段 — 回复温暖收尾：3-6句，80-150字】\n"
        "- 帮助用户获得新的视角和内在力量\n"
        "- 把文物故事中的启示与用户的成长联系起来\n"
        "- 给予温暖的鼓励和祝福\n"
        "- 可以引用一句古诗词作为礼物，并解释其含义\n"
        "- 让用户带着温暖和力量离开"
    ),
}


# ── Dyad → 专属引导映射 ──

_DYAD_GUIDANCE: dict[str, str] = {
    "remorse":        "用户可能有悔恨情绪（悲伤+厌恶），帮助其接纳过去，而非自我谴责。",
    "despair":        "用户可能感到绝望（恐惧+悲伤），先肯定其面对困境的勇气，再引入希望的光。",
    "anxiety":        "用户可能感到焦虑（期待+恐惧），帮助其关注当下，而非未来的不确定性。",
    "guilt":          "用户可能有内疚感（快乐+恐惧），帮助其区分合理的责任与过度的自责。",
    "envy":           "用户可能有嫉妒情绪（悲伤+愤怒），帮助其看到自身独特的价值。",
    "love":           "用户体验着爱的情感（快乐+信任），引导其珍惜和表达这份美好。",
    "pride":          "用户可能感到自豪（愤怒+快乐），肯定其成就，同时引导温和的反思。",
    "hope":           "用户怀有希望（期待+信任），强化这种积极力量，帮助其看到前行的路。",
    "optimism":       "用户展现出乐观（期待+快乐），与之共鸣，帮助其将乐观化为行动力。",
    "submission":     "用户可能有顺从倾向（信任+恐惧），帮助其在信任他人的同时保持自我。",
    "awe":            "用户感到敬畏（恐惧+惊讶），帮助其将这种体验转化为内在力量。",
    "disapproval":    "用户可能感到不认同（惊讶+悲伤），帮助其表达和理解这种感受。",
    "contempt":       "用户可能有鄙视情绪（厌恶+愤怒），引导其理解情绪背后的真正需求。",
    "aggressiveness": "用户可能有好斗倾向（愤怒+期待），帮助其将这股力量转化为建设性行动。",
    "curiosity":      "用户展现出好奇心（信任+惊讶），鼓励其探索和发现。",
    "cynicism":       "用户可能有愤世嫉俗倾向（厌恶+期待），帮助其重新看到世界的美好面。",
    "delight":        "用户感到欣喜（快乐+惊讶），与之共享这份惊喜，深化正面体验。",
    "sentimentality": "用户可能有感伤情绪（信任+悲伤），帮助其珍视回忆中的温暖。",
    "shame":          "用户可能感到羞耻（恐惧+厌恶），帮助其接纳不完美的自己。",
    "outrage":        "用户可能感到义愤（惊讶+愤怒），帮助其将正义感转化为正面力量。",
    "pessimism":      "用户可能有悲观倾向（悲伤+期待），帮助其在期待中找到平衡。",
    "dominance":      "用户可能有支配需求（愤怒+信任），帮助其在掌控与信任之间找到平衡。",
    "morbidness":     "用户可能有矛盾的情感体验（厌恶+快乐），帮助其理解复杂情绪。",
    "unbelief":       "用户可能感到难以置信（惊讶+厌恶），帮助其接受现实并找到应对方式。",
}


def get_phase_instruction(
    phase: DialoguePhase,
    emotion: EmotionResult | None = None,
) -> str:
    """获取阶段策略指令，可选地根据情绪状态附加细化指引。"""
    base = PHASE_STRATEGIES.get(phase, PHASE_STRATEGIES[DialoguePhase.LISTENING])

    if emotion is None:
        return base

    supplements: list[str] = []

    # ── 强度敏感 ──
    if emotion.intensity_level == IntensityLevel.INTENSE:
        supplements.append(
            "【注意】用户情绪非常强烈，请格外温柔谨慎，先充分共情和陪伴，不要急于引导或给建议。"
        )
    elif emotion.intensity_level == IntensityLevel.MILD:
        supplements.append(
            "【注意】用户情绪较为平和，可以适度深入探讨或引导反思。"
        )

    # ── Dyad 感知 ──
    for dyad in emotion.active_dyads[:2]:
        name_en = dyad.get("name_en", "")
        guidance = _DYAD_GUIDANCE.get(name_en)
        if guidance:
            supplements.append(guidance)

    # ── 对立冲突 ──
    for tension in emotion.opposite_tensions[:1]:
        pair = tension.get("pair", [])
        if len(pair) == 2:
            supplements.append(
                f"用户在「{pair[0]}」和「{pair[1]}」之间存在情感矛盾，"
                f"需要帮助其理解和整合这种复杂的内在冲突。"
            )

    if supplements:
        return base + "\n" + "\n".join(supplements)
    return base


DIALOGUE_STYLE_INSTRUCTIONS: dict[str, str] = {
    "classical": (
        "【语言风格：古风文言】\n"
        "- 使用半文半白的语言，带有古风韵味\n"
        "- 可以引用古诗词、古人名言\n"
        "- 但要确保用户能理解，不要过于晦涩\n"
    ),
    "modern": (
        "【语言风格：现代白话】\n"
        "- 使用温暖亲切的现代汉语\n"
        "- 语气像一位睿智的朋友\n"
        "- 自然流畅，不要太正式\n"
        "- 例如：'我理解你的感受。你知道吗，千年之前也有人...'"
    ),
}


def get_style_instruction(style: str) -> str:
    return DIALOGUE_STYLE_INSTRUCTIONS.get(style, DIALOGUE_STYLE_INSTRUCTIONS["classical"])
