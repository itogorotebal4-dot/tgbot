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


# ---- FSM-состояния для формы заказа ----
class OrderForm(StatesGroup):
    waiting_for_city = State()
    waiting_for_street = State()
    waiting_for_time = State()


# ---- Хранилище заказов: order_id -> {user_id, city, street, time} ----
orders = {}


@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Я хочу купить", callback_data="buy_start")],
        [InlineKeyboardButton(text="❓ Мне нужна помощь", callback_data="help_start")]
    ])
    await message.answer("Приветствую! Выберите действие:", reply_markup=kb)


# ---- Кнопка «Я хочу купить» ----
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
    link = "https://www.avito.ru/user/933dea3a19580010f241e515abd5c204/profile?src=sharing"
    await callback.message.edit_text(f"Оформите на Авито: {link}")


# ---- Покупка в городе: предлагаем выбор города ----
@dp.callback_query(F.data == "city_buy")
async def city_choice_handler(callback: types.CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏙 Северодвинск", callback_data="city_severodvinsk")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="buy_start")]
    ])
    await callback.message.edit_text("Выберите город:", reply_markup=kb)


# ---- Клиент выбрал Северодвинск → спрашиваем улицу ----
@dp.callback_query(F.data == "city_severodvinsk")
async def severodvinsk_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(OrderForm.waiting_for_street)
    await state.update_data(city="Северодвинск", user_id=callback.from_user.id)
    await callback.message.edit_text(
        "Вы выбрали город Северодвинск.\n"
        "Укажите улицу:"
    )


# ---- Ловим ответ с улицей, спрашиваем время ----
@dp.message(OrderForm.waiting_for_street)
async def process_street(message: types.Message, state: FSMContext):
    await state.update_data(street=message.text)
    await state.set_state(OrderForm.waiting_for_time)
    await message.answer("Записал! Теперь укажите удобное время:")


# ---- Ловим ответ со временем → отправляем админу ----
@dp.message(OrderForm.waiting_for_time)
async def process_time(message: types.Message, state: FSMContext):
    data = await state.get_data()
    street = data.get("street", "—")
    city = data.get("city", "—")
    user_id = data.get("user_id", message.from_user.id)

    order_id = f"order_{message.from_user.id}_{int(message.date.timestamp())}"
    orders[order_id] = {
        "user_id": user_id,
        "city": city,
        "street": street,
        "time": message.text,
    }

    await state.clear()

    # Клавиатура для админа
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить заказ", callback_data=f"admin_cancel_{order_id}")],
        [InlineKeyboardButton(text="📞 Связаться с клиентом", callback_data=f"admin_contact_{order_id}")]
    ])

    admin_text = (
        "🆕 Новый заказ!\n\n"
        f"👤 Пользователь: @{message.from_user.username or '—'} (ID: {user_id})\n"
        f"🏙 Город: {city}\n"
        f"📍 Улица: {street}\n"
        f"🕐 Время: {message.text}"
    )

    try:
        await bot.send_message(ADMIN_ID, admin_text, reply_markup=admin_kb)
    except Exception as e:
        print(f"Ошибка отправки админу: {e}")

    await message.answer(
        "✅ Ваш заказ принят! Ожидайте, менеджер скоро свяжется с вами."
    )


# ---- Админ: Отменить заказ ----
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
            "Если у вас что-то не получается, обратитесь в раздел «Помощь»."
        )
    except Exception as e:
        print(f"Ошибка отправки клиенту: {e}")

    orders.pop(order_id, None)
    await callback.message.edit_text(
        f"Заказ отменён. Уведомление отправлено клиенту (ID: {user_id})."
    )


# ---- Админ: Связаться с клиентом ----
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

    orders.pop(order_id, None)
    await callback.message.edit_text(
        f"Уведомление отправлено клиенту (ID: {user_id}).\n"
        f"Напишите пользователю: @{callback.from_user.username or '—'}"
    )


# ---- Помощь ----
@dp.callback_query(F.data == "help_start")
async def help_handler(callback: types.CallbackQuery):
    await callback.message.edit_text("Ожидайте ответа менеджера.")
    try:
        await bot.send_message(
            ADMIN_ID,
            f"Новый вопрос! Пользователь: @{callback.from_user.username or '—'} "
            f"(ID: {callback.from_user.id})"
        )
    except Exception as e:
        print(f"Ошибка уведомления админа: {e}")


async def main():
    print("Бот запущен. Напиши /start в Телеграме.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
