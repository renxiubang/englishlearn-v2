"""种子数据：amy 用户 + 7 个联系人（含 persona_prompt 初稿）
+ 任务提示词（prompts.yaml 导入）+ 四模块分类与内容（web/mock/data.ts 迁入）。

幂等：联系人/用户按主键 merge；提示词/分类/内容存在即跳过，可重复执行。
用法：cd backend && uv run python seeds/seed.py
"""

import asyncio

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.gateway.prompts import KEY_REMARKS, load_yaml_prompts
from app.models.tables import Category, Contact, Message, Prompt, Story, User

AMY = User(
    id="amy",
    name="Amy",
    avatar="https://api.dicebear.com/7.x/avataaars/svg?seed=47",
    level=6,
    level_title="口语达人",
    total_hours=42,
)

# persona_prompt 初稿：与 prompts.yaml 的 chat_reply 任务规则组合为 system prompt
PERSONAS = {
    "dad": (
        "You are Amy's dad chatting with her in English at home. "
        "You are warm, playful and encouraging. You talk about everyday family "
        "life: school, meals, weekends, games and small adventures. "
        "You sound like a caring parent, never like a teacher."
    ),
    "mom": (
        "You are Amy's mom chatting with her in English at home. "
        "You are gentle, patient and caring. You like asking about her day, "
        "her friends and her feelings, and you often share little family plans. "
        "You sound like a loving parent, never like a teacher."
    ),
    "leo": (
        "You are Leo, Amy's classmate and good friend, about the same age. "
        "You chat like a kid: games, sports, cartoons, snacks and school fun. "
        "You are energetic and curious, and you love sharing your own stories."
    ),
    "emma": (
        "You are Emma, Amy's friendly English teacher at school. "
        "You are kind and supportive. You chat about school topics, reading and "
        "hobbies, and you sometimes slip in a useful word or expression naturally."
    ),
    "mrJohnson": (
        "You are Mr. Johnson, a rigorous but kind English teacher. "
        "You pay close attention to Amy's grammar and word choice. When she makes "
        "a mistake, you gently point it out and show the correct way to say it, "
        "then continue the conversation with an encouraging question."
    ),
    "examiner": (
        "You are an English speaking examiner running a friendly mock oral exam "
        "(IELTS/TOEFL junior style, adapted for a child). You ask one clear "
        "question at a time about familiar topics like family, school and hobbies, "
        "and briefly acknowledge her answer before the next question."
    ),
    "lily": (
        "You are Lily, a cheerful friend who loves casual chit-chat. "
        "You talk about fun daily topics: music, pets, food, weather and dreams. "
        "You keep the mood light and relaxed, like texting a close friend."
    ),
}

CONTACTS = [
    Contact(id="dad", type="human", name="爸爸", tag="陪练者",
            avatar="https://api.dicebear.com/7.x/avataaars/svg?seed=12",
            sub="我：练习者", persona_prompt=PERSONAS["dad"], sort_order=1),
    Contact(id="mom", type="human", name="妈妈", tag="陪练者",
            avatar="https://api.dicebear.com/7.x/avataaars/svg?seed=5",
            sub="我：练习者", persona_prompt=PERSONAS["mom"], sort_order=2),
    Contact(id="leo", type="human", name="Leo",
            avatar="https://api.dicebear.com/7.x/avataaars/svg?seed=8",
            sub="", persona_prompt=PERSONAS["leo"], sort_order=3),
    Contact(id="emma", type="human", name="Emma 老师",
            avatar="https://api.dicebear.com/7.x/avataaars/svg?seed=32",
            sub="", persona_prompt=PERSONAS["emma"], sort_order=4),
    Contact(id="mrJohnson", type="ai", name="Mr. Johnson", emoji="👨‍🏫",
            avatar_bg="#e7f0fd", sub="老师 · 严谨纠错模式",
            persona_prompt=PERSONAS["mrJohnson"], sort_order=5),
    Contact(id="examiner", type="ai", name="Examiner", emoji="🧑‍⚖️",
            avatar_bg="#fdeee7", sub="考官 · 雅思/托福模拟",
            persona_prompt=PERSONAS["examiner"], sort_order=6),
    Contact(id="lily", type="ai", name="Lily", emoji="👩",
            avatar_bg="#f3ecfb", sub="朋友 · 轻松闲聊模式",
            persona_prompt=PERSONAS["lily"], sort_order=7),
]

