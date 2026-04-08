<div align="center">
    <a href="https://v2.nonebot.dev/store">
    <img src="https://raw.githubusercontent.com/fllesser/nonebot-plugin-template/refs/heads/resource/.docs/NoneBotPlugin.svg" width="310" alt="logo"></a>

## ✨ nonebot-plugin-sublike ✨
[![LICENSE](https://img.shields.io/github/license/ByteColtX/nonebot-plugin-sublike.svg)](./LICENSE)
[![pypi](https://img.shields.io/pypi/v/nonebot-plugin-sublike.svg)](https://pypi.python.org/pypi/nonebot-plugin-sublike)
[![python](https://img.shields.io/badge/python-3.10|3.11|3.12|3.13-blue.svg)](https://www.python.org)
[![uv](https://img.shields.io/badge/package%20manager-uv-black?style=flat-square&logo=uv)](https://github.com/astral-sh/uv)
<br/>
[![ruff](https://img.shields.io/badge/code%20style-ruff-black?style=flat-square&logo=ruff)](https://github.com/astral-sh/ruff)
[![pre-commit](https://results.pre-commit.ci/badge/github/ByteColtX/nonebot-plugin-sublike/master.svg)](https://results.pre-commit.ci/latest/github/ByteColtX/nonebot-plugin-sublike/master)

</div>

## 📖 介绍

一个基于 `OneBot v11` 的 NoneBot2 QQ 点赞插件。

当前已支持：

- 即时点赞自己
- 即时点赞群内其他人
- 订阅定时点赞
- 订阅续期、取消订阅、订阅状态查询
- 按运行时段轮询订阅用户，并在执行前加入随机延迟

此外还提供以下个性化配置能力：

- 自定义“赞我”“赞他”“订阅赞”等触发词
- 控制即时点赞、订阅点赞是否要求好友关系
- 控制是否允许即时点赞他人
- 配置订阅有效期、扫描间隔、运行时段和最大随机延迟
- 配置禁用插件命令的群号列表


## 💿 安装

<details open>
<summary>使用 nb-cli 安装</summary>
在 nonebot2 项目的根目录下打开命令行, 输入以下指令即可安装

    nb plugin install nonebot-plugin-sublike --upgrade
使用 **pypi** 源安装

    nb plugin install nonebot-plugin-sublike --upgrade -i "https://pypi.org/simple"
使用**清华源**安装

    nb plugin install nonebot-plugin-sublike --upgrade -i "https://pypi.tuna.tsinghua.edu.cn/simple"


</details>

<details>
<summary>使用包管理器安装</summary>
在 nonebot2 项目的插件目录下, 打开命令行, 根据你使用的包管理器, 输入相应的安装命令

<details open>
<summary>uv</summary>

    uv add nonebot-plugin-sublike
安装仓库 master 分支

    uv add git+https://github.com/ByteColtX/nonebot-plugin-sublike@master
</details>

<details>
<summary>pdm</summary>

    pdm add nonebot-plugin-sublike
安装仓库 master 分支

    pdm add git+https://github.com/ByteColtX/nonebot-plugin-sublike@master
</details>
<details>
<summary>poetry</summary>

    poetry add nonebot-plugin-sublike
安装仓库 master 分支

    poetry add git+https://github.com/ByteColtX/nonebot-plugin-sublike@master
</details>

打开 nonebot2 项目根目录下的 `pyproject.toml` 文件, 在 `[tool.nonebot]` 部分追加写入

    plugins = ["nonebot_plugin_sublike"]

</details>

<details>
<summary>使用 nbr 安装(使用 uv 管理依赖可用)</summary>

[nbr](https://github.com/fllesser/nbr) 是一个基于 uv 的 nb-cli，可以方便地管理 nonebot2

    nbr plugin install nonebot-plugin-sublike
使用 **pypi** 源安装

    nbr plugin install nonebot-plugin-sublike -i "https://pypi.org/simple"
使用**清华源**安装

    nbr plugin install nonebot-plugin-sublike -i "https://pypi.tuna.tsinghua.edu.cn/simple"

</details>


## ⚙️ 配置

在 nonebot2 项目的 `.env` 文件中添加下表中的配置

| 配置项 | 必填 | 默认值 | 说明 |
| :---: | :---: | :---: | :--- |
| `sublike_cmd_me` | 否 | `["赞我", "草我"]` | 即时点赞自己的触发词 |
| `sublike_cmd_other` | 否 | `["赞ta","赞他"]` | 即时点赞他人的触发词 |
| `sublike_cmd_sub` | 否 | `["订阅赞", "天天赞我"]` | 订阅赞触发词 |
| `sublike_cmd_unsub` | 否 | `["取消订阅赞"]` | 取消订阅触发词 |
| `sublike_cmd_status` | 否 | `["查询订阅赞"]` | 订阅状态查询触发词 |
| `sublike_need_friend_me` | 否 | `false` | 即时点赞是否要求好友关系 |
| `sublike_need_friend_sub` | 否 | `true` | 订阅点赞是否要求好友关系 |
| `sublike_allow_other` | 否 | `true` | 是否允许即时点赞他人 |
| `sublike_sub_expire_days` | 否 | `7` | 订阅有效期天数，需在过期前再次触发订阅命令续期 |
| `sublike_sched_interval` | 否 | `60` | 定时扫描间隔，单位分钟 |
| `sublike_sched_start` | 否 | `8` | 定时任务开始小时 |
| `sublike_sched_end` | 否 | `0` | 定时任务结束小时，`0` 表示次日 `00:00` |
| `sublike_delay_max` | 否 | `2` | 单个订阅用户执行前的最大随机延迟，单位分钟 |
| `sublike_banned_groups` | 否 | `[]` | 禁用插件命令的群号列表 |

## 🎉 使用
### 指令表
| 指令 | 权限 | 需要@ | 范围 | 说明 |
| :---: | :---: | :---: | :---: | :--- |
| `赞我` | 群员 | 否 | 群聊 / 私聊 | 给发送者点赞直到当日上限 |
| `赞他 @用户` | 群员 | 否 | 群聊 | 给目标用户点赞直到当日上限 |
| `订阅赞` / `天天赞我` | 群员 | 否 | 群聊 / 私聊 | 创建或续期订阅赞 |
| `取消订阅赞` | 群员 | 否 | 群聊 / 私聊 | 取消自己的订阅赞 |
| `查询订阅赞` | 群员 | 否 | 群聊 / 私聊 | 普通用户查看自己的订阅状态，`SUPERUSERS` 可查看全部有效订阅 |
