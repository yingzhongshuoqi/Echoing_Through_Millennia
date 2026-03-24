"""
Seed data: historical relics with Plutchik emotion annotations.

Usage:
    python seed_data.py            # 跳过已存在的文物
    python seed_data.py --reseed   # 清空旧表，全量重建

每件文物需包含以下 Plutchik 标注字段：
    emotion_vector: dict — 8 种基本情绪评分 (0.0-1.0)
        joy, trust, fear, surprise, sadness, disgust, anger, anticipation
    emotion_tags: list[str] — 仅使用 Plutchik 词表中的词（基本情绪/强度词/Dyad词）

后续新增文物照此格式填写即可，脚本只负责生成 embedding 并入库。
"""
import argparse
import asyncio
import logging
import os
from pathlib import Path
from urllib import error, request

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

EMOTION_KEYS = ("joy", "trust", "fear", "surprise", "sadness", "disgust", "anger", "anticipation")

# ──────────────────────────────────────────────
# 文物数据（含手动 Plutchik 标注）
#
# emotion_vector: 8 维情绪评分，对应 Plutchik 轮盘
#   joy(快乐) trust(信任) fear(恐惧) surprise(惊讶)
#   sadness(悲伤) disgust(厌恶) anger(愤怒) anticipation(期待)
#
# emotion_tags: 仅使用 Plutchik 词表中的词
#   基本情绪: 快乐、信任、恐惧、惊讶、悲伤、厌恶、愤怒、期待
#   强度词: 宁静/快乐/狂喜、接受/信任/崇敬、忧虑/恐惧/恐怖、
#           分心/惊讶/惊愕、忧伤/悲伤/悲痛、无趣/厌恶/嫌恶、
#           烦扰/愤怒/暴怒、兴趣/期待/警觉
#   Dyad词: 爱、顺从、敬畏、不赞同、悔恨、鄙视、好斗、乐观、
#           内疚、好奇、绝望、难以置信、嫉妒、愤世嫉俗、骄傲、希望、
#           欣喜、感伤、羞耻、义愤、悲观、病态、支配、焦虑
# ──────────────────────────────────────────────

