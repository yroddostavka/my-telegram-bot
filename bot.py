import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 6473159440))
PAYMENT_PHONE = os.getenv("PAYMENT_PHONE", "+7XXXXXXXXXX")
# ===============================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ========== КАТАЛОГ ТОВАРОВ ==========
# Формат: id: (название, цена_с_комиссией)
PRODUCTS = {
    "cola_classic_05":   ("Cola Classic 0.5л", 42),
    "cola_classic_1":    ("Cola Classic 1л", 63),
    "cola_classic_15":   ("Cola Classic 1.5л", 94),
    "fresh_bar_05":      ("Fresh Bar 0.5л", 63),
    "fresh_bar_banana":  ("Fresh Bar Банан 0.5л", 63),
    "fresh_bar_limon":   ("Fresh Bar Лимон 0.5л", 63),
    "fresh_bar_vanilla": ("Fresh Bar Ваниль 0.5л", 63),
    "fresh_bar_lichi":   ("Fresh Bar Личи Пичи 0.5л", 63),
    "fresh_bar_citrus":  ("Fresh Bar Citrus Lime 0.5л", 63),
    "piko_lini":         ("ПикоЛини пачка", 52),
    "piko_libi":         ("ПикоЛиби 1 шт", 27),
    "mos_potato_chili":  ("Московский картофель Сладкий чили", 124),
}
# =====================================


class OrderForm(StatesGroup):
    waiting_name = State()
    waiting_phone = State()


carts = {}  # {user_id: {product_id: qty}}


def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Каталог", callback_data="catalog")],
        [InlineKeyboardButton(text="📦 Моя корзина", callback_data="cart")],
    ])


def catalog_menu():
    buttons = []
    for pid, (name, price) in PRODUCTS.items():
        buttons.append([
            InlineKeyboardButton(
                text=f"{name} — {price}₽",
                callback_data=f"add:{pid}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="📦 Корзина", callback_data="cart")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cart_text_and_kb(uid):
    """Возвращает текст корзины и клавиатуру с +/- для каждого товара"""
    cart = carts.get(uid, {})
    if not cart:
        return (
            "📦 Корзина пуста.\nДобавь товары из каталога.",
            InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🛒 В каталог", callback_data="catalog")],
            ])
        )

    text = "📦 <b>Твоя корзина:</b>\n\n"
    total = 0
    buttons = []
    for pid, qty in cart.items():
        name, price = PRODUCTS[pid]
        sub = price * qty
        total += sub
        text += f"• {name} — {price}₽ x{qty} = {sub}₽\n"
        buttons.append([
            InlineKeyboardButton(text="➖", callback_data=f"minus:{pid}"),
            InlineKeyboardButton(text=f"{name} x{qty}", callback_data="noop"),
            InlineKeyboardButton(text="➕", callback_data=f"plus:{pid}"),
        ])
    text += f"\n💰 <b>Итого: {total}₽</b>"

    buttons.append([InlineKeyboardButton(text="✅ Оформить заказ", callback_data="checkout")])
    buttons.append([InlineKeyboardButton(text="🗑 Очистить", callback_data="clear_cart")])
    buttons.append([InlineKeyboardButton(text="⬅️ В каталог", callback_data="catalog")])

    return text, InlineKeyboardMarkup(inline_keyboard=buttons)


# ========== /start ==========
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        f"Это бот заказа снеков и напитков.\n"
        f"Выбери товары, оформи заказ — я всё привезу.\n",
        reply_markup=main_menu()
    )


# ========== Каталог ==========
@dp.callback_query(F.data == "catalog")
async def show_catalog(call: CallbackQuery):
    await call.message.edit_text(
        "🛒 <b>Каталог</b>\n\nЖми на товар, чтобы добавить в корзину:",
        reply_markup=catalog_menu(),
        parse_mode="HTML"
    )
    await call.answer()


@dp.callback_query(F.data == "back")
async def back_to_main(call: CallbackQuery):
    await call.message.edit_text("Главное меню:", reply_markup=main_menu())
    await call.answer()


