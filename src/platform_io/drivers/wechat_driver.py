"""提供基于 wxauto (UIAutomation) 的 Platform IO 驱动实现。

wxauto 使用微软的 UI Automation 框架与微信客户端交互，不涉及 DLL 注入或
逆向工程，相对 WeChatFerry 更安全。但相应地，它基于界面元素定位，
因此使用聊天显示名称而非稳定 wxid 作为标识。
"""

import asyncio
import os
import re
import tempfile
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

from src.common.logger import get_logger
from src.platform_io.drivers.base import PlatformIODriver
from src.platform_io.types import (
    DeliveryReceipt,
    DeliveryStatus,
    DriverDescriptor,
    DriverKind,
    InboundMessageEnvelope,
    RouteKey,
)

if TYPE_CHECKING:
    from src.chat.message_receive.message import SessionMessage

logger = get_logger("wechat_driver")


def _wx_sync(method, *args, **kwargs):
    """在调用 wxauto 方法前确保 COM 已初始化。"""
    import ctypes
    try:
        ctypes.windll.ole32.CoInitialize(None)
    except Exception:
        pass
    return method(*args, **kwargs)


def _get_wx_listen_messages(wx):
    """获取 wxauto 监听消息，返回 {聊天名(str): [消息]}。

    GetListenMessage 的 key 是窗口对象而非字符串名，
    此函数将 key 转换为字符串名。
    """
    msgs = {}
    if not hasattr(wx, 'listen'):
        return msgs
    for name in list(wx.listen.keys()):
        try:
            chat = wx.listen[name]
            new_msgs = chat.GetNewMessage(savepic=True, savefile=False, savevoice=False)
            if new_msgs:
                msgs[str(name)] = new_msgs
        except Exception:
            pass
    return msgs