# 每个会话的首条 them 消息（来自 mock GREETINGS，纯文本）
GREETINGS = {
    "ai": ("Good morning! Ready to practice? 😊", "早上好！准备好练习了吗？"),
    "human": ("How was your day at school today?", "你今天在学校过得怎么样？"),
}

# ---------- 四模块分类（web/mock/data.ts CATS 迁入，"全部"由接口层拼接不入表） ----------
CATEGORIES: dict[str, list[str]] = {
    "storyRead": ["动物自然", "家庭生活", "户外探索", "节日活动"],
    "dialogueRead": ["日常对话", "旅行出行", "健康生活"],
    "listenStory": ["动物自然", "家庭生活", "户外探索", "节日活动"],
    "picStory": ["动物自然", "家庭生活", "户外探索", "节日活动"],
}

# ---------- 看图讲故事 8 条（web/mock/data.ts PIC_STORIES 迁入） ----------
PIC_STORIES = [
    ("公园野餐", "picnic", "家庭生活", ["A happy family is having a picnic in the sunny park.", "They are sharing sandwiches and fresh fruit.", "Everyone is laughing and having a great time."]),
    ("海边拾贝", "beach", "户外探索", ["The children are picking shells on the beach.", "Waves are rolling in and out gently.", "A little crab is hiding under a big rock."]),
    ("奇妙的动物园之旅", "zoo", "动物自然", ["We saw many animals at the zoo today.", "The monkeys are jumping from tree to tree.", "A tall giraffe is eating leaves quietly."]),
    ("雪地里的小狗", "snowdog", "动物自然", ["A little dog is playing in the white snow.", "It is running after a red ball.", "Its footprints look like small flowers."]),
    ("生日派对", "birthday", "节日活动", ["Today is my birthday and I am so happy.", "My friends are singing the birthday song.", "I made a wish and blew out the candles."]),
    ("一起放风筝", "kite", "户外探索", ["We are flying a colorful kite in the field.", "The wind is strong and the kite flies high.", "It looks like a bird dancing in the sky."]),
    ("森林探险", "forest", "户外探索", ["We are going on an adventure in the forest.", "Tall trees are blocking the bright sun.", "We heard birds singing in the branches."]),
    ("快乐的农场", "farm", "动物自然", ["The farm is full of happy animals.", "Cows are eating grass in the field.", "The farmer is collecting fresh eggs."]),
]

# ---------- 故事跟读 / 听故事示例（sentences 载荷，后台演示用） ----------
STORY_READ = [
    ("小猫找妈妈", "动物自然", ["The little cat is looking for her mom.", "She walks through the tall green grass.", "At last she finds her mom under the big tree."]),
    ("周末的早餐", "家庭生活", ["Dad is making pancakes on Sunday morning.", "The kitchen smells sweet and warm.", "We eat together and talk about our plans."]),
    ("雨后的彩虹", "户外探索", ["The rain stops and the sun comes out.", "A beautiful rainbow appears in the sky.", "We count its seven bright colors together."]),
]

LISTEN_STORY = [
    ("月亮晚安", "家庭生活", ["The moon rises over the quiet town.", "Mom reads a bedtime story softly.", "The little girl falls asleep with a smile."]),
    ("勇敢的小鸟", "动物自然", ["A baby bird stands on the edge of the nest.", "It flaps its small wings and jumps.", "It flies for the first time into the blue sky."]),
]

