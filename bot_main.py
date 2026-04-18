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
from rembg import remove, new_session

# --- កំណត់ Model ស្រាលបំផុតដើម្បីការពារការ Crash លើ Railway ---
fast_session = new_session("u2netp") 

API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_URL = "https://t.me/OG_Raa1"

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
recognizer = sr.Recognizer()
logging.basicConfig(level=logging.INFO)

# បង្កើត Dictionary សម្រាប់រក្សាទុកទិន្នន័យបណ្ដោះអាសន្ន
user_languages, user_voices, last_transcription, user_last_image = {}, {}, {}, {}

# --- ១. មុខងារបំប្លែង Format (SRT, VTT) ---
def format_to_srt(text):
    if not text: return "No data"
    lines = text.split(". ")
    srt_content = ""
    for i, line in enumerate(lines):
        if not line.strip(): continue
        start = f"00:00:{i*3:02d},000"; end = f"00:00:{(i*3)+3:02d},000"
        srt_content += f"{i+1}\n{start} --> {end}\n{line.strip()}\n\n"
    return srt_content

def format_to_vtt(text):
    if not text: return "No data"
    lines = text.split(". ")
    vtt_content = "WEBVTT\n\n"
    for i, line in enumerate(lines):
        if not line.strip(): continue
        start = f"00:00:{i*3:02d}.000"; end = f"00:00:{(i*3)+3:02d}.000"
        vtt_content += f"{start} --> {end}\n{line.strip()}\n\n"
    return vtt_content

# --- ២. KEYBOARDS (៦ ប៊ូតុង រៀបតាមរូបភាពប្អូនចង់បាន) ---
def get_main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🌐 ប្តូរភាសា"), KeyboardButton(text="🎙️ ជ្រើសរើសសំឡេង AI")],
        [KeyboardButton(text="🖼️ កាត់ Background"), KeyboardButton(text="🎨 ប្តូរពណ៌ Background")],
        [KeyboardButton(text="ℹ️ ព័ត៌មាន Bot"), KeyboardButton(text="👤 ទាក់ទង Admin")]
    ], resize_keyboard=True)

def get_export_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 PDF", callback_data="ex_pdf"), InlineKeyboardButton(text="📝 DOCX", callback_data="ex_docx")],
        [InlineKeyboardButton(text="🎬 SRT", callback_data="ex_srt"), InlineKeyboardButton(text="📺 VTT", callback_data="ex_vtt")],
        [InlineKeyboardButton(text="📊 XLSX", callback_data="ex_xlsx"), InlineKeyboardButton(text="📦 JSON", callback_data="ex_json")]
    ])

# --- ៣. បញ្ជាប៊ូតុង Start ---
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.answer("<b>🎙 ស្វាគមន៍មកកាន់ RaaBot Pro v10.0</b>\n                                                         សួស្តីអ្នកទាំងអស់គ្នា! នេះគឺជា Bot ស្វ័យប្រវត្តិសម្រាប់បំប្លែងសំឡេង កាត់ Background ល្បឿនលឿន និងប្តូរពណ៌។\n"
        "សូមជ្រើសរើសមុខងារខាងក្រោម👇៖", reply_markup=get_main_menu())

# --- ៤. មុខងារប្តូរភាសា និង សំឡេង AI ---
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

# --- ៥. មុខងារ Speech to Text & Export ---
@dp.message(F.voice | F.audio)
async def handle_audio(message: types.Message):
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "km")
    g_lang = {"km": "km-KH", "en": "en-US", "ja": "ja-JP", "zh": "zh-CN"}.get(lang, "km-KH")
    msg = await message.answer("⏳ <b>កំពុងដំណើរការ...</b>")
    
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await bot.get_file(file_id)
    ogg, wav = f"{file_id}.ogg", f"{file_id}.wav"
    await bot.download_file(file.file_path, ogg)
    
    try:
        AudioSegment.from_file(ogg).export(wav, format="wav")
        with sr.AudioFile(wav) as source:
            text = recognizer.recognize_google(recognizer.record(source), language=g_lang)
        last_transcription[user_id] = text
        
        # បើ User មិនបានបិទសំឡេង AI ទេ វានឹងផ្ញើ Voice AI ឱ្យ
        if user_id in user_voices:
            tts_p = f"{file_id}.mp3"
            gTTS(text=text, lang=lang).save(tts_p)
            await message.answer_voice(BufferedInputFile.from_file(tts_p))
            os.remove(tts_p)
        
        await message.answer(f"<b>📝 អត្ថបទ៖</b>\n<code>{text}</code>", reply_markup=get_export_keyboard())
        await msg.delete()
    except Exception as e: await message.answer(f"❌ Error: {str(e)}")
    finally:
        for p in [ogg, wav]: 
            if os.path.exists(p): os.remove(p)

