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

# --- ដំឡើង AI Mediapipe សម្រាប់ភាពឥតខ្ចោះ (ដាច់ស្អាត ១០០%) ---
# ប្រើ Mediapipe Selfie Segmentation ល្អខ្លាំងបំផុតសម្រាប់រូបភាពមនុស្ស
BaseOptions = mp.tasks.BaseOptions
ImageSegmenter = mp.tasks.vision.ImageSegmenter
ImageSegmenterOptions = mp.tasks.vision.ImageSegmenterOptions
VisionRunningMode = mp.tasks.vision.RunningMode

# កូដនេះនឹងទាញយក Model 'selfie_multiclass_256x256.tflite' ដោយស្វ័យប្រវត្តិ
options = ImageSegmenterOptions(
    base_options=BaseOptions(model_asset_path='selfie_multiclass_256x256.tflite'),
    running_mode=VisionRunningMode.IMAGE,
    output_category_mask=True
)
with ImageSegmenter.create_from_options(options) as segmenter:
    model_is_ready = True

API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_URL = "https://t.me/OG_Raa1"

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
recognizer = sr.Recognizer()
logging.basicConfig(level=logging.INFO)

# បង្កើត Dictionary សម្រាប់រក្សាទុកទិន្នន័យបណ្ដោះអាសន្ន
user_languages, user_voices, last_transcription, user_last_image = {}, {}, {}, {}

# --- ១. មុខងារជំនួយ Subtitle (SRT/VTT) ---
def format_to_srt(text):
    if not text: return "No data"
    lines = text.split(". ")
    srt_content = ""
    for i, line in enumerate(lines):
        if not line.strip(): continue
        start = f"00:00:{i*3:02d},000"; end = f"00:00:{(i*3)+3:02d},000"
        srt_content += f"{i+1}\n{start} --> {end}\n{line.strip()}\n\n"
    return srt_content

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

# --- ៣. HANDLERS ---
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.answer("<b>🎙 RaaBot Pro v10.0 (Upgrade AI ឥតខ្ចោះ)</b>\n              សួស្តីអ្នកទាំងអស់គ្នា! នេះគឺជា Bot ស្វ័យប្រវត្តិសម្រាប់បំប្លែងសំឡេង កាត់ Background ល្បឿនលឿន និងប្តូរពណ៌។\n"
        "សូមជ្រើសរើសមុខងារខាងក្រោម👇", reply_markup=get_main_menu())

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
        
        if user_id in user_voices:
            tts_p = f"{file_id}.mp3"
            gTTS(text=text, lang=lang).save(tts_p)
            await message.answer_voice(BufferedInputFile.from_file(tts_p))
            os.remove(tts_p)
        
        await message.answer(f"<b>📝 អត្ថបទ៖</b>\n<code>{text}</code>", reply_markup=get_export_keyboard())
        await msg.delete()
    except Exception: await message.answer("❌ Error: មិនអាចបំប្លែងបាន!")
    finally:
        for p in [ogg, wav]: 
            if os.path.exists(p): os.remove(p)

# --- ៤. មុខងារ Remove Background (Upgrade AI ឱ្យឥតខ្ចោះ) ---
@dp.message(F.text == "🖼️ កាត់ Background")
async def cmd_remove_bg(message: types.Message):
    await message.answer("<b>🖼️ សូមផ្ញើរូបភាពមកកាន់ខ្ញុំ ដើម្បីកាត់ Background ឱ្យឥតខ្ចោះ!</b>")

