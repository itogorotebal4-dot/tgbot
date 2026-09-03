import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8727784231:AAHaewyGV6dTaX0hkLPu4AKNiXyROZ6yLs4"
ADMIN_ID = 8915050007
# =============================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ---- FSM-состояния ----
class OrderForm(StatesGroup):
    waiting_for_street = State()
    waiting_for_time = State()


# ---- Хранилище заказов ----
orders = {}


def admin_keyboard(order_id, with_cancel=True):
    buttons = []
    if with_cancel:
        buttons.append([InlineKeyboardButton(text="❌ Отменить заказ",
                                              callback_data=f"admin_cancel_{order_id}")])
    buttons.append([InlineKeyboardButton(text="📞 Связаться с клиентом",
                                         callback_data=f"admin_contact_{order_id}")])
    buttons.append([InlineKeyboardButton(text="🔒 Закрыть диалог",
                                         callback_data=f"admin_close_{order_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ================= /START =================
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Я хочу купить", callback_data="buy_start")],
        [InlineKeyboardButton(text="❓ Мне нужна помощь", callback_data="help_start")]
    ])
    await message.answer("Приветствую! Выберите действие:", reply_markup=kb)


# ================= ПОКУПКА =================
@dp.callback_query(F.data == "buy_start")
async def buy_handler(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚚 Доставка", callback_data="delivery_yes")],
        [InlineKeyboardButton(text="📍 В городе", callback_data="city_buy")]
    ])
    await callback.message.edit_text("Выберите вариант покупки:", reply_markup=kb)


# ---- Доставка ----
@dp.callback_query(F.data == "delivery_yes")
async def delivery_handler(callback: types.CallbackQuery):
    order_id = f"delivery_{callback.from_user.id}_{int(callback.message.date.timestamp())}"
    orders[order_id] = {
        "user_id": callback.from_user.id,
        "type": "Доставка",
        "city": "—",
        "street": "—",
        "time": "—",
    }

    await callback.message.edit_text("🚚 Подождите, с вами сейчас свяжется менеджер.")

    admin_text = (
        "🚚 Новый заказ на доставку!\n\n"
        f"👤 Пользователь: @{callback.from_user.username or '—'} "
        f"(ID: {callback.from_user.id})\n"
        f"📦 Тип: Доставка"
    )
    try:
        await bot.send_message(ADMIN_ID, admin_text,
                               reply_markup=admin_keyboard(order_id))
    except Exception as e:
        print(f"Ошибка отправки админу: {e}")


# ---- В городе: выбор города ----
@dp.callback_query(F.data == "city_buy")
async def city_choice_handler(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏙 Северодвинск", callback_data="city_severodvinsk")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="buy_start")]
    ])
    await callback.message.edit_text("Выберите город:", reply_markup=kb)


# ---- Северодвинск: спрашиваем улицу ----
@dp.callback_query(F.data == "city_severodvinsk")
async def severodvinsk_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(OrderForm.waiting_for_street)
    await state.update_data(city="Северодвинск", user_id=callback.from_user.id)
    await callback.message.edit_text(
        "Вы выбрали город Северодвинск.\nУкажите улицу:"
    )


# ---- Ловим улицу → спрашиваем время ----
@dp.message(OrderForm.waiting_for_street)
async def process_street(message: types.Message, state: FSMContext):
    await state.update_data(street=message.text)
    await state.set_state(OrderForm.waiting_for_time)
    await message.answer("Записал! Теперь укажите удобное время:")


