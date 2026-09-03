import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8727784231:AAHaewyGV6dTaX0hkLPu4AKNiXyROZ6yLs4"
ADMIN_ID = 8915050007
REVIEW_LINK = "https://t.me/manager_ice_shop"
# =============================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ---- FSM-состояния ----
class OrderForm(StatesGroup):
    waiting_for_street = State()
    waiting_for_time = State()

class AdminReply(StatesGroup):
    replying = State()

class ClientActiveChat(StatesGroup):
    chatting = State()


# ---- Хранилища ----
orders = {}                # order_id -> {user_id, type, city, street, time, status}
user_active_order = {}     # user_id -> order_id


# ---- Клавиатуры ----
def admin_keyboard(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить заказ", callback_data=f"admin_cancel_{order_id}")],
        [InlineKeyboardButton(text="✅ Оплачен товар", callback_data=f"admin_paid_{order_id}")],
        [InlineKeyboardButton(text="📞 Связаться с клиентом", callback_data=f"admin_contact_{order_id}")],
        [InlineKeyboardButton(text="🔒 Закрыть диалог", callback_data=f"admin_close_{order_id}")],
    ])

def admin_reply_keyboard(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Ответить", callback_data=f"admin_reply_{order_id}")],
        [InlineKeyboardButton(text="🔒 Закрыть диалог", callback_data=f"admin_close_{order_id}")],
    ])

def client_keyboard(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить заказ", callback_data=f"client_cancel_{order_id}")],
        [InlineKeyboardButton(text="📞 Связаться с менеджером", callback_data=f"client_contact_{order_id}")],
    ])

def client_close_keyboard(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить заказ", callback_data=f"client_cancel_{order_id}")],
        [InlineKeyboardButton(text="🔒 Закрыть диалог", callback_data=f"client_close_{order_id}")],
    ])

def client_reply_keyboard(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Ответить", callback_data=f"client_reply_{order_id}")],
        [InlineKeyboardButton(text="🔒 Закрыть диалог", callback_data=f"client_close_{order_id}")],
    ])


# ================= /START =================
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Я хочу купить", callback_data="buy_start")],
        [InlineKeyboardButton(text="❓ Мне нужна помощь", callback_data="help_start")]
    ])
    await message.answer("Приветствую! Выберите действие:", reply_markup=kb)


# ================= ПОКУПКА (ДОСТАВКА) =================
@dp.callback_query(F.data == "buy_start")
async def buy_handler(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚚 Доставка", callback_data="delivery_yes")],
        [InlineKeyboardButton(text="📍 В городе", callback_data="city_buy")]
    ])
    await callback.message.edit_text("Выберите вариант покупки:", reply_markup=kb)

@dp.callback_query(F.data == "delivery_yes")
async def delivery_handler(callback: types.CallbackQuery):
    order_id = f"delivery_{callback.from_user.id}_{int(callback.message.date.timestamp())}"
    orders[order_id] = {
        "user_id": callback.from_user.id,
        "type": "Доставка",
        "city": "—", "street": "—", "time": "—",
        "status": "active",
    }
    user_active_order[callback.from_user.id] = order_id

    await callback.message.edit_text(
        "🚚 Подождите, с вами скоро свяжется менеджер.\n"
        "Нажмите «Связаться с менеджером», чтобы начать переписку.",
        reply_markup=client_keyboard(order_id),
    )

    admin_text = (
        "🚚 Новый заказ на доставку!\n\n"
        f"👤 Пользователь: @{callback.from_user.username or '—'} (ID: {callback.from_user.id})\n"
        f"📦 Тип: Доставка"
    )
    try:
        await bot.send_message(ADMIN_ID, admin_text, reply_markup=admin_keyboard(order_id))
    except Exception as e:
        print(f"Ошибка отправки админу: {e}")


# ================= ПОКУПКА (В ГОРОДЕ) =================
@dp.callback_query(F.data == "city_buy")
async def city_choice_handler(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏙 Северодвинск", callback_data="city_severodvinsk")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="buy_start")]
    ])
    await callback.message.edit_text("Выберите город:", reply_markup=kb)

@dp.callback_query(F.data == "city_severodvinsk")
async def severodvinsk_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(OrderForm.waiting_for_street)
    await state.update_data(city="Северодвинск", user_id=callback.from_user.id)
    await callback.message.edit_text("Вы выбрали город Северодвинск.\nУкажите улицу:")