class WeChatPlatformDriver(PlatformIODriver):
    """面向 WeChat 的 Platform IO 驱动。

    通过 wxauto (UIAutomation) 与本地运行的微信桌面客户端交互。
    同时支持群聊和私聊消息的收发。

    注意：wxauto 使用聊天显示名称而非 wxid 作为用户标识，
    因此用户修改昵称后可能导致会话连续性中断。
    """

    def __init__(
        self,
        driver_id: str,
        platform: str,
        account_id: Optional[str] = None,
        scope: Optional[str] = None,
        poll_interval: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """初始化 WeChat 驱动。

        Args:
            driver_id: Broker 内的唯一驱动 ID。
            platform: 平台名称（通常为 ``"wx"``）。
            account_id: 可选的机器人账号显示名称。
            scope: 可选的额外路由作用域。
            poll_interval: 消息轮询间隔（秒）。wxauto 基于 UI 轮询，
                建议 1-3 秒。
            metadata: 可选的额外驱动元数据。
        """
        descriptor = DriverDescriptor(
            driver_id=driver_id,
            kind=DriverKind.LEGACY,
            platform=platform,
            account_id=account_id,
            scope=scope,
            metadata=metadata or {},
        )
        super().__init__(descriptor)
        self._poll_interval = poll_interval

        # wxauto WeChat 客户端实例
        self._wx: Any = None
        self._running = False
        self._poll_task: Optional[asyncio.Task] = None

        # 已知会话集合（用于发现新会话）
        self._known_sessions: Set[str] = set()

        # 群聊缓存 {chat_name: True/False}

    async def start(self) -> None:
        """初始化 wxauto 并开始轮询消息。"""
        await super().start()

        try:
            from wxauto import WeChat as WxClient
        except ImportError:
            logger.error("未安装 wxauto 包，无法启动 WeChat 驱动。请执行: pip install wxauto")
            raise

        logger.info("WeChat 驱动正在初始化 wxauto...")

        # wxauto 初始化会校验微信窗口是否存在
        loop = asyncio.get_running_loop()
        self._wx = await loop.run_in_executor(None, lambda: _wx_sync(WxClient))

        # 初始扫描已有会话
        sessions = await loop.run_in_executor(None, lambda: _wx_sync(self._wx.GetSessionList))
        for name in sessions:
            name_str = str(name).strip()
            if name_str:
                self._known_sessions.add(name_str)
                try:
                    _wx_sync(self._wx.AddListenChat, name_str, savepic=True)
                except Exception:
                    pass

        self._running = True
        self._poll_task = asyncio.create_task(self._poll_messages())
        logger.info(
            f"WeChat 驱动已启动: driver_id={self.driver_id}, "
            f"已知会话数={len(self._known_sessions)}"
        )

    async def stop(self) -> None:
        """停止轮询与微信的连接。"""
        self._running = False
        if self._poll_task is not None:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None
        self._wx = None
        logger.info(f"WeChat 驱动已停止: driver_id={self.driver_id}")
        await super().stop()

    async def send_message(
        self,
        message: "SessionMessage",
        route_key: RouteKey,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DeliveryReceipt:
        """通过 wxauto 发送一条消息。

        Args:
            message: 要投递的内部会话消息。
            route_key: Broker 为本次投递选中的路由键。
            metadata: 本次出站投递可选的 Broker 侧元数据。

        Returns:
            DeliveryReceipt: 规范化后的投递回执。
        """
        if self._wx is None:
            return DeliveryReceipt(
                internal_message_id=message.message_id,
                route_key=route_key,
                status=DeliveryStatus.FAILED,
                driver_id=self.driver_id,
                driver_kind=self.descriptor.kind,
                error="wxauto 未初始化",
            )

        # 确定接收者：优先使用 additional_config 中的目标信息
        merged_metadata: Dict[str, Any] = {}
        if metadata:
            merged_metadata.update(metadata)
        additional_config = getattr(message.message_info, "additional_config", {}) or {}
        if isinstance(additional_config, dict):
            for k, v in additional_config.items():
                if k not in merged_metadata:
                    merged_metadata[k] = v

        receiver: Optional[str] = None

        # 群聊：优先从 group_info 获取群名称
        if message.message_info.group_info:
            group_name = str(message.message_info.group_info.group_name or "").strip()
            if group_name:
                receiver = group_name

        # 私聊：从 target_user_id 或 account_id 获取
        if not receiver:
            receiver = str(merged_metadata.get("platform_io_target_user_id", "") or "").strip()
        if not receiver:
            receiver = str(route_key.account_id or "").strip()
        if not receiver:
            receiver = str(route_key.scope or "").strip()

        if not receiver:
            return DeliveryReceipt(
                internal_message_id=message.message_id,
                route_key=route_key,
                status=DeliveryStatus.FAILED,
                driver_id=self.driver_id,
                driver_kind=self.descriptor.kind,
                error="无法确定消息接收者（wxauto 使用聊天名称标识，请确保名称正确）",
            )

        try:
            loop = asyncio.get_running_loop()
            components = list(message.raw_message.components) if message.raw_message else []

            text_parts: List[str] = []
            at_list: List[str] = []

            for component in components:
                ctype = type(component).__name__

                if ctype == "TextComponent":
                    text = getattr(component, "text", "") or ""
                    if text:
                        text_parts.append(text)

                elif ctype == "AtComponent":
                    target = getattr(component, "target_user_id", "") or ""
                    if target:
                        at_list.append(target)
                        text_parts.append(f" @{target} ")

                elif ctype == "ImageComponent":
                    # 图片：先发送已累积文本，再发送图片
                    if text_parts or at_list:
                        full_text = "".join(text_parts)
                        await loop.run_in_executor(
                            None,
                            lambda: _wx_sync(self._wx.SendMsg, full_text, who=receiver, at=at_list if at_list else None),
                        )
                        text_parts.clear()
                        at_list.clear()

                    # 图片保存到临时文件后发送
                    image_data = getattr(component, "binary_data", None) or getattr(
                        component, "binary_hash", None
                    )
                    if image_data:
                        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
                        try:
                            data = image_data if isinstance(image_data, bytes) else image_data.encode()
                            tmp.write(data)
                            tmp.close()
                            await loop.run_in_executor(
                                None,
                                lambda: _wx_sync(self._wx.SendFiles, tmp.name, who=receiver),
                            )
                        finally:
                            os.unlink(tmp.name)

                elif ctype == "EmojiComponent":
                    # 加载表情二进制数据并发送为图片
                    try:
                        if hasattr(component, "load_emoji_binary"):
                            await component.load_emoji_binary()
                        emoji_data = getattr(component, "binary_data", None)
                        if emoji_data and isinstance(emoji_data, bytes):
                            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                            try:
                                tmp.write(emoji_data)
                                tmp.close()
                                await loop.run_in_executor(
                                    None,
                                    lambda: _wx_sync(self._wx.SendFiles, tmp.name, who=receiver),
                                )
                            finally:
                                os.unlink(tmp.name)
                        else:
                            text_parts.append("[表情]")
                    except Exception:
                        text_parts.append("[表情]")

                elif ctype == "ReplyComponent":
                    reply_text = getattr(component, "text", "") or ""
                    if reply_text:
                        text_parts.append(f"引用: {reply_text}")

                elif ctype == "ForwardNodeComponent":
                    text_parts.append("[转发消息]")

            # 发送剩余文本
            if text_parts or at_list:
                full_text = "".join(text_parts)
                await loop.run_in_executor(
                    None,
                    lambda: _wx_sync(self._wx.SendMsg,
                        full_text,
                        who=receiver,
                        at=at_list if at_list else None,
                    ),
                )

        except Exception as exc:
            logger.error(f"wxauto 发送消息失败: {exc}")
            return DeliveryReceipt(
                internal_message_id=message.message_id,
                route_key=route_key,
                status=DeliveryStatus.FAILED,
                driver_id=self.driver_id,
                driver_kind=self.descriptor.kind,
                error=str(exc),
            )

        return DeliveryReceipt(
            internal_message_id=message.message_id,
            route_key=route_key,
            status=DeliveryStatus.SENT,
            driver_id=self.driver_id,
            driver_kind=self.descriptor.kind,
        )

    # ------------------------------------------------------------------
    # 内部方法：入站消息轮询与转换
    # ------------------------------------------------------------------

    async def _poll_messages(self) -> None:
        """轮询 wxauto 消息并作为入站事件发送。"""
        loop = asyncio.get_running_loop()

        while self._running:
            try:
                # 1. 发现新会话并添加到监听列表
                sessions = await loop.run_in_executor(None, lambda: _wx_sync(self._wx.GetSessionList))
                if sessions:
                    for name in sessions:
                        name_str = str(name).strip()
                        if name_str and name_str not in self._known_sessions:
                            self._known_sessions.add(name_str)
                            try:
                                await loop.run_in_executor(
                                    None,
                                    lambda n=name_str: _wx_sync(self._wx.AddListenChat, n, savepic=True),
                                )
                                logger.debug(f"WeChat 添加新监听会话: {name_str}")
                            except Exception:
                                pass

                # 2. 获取监听列表中的新消息
                # GetListenMessage 返回 {window对象: [消息]}，需要自己提取字符串名
                msgs = await loop.run_in_executor(
                    None,
                    lambda: _get_wx_listen_messages(self._wx),
                )

                if msgs and isinstance(msgs, dict):
                    for chat_name, messages in msgs.items():
                        if not chat_name or not messages or not isinstance(messages, list):
                            continue
                        for msg in messages:
                            envelope = await self._convert_to_envelope(chat_name, msg)
                            if envelope is not None:
                                await self.emit_inbound(envelope)

                await asyncio.sleep(self._poll_interval)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"wxauto 消息轮询错误: {exc}")
                await asyncio.sleep(self._poll_interval)

    async def _convert_to_envelope(
        self, chat_name: str, msg: Any
    ) -> Optional[InboundMessageEnvelope]:
        """将 wxauto 消息对象转换为 ``InboundMessageEnvelope``。

        Args:
            chat_name: 消息来源的聊天名称（联系人或群名）。
            msg: wxauto 的 ``FriendMessage`` 或其他消息类型对象。

        Returns:
            Optional[InboundMessageEnvelope]: 转换后的入站封装；
                如果消息应被过滤返回 ``None``。
        """
        # --- 消息类型过滤 ---
        msg_type = getattr(msg, "type", None)
        if msg_type in ("sys", "Time", "Recall", "SYS", "Time", "self", "Self"):
            return None
        if msg_type not in ("friend", "message") and msg_type is not None:
            return None

        # --- 字段提取 ---
        sender = str(getattr(msg, "sender", "") or "").strip()
        content = str(getattr(msg, "content", "") or "")
        msg_id = str(getattr(msg, "id", "") or "")
        if not sender and not content:
            return None

        # 自身消息不收发
        if sender == "Self":
            return None

        # --- 判断群聊 vs 私聊 ---
        is_group = (sender != chat_name and sender != "Self")

        # --- 构建消息组件 ---
        from src.common.data_models.message_component_data_model import (
            TextComponent,
            MessageSequence,
        )

        from src.common.data_models.mai_message_data_model import (
            GroupInfo,
            MessageInfo,
            UserInfo,
        )
        from src.chat.message_receive.message import SessionMessage

        components = []

        # 检测 wxauto 中的图片/文件类型
        # 当 savepic=True 时，图片消息的 content 是文件路径
        if os.path.isfile(content):
            try:
                with open(content, "rb") as f:
                    img_data = f.read()
                desc = await self._describe_image(img_data)
                try:
                    from src.emoji_system.emoji_manager import emoji_manager as emoji_mgr
                    await emoji_mgr.ensure_emoji_saved(img_data)
                except Exception:
                    pass
                if desc:
                    components.append(TextComponent(text=f"[图片：{desc}]"))
                else:
                    from src.common.data_models.message_component_data_model import ImageComponent
                    components.append(ImageComponent(binary_data=img_data))
            except Exception:
                components.append(TextComponent(text="[图片]"))
        elif content.startswith("[图片]") or content.startswith("[Picture]"):
            components.append(TextComponent(text="[图片]"))
        elif content.startswith("[文件]") or content.startswith("[File]"):
            components.append(TextComponent(text="[文件]"))
        elif content.startswith("[语音]") or content.startswith("[Voice]"):
            components.append(TextComponent(text="[语音]"))
        elif content.startswith("[动画") or content.startswith("[表情") or "[Animation]" in content:
            components.append(TextComponent(text="[动画表情]"))
        else:
            components.append(TextComponent(text=content))

        # --- 构建 SessionMessage ---
        user_id: str
        user_nickname: str

        if is_group:
            # 群聊：sender 是群成员名，chat_name 是群名
            user_id = sender if sender else chat_name
            user_nickname = sender if sender else chat_name
            display_name = sender if sender else chat_name
            group_id = chat_name
            group_name = chat_name
        else:
            # 私聊：sender 和 chat_name 都是联系人名
            user_id = sender if sender else chat_name
            user_nickname = sender if sender else chat_name
            display_name = sender if sender else chat_name
            group_id = None
            group_name = None

        user_info = UserInfo(
            user_id=user_id,
            user_nickname=user_nickname,
            user_cardname=display_name,
        )

        group_info = None
        additional_config: Dict[str, Any] = {}

        if is_group and group_id:
            group_info = GroupInfo(group_id=group_id, group_name=group_name or group_id)
            additional_config["platform_io_target_group_id"] = group_id
        else:
            additional_config["platform_io_target_user_id"] = user_id

        session_message = SessionMessage(
            message_id=f"wx_{chat_name}_{msg_id}",
            timestamp=datetime.now(),
            platform="wx",
        )
        session_message.message_info = MessageInfo(
            user_info=user_info,
            group_info=group_info,
            additional_config=additional_config,
        )
        session_message.raw_message = MessageSequence(components=components)
        session_message.initialized = True

        # @提及检测
        if is_group:
            bot_name = str(self.descriptor.account_id or "").strip()
            session_message.is_mentioned = bool(bot_name and bot_name in content)
            session_message.is_at = session_message.is_mentioned
        else:
            session_message.is_mentioned = True
            session_message.is_at = True

        return InboundMessageEnvelope(
            route_key=RouteKey(platform="wx"),
            driver_id=self.driver_id,
            driver_kind=self.descriptor.kind,
            external_message_id=f"wx_{chat_name}_{msg_id}",
            session_message=session_message,
        )

    # ------------------------------------------------------------------
    async def _describe_image(self, image_bytes: bytes) -> str:
        logger.info(f"正在调用 VLM 描述图片，大小={len(image_bytes)}字节")
        """同步获取图片描述（VLM）。"""
        try:
            from src.chat.image_system.image_manager import image_manager
            return await image_manager.get_image_description(
                image_bytes=image_bytes, wait_for_build=True
            )
        except Exception as exc:
            logger.error(f"VLM 图片描述失败: {exc}", exc_info=True)
            return ""

    def refresh_known_sessions(self) -> None:
        """刷新已知会话列表。可在外部调用以强制更新。"""
        if self._wx is None:
            return
        try:
            sessions = self._wx.GetSessionList()
            for name in sessions:
                name_str = str(name).strip()
                if name_str and name_str not in self._known_sessions:
                    self._known_sessions.add(name_str)
                    try:
                        _wx_sync(self._wx.AddListenChat, name_str, savepic=True)
                    except Exception:
                        pass
        except Exception:
            pass
