"""工具函数。"""

from nonebot.adapters.onebot.v11 import Bot


async def is_friend(bot: Bot, user_id: int) -> bool:
    """判断目标用户是否在机器人好友列表中。"""

    friend_list = await bot.get_friend_list()
    return any(friend.get("user_id") == user_id for friend in friend_list)
