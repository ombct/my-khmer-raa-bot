import os
import logging
import asyncio
import speech_recognition as sr
from datetime import timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardButton, InlineKeyboardMarkup, 
    BufferedInputFile
)
from groq import Groq
from pydub import AudioSegment

# --- CONFIGURATION ---
API_TOKEN = os.getenv('BOT_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_KEY')
ADMIN_URL = "https://t.me/OG_Raa1"

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
groq_client = Groq(api_key=GROQ_API_KEY)
recognizer = sr.Recognizer()
logging.basicConfig(level=logging.INFO)

# វចនានុក្រមរក្សាទុកភាសាដែល User ជ្រើសរើស ( Default: ខ្មែរ)
user_languages = {}

# --- KEYBOARDS ---
def get_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🌐 ប្តូរភាសា (Language)"), KeyboardButton(text="ℹ️ ព័ត៌មាន Bot")],
            [KeyboardButton(text="👤 ទាក់ទង Admin")]
        ],
        resize_keyboard=True
    )

def get_lang_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇰🇭 ខ្មែរ (Khmer)", callback_data="setlang_km")],
        [InlineKeyboardButton(text="🇺🇸 អង់គ្លេស (English)", callback_data="setlang_en")],
        [InlineKeyboardButton(text="🇨🇳 ចិន (Chinese)", callback_data="setlang_zh")]
    ])
    return keyboard

# --- SRT HELPER ---
def format_timestamp(seconds: float):
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int(td.microseconds / 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

# --- បន្ថែម៖ Handler សម្រាប់ព័ត៌មាន Bot ---
@dp.message(F.text == "ℹ️ ព័ត៌មាន Bot")
async def cmd_info(message: types.Message):
    info_text = (
        "🤖 **ព័ត៌មានអំពី Bot**\n\n"
        "• **បេសកកម្ម៖** បំប្លែងសំឡេងទៅជាអត្ថបទ និងឯកសារ SRT\n"
        "• **បច្ចេកវិទ្យា៖** Google Speech API & Groq Whisper-v3\n"
        "• **កំណែប្រែ៖** v6.2 (Stable)\n"
        "• **លក្ខណៈពិសេស៖** គាំទ្រអក្សរខ្មែរមានដៃជើង និងម៉ោងរត់ត្រឹមត្រូវ\n"
        "• **រៀបចំដោយ៖** THEARA Rupp"
    )
    await message.answer(info_text, parse_mode="Markdown")
# --- បន្ថែម៖ Handler សម្រាប់ទាក់ទង Admin ---
@dp.message(F.text == "👤 ទាក់ទង Admin")
async def cmd_admin(message: types.Message):
    admin_btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 ផ្ញើសារទៅ Admin", url=ADMIN_URL)]
    ])
    await message.answer("ប្រសិនបើបងប្អូនមានបញ្ហា ឬចម្ងល់ផ្សេងៗ សូមចុចប៊ូតុងខាងក្រោម៖", reply_markup=admin_btn)    
# --- HANDLERS ---
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    welcome_text = (
        "🎙 **សូមស្វាគមន៍មកកាន់ Bot បំប្លែងសំឡេង!**\n\n"
        "កូដត្រូវបានពង្រឹងឱ្យស្គាល់ **អក្សរខ្មែរមានដៃជើង** ត្រឹមត្រូវ (v6.1)\n"
        "សូមជ្រើសរើសភាសាបំប្លែងរបស់អ្នកខាងក្រោម៖"
    )
    await message.answer(welcome_text, reply_markup=get_main_menu(), parse_mode="Markdown")
    await message.answer("ជ្រើសរើសភាសាគោលដៅ៖", reply_markup=get_lang_keyboard())

@dp.message(F.text == "🌐 ប្តូរភាសា (Language)")
async def change_lang(message: types.Message):
    await message.answer("សូមជ្រើសរើសភាសាដែលអ្នកចង់បំប្លែង៖", reply_markup=get_lang_keyboard())

