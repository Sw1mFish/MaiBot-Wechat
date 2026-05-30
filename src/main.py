from typing import TYPE_CHECKING

from rich.traceback import install

import asyncio
import time

from src.A_memorix.host_service import a_memorix_host_service
from src.chat.image_system.image_cache_cleanup import periodic_image_cache_cleanup
from src.chat.message_receive.chat_manager import chat_manager
from src.chat.message_receive.bot import chat_bot
from src.chat.utils.statistic import OnlineTimeRecordTask, StatisticOutputTask
from src.common.i18n import t
from src.common.logger import get_logger
from src.common.message_server.server import Server, get_global_server
from src.common.runtime_loop import set_main_loop
from src.config.config import config_manager, global_config
from src.emoji_system.emoji_manager import emoji_manager
from src.manager.async_task_manager import async_task_manager
from src.plugin_runtime.integration import get_plugin_runtime_manager
from src.prompt.prompt_manager import prompt_manager
from src.services.memory_flow_service import memory_automation_service

# from src.api.main import start_api_server

# 导入插件运行时
# 导入消息API和traceback模块
# from src.chat.utils.token_statistics import TokenStatisticsTask

install(extra_lines=3)

logger = get_logger("main")


if TYPE_CHECKING:
    from maim_message import MessageServer
    from src.webui.webui_server import ThreadedWebUIServer


