import os
import logging
import asyncio
import unicodedata
from datetime import timedelta

import speech_recognition as sr
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardButton, InlineKeyboardMarkup,
    BufferedInputFile
)

from groq import Groq
from pydub import AudioSegment
from gtts import gTTS

# --- CONFIG ---
API_TOKEN = os.getenv('BOT_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_KEY')

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
groq_client = Groq(api_key=GROQ_API_KEY)

logging.basicConfig(level=logging.INFO)
recognizer = sr.Recognizer()

user_settings = {}

# --- KHMER FIX ---
def clean_khmer_text(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("�", "")
    return text.strip()

# --- TIME FORMAT ---
def format_timestamp(seconds: float, fmt="srt"):
    td = timedelta(seconds=seconds)
    total = int(td.total_seconds())
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    ms = int(td.microseconds / 1000)

    if fmt == "vtt":
        return f"{h:02}:{m:02}:{s:02}.{ms:03}"
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

# --- ASS STYLE ---
def generate_ass(segments):
    header = """[Script Info]
Title: Khmer Subtitle
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Khmer OS Battambang,28,&H00FFFFFF,&H00000000,&H64000000,0,0,1,2,1,2,10,10,20,1

[Events]
Format: Layer, Start, End, Style, Text
"""
    body = ""
    for s in segments:
        start = format_timestamp(s['start']).replace(",", ".")
        end = format_timestamp(s['end']).replace(",", ".")
        text = clean_khmer_text(s['text'])
        body += f"Dialogue: 0,{start},{end},Default,{text}\n"

    return header + body

# --- VOICE ---
def generate_voice(text, path="voice.mp3"):
    tts = gTTS(text=text, lang='km')
    tts.save(path)
    return path

# --- KEYBOARDS ---
def get_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🌐 ប្តូរភាសា"), KeyboardButton(text="🔢 ចំនួនពាក្យ")],
            [KeyboardButton(text="ℹ️ ព័ត៌មាន Bot")]
        ],
        resize_keyboard=True
    )

def get_format_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 SRT", callback_data="fmt_srt"),
         InlineKeyboardButton(text="🎨 ASS", callback_data="fmt_ass")],
        [InlineKeyboardButton(text="📋 TXT", callback_data="fmt_txt"),
         InlineKeyboardButton(text="📺 VTT", callback_data="fmt_vtt")],
        [InlineKeyboardButton(text="🎤 Voice Khmer", callback_data="fmt_voice")]
    ])

# --- START ---
@dp.message(Command("start"))
async def start(message: types.Message):
    user_settings[message.from_user.id] = {'lang': 'km', 'words': 3}
    await message.answer("🎙 ផ្ញើ Audio → បង្កើត Subtitle Khmer + Voice", reply_markup=get_main_menu())

# --- AUDIO ---
@dp.message(F.voice | F.audio)
async def handle_audio(message: types.Message):
    user_id = message.from_user.id
    msg = await message.answer("⏳ កំពុងដំណើរការ...")

    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await bot.get_file(file_id)

    ogg = f"{file_id}.ogg"
    wav = f"{file_id}.wav"

    await bot.download_file(file.file_path, ogg)

    try:
        AudioSegment.from_file(ogg).export(wav, format="wav")

        with open(wav, "rb") as f:
            res = groq_client.audio.transcriptions.create(
                file=(wav, f.read()),
                model="whisper-large-v3",
                response_format="verbose_json",
                language="km",
                prompt="អក្សរខ្មែរត្រឹមត្រូវ"
            )

        await message.answer(f"📝 {res.text}")

        user_settings[user_id]['segments'] = res.segments

        await msg.edit_text("✅ រួចរាល់! ជ្រើស format:", reply_markup=get_format_keyboard())

    except Exception as e:
        await msg.edit_text(f"❌ Error: {e}")

    finally:
        for f in [ogg, wav]:
            if os.path.exists(f):
                os.remove(f)

# --- FORMAT ---
@dp.callback_query(F.data.startswith("fmt_"))
async def format_handler(callback: types.CallbackQuery):
    fmt = callback.data.split("_")[1]
    segments = user_settings.get(callback.from_user.id, {}).get('segments')

    if not segments:
        await callback.answer("❌ No data", show_alert=True)
        return

    content = ""
    filename = f"file.{fmt}"

    if fmt == "srt":
        for i, s in enumerate(segments, 1):
            text = clean_khmer_text(s['text'])
            content += f"{i}\n{format_timestamp(s['start'])} --> {format_timestamp(s['end'])}\n{text}\n\n"

    elif fmt == "ass":
        content = generate_ass(segments)

    elif fmt == "txt":
        content = "\n".join([clean_khmer_text(s['text']) for s in segments])

    elif fmt == "vtt":
        content = "WEBVTT\n\n" + "\n".join([
            f"{format_timestamp(s['start'],'vtt')} --> {format_timestamp(s['end'],'vtt')}\n{clean_khmer_text(s['text'])}\n"
            for s in segments
        ])

    elif fmt == "voice":
        full_text = " ".join([clean_khmer_text(s['text']) for s in segments])
        path = generate_voice(full_text)

        with open(path, "rb") as f:
            await callback.message.answer_document(
                BufferedInputFile(f.read(), "voice.mp3"),
                caption="🎤 Khmer Voice Ready"
            )
        os.remove(path)
        await callback.answer()
        return

    file = BufferedInputFile(content.encode("utf-8-sig"), filename)
    await callback.message.answer_document(file, caption=f"✅ {fmt.upper()} Ready!")
    await callback.answer()

# --- RUN ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
