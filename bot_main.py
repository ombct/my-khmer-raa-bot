import os, logging, asyncio, io, json
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
import pandas as pd

# --- AI Setup (High Quality) ---
mp_selfie = mp.solutions.selfie_segmentation
segmenter = mp_selfie.SelfieSegmentation(model_selection=1)

API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_URL = "https://t.me/OG_Raa1"

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
recognizer = sr.Recognizer()
logging.basicConfig(level=logging.INFO)

# Storage
user_settings = {} # {user_id: {'lang': 'km', 'voice': 'fm'}}
last_text = {} 

# --- ១. KEYBOARDS (៦ ប៊ូតុង តាមរូបភាពប្អូន) ---
def get_main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🌐 ប្តូរភាសា"), KeyboardButton(text="🎙️ ជ្រើសរើសសំឡេង AI")],
        [KeyboardButton(text="🖼️ កាត់ Background"), KeyboardButton(text="🎨 ប្តូរពណ៌ Background")],
        [KeyboardButton(text="ℹ️ ព័ត៌មាន Bot"), KeyboardButton(text="👤 ទាក់ទង Admin")]
    ], resize_keyboard=True)

def get_export_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 PDF", callback_data="ex_pdf"), InlineKeyboardButton(text="📝 DOCX", callback_data="ex_docx")],
        [InlineKeyboardButton(text="🎬 SRT", callback_data="ex_srt"), InlineKeyboardButton(text="📺 VTT", callback_data="ex_vtt")],
        [InlineKeyboardButton(text="📊 XLSX", callback_data="ex_xlsx"), InlineKeyboardButton(text="📦 JSON", callback_data="ex_json")]
    ])

# --- ២. មុខងារប្ដូរភាសា & សំឡេង ---
@dp.message(F.text == "🌐 ប្តូរភាសា")
async def cmd_lang(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇰🇭 ខ្មែរ", callback_data="setl_km"), InlineKeyboardButton(text="🇺🇸 English", callback_data="setl_en")],
        [InlineKeyboardButton(text="🇯🇵 Japanese", callback_data="setl_ja"), InlineKeyboardButton(text="🇨🇳 Chinese", callback_data="setl_zh")]
    ])
    await message.answer("<b>🌐 ជ្រើសរើសភាសាសម្រាប់បំប្លែងសំឡេង៖</b>", reply_markup=kb)

@dp.message(F.text == "🎙️ ជ្រើសរើសសំឡេង AI")
async def cmd_voice(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👩 ភេទស្រី", callback_data="setv_fm"), InlineKeyboardButton(text="👨 ភេទប្រុស", callback_data="setv_m")],
        [InlineKeyboardButton(text="🛑 ឈប់ប្រើសំឡេង AI", callback_data="setv_off")]
    ])
    await message.answer("<b>🎙️ ជ្រើសរើសប្រភេទសំឡេង AI៖</b>", reply_markup=kb)

# --- ៣. មុខងារ SPEECH TO TEXT & EXPORT ---
@dp.message(F.voice | F.audio)
async def handle_audio(message: types.Message):
    uid = message.from_user.id
    conf = user_settings.get(uid, {'lang': 'km', 'voice': 'off'})
    g_lang = {"km": "km-KH", "en": "en-US", "ja": "ja-JP", "zh": "zh-CN"}.get(conf['lang'], "km-KH")
    
    msg = await message.answer("⏳ <b>កំពុងបំប្លែង...</b>")
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await bot.get_file(file_id)
    ogg_p, wav_p = f"{file_id}.ogg", f"{file_id}.wav"
    await bot.download_file(file.file_path, ogg_p)
    
    try:
        AudioSegment.from_file(ogg_p).export(wav_p, format="wav")
        with sr.AudioFile(wav_p) as source:
            text = recognizer.recognize_google(recognizer.record(source), language=g_lang)
        last_text[uid] = text
        
        if conf['voice'] != 'off':
            tts_p = f"{file_id}.mp3"
            gTTS(text=text, lang=conf['lang']).save(tts_p)
            await message.answer_voice(BufferedInputFile.from_file(tts_p))
            os.remove(tts_p)
            
        await message.answer(f"<b>📝 អត្ថបទ៖</b>\n<code>{text}</code>", reply_markup=get_export_menu())
        await msg.delete()
    except: await msg.edit_text("❌ មិនអាចបំប្លែងបាន!")
    finally:
        for p in [ogg_p, wav_p]: 
            if os.path.exists(p): os.remove(p)

