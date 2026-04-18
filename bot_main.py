import os
import logging
import asyncio
import io
import speech_recognition as sr
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardButton, InlineKeyboardMarkup, 
    BufferedInputFile
)
from aiogram.client.default import DefaultBotProperties
from pydub import AudioSegment
from gtts import gTTS
import numpy as np
import cv2
import mediapipe as mp
from docx import Document
from fpdf import FPDF

# --- AI Setup (Mediapipe សម្រាប់កាត់ Background ឥតខ្ចោះ) ---
mp_selfie_segmentation = mp.solutions.selfie_segmentation
segmenter = mp_selfie_segmentation.SelfieSegmentation(model_selection=1)

API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_URL = "https://t.me/OG_Raa1"

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
recognizer = sr.Recognizer()
logging.basicConfig(level=logging.INFO)

# រក្សាទុកទិន្នន័យចំណូលចិត្ត User
user_languages, user_voices, last_transcription, user_last_image = {}, {}, {}, {}

# --- ១. KEYBOARDS (៦ ប៊ូតុងពេញលេញ តាមរូបភាព) ---
def get_main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🌐 ប្តូរភាសា"), KeyboardButton(text="🎙️ ជ្រើសរើសសំឡេង AI")],
        [KeyboardButton(text="🖼️ កាត់ Background"), KeyboardButton(text="🎨 ប្តូរពណ៌ Background")],
        [KeyboardButton(text="ℹ️ ព័ត៌មាន Bot"), KeyboardButton(text="👤 ទាក់ទង Admin")]
    ], resize_keyboard=True)

# --- ២. មុខងារប្ដូរភាសា និង សំឡេង AI ---
@dp.message(F.text == "🌐 ប្តូរភាសា")
async def cmd_lang(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇰🇭 ខ្មែរ", callback_data="l_km"), InlineKeyboardButton(text="🇺🇸 English", callback_data="l_en")],
        [InlineKeyboardButton(text="🇯🇵 Japanese", callback_data="l_ja"), InlineKeyboardButton(text="🇨🇳 Chinese", callback_data="l_zh")]
    ])
    await message.answer("<b>🌐 សូមជ្រើសរើសភាសា៖</b>", reply_markup=kb)

@dp.message(F.text == "🎙️ ជ្រើសរើសសំឡេង AI")
async def cmd_voice(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👩 ភេទស្រី", callback_data="v_fm"), InlineKeyboardButton(text="👨 ភេទប្រុស", callback_data="v_m")],
        [InlineKeyboardButton(text="🛑 ឈប់ប្រើសំឡេង AI", callback_data="v_off")]
    ])
    await message.answer("<b>🎙️ សូមជ្រើសរើសប្រភេទសំឡេង AI៖</b>", reply_markup=kb)

# --- ៣. មុខងារកាត់ Background (Mediapipe AI) ---
@dp.message(F.text == "🖼️ កាត់ Background")
async def cmd_remove_bg(message: types.Message):
    await message.answer("<b>🖼️ សូមផ្ញើរូបភាពមកកាន់ខ្ញុំ!</b>")

@dp.photo
async def handle_photo(message: types.Message):
    user_id = message.from_user.id
    msg = await message.reply("⚡ <b>AI កំពុងកាត់ឱ្យ... (ឥតខ្ចោះ)</b>")
    try:
        file_i = await bot.get_file(message.photo[-1].file_id)
        p_bytes = await bot.download_file(file_i.file_path)
        input_data = p_bytes.read()
        user_last_image[user_id] = input_data
        
        nparr = np.frombuffer(input_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        results = segmenter.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        condition = np.stack((results.segmentation_mask,) * 3, axis=-1) > 0.1
        
        out_img = np.where(condition, img, np.zeros(img.shape, dtype=np.uint8))
        tmp = cv2.cvtColor(out_img, cv2.COLOR_BGR2GRAY)
        _, alpha = cv2.threshold(tmp, 0, 255, cv2.THRESH_BINARY)
        b, g, r = cv2.split(out_img)
        dst = cv2.merge([b, g, r, alpha], 4)

        _, buffer = cv2.imencode('.png', dst)
        await message.answer_document(BufferedInputFile(buffer.tobytes(), filename="RAA_BG_PERFECT.png"), caption="<b>✅ កាត់រួចរាល់!</b>")
        await msg.delete()
    except Exception as e: await msg.edit_text(f"❌ Error: {str(e)}")

# --- ៤. មុខងារ Start & ផ្សេងៗ ---
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.answer("<b>🎙 ស្វាគមន៍មកកាន់ RaaBot Pro v10.0</b>", reply_markup=get_main_menu())

@dp.message(F.text == "ℹ️ ព័ត៌មាន Bot")
async def cmd_info(message: types.Message):
    await message.answer("<b>🤖 RaaBot Pro v10.0</b>\n- Voice AI, SRT, PDF, DOCX, Perfect BG Removal")

@dp.message(F.text == "👤 ទាក់ទង Admin")
async def cmd_admin(message: types.Message):
    await message.answer(f"<b>Admin:</b> <a href='{ADMIN_URL}'>OG_Raa1</a>")

# Callback Handler សម្រាប់ប្ដូរភាសា និង សំឡេង
@dp.callback_query(F.data.startswith(("v_", "l_")))
async def handle_settings(callback: types.CallbackQuery):
    if callback.data.startswith("v_"): user_voices[callback.from_user.id] = callback.data
    else: user_languages[callback.from_user.id] = callback.data
    await callback.message.edit_text("✅ រួចរាល់!")
    await callback.answer()

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
