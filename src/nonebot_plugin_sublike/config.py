"""插件配置。"""

from nonebot import get_plugin_config
from pydantic import BaseModel, Field


class Config(BaseModel):
    """插件配置模型。"""

    sublike_cmd_me: tuple[str, ...] = ("赞我", "草我", "超我")
    sublike_cmd_sub: tuple[str, ...] = ("每日赞", "天天赞我")
    sublike_cmd_unsub: tuple[str, ...] = ("取消每日赞", "每日赞取消")
    sublike_cmd_status: tuple[str, ...] = (
        "每日赞查看",
        "查看每日赞",
        "每日赞状态",
        "每日赞查询",
        "查询每日赞",
    )
    sublike_cmd_other: tuple[str, ...] = (
        "赞ta",
        "赞TA",
        "赞他",
        "赞她",
        "草ta",
        "草TA",
        "草他",
        "草她",
    )

    sublike_need_friend_me: bool = False
    sublike_need_friend_sub: bool = True
    sublike_allow_other: bool = True

    sublike_sub_expire_days: int = Field(default=7, ge=1)
    sublike_sched_interval: int = Field(default=60, ge=1)
    sublike_sched_start: int = Field(default=8, ge=0, le=23)
    sublike_sched_end: int = Field(default=0, ge=0, le=23)
    sublike_delay_max: int = Field(default=2, ge=0)

    sublike_banned_groups: tuple[int, ...] = ()


plugin_config = get_plugin_config(Config)
