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

# --- កំណត់ការកាត់ Background ---
fast_session = new_session("u2netp") 

API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_URL = "https://t.me/OG_Raa1"

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
recognizer = sr.Recognizer()
logging.basicConfig(level=logging.INFO)

# ចងចាំទិន្នន័យក្នុង Memory
user_languages = {}
user_voices = {}
last_transcription = {}
user_last_image = {}

# --- ១. មុខងារជំនួយសម្រាប់ Subtitle (SRT/VTT) ---
def format_to_srt(text):
    lines = text.split(". ")
    srt_content = ""
    for i, line in enumerate(lines):
        if not line.strip(): continue
        start = f"00:00:{i*3:02d},000"
        end = f"00:00:{(i*3)+3:02d},000"
        srt_content += f"{i+1}\n{start} --> {end}\n{line.strip()}\n\n"
    return srt_content

def format_to_vtt(text):
    lines = text.split(". ")
    vtt_content = "WEBVTT\n\n"
    for i, line in enumerate(lines):
        if not line.strip(): continue
        start = f"00:00:{i*3:02d}.000"
        end = f"00:00:{(i*3)+3:02d}.000"
        vtt_content += f"{start} --> {end}\n{line.strip()}\n\n"
    return vtt_content

# --- ២. KEYBOARDS ---
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
        [InlineKeyboardButton(text="📊 XLSX", callback_data="ex_xlsx"), InlineKeyboardButton(text="📦 JSON", callback_data="ex_json")],
        [InlineKeyboardButton(text="📋 TXT", callback_data="ex_txt")]
    ])

# --- ៣. HANDLERS សម្រាប់បញ្ជាប៊ូតុង (ទើបបន្ថែមឱ្យដើរគ្រប់ប៊ូតុង) ---

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.answer("<b>🎙 ស្វាគមន៍មកកាន់ RaaBot Pro v10.0</b>
    សួស្តីអ្នកទាំងអស់គ្នា! នេះគឺជា Bot ស្វ័យប្រវត្តិសម្រាប់បំប្លែងសំឡេង កាត់ Background ល្បឿនលឿន និងប្តូរពណ៌។\n"
        "សូមជ្រើសរើសមុខងារខាងក្រោម👇៖", reply_markup=get_main_menu())

# មុខងារប្តូរភាសា
@dp.message(F.text == "🌐 ប្តូរភាសា")
async def cmd_lang(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇰🇭 ខ្មែរ", callback_data="setlang_km"), InlineKeyboardButton(text="🇺🇸 English", callback_data="setlang_en")],
        [InlineKeyboardButton(text="🇯🇵 Japanese", callback_data="setlang_ja"), InlineKeyboardButton(text="🇨🇳 Chinese", callback_data="setlang_zh")]
    ])
    await message.answer("<b>🌐 សូមជ្រើសរើសភាសាសម្រាប់បំប្លែង៖</b>", reply_markup=kb)

@dp.callback_query(F.data.startswith("setlang_"))
async def set_lang(callback: types.CallbackQuery):
    user_languages[callback.from_user.id] = callback.data.split("_")[1]
    await callback.message.edit_text("✅ បានកំណត់ភាសារួចរាល់!")
    await callback.answer()

# មុខងារជ្រើសរើសសំឡេង AI
@dp.message(F.text == "🎙️ ជ្រើសរើសសំឡេង AI")
async def cmd_voice(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👩 ភេទស្រី", callback_data="v_female"), InlineKeyboardButton(text="👨 ភេទប្រុស", callback_data="v_male")],
        [InlineKeyboardButton(text="🛑 ឈប់ប្រើសំឡេង AI", callback_data="v_stop")]
    ])
    await message.answer("<b>🎙️ សូមជ្រើសរើសភេទសំឡេង AI៖</b>", reply_markup=kb)

@dp.callback_query(F.data.startswith("v_"))
async def set_voice(callback: types.CallbackQuery):
    action = callback.data.replace("v_", "")
    if action == "stop":
        user_voices.pop(callback.from_user.id, None)
        await callback.message.edit_text("✅ បិទសំឡេង AI រួចរាល់!")
    else:
        user_voices[callback.from_user.id] = action
        await callback.message.edit_text(f"✅ កំណត់សំឡេង AI ({action}) រួចរាល់!")
    await callback.answer()

