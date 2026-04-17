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

# --- ការកំណត់សម្រាប់ការកាត់ឱ្យលឿន និងប្តូរពណ៌ ---
from rembg import remove, new_session
from PIL import Image

# បង្កើត Session ទុកជាមុនដើម្បីកុំឱ្យវា Load យូរពេល User ផ្ញើរូបមក
# ប្រើ Model 'u2net_lite' ដើម្បីឱ្យលឿនបំផុត
fast_session = new_session("u2net_lite") 

# --- CONFIGURATION ---
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_URL = "https://t.me/OG_Raa1"

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
recognizer = sr.Recognizer()
logging.basicConfig(level=logging.INFO)

user_languages = {}
user_voices = {}
last_transcription = {}
last_input_data = {} # សម្រាប់រក្សារូបភាពដើមទុករក្សាពណ៌

# --- KEYBOARDS (រក្សាភាសា និងទម្រង់ដើម) ---
def get_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🌐 ប្តូរភាសា (Language)"), KeyboardButton(text="🎙️ ជ្រើសរើសសំឡេង AI")],
            [KeyboardButton(text="🖼️ Remove Background"), KeyboardButton(text="ℹ️ ព័ត៌មាន Bot")],
            [KeyboardButton(text="👤 ទាក់ទង Admin")]
        ],
        resize_keyboard=True
    )

def get_lang_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇰🇭 ខ្មែរ (Khmer)", callback_data="setlang_km")],
        [InlineKeyboardButton(text="🇺🇸 English", callback_data="setlang_en")],
        [InlineKeyboardButton(text="🇯🇵 Japanese (日本語)", callback_data="setlang_ja")],
        [InlineKeyboardButton(text="🇨🇳 Chinese (中文)", callback_data="setlang_zh")]
    ])

def get_file_type_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 PDF", callback_data="export_pdf"), InlineKeyboardButton(text="📝 DOCX", callback_data="export_docx")],
        [InlineKeyboardButton(text="📋 TXT", callback_data="export_txt"), InlineKeyboardButton(text="📊 XLSX", callback_data="export_xlsx")],
        [InlineKeyboardButton(text="🎬 SRT", callback_data="export_srt"), InlineKeyboardButton(text="📺 VTT", callback_data="export_vtt")],
        [InlineKeyboardButton(text="🎞 ASS", callback_data="export_ass"), InlineKeyboardButton(text="📦 JSON", callback_data="export_json")]
    ])

# មុខងារថ្មី៖ Keybaord សម្រាប់ជ្រើសរើសពណ៌ Background
def get_color_keyboard(file_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬜ ពណ៌ស", callback_data=f"color_white_{file_id}"), InlineKeyboardButton(text="⬛ ពណ៌ខ្មៅ", callback_data=f"color_black_{file_id}")],
        [InlineKeyboardButton(text="🟦 ពណ៌ខៀវ", callback_data=f"color_blue_{file_id}"), InlineKeyboardButton(text="🟥 ពណ៌ក្រហម", callback_data=f"color_red_{file_id}")],
        [InlineKeyboardButton(text="🖼️ ភាពថ្លា (Transparent)", callback_data=f"color_transparent_{file_id}")],
        [InlineKeyboardButton(text="❌ បោះបង់", callback_data="cancel_color")]
    ])

# --- មុខងារគណនាពណ៌ (សម្រាប់ប្រើជំនួយ) ---
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

# --- HANDLERS ---

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.answer(
        "<b>🎙 ស្វាគមន៍មកកាន់ RaaBot Pro v10.0</b>\n\n"
        "សួស្តីអ្នកទាំងអស់គ្នា! នេះគឺជា Bot ស្វ័យប្រវត្តិសម្រាប់បំប្លែងសំឡេង កាត់ Background ល្បឿនលឿន និងប្តូរពណ៌។\n"
        "សូមជ្រើសរើសមុខងារខាងក្រោម៖", 
        reply_markup=get_main_menu()
    )

