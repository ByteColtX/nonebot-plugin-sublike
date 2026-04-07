"""点赞业务逻辑。"""

from nonebot import logger
from nonebot.adapters.onebot.v11 import Bot


async def send_like_until_limit(bot: Bot, user_id: int) -> int:
    """持续点赞，直到接口拒绝继续点赞为止。"""

    total = 0

    while True:
        try:
            result = await bot.send_like(user_id=user_id, times=10)
        except Exception as exception:
            if total > 0:
                logger.info(
                    f"用户 {user_id} 点赞已到上限，本次累计 {total} 赞："
                    f"{exception!r}"
                )
            else:
                logger.warning(f"用户 {user_id} 点赞失败：{exception!r}")
            break

        # OneBot v11 单次最多 10 赞，持续累加直到接口拒绝。
        total += 10

        if isinstance(result, dict):
            if result.get("ok") is False:
                logger.info(f"用户 {user_id} 的点赞接口返回停止信号")
                break
            if result.get("times") == 0:
                logger.info(f"用户 {user_id} 当日剩余点赞次数为 0")
                break

    return total
