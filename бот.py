# -*- coding: utf-8 -*-
import aiohttp, asyncio, logging, os, random, smtplib, functools
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage

api_id = int(os.getenv("API_ID", 21826549))
api_hash = os.getenv("API_HASH", "c1a19f792cfd9e397200d16c7e448160")
bot_token = os.getenv("BOT_TOKEN", "9051064757:AAE--olRS1MR26WNDEzYov-TIlLJxV-k2k0")
admin_chat_id = os.getenv("ADMIN_CHAT_ID", "649017709")

from config import senders, receivers, smtp_servers
from proxies import proxies
from user_agents import user_agents
from emails import mail, phone_numbers
try:
    from config import clients
except ImportError:
    clients = []

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
bot = Bot(token=bot_token)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())
script_dir = os.path.dirname(os.path.abspath(__file__))
photo_path = os.path.join(script_dir, 'welcome_photo.jpg')

def generate_dynamic_text(category, target_info):
    greetings = ["Здравствуйте, уважаемая команда поддержки!", "Добрый день, администрация Telegram.", "Приветствую. Прошу обратить внимание на серьезное нарушение.", "Уважаемые модераторы, прошу проверить данный аккаунт/канал.", "Обращаюсь к вам с просьбой о помощи в очистке платформы."]
    endings = ["Прошу принять меры и заблокировать нарушителя.", "Надеюсь на вашу оперативную реакцию.", "Пожалуйста, проверьте этот профиль как можно скорее.", "Данный контент нарушает правила платформы, прошу удалить его.", "Заранее благодарю за вашу работу по обеспечению безопасности."]
    if 'Наркотики' in category:
        core = f"Данный аккаунт/канал ({target_info}) незаконно распространяет наркотические вещества. Это нарушает Условия использования Telegram и преследуется по закону."
    elif 'Спам' in category:
        core = f"Аккаунт ({target_info}) занимается массовой рассылкой спама и мошенническими действиями с фишинговыми ссылками."
    elif 'Детское насилие' in category:
        core = f"Аккаунт ({target_info}) распространяет материалы, связанные с насилием над детьми. Требуется немедленное вмешательство."
    elif 'Насилие' in category:
        core = f"Профиль ({target_info}) пропагандирует насилие и содержит прямые угрозы в адрес других пользователей."
    elif 'Порнография' in category:
        core = f"Данный канал ({target_info}) распространяет порнографический контент, что строго запрещено правилами."
    elif 'Личные данные' in category:
        core = f"Аккаунт ({target_info}) занимается доксингом — незаконно публикует личные данные пользователей."
    elif 'Авторское право' in category:
        core = f"Аккаунт ({target_info}) нарушает авторские права, распространяя защищённый контент без разрешения."
    else:
        core = f"Аккаунт ({target_info}) нарушает Условия использования Telegram и правила сообщества."
    return f"{random.choice(greetings)}\n\n{core}\n\n{random.choice(endings)}"

class ComplaintStates(StatesGroup):
    target_info = State()
    subject = State()
    body = State()
    photos = State()
    count = State()
    text_for_site = State()
    count_for_site = State()

class SupportStates(StatesGroup):
    message = State()

class RestoreAccountStates(StatesGroup):
    phone = State()
    send_count = State()

class SpamCodeStates(StatesGroup):
    phone_and_count = State()

class BanState(StatesGroup):
    waiting_for_ban_user_id = State()
    waiting_for_unban_user_id = State()

banned_users_file = 'banned_users.txt'
def load_banned_users():
    try:
        with open(banned_users_file, 'r') as f:
            return set(map(int, f.read().splitlines()))
    except FileNotFoundError:
        return set()

def save_banned_users(banned_users):
    with open(banned_users_file, 'w') as f:
        for uid in banned_users:
            f.write(f'{uid}\n')

banned_users = load_banned_users()

def load_admins():
    admins_set = set()
    try:
        with open('admins.txt', 'r') as f:
            admins_set = set(map(int, f.read().splitlines()))
    except FileNotFoundError:
        pass
    try:
        main_admin = int(str(admin_chat_id).strip())
        if main_admin not in admins_set:
            admins_set.add(main_admin)
            with open('admins.txt', 'w') as f:
                for a in admins_set:
                    f.write(f'{a}\n')
    except (ValueError, TypeError):
        pass
    return admins_set

admins = load_admins()

def is_admin(user_id):
    try:
        return int(user_id) in admins
    except (ValueError, TypeError):
        return False