# --- មុខងារកាត់រូបភាពល្បឿនលឿន និងប្តូរពណ៌ ---
@dp.message(F.photo)
async def ask_remove_bg_with_color(message: types.Message):
    photo_id = message.photo[-1].file_id
    msg = await message.reply("⚡ <b>កំពុងកាត់ Background យ៉ាងលឿនបំផុត...</b>")
    
    try:
        # ទាញយករូបភាពពី Telegram
        file_info = await bot.get_file(photo_id)
        photo_bytes = await bot.download_file(file_info.file_path)
        input_data = photo_bytes.read()

        # រក្សារូបភាពដើមទុកសម្រាប់ប្រើពេលដូរពណ៌
        last_input_data[photo_id] = input_data

        # កាត់ Background យ៉ាងលឿន (ភាពថ្លា)
        output_data = remove(input_data, session=fast_session)

        # ផ្ញើលទ្ធផល (ភាពថ្លា) ទៅ User សិន
        await message.answer_document(
            BufferedInputFile(output_data, filename="RAA_NO_BG.png"),
            caption="<b>✅ កាត់រួចរាល់យ៉ាងរហ័ស!</b>\n\n"
                    "<i>តើប្អូនចង់ដាក់ពណ៌ Background ជំនួសទេ? សូមជ្រើសរើសពណ៌ខាងក្រោម៖</i>",
            reply_markup=get_color_keyboard(photo_id)
        )
        await msg.delete()
        
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")

# Handler សម្រាប់ទទួលការចុចប៊ូតុងពណ៌
@dp.callback_query(F.data.startswith("color_"))
async def process_color_change(callback: types.CallbackQuery):
    color_code = callback.data.split("_")[1]
    file_id = callback.data.split("_")[2]
    
    if file_id not in last_input_data:
        await callback.message.edit_text("❌ Error: មិនមានទិន្នន័យរូបភាពដើម។ សូមផ្ញើរូបភាពម្ដងទៀត។")
        await callback.answer()
        return

    await callback.message.edit_text(f"⚡ <b>កំពុងដាក់ពណ៌ Background ({color_code.upper()})...</b>")
    
    try:
        # ទាញយករូបភាពដើម
        input_data = last_input_data[file_id]
        
        # កំណត់ពណ៌
        if color_code == "transparent":
            bg_color = (0, 0, 0, 0) # គ្មានពណ៌
        else:
            # បំប្លែងឈ្មោះពណ៌ទៅជា RGB
            color_map = {
                "white": (255, 255, 255),
                "black": (0, 0, 0),
                "blue": (0, 0, 255),
                "red": (255, 0, 0)
            }
            bg_color = color_map.get(color_code, (255, 255, 255))
        
        # ដំណើរការកាត់ Background និងដាក់ពណ៌ដោយ rembg (លឿនខ្លាំង)
        output_data = remove(input_data, session=fast_session, bgcolor=bg_color)
        
        # ផ្ញើលទ្ធផលថ្មី
        await callback.message.answer_document(
            BufferedInputFile(output_data, filename=f"RAA_BG_{color_code.upper()}.png"),
            caption=f"<b>✅ បានដាក់ពណ៌ Background {color_code.upper()} រួចរាល់!</b>"
        )
        await callback.message.delete()
        
    except Exception as e:
        await callback.message.edit_text(f"❌ កំហុសបច្ចេកទេស: {str(e)}")
    await callback.answer()

