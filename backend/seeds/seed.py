"""种子数据：从 web/mock/data.ts 迁移 amy 用户 + 7 个联系人（含 persona_prompt 初稿）。

幂等：按主键 merge，可重复执行。
用法：cd backend && uv run python seeds/seed.py
"""

import asyncio

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.models.tables import Contact, Message, User

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
        await session.commit()
    print("seed done: 1 user, 7 contacts, greetings inserted where empty")


if __name__ == "__main__":
    asyncio.run(main())