async def write_user_data(user_id, first_name, last_name, username):
    with open('users.txt', 'a', encoding='utf-8') as f:
        f.write(f"{user_id} {first_name} {last_name} {username}\n")

async def is_user_in_file(user_id):
    if not os.path.exists('users.txt'):
        return False
    with open('users.txt', 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split()
            if parts and parts[0] == str(user_id):
                return True
    return False

@dp.message_handler(commands=['start'], state='*')
async def send_welcome(message: types.Message, state: FSMContext):
    await state.finish()
    user = message.from_user
    if not await is_user_in_file(user.id):
        await write_user_data(user.id, user.first_name or '', user.last_name or '', f"@{user.username}" if user.username else f"id{user.id}")
    welcome_message = f"Добро пожаловать, {user.first_name}!\nВыберите нужное действие:"
    await send_menu(message, welcome_message)

async def send_menu(message: types.Message, welcome_message: str):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton('📢 Поддержка', callback_data='support'))
    markup.add(InlineKeyboardButton('📫 Email-Снос', callback_data='email_complaint'))
    markup.add(InlineKeyboardButton('💻 Web-Снос', callback_data='website_complaint'))
    markup.add(InlineKeyboardButton('🔥 Спам-Снос', callback_data='spam_code'))
    markup.add(InlineKeyboardButton('🔄 Восстановить аккаунт', callback_data='restore_account'))
    if is_admin(message.from_user.id):
        markup.add(InlineKeyboardButton('🛠 Админ панель', callback_data='admin_panel'))
    if os.path.exists(photo_path):
        with open(photo_path, 'rb') as photo:
            await bot.send_photo(message.chat.id, photo, caption=welcome_message, reply_markup=markup)
    else:
        await message.answer(welcome_message, reply_markup=markup)

def get_category_keyboard(target):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton('Наркотики', callback_data=f'cat_{target}_drugs'),
        InlineKeyboardButton('Спам/Скам', callback_data=f'cat_{target}_spam'),
        InlineKeyboardButton('Детское насилие', callback_data=f'cat_{target}_childabuse'),
        InlineKeyboardButton('Насилие', callback_data=f'cat_{target}_violence'),
        InlineKeyboardButton('Порнография', callback_data=f'cat_{target}_porn'),
        InlineKeyboardButton('Личные данные', callback_data=f'cat_{target}_personal'),
        InlineKeyboardButton('Авторское право', callback_data=f'cat_{target}_copyright'),
        InlineKeyboardButton('Другое', callback_data=f'cat_{target}_other')
    )
    return markup

