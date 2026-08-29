import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8727784231:AAHaewyGV6dTaX0hkLPu4AKNiXyROZ6yLs4"       # <-- Вставь токен
ADMIN_ID = 8915050007                # <-- Вставь свой цифровой ID (от @userinfobot)
# ===========================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Хранилище активных диалогов: { client_id: admin_id }
# Это значит: клиент с ID X сейчас общается с админом Y
active_chats = {} 

# --- Клавиатуры ---

def get_start_keyboard():
    buttons = [
        [InlineKeyboardButton(text="🛒 Я хочу купить", callback_data="buy_start")],
        [InlineKeyboardButton(text="❓ Мне нужна помощь", callback_data="help_start")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_buy_keyboard():
    buttons = [
        [InlineKeyboardButton(text="📍 Купить в Северодвинске", callback_data="city_buy")],
        [InlineKeyboardButton(text="🚚 Купить на Авито", callback_data="avito_buy")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_control_keyboard(client_id):
    """Клавиатура для админа с кнопкой завершения"""
    buttons = [
        [InlineKeyboardButton(text="✅ Завершить диалог", callback_data=f"end_chat_{client_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- Обработчики команд и нажатий ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    text = "Приветствую! Выберите вариант ниже:"
    await message.answer(text=text, reply_markup=get_start_keyboard())

@dp.callback_query(lambda c: c.data == "buy_start")
async def process_buy(callback_query: types.CallbackQuery):
    await callback_query.message.answer("Варианты покупки:", reply_markup=get_buy_keyboard())
    await callback_query.message.delete()

@dp.callback_query(lambda c: c.data == "avito_buy")
async def process_avito(callback_query: types.CallbackQuery):
    link = "https://www.avito.ru/user/68751186e6db0b6b413ef5f1eefc29c1/profile?src=sharing"
    await callback_query.message.edit_text(f"Оформите заказ здесь: {link}")

@dp.callback_query(lambda c: c.data == "city_buy")
async def process_city_buy(callback_query: types.CallbackQuery):
    user = callback_query.from_user
    client_id = user.id
    username = user.username or "без юзернейма"
    
    # 1. Записываем, что этот клиент теперь в чате с админом
    active_chats[client_id] = ADMIN_ID
    
    # 2. Уведомляем админа
    admin_msg = (
        f"⚠️ <b>НОВЫЙ ЗАКАЗ!</b>\n\n"
        f"Пользователь: @{username} (ID: {client_id})\n"
        f"Хочет купить в Северодвинске.\n\n"
        f"Теперь вы можете переписываться: все ваши сообщения будут уходить ему."
    )
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode="HTML", reply_markup=get_admin_control_keyboard(client_id))
        await callback_query.message.edit_text("Спасибо! Менеджер скоро свяжется с вами.")
    except Exception as e:
        print(f"Ошибка отправки админу: {e}")
        await callback_query.answer("Произошла ошибка, попробуйте позже.")

@dp.callback_query(lambda c: c.data == "help_start")
async def process_help(callback_query: types.CallbackQuery):
    await callback_query.message.edit_text("Напишите ваш вопрос текстом ниже, я передам его менеджеру.")
    # Здесь мы НЕ создаем чат сразу. Чат начнется, когда клиент напишет текст.

@dp.callback_query(lambda c: c.data.startswith("end_chat_"))
async def end_chat(callback_query: types.CallbackQuery):
    # ИСПРАВЛЕНИЕ: используем callback_query вместо несуществующего c
    client_id = int(callback_query.data.split("_")[2])
    
    if client_id in active_chats:
        del active_chats[client_id]
        await callback_query.message.edit_text("✅ Диалог завершен. Клиент больше не будет получать сообщения от админа.")
    else:
        await callback_query.answer("Этот диалог уже был закрыт.")

    
    if client_id in active_chats:
        del active_chats[client_id]
        await callback_query.message.edit_text("✅ Диалог завершен. Клиент больше не будет получать сообщения от админа.")
    else:
        await callback_query.answer("Этот диалог уже был закрыт.")

# --- ЛОГИКА ПЕРЕПИСКИ (ГЛАВНОЕ) ---

@dp.message()
async def handle_text(message: types.Message):
    user_id = message.from_user.id
    text_content = message.text
    
    # Если пишет АДМИН
    if user_id == ADMIN_ID:
        # Ищем, есть ли у админа активный чат с каким-то клиентом.
        # В нашей схеме active_chats хранит {client: admin}. 
        # Нам нужно найти клиента, у которого admin == ADMIN_ID.
        client_to_answer = None
        for client, admin in active_chats.items():
            if admin == ADMIN_ID:
                client_to_answer = client
                break
        
        if client_to_answer:
            try:
                # Отправляем сообщение клиента этому клиенту
                await bot.copy_message(
                    chat_id=client_to_answer, 
                    from_chat_id=user_id, 
                    message_id=message.message_id
                )
                # Если copy_message не сработает (редкие случаи), можно использовать send_message для текста
                # await bot.send_message(client_to_answer, text=text_content)
            except Exception as e:
                await message.answer(f"❌ Не удалось отправить сообщение. Возможно, клиент заблокировал бота.\nОшибка: {e}")
            return
        else:
            # Если админ пишет, но нет активного чата
            await message.answer("Сейчас нет активных диалогов. Сначала кто-то должен запросить помощь или заказ.")
        return

    # Если пишет КЛИЕНТ
    # Проверяем, находится ли этот клиент в активном чате
    if user_id in active_chats:
        # Клиент уже в чате, просто пересылаем сообщение админу
        admin_id = active_chats[user_id]
        try:
            await bot.copy_message(
                chat_id=admin_id,
                from_chat_id=user_id,
                message_id=message.message_id
            )
        except Exception as e:
            print(f"Не удалось переслать сообщение от клиента: {e}")
    else:
        # Клиент НЕ в чате.
        # Сценарий 1: Он нажал "Помощь" и теперь пишет вопрос.
        # Сценарий 2: Он просто что-то пишет без кнопок.
        
        # Проверяем, не является ли это началом диалога (клиент только что запросил помощь)
        # Для простоты: если клиент пишет текст и его нет в active_chats, мы создаем чат.
        # Но чтобы не спамить, лучше явно связать начало. 
        # В этой версии: ЛЮБОЕ текстовое сообщение от клиента, если он не в чате, запускает диалог.
        
        active_chats[user_id] = ADMIN_ID
        
        username = message.from_user.username or "без юзернейма"
        admin_notification = (
            f"📩 <b>НОВЫЙ ВОПРОС ОТ КЛИЕНТА!</b>\n\n"
            f"От: @{username} (ID: {user_id})\n"
            f"Текст: {text_content}\n\n"
            f"Теперь вы можете отвечать ему напрямую."
        )
        try:
            sent_msg = await bot.send_message(chat_id=ADMIN_ID, text=admin_notification, parse_mode="HTML", reply_markup=get_admin_control_keyboard(user_id))
            await message.answer("Ваш вопрос передан менеджеру. Ожидайте ответа.")
        except Exception as e:
            print(f"Не удалось уведомить админа: {e}")

# --- Запуск ---

async def main():
    print("🚀 Бот запущен! Ожидаю команды...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
