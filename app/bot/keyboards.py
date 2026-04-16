from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

ADMIN_MENU_LABELS: tuple[str, ...] = (
    "系统总览",
    "客户列表",
    "我的服务",
    "帮助",
    "新增客户格式",
    "更新客户格式",
)

CUSTOMER_MENU_LABELS: tuple[str, ...] = (
    "我的服务",
    "帮助",
)


def build_main_menu(is_admin: bool) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    if is_admin:
        builder.row(
            KeyboardButton(text="系统总览"),
            KeyboardButton(text="客户列表"),
        )
        builder.row(
            KeyboardButton(text="我的服务"),
            KeyboardButton(text="帮助"),
        )
        builder.row(
            KeyboardButton(text="新增客户格式"),
            KeyboardButton(text="更新客户格式"),
        )
    else:
        builder.row(
            KeyboardButton(text="我的服务"),
            KeyboardButton(text="帮助"),
        )

    return builder.as_markup(resize_keyboard=True, input_field_placeholder="选择一个操作")


def build_admin_customer_actions(customer_keyword: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="查看", callback_data=f"admin:view:{customer_keyword}"),
        InlineKeyboardButton(text="编辑", callback_data=f"admin:edit:{customer_keyword}"),
        InlineKeyboardButton(text="删除", callback_data=f"admin:delete:{customer_keyword}"),
    )
    return builder.as_markup()


def build_admin_delete_confirm(customer_keyword: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="确认删除", callback_data=f"admin:delete_confirm:{customer_keyword}"),
        InlineKeyboardButton(text="取消", callback_data=f"admin:delete_cancel:{customer_keyword}"),
    )
    return builder.as_markup()


def build_post_delete_actions() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="查看客户列表", callback_data="menu:list"),
        InlineKeyboardButton(text="新增客户示例", callback_data="menu:add_help"),
    )
    return builder.as_markup()


def build_customer_service_actions() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="我要续费", callback_data="customer:renew"),
        InlineKeyboardButton(text="修改信息", callback_data="customer:update_info"),
    )
    return builder.as_markup()