@dp.callback_query_handler(lambda c: c.data.startswith('cat_'), state='*')
async def process_category_select(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id in banned_users:
        await callback_query.answer('Вы забанены!', show_alert=True)
        return
    try:
        _, target, category = callback_query.data.split('_')
    except ValueError:
        await callback_query.answer('Ошибка')
        return
    cat_names = {'drugs': 'Наркотики', 'spam': 'Спам', 'childabuse': 'Детское насилие', 'violence': 'Насилие', 'porn': 'Порнография', 'personal': 'Личные данные', 'copyright': 'Авторское право', 'other': 'Другое'}
    cat_text = cat_names.get(category, 'Нарушение')
    await bot.answer_callback_query(callback_query.id)
    text_msg = f'Выбрана категория: {cat_text}\n\nОтправьте данные нарушителя (ссылку/юзернейм).\nБот сгенерирует уникальный текст жалобы!\nИли напишите "вручную".'
    if target == 'email':
        await state.update_data(category=cat_text, target_type='email')
        await callback_query.message.answer(text_msg)
        await ComplaintStates.target_info.set()
    elif target == 'site':
        await state.update_data(category_site=cat_text, target_type='site')
        await callback_query.message.answer(text_msg)
        await ComplaintStates.target_info.set()

@dp.message_handler(state=ComplaintStates.target_info)
async def process_target_info(message: types.Message, state: FSMContext):
    if message.from_user.id in banned_users:
        await state.finish()
        return
    if not message.text:
        await message.answer('❌ Отправьте текстовое сообщение')
        return
    data = await state.get_data()
    target_type = data.get('target_type', 'email')
    category = data.get('category') if target_type == 'email' else data.get('category_site')
    if message.text.lower().strip() == 'вручную':
        if target_type == 'email':
            await message.answer('Введите тему письма (Subject):')
            await ComplaintStates.subject.set()
        else:
            await message.answer('Введите текст жалобы:')
            await ComplaintStates.text_for_site.set()
        return
    generated_body = generate_dynamic_text(category, message.text)
    if target_type == 'email':
        subject = f"Жалоба: {category}"
        await state.update_data(subject=subject, body=generated_body, photos=[])
        await message.answer(f'Сгенерированный текст:\n\n{generated_body}\n\nДобавить фото? (Да/Нет)')
        await ComplaintStates.photos.set()
    else:
        await state.update_data(text_for_site=generated_body)
        await message.answer(f'Сгенерированный текст:\n\n{generated_body}\n\nКоличество отправок (до 50):')
        await ComplaintStates.count_for_site.set()

@dp.callback_query_handler(lambda c: c.data in {'support', 'email_complaint', 'website_complaint', 'spam_code', 'restore_account'}, state='*')
async def callback_query(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id in banned_users:
        await call.answer('Вы забанены администратором', show_alert=True)
        return
    await call.answer()
    if call.data == 'support':
        await call.message.answer('📝 Напишите ваше сообщение для поддержки:')
        await SupportStates.message.set()
    elif call.data == 'email_complaint':
        await call.message.answer('📫 Выберите категорию жалобы:', reply_markup=get_category_keyboard('email'))
    elif call.data == 'website_complaint':
        await call.message.answer('💻 Выберите категорию жалобы:', reply_markup=get_category_keyboard('site'))
    elif call.data == 'spam_code':
        if not clients:
            await call.message.answer('❌ Спам-снос не настроен (config.clients бос)')
            return
        await call.message.answer('📞 Введите номер и количество: +79991234567 10')
        await SpamCodeStates.phone_and_count.set()
    elif call.data == 'restore_account':
        await call.message.answer('📱 Введите номер телефона для восстановления:')
        await RestoreAccountStates.phone.set()

@dp.message_handler(state=SupportStates.message)
async def process_support(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer('❌ Отправьте текст')
        return
    user = message.from_user
    try:
        await bot.send_message(admin_chat_id, f"📩 Поддержка\nОт: {user.first_name} (id: {user.id}, @{user.username or '—'})\n\n{message.text}")
        await message.answer('✅ Сообщение отправлено в поддержку')
    except Exception as e:
        logging.error(f"Support error: {e}")
        await message.answer('❌ Не удалось отправить')
    await state.finish()

@dp.message_handler(state=ComplaintStates.subject)
async def process_subject_step(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer('❌ Отправьте текст')
        return
    data = await state.get_data()
    await state.update_data(subject=f"[{data.get('category', 'Жалоба')}] {message.text}")
    await message.answer('📝 Введите текст жалобы:')
    await ComplaintStates.body.set()

@dp.message_handler(state=ComplaintStates.body)
async def process_body_step(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer('❌ Отправьте текст')
        return
    await state.update_data(body=message.text)
    await message.answer('🖼 Добавить фото? (Да/Нет):')
    await ComplaintStates.photos.set()

@dp.message_handler(state=ComplaintStates.photos)
async def process_photo_decision(message: types.Message, state: FSMContext):
    if not message.text:
        return
    answer = message.text.lower().strip()
    if answer == 'да':
        await message.answer('📎 Отправьте фотографии (когда закончите — напишите "готово"):')
    elif answer == 'нет':
        await message.answer('🔢 Количество отправок (до 50):')
        await ComplaintStates.count.set()
    elif answer == 'готово':
        await message.answer('🔢 Количество отправок (до 50):')
        await ComplaintStates.count.set()
    else:
        await message.answer('❌ Ответьте "Да", "Нет" или "готово"')

@dp.message_handler(content_types=['photo'], state=ComplaintStates.photos)
async def process_photos_step(message: types.Message, state: FSMContext):
    photo = message.photo[-1]
    file_info = await bot.get_file(photo.file_id)
    downloaded = await bot.download_file(file_info.file_path)
    photo_bytes = downloaded.read()
    data = await state.get_data()
    photos = data.get('photos', [])
    if len(photos) >= 5:
        await message.answer('⚠️ Максимум 5 фото. Напишите "готово" для продолжения.')
        return
    photos.append(photo_bytes)
    await state.update_data(photos=photos)
    await message.answer(f'✅ Фото добавлено ({len(photos)}/5).\nОтправьте ещё или напишите "готово".')

@dp.message_handler(state=ComplaintStates.count)
async def process_count_step(message: types.Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer('🔢 Введите число (1–50):')
        return
    count = int(message.text.strip())
    if count < 1 or count > 50:
        await message.answer('🚫 От 1 до 50. Повторите:')
        return
    data = await state.get_data()
    subject = data['subject']
    body = data['body']
    photos = data.get('photos') or None
    status_msg = await message.answer(f"⏳ Начинаю отправку {count} писем...")
    success_count = 0
    fail_count = 0
    for _ in range(count):
        receiver = random.choice(receivers)
        sender_email, sender_password = random.choice(list(senders.items()))
        ok, result = await send_email_async(receiver, sender_email, sender_password, subject, body, photos)
        if ok:
            success_count += 1
        else:
            fail_count += 1
            logging.warning(f"Email fail: {result}")
        try:
            await status_msg.edit_text(f"⏳ Отправка...\n✅ Успешно: {success_count}\n❌ Ошибок: {fail_count}")
        except Exception:
            pass
        await asyncio.sleep(1)
    await status_msg.edit_text(f"✅ Email-снос завершен!\n\n✅ Успешно: {success_count}\n❌ Безуспешно: {fail_count}")
    await state.finish()

async def send_email_async(receiver, sender_email, sender_password, subject, body, photos=None):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, functools.partial(_send_email_sync, receiver, sender_email, sender_password, subject, body, photos))

def _send_email_sync(receiver, sender_email, sender_password, subject, body, photos=None):
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    if photos:
        for idx, photo in enumerate(photos):
            try:
                msg.attach(MIMEImage(photo, _subtype='jpeg', name=f'photo{idx}.jpg'))
            except Exception as e:
                logging.warning(f"MIMEImage error: {e}")
    try:
        domain = sender_email.split('@')[1]
        if domain not in smtp_servers:
            return False, f'❌ Домен жоқ: {sender_email}'
        smtp_server, smtp_port = smtp_servers[domain]
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=15) as server:
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, receiver, msg.as_string())
        else:
            with smtplib.SMTP(smtp_server, smtp_port, timeout=15) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, receiver, msg.as_string())
        return True, 'Отправлено'
    except Exception as e:
        return False, f'❌ Ошибка: {e}'

@dp.message_handler(state=ComplaintStates.text_for_site)
async def process_text_for_site_step(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer('❌ Отправьте текст')
        return
    await state.update_data(text_for_site=message.text)
    await message.answer('🔢 Количество отправок (до 50):')
    await ComplaintStates.count_for_site.set()

@dp.message_handler(state=ComplaintStates.count_for_site)
async def process_count_for_site_step(message: types.Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer('🔢 Введите число (1–50):')
        return
    count = int(message.text.strip())
    if count < 1 or count > 50:
        await message.answer('🚫 От 1 до 50. Повторите:')
        return
    data = await state.get_data()
    text = data['text_for_site']
    status_msg = await message.answer("⏳ Начинаю Web-снос...")
    success_count = 0
    fail_count = 0
    async with aiohttp.ClientSession() as session:
        for _ in range(count):
            email = random.choice(mail)
            phone = random.choice(phone_numbers)
            proxy_url = await get_working_proxy(session)
            if not proxy_url:
                fail_count += 1
                continue
            ok = await send_to_site(session, text, email, phone, proxy_url)
            if ok:
                success_count += 1
            else:
                fail_count += 1
            try:
                await status_msg.edit_text(f"⏳ Отправка...\n✅ Успешно: {success_count}\n❌ Ошибок: {fail_count}")
            except Exception:
                pass
            await asyncio.sleep(2)
    await status_msg.edit_text(f"✅ Web-снос завершен!\n\n✅ Успешно: {success_count}\n❌ Безуспешно: {fail_count}")
    await state.finish()

async def get_working_proxy(session):
    for proxy in proxies:
        proxy_url = proxy.get('http') or proxy.get('https') if isinstance(proxy, dict) else proxy
        if not proxy_url:
            continue
        try:
            async with session.get('https://www.google.com', proxy=proxy_url, timeout=5) as r:
                if r.status == 200:
                    return proxy_url
        except Exception:
            continue
    return None

async def send_to_site(session, text, email, phone, proxy_url):
    url = "https://telegram.org/support"
    headers = {"User-Agent": random.choice(user_agents), "Content-Type": "application/x-www-form-urlencoded"}
    data = {"message": text, "email": email, "phone": phone, "setln": "ru"}
    try:
        async with session.post(url, data=data, headers=headers, proxy=proxy_url, timeout=15) as resp:
            return resp.status == 200
    except Exception as e:
        logging.error(f"Site error: {e}")
        return False

@dp.message_handler(state=SpamCodeStates.phone_and_count)
async def process_spam_code_input(message: types.Message, state: FSMContext):
    if not message.text:
        return
    if not clients:
        await message.answer('❌ Спам-снос не настроен')
        await state.finish()
        return
    try:
        parts = message.text.split()
        if len(parts) != 2:
            await message.reply('❌ Формат: +79991234567 10')
            return
        phone_number, num_str = parts
        num_sendings = int(num_str)
        if num_sendings < 1 or num_sendings > 100:
            await message.reply('🚫 От 1 до 100')
            return
    except ValueError:
        await message.reply('❌ Формат: +79991234567 10')
        return
    from telethon import TelegramClient
    status_msg = await message.answer("⏳ Отправка кодов...")
    success_count = 0
    for _ in range(num_sendings):
        client_data = random.choice(clients)
        client = None
        try:
            client = TelegramClient(client_data["name"], client_data["api_id"], client_data["api_hash"])
            await client.connect()
            await client.send_code_request(phone_number)
            success_count += 1
            try:
                await status_msg.edit_text(f"⏳ Отправка кодов...\n✅ Успешно: {success_count}/{num_sendings}")
            except Exception:
                pass
        except Exception as e:
            logging.error(f"Spam error: {e}")
        finally:
            if client:
                try:
                    await client.disconnect()
                    if client.session:
                        client.session.delete()
                except Exception:
                    pass
        await asyncio.sleep(1)
    await status_msg.edit_text(f"✅ Спам-снос завершен!\n\n✅ Успешно: {success_count}/{num_sendings}")
    await state.finish()

@dp.message_handler(state=RestoreAccountStates.phone)
async def process_restore_phone(message: types.Message, state: FSMContext):
    if not message.text or not message.text.strip().startswith('+'):
        await message.answer('❌ Номер должен начинаться с "+". Пример: +79991234567')
        return
    await state.update_data(phone_number=message.text.strip())
    await message.answer("📝 Введите количество отправок (1–100):")
    await RestoreAccountStates.send_count.set()

@dp.message_handler(state=RestoreAccountStates.send_count)
async def process_send_count(message: types.Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer('🔢 Введите число (1–100):')
        return
    count = int(message.text.strip())
    if count < 1 or count > 100:
        await message.answer('🚫 От 1 до 100')
        return
    data = await state.get_data()
    phone = data.get("phone_number")
    status_msg = await message.answer("⏳ Отправка заявок на восстановление...")
    success = 0
    for i in range(count):
        sender_email, sender_password = random.choice(list(senders.items()))
        ok, _ = await send_email_async("recover@telegram.org", sender_email, sender_password, f"Banned phone number: {phone}", f"Please help restore my account.\nPhone: {phone}\n\nС уважением.")
        if ok:
            success += 1
        try:
            await status_msg.edit_text(f"⏳ Отправка...\n✅ Успешно: {success}/{count}")
        except Exception:
            pass
        await asyncio.sleep(1)
    await status_msg.edit_text(f"✅ Заявки отправлены!\n\n✅ Успешно: {success}/{count}")
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == 'admin_panel', state='*')
async def admin_panel_callback(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    if not is_admin(callback_query.from_user.id):
        await callback_query.message.answer('❌ Вы не админ.')
        return
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton('🚫 Бан', callback_data='ban_user'), InlineKeyboardButton('🔓 Снять бан', callback_data='unban_user'))
    await callback_query.message.answer('🛠 Админ панель:', reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data == 'ban_user', state='*')
async def ban_user_callback(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    if not is_admin(callback_query.from_user.id):
        return
    await callback_query.message.answer('📝 Введите ID пользователя для бана:')
    await BanState.waiting_for_ban_user_id.set()

@dp.callback_query_handler(lambda c: c.data == 'unban_user', state='*')
async def unban_user_callback(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    if not is_admin(callback_query.from_user.id):
        return
    await callback_query.message.answer('📝 Введите ID пользователя для снятия бана:')
    await BanState.waiting_for_unban_user_id.set()

@dp.message_handler(state=BanState.waiting_for_ban_user_id)
async def ban_user_input(message: types.Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer('❌ Введите числовой ID')
        return
    uid = int(message.text.strip())
    banned_users.add(uid)
    save_banned_users(banned_users)
    await message.answer(f'✅ Пользователь {uid} забанен.')
    await state.finish()

@dp.message_handler(state=BanState.waiting_for_unban_user_id)
async def unban_user_input(message: types.Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer('❌ Введите числовой ID')
        return
    uid = int(message.text.strip())
    if uid in banned_users:
        banned_users.discard(uid)
        save_banned_users(banned_users)
        await message.answer(f'✅ Пользователь {uid} разбанен.')
    else:
        await message.answer(f'ℹ️ Пользователь {uid} не был забанен.')
    await state.finish()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