@dp.callback_query(F.data.startswith("setlang_"))
async def process_lang_selection(callback: types.CallbackQuery):
    lang_code = callback.data.split("_")[1]
    user_languages[callback.from_user.id] = lang_code
    
    names = {"km": "ខ្មែរ 🇰🇭", "en": "English 🇺🇸", "zh": "Chinese 🇨🇳"}
    await callback.message.edit_text(f"✅ បានកំណត់យកភាសា៖ **{names[lang_code]}**")
    await callback.answer()

@dp.message(F.voice | F.audio)
async def handle_audio(message: types.Message):
    # ទាញយកភាសា (Default: ខ្មែរ)
    lang = user_languages.get(message.from_user.id, "km")
    google_lang = {"km": "km-KH", "en": "en-US", "zh": "zh-CN"}[lang]
    
    msg = await message.answer("⏳ កំពុងស្តាប់ និងកំណត់ត្រាម៉ោងអក្សរ (SRT) ភាសា {}... សូមរង់ចាំ".format(lang.upper()))
    
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await bot.get_file(file_id)
    ogg_path = f"{file_id}.ogg"
    wav_path = f"{file_id}.wav"
    await bot.download_file(file.file_path, ogg_path)

    try:
        # បំប្លែងឯកសារទៅជា WAV សម្រាប់ SpeechRecognition
        audio_segment = AudioSegment.from_file(ogg_path)
        audio_segment.export(wav_path, format="wav")

        # ១. ប្រើ SpeechRecognition (Google API) សម្រាប់អត្ថបទសង្ខេប
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            google_text = recognizer.recognize_google(audio_data, language=google_lang)

        # ២. ប្រើ Groq Whisper ដើម្បីបង្កើត SRT ដែលមានម៉ោងរត់ត្រូវជាមួយមាត់និយាយ
        with open(wav_path, "rb") as audio_file:
            # ចំណុចសំខាន់ដើម្បីឱ្យស្គាល់ខ្មែរមានដៃជើងគឺត្រង់ prompt នេះ
            response = groq_client.audio.transcriptions.create(
                file=(wav_path, audio_file.read()),
                model="whisper-large-v3",
                response_format="verbose_json", # យកទិន្នន័យម៉ោងលម្អិត
                language=lang,
                prompt="នេះគឺជាសំឡេងនិយាយភាសាខ្មែរ។ សូមសរសេរជាអក្សរខ្មែរឱ្យបានត្រឹមត្រូវបំផុតតាមអក្ខរាវិរុទ្ធ មានស្រៈត្រឹមត្រូវ មានជើងអក្សរច្បាស់លាស់ និងសញ្ញាខណ្ឌឱ្យបានច្បាស់លាស់។"
            )

        # ផ្ញើអត្ថបទសង្ខេប (យកពី Google ព្រោះ Google recognize ខ្មែរបានត្រូវជាង Whisper នៅដុំៗ)
        await message.answer(f"📝 **អត្ថបទបំប្លែងរួច ({lang.upper()}):**\n\n{google_text}")

        # បង្កើតឯកសារ SRT ពីទិន្នន័យ Groq (ព្រោះ Groq ផ្ដល់ Time-Sync ច្បាស់លាស់)
        srt_content = ""
        for i, segment in enumerate(response.segments, start=1):
            start = format_timestamp(segment['start'])
            end = format_timestamp(segment['end'])
            # ពង្រឹងអក្សរក្នុង SRT ឱ្យមានដៃជើង និងមានរបៀបរៀបរយ
            text = segment['text'].strip()
            if not text: continue # រំលងបើអត់មានអក្សរ
            
            srt_content += f"{i}\n{start} --> {end}\n{text}\n\n"

        # បំប្លែងទៅជា File SRT ដោយប្រើ Encoding UTF-8 ដើម្បីឱ្យស្គាល់ខ្មែរ
        srt_file = BufferedInputFile(srt_content.encode('utf-8'), filename=f"sub_{lang}_sync.srt")
        await message.answer_document(srt_file, caption=f"🎬 ឯកសារ SRT ភាសា {lang.upper()} ដែលមានម៉ោងរត់ត្រូវជាមួយមាត់និយាយ (v6.1 - High Khmer Accuracy)!")
        
        await msg.delete()

    except Exception as e:
        await msg.edit_text(f"❌ កំហុស៖ {str(e)}")
    finally:
        for p in [ogg_path, wav_path]:
            if os.path.exists(p): os.remove(p)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