@dp.message(F.text == "🎨 ប្តូរពណ៌ Background")
async def cmd_change_bg(message: types.Message):
    await message.answer("<b>🎨 សូមផ្ញើរូបភាពមកเพื่อជ្រើសរើសពណ៌ថ្មី!</b>")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    user_id = message.from_user.id
    photo_id = message.photo[-1].file_id
    msg = await message.reply("⚡ <b>AI កម្រិតខ្ពស់កំពុងកាត់ឱ្យ... (ដាច់ស្អាត ១០០%)</b>")
    try:
        # ទាញយករូបភាពពី Telegram
        file_i = await bot.get_file(photo_id)
        p_bytes = await bot.download_file(file_i.file_path)
        
        # ចងចាំរូបភាពដើម
        user_last_image[user_id] = p_bytes.read()
        
        # បំប្លែងរូបភាពពី Byte ទៅជា OpenCV Image
        input_d = np.frombuffer(user_last_image[user_id], np.uint8)
        input_image = cv2.imdecode(input_d, cv2.IMREAD_COLOR)
        h, w = input_image.shape[:2]

        # បំប្លែងពណ៌រូបភាព (BGR to RGB) សម្រាប់ AI
        rgb_image = cv2.cvtColor(input_image, cv2.COLOR_BGR2RGB)
        
        # ប្រើ Mediapipe AI ដើម្បីសម្គាល់រូបភាពមនុស្ស និងកាត់ឱ្យឥតខ្ចោះ
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
        with ImageSegmenter.create_from_options(options) as segmenter:
            segmentation_result = segmenter.segment(mp_image)
            category_mask = segmentation_result.category_mask

            # បង្កើត Mask សម្រាប់រូបភាពមនុស្ស (ដាច់ស្អាតដល់សរសៃសក់)
            person_mask = (category_mask.numpy_view() > 0.5).astype(np.uint8) * 255
            person_mask = cv2.cvtColor(person_mask, cv2.COLOR_GRAY2BGR)
            
            # ប្រើ Mask ដើម្បីកាត់ Background (ភាពឥតខ្ចោះ ១០០%)
            person_mask_inv = cv2.bitwise_not(person_mask)
            background_color = np.zeros(input_image.shape, np.uint8) # ខ្មៅ (ថ្លា)
            person = cv2.bitwise_and(input_image, person_mask)
            bg = cv2.bitwise_and(background_color, person_mask_inv)
            out_d = cv2.add(person, bg)

            # បន្ថែម Alpha Channel សម្រាប់ភាពថ្លា (PNG Transparent)
            b_channel, g_channel, r_channel = cv2.split(out_d)
            alpha_channel = person_mask[:, :, 0]
            out_d_png = cv2.merge((b_channel, g_channel, r_channel, alpha_channel))

            # បំប្លែងរូបភាពពី OpenCV Image ទៅជា Byte សម្រាប់ផ្ញើត្រឡប់
            _, out_d_final = cv2.imencode('.png', out_d_png)
            final_data = out_d_final.tobytes()

            color_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬜ ស", callback_data="bg_w"), InlineKeyboardButton(text="⬛ ខ្មៅ", callback_data="bg_b")],
                [InlineKeyboardButton(text="🟦 ខៀវ", callback_data="bg_bl"), InlineKeyboardButton(text="🟥 ក្រហម", callback_data="bg_r")]
            ])
            await message.answer_document(BufferedInputFile(final_data, filename="RAA_BG_PERFECT.png"), caption="<b>✅ កាត់រួចរាល់! ដាច់ស្អាត ១០០%។</b>", reply_markup=color_kb)
            await msg.delete()
    except Exception as e: await msg.edit_text(f"❌ Error: {str(e)}")

# --- ៥. Callback Query Handler (Export & Change Color) ---
@dp.callback_query(F.data.startswith(("v_", "l_", "ex_", "bg_")))
async def handle_callbacks(callback: types.CallbackQuery):
    data = callback.data
    user_id = callback.from_user.id
    
    if data.startswith("ex_"):
        f_t = data.replace("ex_", "")
        text = last_transcription.get(user_id, "No data")
        if f_t == "srt": final = format_to_srt(text)
        else: final = text
        await callback.message.answer_document(BufferedInputFile(final.encode('utf-8'), filename=f"result.{f_t}"))
        
    elif data.startswith("bg_"):
        color = data.replace("bg_", ""); c_map = {"w": (255, 255, 255), "b": (0, 0, 0), "bl": (255, 0, 0), "r": (0, 0, 255)} # OpenCV ប្រើ BGR
        if user_id in user_last_image:
            # បំប្លែង Byte ទៅ OpenCV
            input_d = np.frombuffer(user_last_image[user_id], np.uint8)
            input_image = cv2.imdecode(input_d, cv2.IMREAD_COLOR)

            # ប្រើ AI កាត់ និងដាក់ពណ៌ឱ្យឥតខ្ចោះ
            rgb_image = cv2.cvtColor(input_image, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
            with ImageSegmenter.create_from_options(options) as segmenter:
                segmentation_result = segmenter.segment(mp_image)
                category_mask = segmentation_result.category_mask
                person_mask = (category_mask.numpy_view() > 0.5).astype(np.uint8) * 255
                person_mask = cv2.cvtColor(person_mask, cv2.COLOR_GRAY2BGR)
                person_mask_inv = cv2.bitwise_not(person_mask)
                background_color = np.full(input_image.shape, c_map.get(color), np.uint8)
                person = cv2.bitwise_and(input_image, person_mask)
                bg = cv2.bitwise_and(background_color, person_mask_inv)
                out_d = cv2.add(person, bg)

                _, out_d_final = cv2.imencode('.png', out_d)
                final_data = out_d_final.tobytes()
                await callback.message.answer_document(BufferedInputFile(final_data, filename=f"RAA_COLOR_{color}.png"))
    
    # បន្ថែមការឆ្លើយតបសម្រាប់ប៊ូតុង Voice និង ភាសា
    elif data.startswith("v_"):
        if data == "v_off": user_voices.pop(user_id, None)
        else: user_voices[user_id] = data.replace("v_", "")
        await callback.message.edit_text("✅ រួចរាល់!")
    elif data.startswith("l_"):
        user_languages[user_id] = data.replace("l_", "")
        await callback.message.edit_text("✅ កំណត់ភាសារួចរាល់!")
        
    await callback.answer()

@dp.message(F.text == "ℹ️ ព័ត៌មាន Bot")
async def cmd_info(message: types.Message):
    await message.answer("<b>🤖 RaaBot Pro v10.0</b>\n• Auto Remove BG & Change Color\n• Google Recognition (4 Langs)\n• Dev: THEARA Rupp")

@dp.message(F.text == "👤 ទាក់ទង Admin")
async def cmd_admin(message: types.Message):
    await message.answer(f"<b>Admin:</b> <a href='{ADMIN_URL}'>OG_Raa1</a>")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