# ---- Ловим время → отправляем админу ----
@dp.message(OrderForm.waiting_for_time)
async def process_time(message: types.Message, state: FSMContext):
    data = await state.get_data()
    street = data.get("street", "—")
    city = data.get("city", "—")
    user_id = data.get("user_id", message.from_user.id)

    order_id = f"order_{message.from_user.id}_{int(message.date.timestamp())}"
    orders[order_id] = {
        "user_id": user_id,
        "type": "В городе",
        "city": city,
        "street": street,
        "time": message.text,
    }

    await state.clear()

    admin_text = (
        "🆕 Новый заказ (в городе)!\n\n"
        f"👤 Пользователь: @{message.from_user.username or '—'} (ID: {user_id})\n"
        f"🏙 Город: {city}\n"
        f"📍 Улица: {street}\n"
        f"🕐 Время: {message.text}"
    )
    try:
        await bot.send_message(ADMIN_ID, admin_text,
                               reply_markup=admin_keyboard(order_id))
    except Exception as e:
        print(f"Ошибка отправки админу: {e}")

    await message.answer("✅ Ваш заказ принят! Ожидайте, менеджер скоро свяжется с вами.")


# ================= ПОМОЩЬ =================
@dp.callback_query(F.data == "help_start")
async def help_handler(callback: types.CallbackQuery):
    order_id = f"help_{callback.from_user.id}_{int(callback.message.date.timestamp())}"
    orders[order_id] = {
        "user_id": callback.from_user.id,
        "type": "Помощь",
        "city": "—",
        "street": "—",
        "time": "—",
    }

    await callback.message.edit_text("❓ Ожидайте ответа менеджера.")

    help_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Связаться с клиентом",
                              callback_data=f"admin_contact_{order_id}")],
        [InlineKeyboardButton(text="🔒 Закрыть диалог",
                              callback_data=f"admin_close_{order_id}")]
    ])

    try:
        await bot.send_message(
            ADMIN_ID,
            f"❓ Новый вопрос!\n"
            f"👤 Пользователь: @{callback.from_user.username or '—'} "
            f"(ID: {callback.from_user.id})",
            reply_markup=help_kb
        )
    except Exception as e:
        print(f"Ошибка уведомления админа: {e}")


# ================= КНОПКИ АДМИНА =================

# ---- Отменить заказ ----
@dp.callback_query(F.data.startswith("admin_cancel_"))
async def admin_cancel_handler(callback: types.CallbackQuery):
    order_id = callback.data.replace("admin_cancel_", "")
    order = orders.get(order_id)

    if not order:
        await callback.answer("Заказ не найден.")
        return

    user_id = order["user_id"]
    try:
        await bot.send_message(
            user_id,
            "❌ Ваш заказ отменён.\n"
            "Если у вас что-то не получается, нажмите «Мне нужна помощь» "
            "или /start."
        )
    except Exception as e:
        print(f"Ошибка отправки клиенту: {e}")

    orders.pop(order_id, None)
    await callback.message.edit_text(
        f"Заказ отменён. Уведомление отправлено клиенту (ID: {user_id})."
    )


# ---- Связаться с клиентом ----
@dp.callback_query(F.data.startswith("admin_contact_"))
async def admin_contact_handler(callback: types.CallbackQuery):
    order_id = callback.data.replace("admin_contact_", "")
    order = orders.get(order_id)

    if not order:
        await callback.answer("Заказ не найден.")
        return

    user_id = order["user_id"]
    try:
        await bot.send_message(
            user_id,
            "📞 С вами связался менеджер. Ожидайте сообщения."
        )
    except Exception as e:
        print(f"Ошибка отправки клиенту: {e}")

    # Диалог остаётся открытым — кнопки не исчезают
    await callback.answer("Уведомление отправлено клиенту.")


# ---- Закрыть диалог ----
@dp.callback_query(F.data.startswith("admin_close_"))
async def admin_close_handler(callback: types.CallbackQuery):
    order_id = callback.data.replace("admin_close_", "")
    order = orders.get(order_id)

    if not order:
        await callback.answer("Диалог не найден.")
        return

    user_id = order["user_id"]
    try:
        await bot.send_message(
            user_id,
            "🔒 Диалог закрыт.\n"
            "Если нужно что-то ещё, нажмите /start."
        )
    except Exception as e:
        print(f"Ошибка отправки клиенту: {e}")

    orders.pop(order_id, None)
    await callback.message.edit_text(f"Диалог закрыт. (ID: {user_id})")


# ================= ЗАПУСК =================
async def main():
    print("Бот запущен. Напиши /start в Телеграме.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