# --- ៤. មុខងារកាត់ BACKGROUND (PERFECT QUALITY) ---
@dp.message(F.text == "🖼️ កាត់ Background")
async def cmd_rem(message: types.Message):
    await message.answer("<b>🖼️ សូមផ្ញើរូបភាពមកកាន់ខ្ញុំ!</b>")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    msg = await message.reply("⚡ <b>AI កំពុងកាត់ឱ្យ...</b>")
    try:
        file_i = await bot.get_file(message.photo[-1].file_id)
        p_bytes = await bot.download_file(file_i.file_path)
        
        nparr = np.frombuffer(p_bytes.read(), np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        res = segmenter.process(rgb_img)
        mask = res.segmentation_mask > 0.5
        
        b, g, r = cv2.split(img)
        a = (mask * 255).astype(np.uint8)
        rgba = cv2.merge([b, g, r, a])
        
        _, buffer = cv2.imencode('.png', rgba)
        await message.answer_document(BufferedInputFile(buffer.tobytes(), filename="RAA_PERFECT.png"), caption="<b>✅ រួចរាល់!</b>")
        await msg.delete()
    except Exception as e: await msg.edit_text(f"❌ Error: {str(e)}")

# --- ៥. EXPORT SYSTEM ---
@dp.callback_query(F.data.startswith("ex_"))
async def export_file(callback: types.CallbackQuery):
    mode = callback.data.replace("ex_", "")
    text = last_text.get(callback.from_user.id, "No data")
    
    if mode == "pdf":
        pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, txt=text.encode('latin-1', 'ignore').decode('latin-1'))
        data = pdf.output(dest='S').encode('latin-1')
    elif mode == "docx":
        doc = Document(); doc.add_paragraph(text); s = io.BytesIO(); doc.save(s); data = s.getvalue()
    elif mode == "srt": data = f"1\n00:00:00,000 --> 00:00:10,000\n{text}".encode('utf-8')
    elif mode == "vtt": data = f"WEBVTT\n\n00:00:00.000 --> 00:00:10.000\n{text}".encode('utf-8')
    elif mode == "xlsx":
        df = pd.DataFrame([{"Content": text}]); s = io.BytesIO()
        with pd.ExcelWriter(s, engine='openpyxl') as writer: df.to_excel(writer, index=False)
        data = s.getvalue()
    else: data = json.dumps({"text": text}, ensure_ascii=False).encode('utf-8')

    await callback.message.answer_document(BufferedInputFile(data, filename=f"RAA_RESULT.{mode}"))
    await callback.answer()

# --- ៦. SETTINGS CALLBACKS ---
@dp.callback_query(F.data.startswith(("setl_", "setv_")))
async def handle_settings(callback: types.CallbackQuery):
    uid = callback.from_user.id
    if uid not in user_settings: user_settings[uid] = {'lang': 'km', 'voice': 'off'}
    
    if callback.data.startswith("setl_"): user_settings[uid]['lang'] = callback.data.replace("setl_", "")
    else: user_settings[uid]['voice'] = callback.data.replace("setv_", "")
    
    await callback.message.edit_text("✅ រួចរាល់!")
    await callback.answer()

# --- ៧. ADMIN & INFO ---
@dp.message(F.text == "ℹ️ ព័ត៌មាន Bot")
async def cmd_info(message: types.Message):
    await message.answer("<b>🤖 RaaBot Pro v10.0 Full</b>\n- Voice AI, SRT, PDF, DOCX, XLSX, JSON\n- Perfect BG Removal")

@dp.message(F.text == "👤 ទាក់ទង Admin")
async def cmd_admin(message: types.Message):
    await message.answer(f"<b>Admin:</b> <a href='{ADMIN_URL}'>OG_Raa1</a>")

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("<b>🎙 ស្វាគមន៍មកកាន់ RaaBot Pro</b>", reply_markup=get_main_menu())

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