# ========== Добавление в корзину ==========
@dp.callback_query(F.data.startswith("add:"))
async def add_to_cart(call: CallbackQuery):
    pid = call.data.split(":")[1]
    uid = call.from_user.id
    carts.setdefault(uid, {})
    carts[uid][pid] = carts[uid].get(pid, 0) + 1
    name, price = PRODUCTS[pid]
    qty = carts[uid][pid]
    await call.answer(f"✅ {name} x{qty} в корзине")


# ========== Плюс / минус ==========
@dp.callback_query(F.data.startswith("plus:"))
async def plus_item(call: CallbackQuery):
    pid = call.data.split(":")[1]
    uid = call.from_user.id
    carts.setdefault(uid, {})
    carts[uid][pid] = carts[uid].get(pid, 0) + 1
    text, kb = cart_text_and_kb(uid)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@dp.callback_query(F.data.startswith("minus:"))
async def minus_item(call: CallbackQuery):
    pid = call.data.split(":")[1]
    uid = call.from_user.id
    if uid in carts and pid in carts[uid]:
        carts[uid][pid] -= 1
        if carts[uid][pid] <= 0:
            del carts[uid][pid]
    text, kb = cart_text_and_kb(uid)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@dp.callback_query(F.data == "noop")
async def noop(call: CallbackQuery):
    await call.answer()


# ========== Корзина ==========
@dp.callback_query(F.data == "cart")
async def show_cart(call: CallbackQuery):
    text, kb = cart_text_and_kb(call.from_user.id)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@dp.callback_query(F.data == "clear_cart")
async def clear_cart(call: CallbackQuery):
    carts[call.from_user.id] = {}
    text, kb = cart_text_and_kb(call.from_user.id)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer("🗑 Корзина очищена")


# ========== Оформление заказа ==========
@dp.callback_query(F.data == "checkout")
async def start_checkout(call: CallbackQuery, state: FSMContext):
    if not carts.get(call.from_user.id):
        await call.answer("Корзина пуста", show_alert=True)
        return
    await call.message.answer(
        "✍️ Напиши своё <b>имя</b> (как к тебе обращаться):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_order")]
        ]),
        parse_mode="HTML"
    )
    await state.set_state(OrderForm.waiting_name)
    await call.answer()


@dp.message(OrderForm.waiting_name)
async def get_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer(
        "📞 Теперь напиши свой <b>номер телефона</b> или ник в ТГ:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_order")]
        ]),
        parse_mode="HTML"
    )
    await state.set_state(OrderForm.waiting_phone)


@dp.message(OrderForm.waiting_phone)
async def get_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    data = await state.get_data()
    await state.clear()

    uid = message.from_user.id
    cart = carts.get(uid, {})
    if not cart:
        await message.answer("Корзина пуста 🤷")
        return

    lines = []
    total = 0
    for pid, qty in cart.items():
        name, price = PRODUCTS[pid]
        sub = price * qty
        total += sub
        lines.append(f"• {name} x{qty} = {sub}₽")
    composition = "\n".join(lines)

    order_text = (
        f"🆕 <b>НОВЫЙ ЗАКАЗ</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👤 {data['name']}\n"
        f"📞 {data['phone']}\n"
        f"🆔 @{message.from_user.username or '—'} (id: {uid})\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🛒 <b>Состав:</b>\n{composition}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 <b>Итого: {total}₽</b>"
    )

    await bot.send_message(ADMIN_ID, order_text, parse_mode="HTML")

    await message.answer(
        f"✅ Заказ оформлен!\n\n"
        f"💰 Сумма: <b>{total}₽</b>\n"
        f"📱 Переведи на номер: <code>{PAYMENT_PHONE}</code>\n"
        f"💬 В комментарии к переводу укажи своё имя.\n\n"
        f"После перевода я свяжусь с тобой.",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )
    carts[uid] = {}


# ========== Отмена оформления ==========
@dp.callback_query(F.data == "cancel_order")
async def cancel_order(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "❌ Оформление отменено. Корзина сохранена.",
        reply_markup=main_menu()
    )
    await call.answer()


# ========== /myid ==========
@dp.message(Command("myid"))
async def cmd_myid(message: Message):
    await message.answer(f"Твой ID: <code>{message.from_user.id}</code>", parse_mode="HTML")


# ========== Запуск ==========
async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

if __name__ == "__main__":
    asyncio.run(main())