@dp.callback_query(F.data == "cancel_color")
async def cancel_color(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer()

# --- មុខងារសំឡេង (រក្សាទម្រង់ដើម - ភាសាទាំង ៤) ---
@dp.message(F.voice | F.audio)
async def handle_audio(message: types.Message):
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "km")
    voice_choice = user_voices.get(user_id, None)
    google_lang = {"km": "km-KH", "en": "en-US", "ja": "ja-JP", "zh": "zh-CN"}.get(lang, "km-KH")
    
    msg = await message.answer(f"<b>⏳ កំពុងបំប្លែងសំឡេង ({lang.upper()}) ដោយ Google...</b>")
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await bot.get_file(file_id)
    ogg_path, wav_path = f"{file_id}.ogg", f"{file_id}.wav"
    await bot.download_file(file.file_path, ogg_path)

    try:
        AudioSegment.from_file(ogg_path).export(wav_path, format="wav")
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            text_result = recognizer.recognize_google(audio_data, language=google_lang)
        last_transcription[user_id] = text_result

        if voice_choice:
            tts_path = f"{file_id}_ai.mp3"
            gTTS(text=text_result, lang=lang).save(tts_path)
            await message.answer_voice(BufferedInputFile.from_file(tts_path))
            if os.path.exists(tts_path): os.remove(tts_path)

        await message.answer(f"<b>📝 អត្ថបទ (Google):</b>\n\n<code>{text_result}</code>")
        await message.answer("<b>✅ រួចរាល់! សូមជ្រើសរើសប្រភេទ File:</b>", reply_markup=get_file_type_keyboard())
        await msg.delete()
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")
    finally:
        for p in [ogg_path, wav_path]:
            if os.path.exists(p): os.remove(p)

@dp.callback_query(F.data.startswith("export_"))
async def process_export(callback: types.CallbackQuery):
    file_type = callback.data.split("_")[1]
    text = last_transcription.get(callback.from_user.id, "មិនមានទិន្នន័យ")
    content = f"1\n00:00:00,000 --> 00:00:10,000\n{text}" if file_type == "srt" else text
    await callback.message.answer_document(
        BufferedInputFile(content.encode('utf-8'), filename=f"raa_file.{file_type}"),
        caption=f"<b>🎬 ឯកសារ {file_type.upper()} រួចរាល់!</b>"
    )
    await callback.answer()

@dp.message(F.text == "🌐 ប្តូរភាសា (Language)")
async def change_lang(message: types.Message):
    await message.answer("<b>🌐 សូមជ្រើសរើសភាសា:</b>", reply_markup=get_lang_keyboard())

@dp.callback_query(F.data.startswith("setlang_"))
async def set_lang(callback: types.CallbackQuery):
    lang_code = callback.data.split("_")[1]
    user_languages[callback.from_user.id] = lang_code
    await callback.message.edit_text(f"✅ បានកំណត់ភាសាទៅជា: <b>{lang_code.upper()}</b>")
    await callback.answer()

@dp.message(F.text == "🎙️ ជ្រើសរើសសំឡេង AI")
async def choose_voice(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👩 ស្រី", callback_data="setvoice_female"), InlineKeyboardButton(text="👨 ប្រុស", callback_data="setvoice_male")]])
    await message.answer("<b>🎙️ សូមជ្រើសរើសភេទសំឡេង AI:</b>", reply_markup=kb)

@dp.callback_query(F.data.startswith("setvoice_"))
async def set_voice(callback: types.CallbackQuery):
    user_voices[callback.from_user.id] = callback.data.split("_")[1]
    await callback.message.edit_text("✅ បានកំណត់សំឡេង AI រួចរាល់!")
    await callback.answer()

@dp.message(F.text == "ℹ️ ព័ត៌មាន Bot")
async def cmd_info(message: types.Message):
    await message.answer("<b>🤖 RaaBot Pro v10.0</b>\n• Ultra Fast Auto Remove BG\n• Change Background Color\n• Google Recognition (4 Langs)\n• Dev: THEARA Rupp")

@dp.message(F.text == "👤 ទាក់ទង Admin")
async def cmd_admin(message: types.Message):
    await message.answer(f"<b>ទាក់ទង Admin:</b> <a href='{ADMIN_URL}'>OG_Raa1</a>")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
