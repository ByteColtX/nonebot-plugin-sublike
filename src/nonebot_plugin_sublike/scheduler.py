"""定时任务入口。"""

from datetime import datetime

from nonebot import get_bots, logger, require
from nonebot.adapters.onebot.v11 import Bot

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler

from .config import plugin_config
from .service import run_subscription_scan
from .utils import in_active_window


def _get_onebot_bot() -> Bot | None:
    """获取可用的 OneBot v11 Bot。"""

    for bot in get_bots().values():
        if isinstance(bot, Bot):
            return bot
    return None


@scheduler.scheduled_job(
    "interval",
    minutes=plugin_config.sublike_sched_interval,
    id="nonebot_plugin_sublike_subscription_scan",
)
async def subscription_scan_job() -> None:
    """定时扫描订阅用户。"""

    now = datetime.now()
    if not in_active_window(
        now,
        plugin_config.sublike_sched_start,
        plugin_config.sublike_sched_end,
    ):
        return

    bot = _get_onebot_bot()
    if bot is None:
        logger.warning("nonebot_plugin_sublike 未找到可用的 OneBot v11 Bot")
        return

    await run_subscription_scan(bot)