@dp.message(OrderForm.waiting_for_street)
async def process_street(message: types.Message, state: FSMContext):
    await state.update_data(street=message.text)
    await state.set_state(OrderForm.waiting_for_time)
    await message.answer("Записал! Теперь укажите удобное время:")

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
        "city": city, "street": street, "time": message.text,
        "status": "active",
    }
    user_active_order[user_id] = order_id
    await state.clear()

    admin_text = (
        "🆕 Новый заказ (в городе)!\n\n"
        f"🏙 Город: {city}\n📍 Улица: {street}\n🕐 Время: {message.text}\n"
        f"👤 Пользователь: @{message.from_user.username or '—'} (ID: {user_id})"
    )
    try:
        await bot.send_message(ADMIN_ID, admin_text, reply_markup=admin_keyboard(order_id))
    except Exception as e:
        print(f"Ошибка отправки админу: {e}")

    await message.answer(
        "✅ Ваш заказ принят! Ожидайте, менеджер скоро свяжется с вами.\n"
        "Нажмите «Связаться с менеджером», чтобы начать переписку.",
        reply_markup=client_keyboard(order_id),
    )


# ================= ПОМОЩЬ =================
@dp.callback_query(F.data == "help_start")
async def help_handler(callback: types.CallbackQuery):
    order_id = f"help_{callback.from_user.id}_{int(callback.message.date.timestamp())}"
    orders[order_id] = {
        "user_id": callback.from_user.id,
        "type": "Помощь",
        "city": "—", "street": "—", "time": "—",
        "status": "active",
    }
    user_active_order[callback.from_user.id] = order_id

    await callback.message.edit_text(
        "❓ Ожидайте ответа менеджера.\n"
        "Нажмите «Связаться с менеджером», чтобы начать переписку.",
        reply_markup=client_keyboard(order_id),
    )

    help_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Связаться с клиентом", callback_data=f"admin_contact_{order_id}")],
        [InlineKeyboardButton(text="🔒 Закрыть диалог", callback_data=f"admin_close_{order_id}")],
    ])
    try:
        await bot.send_message(
            ADMIN_ID,
            f"❓ Новый вопрос!\n"
            f"👤 Пользователь: @{callback.from_user.username or '—'} (ID: {callback.from_user.id})",
            reply_markup=help_kb,
        )
    except Exception as e:
        print(f"Ошибка уведомления админа: {e}")


# ================= КНОПКИ КЛИЕНТА =================

@dp.callback_query(F.data.startswith("client_cancel_"))
async def client_cancel_handler(callback: types.CallbackQuery, state: FSMContext):
    order_id = callback.data.replace("client_cancel_", "")
    order = orders.get(order_id)
    if not order or order["status"] != "active":
        await callback.answer("Заказ уже не активен.")
        return
    user_id = order["user_id"]
    if user_id != callback.from_user.id:
        await callback.answer("Это не ваш заказ.")
        return
    orders.pop(order_id, None)
    if user_active_order.get(user_id) == order_id:
        del user_active_order[user_id]
    await state.clear()
    try:
        await bot.send_message(ADMIN_ID, f"❌ Клиент отменил заказ.\n👤 (ID: {user_id})")
    except Exception as e:
        print(f"Ошибка: {e}")
    await callback.message.edit_text("❌ Ваш заказ отменён.\nЕсли нужно что-то ещё, нажмите /start.")

# Клиент жмёт «Связаться с менеджером» → режим чата
@dp.callback_query(F.data.startswith("client_contact_"))
async def client_contact_handler(callback: types.CallbackQuery, state: FSMContext):
    order_id = callback.data.replace("client_contact_", "")
    order = orders.get(order_id)
    if not order or order["status"] != "active":
        await callback.answer("Диалог уже не активен.", show_alert=True)
        return
    user_id = order["user_id"]
    if user_id != callback.from_user.id:
        await callback.answer("Это не ваш диалог.", show_alert=True)
        return
    await state.set_state(ClientActiveChat.chatting)
    await state.update_data(order_id=order_id)
    await callback.message.edit_text(
        "📞 Чат с менеджером открыт!\n"
        "Пишите любое сообщение — оно сразу уйдёт менеджеру.\n"
        "Когда разговор завершён — нажмите «Закрыть диалог».\n"
        "Заказ при этом останется активным.",
        reply_markup=client_close_keyboard(order_id),
    )
    await callback.answer()

# Клиент жмёт «Ответить» на сообщении от менеджера → режим чата
@dp.callback_query(F.data.startswith("client_reply_"))
async def client_reply_handler(callback: types.CallbackQuery, state: FSMContext):
    order_id = callback.data.replace("client_reply_", "")
    order = orders.get(order_id)
    if not order or order["status"] != "active":
        await callback.answer("Диалог уже не активен.", show_alert=True)
        return
    user_id = order["user_id"]
    if user_id != callback.from_user.id:
        await callback.answer("Это не ваш диалог.", show_alert=True)
        return
    await state.set_state(ClientActiveChat.chatting)
    await state.update_data(order_id=order_id)
    await callback.message.answer(
        "💬 Режим ответа включён.\n"
        "Пишите сообщение — оно уйдёт менеджеру.\n"
        "Чтобы закончить — нажмите «Закрыть диалог» или напишите /cancel."
    )
    await callback.answer("Режим ответа включён.")