RELICS = [
    {
        "name": "司母戊鼎",
        "dynasty": "商朝",
        "period": "公元前1300年-公元前1046年",
        "category": "青铜器",
        "description": "中国商代后期王室祭祀用的青铜方鼎，是已知中国古代最重的青铜器。",
        "story": "三千多年前的殷商王朝，一位王子为纪念他的母亲'戊'，倾举国之力铸造了这尊巨鼎。数百位工匠日夜不休，将滚烫的铜液注入模具——这是一个儿子对母亲最深沉的思念。他用当时最珍贵的材料、最高超的技艺，将跨越生死的爱铸成了永恒。司母戊鼎重达八百多公斤，是已知中国古代最重的青铜器，三千年过去，这份深情依然震撼人心。",
        "life_insight": "最深沉的爱，往往在失去后才懂得珍惜。但正是这份珍惜，让爱变成了永恒。",
        "emotion_tags": ["忧伤", "崇敬", "爱", "感伤", "信任", "悲伤"],
        "emotion_vector": {
            "joy": 0.3, "trust": 0.7, "fear": 0.1, "surprise": 0.05,
            "sadness": 0.7, "disgust": 0.0, "anger": 0.0, "anticipation": 0.15,
        },
    },
    {
        "name": "越王勾践剑",
        "dynasty": "春秋",
        "period": "公元前496年-公元前465年",
        "category": "兵器",
        "description": "越王勾践使用的青铜剑，历经两千余年依然锋利无比。",
        "story": "春秋末年，越王勾践被吴王夫差打败，沦为阶下囚，做了三年奴仆。那些日子里，他每天舔尝苦胆提醒自己不忘耻辱。这把青铜剑静静伴在他枕边，见证了一个被命运打倒的人如何一步步站起来。二十年的隐忍与坚持，勾践最终灭吴复国。世人只看到最后的辉煌，却不知那些漫漫长夜里的孤独与不甘。这把剑历经两千余年依然锋利如新，仿佛在诉说：意志也可以不朽。",
        "life_insight": "人生最大的敌人不是失败，而是失败后的放弃。凡是杀不死你的，终将使你更强大。",
        "emotion_tags": ["暴怒", "好斗", "忧伤", "警觉", "鄙视", "悲观", "愤怒"],
        "emotion_vector": {
            "joy": 0.1, "trust": 0.35, "fear": 0.2, "surprise": 0.05,
            "sadness": 0.6, "disgust": 0.35, "anger": 0.7, "anticipation": 0.8,
        },
    },
    {
        "name": "长信宫灯",
        "dynasty": "西汉",
        "period": "公元前172年",
        "category": "灯具",
        "description": "中国汉代青铜器，宫女跪坐执灯造型，设计精巧环保。",
        "story": "西汉时期，窦太后的长信宫中，一位宫女日复一日地在深宫里默默服侍。她没有名字，没有人记住她的容颜。但一位匠人将她跪坐执灯的身影铸成了青铜——长信宫灯由此诞生。灯的烟气通过宫女的衣袖导入体内，保持室内清净，设计巧妙令人叹服。两千多年过去，这盏灯让人不禁思考：那些默默无闻的人，那些在暗处执灯照亮他人的人，他们的价值被谁看见？也许，真正的光芒不在于被人看见，而在于你照亮了谁。",
        "life_insight": "每个默默付出的人都有自己的光芒。不是每盏灯都需要被人仰望，有时候，照亮身边的一小片天地，就是最大的意义。",
        "emotion_tags": ["宁静", "接受", "忧伤", "爱", "感伤", "信任", "顺从"],
        "emotion_vector": {
            "joy": 0.3, "trust": 0.65, "fear": 0.05, "surprise": 0.05,
            "sadness": 0.55, "disgust": 0.0, "anger": 0.0, "anticipation": 0.15,
        },
    },
    {
        "name": "马踏飞燕",
        "dynasty": "东汉",
        "period": "公元25年-220年",
        "category": "青铜器",
        "description": "铜奔马，中国旅游标志。奔马三足腾空，一足踏燕，气势磅礴。",
        "story": "东汉时期，一位匠人铸造了这匹铜奔马，后人称之为'马踏飞燕'。它的造型定格在最自由的一瞬间——三足腾空、一足踏燕，像是要挣脱大地的束缚飞向天际。铸造它的匠人一定也渴望这样的自由。在那个烽火连天的年代，多少人渴望挣脱困境、纵横四方。这匹铜马承载的不只是速度和力量，更是千百年来人们心中对自由和突破的渴望。",
        "life_insight": "真正的自由不是没有束缚，而是在束缚中依然保持飞翔的姿态。",
        "emotion_tags": ["狂喜", "乐观", "欣喜", "警觉", "快乐", "期待", "好斗"],
        "emotion_vector": {
            "joy": 0.75, "trust": 0.3, "fear": 0.05, "surprise": 0.3,
            "sadness": 0.05, "disgust": 0.0, "anger": 0.1, "anticipation": 0.8,
        },
    },
    {
        "name": "《兰亭集序》",
        "dynasty": "东晋",
        "period": "公元353年",
        "category": "书法",
        "description": "王羲之在兰亭雅集上即兴书写的序文，被誉为天下第一行书。",
        "story": "东晋永和九年暮春三月，王羲之与四十一位友人在会稽山阴的兰亭流觞曲水、吟诗作对。微醺之间，王羲之提笔写下'死生亦大矣'的感慨，这便是被誉为'天下第一行书'的《兰亭集序》。他在最欢乐的时刻想到了生命的短暂，在最美的春光里看到了时光的无情。这不是悲观，而是对生命最深刻的觉察。正因为知道一切终将逝去，当下的每一个瞬间才如此珍贵。",
        "life_insight": "快乐的时刻转瞬即逝，但这不是悲伤的理由。恰恰相反，正因为短暂，所以我们更要珍惜当下。",
        "emotion_tags": ["快乐", "忧伤", "敬畏", "感伤", "欣喜", "宁静", "接受"],
        "emotion_vector": {
            "joy": 0.6, "trust": 0.35, "fear": 0.2, "surprise": 0.3,
            "sadness": 0.5, "disgust": 0.0, "anger": 0.0, "anticipation": 0.25,
        },
    },
    {
        "name": "岳飞《满江红》手迹",
        "dynasty": "南宋",
        "period": "公元1136年",
        "category": "书法",
        "description": "岳飞手书的千古名篇，慷慨激昂。",
        "story": "南宋绍兴六年，岳飞挥笔写下《满江红》。'怒发冲冠'——那一刻他心中燃烧的不只是愤怒，还有对山河破碎的心痛、对百姓流离的不忍、对收复失地的渴望。岳飞是一个矛盾的人：忠义让他一往无前，现实却让他处处受阻。'莫等闲白了少年头，空悲切'不只是对他人的劝勉，更是他对自己人生的叹息。壮志未酬的遗憾，千年来依然震撼人心。",
        "life_insight": "人生最大的遗憾不是失败，而是'本可以'。趁还来得及，去做你认为对的事，不要让热血在等待中凉透。",
        "emotion_tags": ["暴怒", "好斗", "悲痛", "义愤", "警觉", "愤怒", "鄙视"],
        "emotion_vector": {
            "joy": 0.05, "trust": 0.3, "fear": 0.15, "surprise": 0.1,
            "sadness": 0.7, "disgust": 0.3, "anger": 0.9, "anticipation": 0.65,
        },
    },
    {
        "name": "龙门石窟卢舍那大佛",
        "dynasty": "唐朝",
        "period": "公元675年",
        "category": "石刻",
        "description": "洛阳龙门石窟的主佛像，面容慈祥庄严。",
        "story": "唐高宗咸亨三年，龙门石窟的卢舍那大佛落成，据说面容是按照武则天的形象塑造的。千百年来，无数人来到大佛面前跪拜、祈祷、倾诉。他们中有帝王将相，也有普通百姓；有人求功名利禄，有人求家人平安，有人只是来哭一场。大佛不会说话，但它一直在那里，静静地听。有时候，人们需要的不是答案，只是一个愿意听的存在。那微笑不是敷衍，而是告诉每一个人：你的痛苦被看见了。",
        "life_insight": "被倾听、被看见，本身就是一种疗愈。你不需要独自承受一切。",
        "emotion_tags": ["宁静", "崇敬", "爱", "接受", "感伤", "顺从", "信任"],
        "emotion_vector": {
            "joy": 0.3, "trust": 0.8, "fear": 0.1, "surprise": 0.05,
            "sadness": 0.5, "disgust": 0.0, "anger": 0.0, "anticipation": 0.15,
        },
    },
    {
        "name": "圆明园十二兽首",
        "dynasty": "清朝",
        "period": "公元1760年",
        "category": "青铜器",
        "description": "圆明园海晏堂前的十二生肖人身兽首铜像。",
        "story": "清乾隆年间，圆明园海晏堂前建造了十二生肖人身兽首铜像喷泉，精美绝伦。1860年英法联军的大火改变了它们的命运——从皇家花园的瑰宝沦为流落异国的'战利品'。一百多年来，兽首辗转世界各地，见证了人间的贪婪与善良。有人把它们当成炫耀的资本，也有人为了让它们回家而奔走呼号。这段历史让很多人感到愤怒，但它也在诉说：比愤怒更重要的是铭记，比铭记更重要的是强大。",
        "life_insight": "伤痛无法抹去，但可以转化为前进的力量。不是为了报复，而是为了再也不让同样的事情发生。",
        "emotion_tags": ["暴怒", "义愤", "悲痛", "鄙视", "好斗", "嫌恶", "愤怒"],
        "emotion_vector": {
            "joy": 0.0, "trust": 0.1, "fear": 0.2, "surprise": 0.15,
            "sadness": 0.7, "disgust": 0.5, "anger": 0.85, "anticipation": 0.5,
        },
    },
    {
        "name": "鸟尊",
        "dynasty": "西周",
        "period": "约公元前1000年",
        "category": "青铜器",
        "description": "山西出土的凤鸟形青铜酒器，造型生动优美。",
        "story": "约三千年前的西周，一位匠人铸造了这只凤鸟形青铜酒器——鸟尊。凤凰在中国文化中象征着浴火重生，传说它每五百年投入烈火焚烧自己，然后从灰烬中重新诞生。这个传说流传了三千年，因为每个人都经历过'焚烧'的时刻——失败、失恋、失去亲人，觉得一切都完了。但凤凰的故事在说：完了不代表结束。灰烬之中，新的生命正在酝酿。",
        "life_insight": "最深的低谷之后，往往是最壮丽的新生。不要害怕一切归零，因为从零开始也是一种自由。",
        "emotion_tags": ["悲痛", "乐观", "希望", "绝望", "期待", "忧虑", "快乐"],
        "emotion_vector": {
            "joy": 0.4, "trust": 0.3, "fear": 0.3, "surprise": 0.2,
            "sadness": 0.65, "disgust": 0.05, "anger": 0.1, "anticipation": 0.7,
        },
    },
    {
        "name": "翠玉白菜",
        "dynasty": "清朝",
        "period": "约公元19世纪",
        "category": "玉器",
        "description": "利用天然玉石的色泽雕刻而成的白菜造型玉雕。",
        "story": "清代某位匠人发现了一块半白半绿的天然翡翠，别人觉得它颜色不纯、不够完美。但这位匠人看到了它的独特——白色做菜帮，绿色做菜叶，将瑕疵变成了亮点，雕出了这棵栩栩如生的翠玉白菜。菜叶上还趴着一只蝗虫和一只蝈蝈，象征着多子多福。这件作品在告诉世人：所谓的'缺点'，换个角度看，恰恰是最独特的魅力所在。",
        "life_insight": "不完美不是缺陷，而是独特。一个好的创造者能把瑕疵变成亮点，你的人生也一样。",
        "emotion_tags": ["快乐", "欣喜", "接受", "好奇", "信任", "惊讶", "乐观"],
        "emotion_vector": {
            "joy": 0.6, "trust": 0.5, "fear": 0.05, "surprise": 0.4,
            "sadness": 0.2, "disgust": 0.15, "anger": 0.0, "anticipation": 0.35,
        },
    },
]