class MainSystem:
    def __init__(self) -> None:
        # 使用消息API替代直接的FastAPI实例
        from src.common.message_server import get_global_api

        self.app: MessageServer = get_global_api()
        self.server: Server = get_global_server()
        self.webui_server: ThreadedWebUIServer | None = None  # 独立线程中的 WebUI 服务器

    def _start_webui_server(self) -> None:
        """启动独立线程中的 WebUI 服务器。"""
        from src.config.config import global_config

        if not global_config.webui.enabled:
            logger.info(t("startup.webui_disabled"))
            return

        try:
            from src.webui.webui_server import get_threaded_webui_server

            self.webui_server = get_threaded_webui_server()
            self.webui_server.start()

        except Exception as e:
            logger.error(t("startup.webui_server_init_failed", error=e))

    async def initialize(self) -> None:
        """初始化系统组件"""
        logger.info(t("startup.waking_up", nickname=global_config.bot.nickname))

        self._start_webui_server()
        try:
            await self._init_components()
        except Exception:
            if self.webui_server:
                await self.webui_server.shutdown()
            raise

        logger.info(t("startup.initialization_completed_banner", nickname=global_config.bot.nickname))

    async def _init_components(self) -> None:
        """初始化其他组件"""
        init_start_time = time.time()

        await config_manager.start_file_watcher()
        a_memorix_host_service.register_config_reload_callback()
        prompt_manager.load_prompts()

        # 添加在线时间统计任务
        await async_task_manager.add_task(OnlineTimeRecordTask())

        # 添加统计信息输出任务
        await async_task_manager.add_task(StatisticOutputTask())

        # 添加遥测心跳任务
        from src.common.remote import TelemetryHeartBeatTask

        await async_task_manager.add_task(TelemetryHeartBeatTask())

        # 启动API服务器
        # start_api_server()
        # logger.info("API服务器启动成功")

        # 启动插件运行时（内置插件 + 第三方插件双子进程）
        await get_plugin_runtime_manager().start()
        await a_memorix_host_service.start()
        # 初始化 WeChat 驱动
        await self._init_wechat_driver()

        # 初始化表情管理器
        emoji_manager.load_emojis_from_db()
        # 启动后立即扫描一次表情包目录
        # 启动后扫描一次表情包目录并注册新图片
        async def _scan_emojis():
            await asyncio.sleep(5)
            from pathlib import Path
            import hashlib
            emoji_dir = Path("data/emoji")
            if not emoji_dir.exists():
                return
            for f in sorted(emoji_dir.iterdir()):
                if not f.is_file():
                    continue
                data = f.read_bytes()
                h = hashlib.sha256(data).hexdigest()
                from src.common.database.database import get_db_session
                from src.common.database.database_model import Images, ImageType
                from sqlmodel import select
                with get_db_session() as db:
                    if db.exec(select(Images).where(Images.image_hash == h, Images.image_type == ImageType.EMOJI)).first():
                        continue
                try:
                    await emoji_manager.ensure_emoji_saved(data)
                    logger.info(f"自动注册表情包: {f.name}")
                except Exception as e:
                    logger.debug(f"表情包注册失败 {f.name}: {e}")
        asyncio.ensure_future(_scan_emojis())
        logger.info(t("startup.emoji_manager_initialized"))

        # 初始化聊天管理器
        await chat_manager.initialize()
        asyncio.create_task(chat_manager.regularly_save_sessions())

        logger.info(t("startup.chat_manager_initialized"))
        await memory_automation_service.start()

        # await asyncio.sleep(0.5) #防止logger输出飞了

        # 将bot.py中的chat_bot.message_process消息处理函数注册到api.py的消息处理基类中
        self.app.register_message_handler(chat_bot.message_process)
        self.app.register_custom_message_handler("message_id_echo", chat_bot.echo_message_process)

        # 触发 ON_START 事件
        from src.core.event_bus import event_bus
        from src.core.types import EventType

        await event_bus.emit(event_type=EventType.ON_START)

        # 分发 ON_START 事件到插件运行时
        await get_plugin_runtime_manager().bridge_event("on_start")
        # logger.info("已触发 ON_START 事件")
        try:
            init_time = int(1000 * (time.time() - init_start_time))
            logger.info(t("startup.initialization_completed_cycles", init_time=init_time))
        except Exception as e:
            logger.error(t("startup.brain_external_world_failed", error=e))
            raise

    async def _init_wechat_driver(self) -> None:
        """如果配置已启用，初始化并注册 WeChat 驱动。"""
        if not global_config.wechat.enabled:
            return

        from src.platform_io import get_platform_io_manager, RouteKey, RouteBinding, DriverKind
        from src.platform_io.drivers.wechat_driver import WeChatPlatformDriver
        from src.chat.utils.utils import get_bot_account

        platform_io_manager = get_platform_io_manager()
        bot_wxid = get_bot_account("wx")

        driver = WeChatPlatformDriver(
            driver_id="wechat.driver",
            platform="wx",
            account_id=bot_wxid or None,
            poll_interval=global_config.wechat.poll_interval,
        )

        await platform_io_manager.add_driver(driver)

        route_key = RouteKey(platform="wx")
        binding = RouteBinding(
            route_key=route_key,
            driver_id=driver.driver_id,
            driver_kind=driver.descriptor.kind,
        )
        platform_io_manager.bind_send_route(binding)
        platform_io_manager.bind_receive_route(binding)
        logger.info(f"WeChat 驱动已注册: account_id={bot_wxid}")

    async def schedule_tasks(self) -> None:
        """调度定时任务"""
        try:
            tasks = [
                emoji_manager.periodic_emoji_maintenance(),
                periodic_image_cache_cleanup(),
                self.app.run(),
                self.server.run(),
            ]

            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info(t("startup.schedule_cancelled"))
            raise


async def main() -> None:
    """主函数"""
    set_main_loop(asyncio.get_running_loop())
    system = MainSystem()
    try:
        await system.initialize()
        await system.schedule_tasks()
    finally:
        if system.webui_server:
            await system.webui_server.shutdown()
        emoji_manager.shutdown()
        await memory_automation_service.shutdown()
        await a_memorix_host_service.stop()
        await get_plugin_runtime_manager().bridge_event("on_stop")
        await get_plugin_runtime_manager().stop()
        await async_task_manager.stop_and_wait_all_tasks()
        await config_manager.stop_file_watcher()
        set_main_loop(None)


if __name__ == "__main__":
    asyncio.run(main())