# Клиент закрывает диалог (заказ остаётся активным!)
@dp.callback_query(F.data.startswith("client_close_"))
async def client_close_handler(callback: types.CallbackQuery, state: FSMContext):
    order_id = callback.data.replace("client_close_", "")
    order = orders.get(order_id)
    if not order or order["status"] != "active":
        await callback.answer("Диалог уже не активен.")
        return
    user_id = order["user_id"]
    if user_id != callback.from_user.id:
        await callback.answer("Это не ваш диалог.")
        return

    # Только сбрасываем режим чата, заказ НЕ удаляем
    await state.clear()

    try:
        await bot.send_message(ADMIN_ID, f"🔒 Клиент закрыл диалог (заказ активен).\n👤 (ID: {user_id})")
    except Exception as e:
        print(f"Ошибка: {e}")

    await callback.message.edit_text(
        "🔒 Диалог закрыт, но заказ всё ещё активен.\n"
        "Нажмите «Связаться с менеджером», чтобы снова начать переписку.\n"
        "Или отмените заказ кнопкой ниже.",
        reply_markup=client_keyboard(order_id),
    )


# ================= КНОПКИ АДМИНА =================

@dp.callback_query(F.data.startswith("admin_cancel_"))
async def admin_cancel_handler(callback: types.CallbackQuery, state: FSMContext):
    order_id = callback.data.replace("admin_cancel_", "")
    order = orders.get(order_id)
    if not order:
        await callback.answer("Заказ не найден.")
        return
    user_id = order["user_id"]
    orders.pop(order_id, None)
    if user_active_order.get(user_id) == order_id:
        del user_active_order[user_id]
    await state.clear()
    try:
        await bot.send_message(user_id, "❌ Ваш заказ отменён.\nНажмите /start для нового.")
    except Exception as e:
        print(f"Ошибка: {e}")
    await callback.message.edit_text(f"Заказ отменён. (ID клиента: {user_id})")

@dp.callback_query(F.data.startswith("admin_paid_"))
async def admin_paid_handler(callback: types.CallbackQuery):
    order_id = callback.data.replace("admin_paid_", "")
    order = orders.get(order_id)
    if not order:
        await callback.answer("Заказ не найден.")
        return
    user_id = order["user_id"]
    review_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Оставить отзыв", url=REVIEW_LINK)]
    ])
    try:
        await bot.send_message(
            user_id,
            "✅ Ваш товар оплачен! Спасибо за покупку 🙏\n\n"
            "Будем благодарны за отзыв о нашем магазине.",
            reply_markup=review_kb,
        )
    except Exception as e:
        print(f"Ошибка: {e}")
    await callback.answer("Клиенту отправлено сообщение об оплате.")

# Админ жмёт «Связаться с клиентом» → режим ответа
@dp.callback_query(F.data.startswith("admin_contact_"))
async def admin_contact_handler(callback: types.CallbackQuery, state: FSMContext):
    order_id = callback.data.replace("admin_contact_", "")
    order = orders.get(order_id)
    if not order or order["status"] != "active":
        await callback.answer("Диалог уже не активен.", show_alert=True)
        return
    await state.set_state(AdminReply.replying)
    await state.update_data(order_id=order_id)
    await callback.message.answer(
        f"📞 Чат с клиентом (ID: {order['user_id']}) открыт!\n"
        "Пишите любое сообщение — оно сразу уйдёт клиенту.\n"
        "Когда разговор завершён — нажмите «Закрыть диалог».\n"
        "Заказ при этом останется активным."
    )
    await callback.answer("Режим чата с клиентом включён.")

# Админ жмёт «Ответить» на сообщении от клиента → режим ответа
@dp.callback_query(F.data.startswith("admin_reply_"))
async def admin_reply_handler(callback: types.CallbackQuery, state: FSMContext):
    order_id = callback.data.replace("admin_reply_", "")
    order = orders.get(order_id)
    if not order or order["status"] != "active":
        await callback.answer("Диалог уже закрыт.", show_alert=True)
        return
    await state.set_state(AdminReply.replying)
    await state.update_data(order_id=order_id)
    await callback.message.answer(
        f"💬 Режим ответа включён (ID клиента: {order['user_id']}).\n"
        "Пишите сообщение — оно уйдёт клиенту.\n"
        "Чтобы закончить — нажмите «Закрыть диалог» или напишите /cancel."
    )
    await callback.answer("Режим ответа включён.")

