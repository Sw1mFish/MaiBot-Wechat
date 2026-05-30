"""WeChat Platform IO driver 单元测试（基于 wxauto）"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.common.data_models.message_component_data_model import (
    AtComponent,
    ImageComponent,
    MessageSequence,
    TextComponent,
)
from src.common.data_models.mai_message_data_model import (
    GroupInfo,
    MessageInfo,
    UserInfo,
)
from src.platform_io.drivers.base import PlatformIODriver
from src.platform_io.drivers.wechat_driver import WeChatPlatformDriver
from src.platform_io.manager import PlatformIOManager
from src.platform_io.types import (
    DeliveryReceipt,
    DeliveryStatus,
    DriverDescriptor,
    DriverKind,
    InboundMessageEnvelope,
    RouteBinding,
    RouteKey,
)


class FakeWxMessage:
    """模拟 wxauto 的消息对象。"""
    def __init__(self, msg_type="friend", sender="wx_user", content="hello", msg_id="123-456"):
        self.type = msg_type
        self.sender = sender
        self.content = content
        self.id = msg_id


class TestWeChatDriverDescriptor:

    def test_descriptor_fields(self):
        driver = WeChatPlatformDriver(driver_id="wx.driver", platform="wx", account_id="bot_name")
        desc = driver.descriptor
        assert desc.driver_id == "wx.driver"
        assert desc.platform == "wx"
        assert desc.kind == DriverKind.LEGACY
        assert desc.account_id == "bot_name"


class TestInboundConversion:

    @pytest.mark.asyncio
    async def test_private_text_message(self):
        driver = WeChatPlatformDriver(driver_id="wx.driver", platform="wx")
        msg = FakeWxMessage(sender="好友甲", content="你好")
        envelope = await driver._convert_to_envelope("好友甲", msg)
        assert envelope is not None
        assert envelope.driver_id == "wx.driver"
        assert envelope.route_key.platform == "wx"
        assert envelope.session_message is not None
        assert envelope.session_message.is_mentioned is True

    @pytest.mark.asyncio
    async def test_self_message_filtered(self):
        driver = WeChatPlatformDriver(driver_id="wx.driver", platform="wx")
        msg = FakeWxMessage(msg_type="self", sender="Self", content="no")
        envelope = await driver._convert_to_envelope("test", msg)
        assert envelope is None

    @pytest.mark.asyncio
    async def test_sys_message_filtered(self):
        driver = WeChatPlatformDriver(driver_id="wx.driver", platform="wx")
        msg = FakeWxMessage(msg_type="sys", sender="", content="sys")
        envelope = await driver._convert_to_envelope("test", msg)
        assert envelope is None

    @pytest.mark.asyncio
    async def test_time_message_filtered(self):
        driver = WeChatPlatformDriver(driver_id="wx.driver", platform="wx")
        msg = FakeWxMessage(msg_type="Time", sender="", content="12:00")
        envelope = await driver._convert_to_envelope("test", msg)
        assert envelope is None


class TestOutboundSend:

    def _make_msg(self, text="hello", group_id=None, components=None, add_cfg=None):
        from src.chat.message_receive.message import SessionMessage
        msg = SessionMessage(message_id="test_1", timestamp=datetime.now(), platform="wx")
        msg.message_info = MessageInfo(
            user_info=UserInfo(user_id="bot", user_nickname="Bot"),
            group_info=GroupInfo(group_id=group_id, group_name=group_id) if group_id else None,
            additional_config=add_cfg or {},
        )
        msg.raw_message = MessageSequence(components=components or [TextComponent(text=text)])
        msg.processed_plain_text = text
        msg.initialized = True
        return msg

    @pytest.mark.asyncio
    async def test_send_when_disconnected(self):
        driver = WeChatPlatformDriver(driver_id="wx.driver", platform="wx")
        msg = self._make_msg()
        receipt = await driver.send_message(msg, RouteKey(platform="wx"))
        assert receipt.status == DeliveryStatus.FAILED

    @pytest.mark.asyncio
    async def test_send_text_private(self):
        driver = WeChatPlatformDriver(driver_id="wx.driver", platform="wx")
        driver._wx = MagicMock()
        msg = self._make_msg(add_cfg={"platform_io_target_user_id": "好友甲"})
        receipt = await driver.send_message(msg, RouteKey(platform="wx"))
        assert receipt.status == DeliveryStatus.SENT
        driver._wx.SendMsg.assert_called_once()
        kwargs = driver._wx.SendMsg.call_args[1]
        assert kwargs.get("who") == "好友甲"

    @pytest.mark.asyncio
    async def test_send_to_group(self):
        driver = WeChatPlatformDriver(driver_id="wx.driver", platform="wx")
        driver._wx = MagicMock()
        msg = self._make_msg(text="大家好", group_id="测试群")
        receipt = await driver.send_message(msg, RouteKey(platform="wx"))
        assert receipt.status == DeliveryStatus.SENT
        driver._wx.SendMsg.assert_called_once()
        kwargs = driver._wx.SendMsg.call_args[1]
        assert kwargs.get("who") == "测试群"

    @pytest.mark.asyncio
    async def test_no_receiver_returns_failed(self):
        driver = WeChatPlatformDriver(driver_id="wx.driver", platform="wx")
        driver._wx = MagicMock()
        msg = self._make_msg(add_cfg={})
        receipt = await driver.send_message(msg, RouteKey(platform="wx"))
        assert receipt.status == DeliveryStatus.FAILED


class TestManagerIntegration:

    @pytest.mark.asyncio
    async def test_register_and_resolve(self):
        manager = PlatformIOManager()
        try:
            driver = WeChatPlatformDriver(driver_id="wx.driver", platform="wx", account_id="bot_name")
            await manager.add_driver(driver)
            manager.bind_send_route(RouteBinding(
                route_key=RouteKey(platform="wx"),
                driver_id=driver.driver_id,
                driver_kind=driver.descriptor.kind,
            ))
            manager.bind_receive_route(RouteBinding(
                route_key=RouteKey(platform="wx"),
                driver_id=driver.driver_id,
                driver_kind=driver.descriptor.kind,
            ))
            resolved = manager.resolve_drivers(RouteKey(platform="wx"))
            assert any(d.driver_id == "wx.driver" for d in resolved)
        finally:
            await manager.stop()