async def seed_relics(*, reseed: bool = False):
    """Import seed data into PostgreSQL with embeddings."""
    load_dotenv(Path(__file__).parent / ".env")
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    from echobot.relic_knowledge.db import init_relic_db, get_relic_db_session
    from echobot.relic_knowledge.models import Relic
    from echobot.relic_knowledge.embeddings import EmbeddingService
    from sqlalchemy import text

    engine = await init_relic_db()
    if engine is None:
        print("ERROR: RELIC_DATABASE_URL not set in .env")
        return

    embedding_svc = EmbeddingService(
        api_key=os.environ.get("EMBEDDING_API_KEY", ""),
        base_url=os.environ.get("EMBEDDING_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        model=os.environ.get("EMBEDDING_MODEL", "text-embedding-v3"),
        dimensions=int(os.environ.get("EMBEDDING_DIMENSIONS", "1024")),
    )

    if reseed:
        print("Reseed mode: dropping and recreating relics table...")
        async with engine.begin() as conn:
            await conn.execute(text("DROP TABLE IF EXISTS relics"))
            await conn.run_sync(Relic.metadata.create_all)
        print("  Table recreated.\n")

    print(f"Seeding {len(RELICS)} relics...")
    async with get_relic_db_session() as db:
        for i, data in enumerate(RELICS):
            label = f"[{i + 1}/{len(RELICS)}]"

            existing = await db.execute(
                text("SELECT id FROM relics WHERE name = :name"),
                {"name": data["name"]},
            )
            if existing.scalar_one_or_none():
                print(f"  {label} Skip (exists): {data['name']}")
                continue

            # 从预标注数据中读取 8 维向量
            ev = data.get("emotion_vector", {})
            emotion_vec = [max(0.0, min(1.0, float(ev.get(k, 0.0)))) for k in EMOTION_KEYS]

            # 生成 embedding：name + dynasty + story + life_insight + tags
            life_insight = data.get("life_insight", "") or ""
            tags = data.get("emotion_tags", [])
            embed_text = (
                f"{data['name']} {data['dynasty']} {data['story']} "
                f"{life_insight} {' '.join(tags)}"
            )
            try:
                embedding = await embedding_svc.embed(embed_text)
            except Exception as e:
                print(f"  {label} Embedding failed for {data['name']}: {e}")
                embedding = None

            relic = Relic(
                name=data["name"],
                dynasty=data["dynasty"],
                period=data.get("period"),
                category=data.get("category"),
                description=data.get("description"),
                story=data["story"],
                life_insight=data.get("life_insight"),
                emotion_tags=tags,
                image_url=data.get("image_url"),
                embedding=embedding,
                emotion_vector=emotion_vec,
            )
            db.add(relic)
            vec_str = " ".join(f"{k[:3]}={v:.2f}" for k, v in zip(EMOTION_KEYS, emotion_vec))
            print(f"  {label} Added: {data['name']}  [{vec_str}]")

        await db.commit()
    print("\nSeeding complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed relic knowledge base")
    parser.add_argument(
        "--reseed", action="store_true",
        help="Drop and recreate relics table, then seed all data",
    )
    args = parser.parse_args()
    asyncio.run(seed_relics(reseed=args.reseed))