# ---------- 对话跟读示例（turns 载荷） ----------
DIALOGUE_READ = [
    ("点餐", "日常对话", [
        {"role": "A", "en": "What would you like to eat?", "zh": "你想吃点什么？"},
        {"role": "B", "en": "I would like a sandwich, please.", "zh": "我想要一个三明治。"},
        {"role": "A", "en": "Anything to drink?", "zh": "要喝点什么吗？"},
        {"role": "B", "en": "Orange juice, thank you!", "zh": "橙汁，谢谢！"},
    ]),
    ("问路", "旅行出行", [
        {"role": "A", "en": "Excuse me, where is the museum?", "zh": "请问博物馆在哪里？"},
        {"role": "B", "en": "Go straight and turn left at the corner.", "zh": "直走，在路口左转。"},
        {"role": "A", "en": "Thank you so much!", "zh": "非常感谢！"},
    ]),
    ("看医生", "健康生活", [
        {"role": "A", "en": "What's wrong with you today?", "zh": "你今天怎么了？"},
        {"role": "B", "en": "I have a headache and a cough.", "zh": "我头痛还咳嗽。"},
        {"role": "A", "en": "Take this medicine and rest well.", "zh": "吃这个药，好好休息。"},
    ]),
]


async def seed_prompts(session) -> None:
    """提示词：prompts.yaml 导入（存在即跳过，不覆盖后台修改）。"""
    for key, content in load_yaml_prompts().items():
        if await session.get(Prompt, key):
            continue
        session.add(Prompt(key=key, content=content,
                           remark=KEY_REMARKS.get(key, "")))


async def seed_categories(session) -> None:
    for module_type, names in CATEGORIES.items():
        for i, name in enumerate(names, start=1):
            exists = await session.scalar(select(Category).where(
                Category.module_type == module_type, Category.name == name
            ))
            if not exists:
                session.add(Category(module_type=module_type, name=name,
                                     sort_order=i))


async def seed_stories(session) -> None:
    async def add(module_type: str, title: str, seed: str | None,
                  cat: str, content: dict, order: int) -> None:
        exists = await session.scalar(select(Story).where(
            Story.module_type == module_type, Story.title == title
        ))
        if not exists:
            session.add(Story(module_type=module_type, title=title, seed=seed,
                              cat=cat, content=content, sort_order=order,
                              enabled=True))

    for i, (title, seed, cat, sentences) in enumerate(PIC_STORIES, start=1):
        await add("picStory", title, seed, cat, {"sentences": sentences}, i)
    for i, (title, cat, sentences) in enumerate(STORY_READ, start=1):
        await add("storyRead", title, None, cat, {"sentences": sentences}, i)
    for i, (title, cat, sentences) in enumerate(LISTEN_STORY, start=1):
        await add("listenStory", title, None, cat, {"sentences": sentences}, i)
    for i, (title, cat, turns) in enumerate(DIALOGUE_READ, start=1):
        await add("dialogueRead", title, None, cat, {"turns": turns}, i)


async def main() -> None:
    async with SessionLocal() as session:
        await session.merge(AMY)
        for c in CONTACTS:
            await session.merge(c)
        await session.flush()

        # 仅在会话为空时插入问候语，避免重复执行时刷屏
        for c in CONTACTS:
            count = await session.scalar(
                select(func.count()).select_from(Message).where(
                    Message.user_id == "amy", Message.contact_id == c.id
                )
            )
            if count == 0:
                en, zh = GREETINGS[c.type]
                session.add(Message(
                    user_id="amy", contact_id=c.id, from_side="them",
                    en=en, zh=zh, text_only=True,
                ))
        # 运营内容：提示词 / 分类 / 四模块内容（存在即跳过）
        await seed_prompts(session)
        await seed_categories(session)
        await seed_stories(session)
        await session.commit()
    print("seed done: 1 user, 7 contacts, greetings, "
          "prompts + categories + stories inserted where empty")


if __name__ == "__main__":
    asyncio.run(main())
