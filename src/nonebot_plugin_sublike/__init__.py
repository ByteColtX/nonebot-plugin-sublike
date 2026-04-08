from nonebot import require
from nonebot.plugin import PluginMetadata

_ = require("nonebot_plugin_apscheduler")
_ = require("nonebot_plugin_localstore")

from .config import Config
from .matcher import like_me
from .scheduler import subscription_scan_job

__plugin_meta__ = PluginMetadata(
    name="QQ点赞",
    description="QQ点赞、订阅赞",
    usage="赞我|赞他|订阅赞|取消订阅赞|订阅列表查询",
    type="application",
    homepage="https://github.com/ByteColtX/nonebot-plugin-sublike",
    config=Config,
    supported_adapters={"~onebot.v11"},
    extra={"author": "ByteColtX <umk@live.com>"},
)

__all__ = ["__plugin_meta__", "like_me", "subscription_scan_job"]
