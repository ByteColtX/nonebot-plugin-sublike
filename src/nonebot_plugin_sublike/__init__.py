from nonebot.plugin import PluginMetadata

from .config import Config
from .matcher import like_me

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

__all__ = ["__plugin_meta__", "like_me"]