# --- ៦. មុខងារ Remove Background ---
@dp.message(F.text == "🖼️ កាត់ Background")
async def cmd_remove_bg(message: types.Message):
    await message.answer("<b>🖼️ សូមផ្ញើរូបភាពមកកាន់ខ្ញុំ!</b>")

@dp.message(F.text == "🎨 ប្តូរពណ៌ Background")
async def cmd_change_bg(message: types.Message):
    await message.answer("<b>🎨 សូមផ្ញើរូបភាពមកដើម្បីប្តូរពណ៌!</b>")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    user_id = message.from_user.id
    photo_id = message.photo[-1].file_id
    msg = await message.reply("⚡ <b>AI កំពុងដំណើរការ...</b>")
    try:
        file_i = await bot.get_file(photo_id)
        p_bytes = await bot.download_file(file_i.file_path)
        input_d = p_bytes.read()
        user_last_image[user_id] = input_d
        
        out_d = remove(input_d, session=fast_session)
        color_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬜ ស", callback_data="bg_w"), InlineKeyboardButton(text="⬛ ខ្មៅ", callback_data="bg_b")],
            [InlineKeyboardButton(text="🟦 ខៀវ", callback_data="bg_bl"), InlineKeyboardButton(text="🟥 ក្រហម", callback_data="bg_r")]
        ])
        await message.answer_document(BufferedInputFile(out_d, filename="RAA_BG.png"), caption="<b>✅ កាត់រួចរាល់!</b>", reply_markup=color_kb)
        await msg.delete()
    except Exception as e: await msg.edit_text(f"❌ Error: {str(e)}")

# --- ៧. ប៊ូតុង Info & Admin ---
@dp.message(F.text == "ℹ️ ព័ត៌មាន Bot")
async def cmd_info(message: types.Message):
    await message.answer("<b>🤖 RaaBot Pro v10.0</b>\n• Auto Remove BG & Change Color\n• Google Recognition (4 Langs)\n• Dev: THEARA Rupp")

@dp.message(F.text == "👤 ទាក់ទង Admin")
async def cmd_admin(message: types.Message):
    await message.answer(f"<b>Admin:</b> <a href='{ADMIN_URL}'>OG_Raa1</a>")

# --- ៨. Callback Handler (Export & Change Color) ---
@dp.callback_query(F.data.startswith(("v_", "l_", "ex_", "bg_")))
async def handle_callbacks(callback: types.CallbackQuery):
    data = callback.data
    user_id = callback.from_user.id
    
    if data.startswith("ex_"):
        f_t = data.replace("ex_", "")
        text = last_transcription.get(user_id, "")
        if f_t == "srt": final = format_to_srt(text)
        elif f_t == "vtt": final = format_to_vtt(text)
        else: final = text # សម្រាប់ PDF/DOCX ប្អូនអាចថែម Library ផ្សេងទៀតបាន
        await callback.message.answer_document(BufferedInputFile(final.encode('utf-8'), filename=f"result.{f_t}"))
        
    elif data.startswith("bg_"):
        color = data.replace("bg_", ""); c_map = {"w": (255, 255, 255), "b": (0, 0, 0), "bl": (0, 0, 255), "r": (255, 0, 0)}
        if user_id in user_last_image:
            out_d = remove(user_last_image[user_id], session=fast_session, bgcolor=c_map.get(color))
            await callback.message.answer_document(BufferedInputFile(out_d, filename=f"RAA_COLOR_{color}.png"))
    
    # បន្ថែមការឆ្លើយតបសម្រាប់ប៊ូតុង Voice និង ភាសា
    elif data.startswith("v_"):
        if data == "v_off": user_voices.pop(user_id, None)
        else: user_voices[user_id] = data.replace("v_", "")
        await callback.message.edit_text("✅ រួចរាល់!")
    elif data.startswith("l_"):
        user_languages[user_id] = data.replace("l_", "")
        await callback.message.edit_text("✅ កំណត់ភាសារួចរាល់!")
        
    await callback.answer()

async def main():
    await bot.delete_webhook(drop_pending_updates=True) # ដោះស្រាយបញ្ហា Conflict
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