# Админ закрывает диалог (заказ остаётся активным!)
@dp.callback_query(F.data.startswith("admin_close_"))
async def admin_close_handler(callback: types.CallbackQuery, state: FSMContext):
    order_id = callback.data.replace("admin_close_", "")
    order = orders.get(order_id)
    if not order:
        await callback.answer("Диалог не найден.")
        return
    user_id = order["user_id"]

    # Только сбрасываем режим чата, заказ НЕ удаляем
    await state.clear()

    try:
        await bot.send_message(
            user_id,
            "🔒 Менеджер закрыл диалог, но ваш заказ ещё активен.\n"
            "Нажмите «Связаться с менеджером», чтобы снова начать переписку.\n"
            "Или отмените заказ кнопкой ниже.",
            reply_markup=client_keyboard(order_id),
        )
    except Exception as e:
        print(f"Ошибка: {e}")

    await callback.message.edit_text(
        f"Диалог закрыт (заказ активен). (ID клиента: {user_id})",
        reply_markup=admin_keyboard(order_id),
    )


# ================= ПЕРЕСЫЛКА СООБЩЕНИЙ =================

# Админ пишет в режиме ответа → летит клиенту с кнопкой «Ответить»
@dp.message(AdminReply.replying, F.from_user.id == ADMIN_ID)
async def admin_send_to_client(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith("/"):
        if message.text == "/cancel":
            await state.clear()
            await message.answer("Режим ответа выключен.")
            return
        return

    data = await state.get_data()
    order_id = data.get("order_id")
    order = orders.get(order_id)
    if not order or order["status"] != "active":
        await state.clear()
        await message.answer("Диалог уже закрыт.")
        return

    client_user_id = order["user_id"]
    text = message.text or "(пустое сообщение)"

    try:
        await bot.send_message(
            client_user_id,
            f"💬 Сообщение от менеджера:\n\n{text}\n\n"
            "Если разговор завершён — нажмите «Закрыть диалог».",
            reply_markup=client_reply_keyboard(order_id),
        )
    except Exception as e:
        await message.answer(f"Не удалось отправить: {e}")


# Клиент пишет в режиме чата → летит админу с кнопкой «Ответить»
@dp.message(ClientActiveChat.chatting, F.chat.type == "private")
async def client_chat_to_admin(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith("/"):
        if message.text == "/cancel":
            await state.clear()
            await message.answer("Режим ответа выключен.")
            return
        return

    data = await state.get_data()
    order_id = data.get("order_id")
    order = orders.get(order_id)
    if not order or order["status"] != "active":
        await state.clear()
        await message.answer("Диалог закрыт. Нажмите /start.")
        return

    user_id = order["user_id"]
    text = message.text or "(пустое сообщение)"

    admin_msg = (
        "📩 Сообщение от клиента:\n\n"
        f"👤 Пользователь: @{message.from_user.username or '—'} (ID: {user_id})\n\n"
        f"{text}"
    )

    try:
        await bot.send_message(ADMIN_ID, admin_msg, reply_markup=admin_reply_keyboard(order_id))
    except Exception as e:
        await message.answer(f"Не удалось отправить: {e}")


# Если клиент НЕ в режиме чата, но есть активный заказ — тоже пересылаем
@dp.message(F.chat.type == "private", ~F.from_user.id == ADMIN_ID)
async def client_auto_forward(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith("/"):
        return
    current_state = await state.get_state()
    if current_state in [OrderForm.waiting_for_street, OrderForm.waiting_for_time]:
        return

    user_id = message.from_user.id
    order_id = user_active_order.get(user_id)
    if not order_id:
        return

    order = orders.get(order_id)
    if not order or order["status"] != "active":
        if user_active_order.get(user_id) == order_id:
            del user_active_order[user_id]
        return

    # Автоматически включаем режим чата
    await state.set_state(ClientActiveChat.chatting)
    await state.update_data(order_id=order_id)

    text = message.text or "(пустое сообщение)"
    admin_msg = (
        "📩 Сообщение от клиента:\n\n"
        f"👤 Пользователь: @{message.from_user.username or '—'} (ID: {user_id})\n\n"
        f"{text}"
    )

    try:
        await bot.send_message(ADMIN_ID, admin_msg, reply_markup=admin_reply_keyboard(order_id))
    except Exception as e:
        await message.answer(f"Не удалось отправить: {e}")


# ================= ЗАПУСК =================
async def main():
    print("Бот запущен. Напиши /start в Телеграме.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