# --- ៤. មុខងារបំប្លែងសំឡេង (Speech to Text) ---
@dp.message(F.voice | F.audio)
async def handle_audio(message: types.Message):
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "km")
    g_lang = {"km": "km-KH", "en": "en-US", "ja": "ja-JP", "zh": "zh-CN"}.get(lang, "km-KH")
    
    msg = await message.answer("⏳ <b>កំពុងបំប្លែង...</b>")
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await bot.get_file(file_id)
    ogg, wav = f"{file_id}.ogg", f"{file_id}.wav"
    await bot.download_file(file.file_path, ogg)
    
    try:
        AudioSegment.from_file(ogg).export(wav, format="wav")
        with sr.AudioFile(wav) as source:
            text = recognizer.recognize_google(recognizer.record(source), language=g_lang)
        last_transcription[user_id] = text
        
        if user_id in user_voices:
            tts_p = f"{file_id}.mp3"
            gTTS(text=text, lang=lang).save(tts_p)
            await message.answer_voice(BufferedInputFile.from_file(tts_p))
            os.remove(tts_p)
        
        await message.answer(f"<b>📝 អត្ថបទ៖</b>\n<code>{text}</code>", reply_markup=get_export_keyboard())
        await msg.delete()
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")
    finally:
        for p in [ogg, wav]: 
            if os.path.exists(p): os.remove(p)

@dp.callback_query(F.data.startswith("ex_"))
async def do_export(callback: types.CallbackQuery):
    f_t = callback.data.replace("ex_", "")
    text = last_transcription.get(callback.from_user.id, "")
    if f_t == "srt": final = format_to_srt(text)
    elif f_t == "vtt": final = format_to_vtt(text)
    else: final = text
    await callback.message.answer_document(BufferedInputFile(final.encode('utf-8'), filename=f"result.{f_t}"))
    await callback.answer()

# --- ៥. មុខងារ Remove Background & Color ---
@dp.message(F.text == "🖼️ កាត់ Background")
async def cmd_remove_bg(message: types.Message):
    await message.answer("<b>🖼️ សូមផ្ញើរូបភាពមក!</b>")

@dp.message(F.text == "🎨 ប្តូរពណ៌ Background")
async def cmd_change_bg(message: types.Message):
    await message.answer("<b>🎨 សូមផ្ញើរូបភាពមកដើម្បីប្តូរពណ៌!</b>")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    user_id = message.from_user.id
    photo_id = message.photo[-1].file_id
    msg = await message.reply("⚡ <b>កំពុងដំណើរការ...</b>")
    try:
        file_i = await bot.get_file(photo_id)
        p_bytes = await bot.download_file(file_i.file_path)
        input_d = p_bytes.read()
        user_last_image[user_id] = input_d
        out_d = remove(input_d, session=fast_session)
        
        color_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬜ ស", callback_data="bg_white"), InlineKeyboardButton(text="⬛ ខ្មៅ", callback_data="bg_black")],
            [InlineKeyboardButton(text="🟦 ខៀវ", callback_data="bg_blue"), InlineKeyboardButton(text="🟥 ក្រហម", callback_data="bg_red")],
            [InlineKeyboardButton(text="🖼️ ភាពថ្លា", callback_data="bg_trans")]
        ])
        await message.answer_document(BufferedInputFile(out_d, filename="RAA_BG.png"), caption="<b>✅ រួចរាល់! ប្តូរពណ៌ខាងក្រោម៖</b>", reply_markup=color_kb)
        await msg.delete()
    except Exception as e: await msg.edit_text(f"❌ Error: {str(e)}")

@dp.callback_query(F.data.startswith("bg_"))
async def change_color(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    color = callback.data.replace("bg_", "")
    if user_id not in user_last_image:
        await callback.answer("❌ សូមផ្ញើរូបភាពថ្មី!", show_alert=True)
        return
    try:
        c_map = {"white": (255, 255, 255), "black": (0, 0, 0), "blue": (0, 0, 255), "red": (255, 0, 0), "trans": (0,0,0,0)}
        out_d = remove(user_last_image[user_id], session=fast_session, bgcolor=c_map.get(color))
        await callback.message.answer_document(BufferedInputFile(out_d, filename=f"RAA_{color}.png"))
    except Exception as e: await callback.message.answer(f"❌ Error: {str(e)}")
    await callback.answer()

# --- ៦. ព័ត៌មានផ្សេងៗ ---
@dp.message(F.text == "ℹ️ ព័ត៌មាន Bot")
async def cmd_info(message: types.Message):
    await message.answer("<b>🤖 RaaBot Pro v10.0</b>\n• Auto Remove BG & Change Color\n• Google Recognition (4 Langs)\n• Dev: THEARA Rupp")

@dp.message(F.text == "👤 ទាក់ទង Admin")
async def cmd_admin(message: types.Message):
    await message.answer(f"<b>Admin:</b> <a href='{ADMIN_URL}'>OG_Raa1</a>")

async def main(): await dp.start_polling(bot)
if __name__ == "__main__": asyncio.run(main())
