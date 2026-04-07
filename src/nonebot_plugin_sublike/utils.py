"""工具函数。"""

from datetime import datetime
from random import randint

from nonebot.adapters.onebot.v11 import Bot


async def is_friend(bot: Bot, user_id: int) -> bool:
    """判断目标用户是否在机器人好友列表中。"""

    friend_list = await bot.get_friend_list()
    return any(friend.get("user_id") == user_id for friend in friend_list)


def in_active_window(now: datetime, start_hour: int, end_hour: int) -> bool:
    """判断当前时间是否处于定时任务运行时段。"""

    current_hour = now.hour
    if start_hour == end_hour:
        return True
    if start_hour < end_hour:
        return start_hour <= current_hour < end_hour
    return current_hour >= start_hour or current_hour < end_hour


def get_random_delay_seconds(max_minutes: int) -> int:
    """获取随机延迟秒数。"""

    if max_minutes <= 0:
        return 0
    return randint(0, max_minutes * 60)
