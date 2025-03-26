import json
import asyncio
import random
from telegram import Update, Poll, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, PollAnswerHandler, CallbackQueryHandler, CallbackContext
import os
import signal
import atexit

TOKEN = os.getenv("BOT_TOKEN", "7061995193:AAFMOJNR39xJdMqwDBTqShPa_ayXRfwDyzk")
kullanici_verileri = {}
quiz_katalogu = {"A1": [], "A2": [], "B1": [], "B2": []}

def quiz_dosyalarini_yukle(dizin="quizzes"):
    global quiz_katalogu
    quiz_katalogu = {"A1": [], "A2": [], "B1": [], "B2": []}
    bolumler = ["A1", "A2", "B1", "B2"]
    
    if not os.path.exists(dizin):
        os.makedirs(dizin)
    
    for bolum in bolumler:
        bolum_dizini = os.path.join(dizin, bolum)
        if not os.path.exists(bolum_dizini):
            os.makedirs(bolum_dizini)
        
        for dosya_adi in os.listdir(bolum_dizini):
            if dosya_adi.endswith(".json"):
                dosya_yolu = os.path.join(bolum_dizini, dosya_adi)
                try:
                    with open(dosya_yolu, "r", encoding="utf-8") as dosya:
                        quiz_verileri = json.load(dosya)
                        if "name" in quiz_verileri and "questions" in quiz_verileri:
                            quiz_verileri["bolum"] = bolum  # Bölüm ekleniyor
                            quiz_katalogu[bolum].append(quiz_verileri)
                except (json.JSONDecodeError, FileNotFoundError) as hata:
                    print(f"{bolum}/{dosya_adi} dosyasını okurken hata: {hata}")

async def bot_komutlarini_ayarla(bot):
    komutlar = [
        BotCommand("start", "Testi başlat"),
        BotCommand("restart", "Testi yeniden başlat"),
        BotCommand("stop", "Testi durdur"),
        BotCommand("quizlist", "Test listesi")
    ]
    await bot.set_my_commands(komutlar)

async def start(update: Update, context: CallbackContext) -> None:
    quiz_dosyalarini_yukle()
    if not any(quiz_katalogu[bolum] for bolum in quiz_katalogu):
        await update.message.reply_text("Hata! Hiçbir test dosyası bulunamadı.")
        return

    if context.args and len(context.args) > 0 and context.args[0].startswith("quiz_"):
        try:
            quiz_idx = int(context.args[0].split("_")[1])
            bolum = context.args[0].split("_")[2]  # Bölüm eklendi
            await aralik_secimi_goster(update, context, update.message.chat_id, bolum, quiz_idx)
            return
        except (IndexError, ValueError):
            pass

    await bolumleri_goster(update, context, update.message.chat_id)

async def quiz_listesi(update: Update, context: CallbackContext) -> None:
    sohbet_id = update.message.chat_id
    await bolumleri_goster(update, context, sohbet_id)

async def bolumleri_goster(update: Update, context: CallbackContext, sohbet_id: int) -> None:
    quiz_dosyalarini_yukle()
    klavye = [
        [InlineKeyboardButton("A1", callback_data="bolum_A1")],
        [InlineKeyboardButton("A2", callback_data="bolum_A2")],
        [InlineKeyboardButton("B1", callback_data="bolum_B1")],
        [InlineKeyboardButton("B2", callback_data="bolum_B2")]
    ]
    cevap_isareti = InlineKeyboardMarkup(klavye)
    await context.bot.send_message(sohbet_id, "Aşağıdaki bölümlerden birini seçin:", reply_markup=cevap_isareti)

async def quiz_listesini_goster(update: Update, context: CallbackContext, sohbet_id: int, bolum: str) -> None:
    quiz_dosyalarini_yukle()
    if not quiz_katalogu[bolum]:
        await context.bot.send_message(sohbet_id, f"{bolum} bölümünde hiçbir test bulunamadı.")
        return

    klavye = []
    for idx, quiz in enumerate(quiz_katalogu[bolum]):
        klavye.append([
            InlineKeyboardButton(f"📖 {quiz['name']}", callback_data=f"select_quiz_{idx}_{bolum}"),
            InlineKeyboardButton("📤 Paylaş", switch_inline_query=f"Test: {quiz['name']} - https://t.me/{context.bot.username}?start=quiz_{idx}_{bolum}")
        ])

    cevap_isareti = InlineKeyboardMarkup(klavye)
    await context.bot.send_message(sohbet_id, f"{bolum} bölümündeki testlerden birini seçin:", reply_markup=cevap_isareti)

async def aralik_secimi_goster(update: Update, context: CallbackContext, sohbet_id: int, bolum: str, quiz_idx: int) -> None:
    if bolum not in quiz_katalogu or quiz_idx >= len(quiz_katalogu[bolum]):
        await context.bot.send_message(sohbet_id, "Hata! Seçilen test bulunamadı.")
        return

    quiz_verileri = quiz_katalogu[bolum][quiz_idx]
    toplam_soru = len(quiz_verileri["questions"])

    araliklar = []
    adim = 20
    for baslangic in range(0, toplam_soru, adim):
        bitis = min(baslangic + adim, toplam_soru)
        araliklar.append((baslangic, bitis))

    if not araliklar:
        await context.bot.send_message(sohbet_id, "Hata! Bu testte yeterli soru yok.")
        return

    klavye = [
        [InlineKeyboardButton(f"{baslangic + 1}-{bitis}", callback_data=f"start_quiz_{quiz_idx}_{bolum}_{baslangic}_{bitis}")]
        for baslangic, bitis in araliklar
    ]
    cevap_isareti = InlineKeyboardMarkup(klavye)
    await context.bot.send_message(sohbet_id, f"{quiz_verileri['name']} için soru aralığını seçin:", reply_markup=cevap_isareti)

async def dugme_yonetici(update: Update, context: CallbackContext) -> None:
    sorgu = update.callback_query
    await sorgu.answer()

    sohbet_id = sorgu.message.chat_id
    veri = sorgu.data

    if veri.startswith("bolum_"):
        bolum = veri.split("_")[1]
        await quiz_listesini_goster(update, context, sohbet_id, bolum)
    elif veri.startswith("select_quiz_"):
        parcalar = veri.split("_")
        quiz_idx = int(parcalar[2])
        bolum = parcalar[3]
        await aralik_secimi_goster(update, context, sohbet_id, bolum, quiz_idx)
    elif veri.startswith("start_quiz_"):
        parcalar = veri.split("_")
        quiz_idx = int(parcalar[2])
        bolum = parcalar[3]
        baslangic_idx = int(parcalar[4])
        bitis_idx = int(parcalar[5])
        await quiz_gonder(update, context, sohbet_id, bolum, quiz_idx, baslangic_idx, bitis_idx)
    elif veri == "restart_quiz":
        await yeniden_baslat(update, context)
    elif veri == "stop_quiz":
        await durdur(update, context)

async def yeniden_baslat(update: Update, context: CallbackContext) -> None:
    sohbet_id = update.effective_chat.id
    if sohbet_id not in kullanici_verileri:
        await context.bot.send_message(sohbet_id, "Şu anda aktif bir test yok. Testi başlatmak için bir test seçin.")
        return

    bolum = kullanici_verileri[sohbet_id]["bolum"]
    quiz_idx = kullanici_verileri[sohbet_id]["quiz_idx"]
    baslangic_idx = kullanici_verileri[sohbet_id]["start_idx"]
    bitis_idx = kullanici_verileri[sohbet_id]["end_idx"]
    await gorevleri_temizle(sohbet_id)
    del kullanici_verileri[sohbet_id]
    await quiz_gonder(update, context, sohbet_id, bolum, quiz_idx, baslangic_idx, bitis_idx)
    await context.bot.send_message(sohbet_id, "Test yeniden başlatıldı!")

async def durdur(update: Update, context: CallbackContext) -> None:
    sohbet_id = update.effective_chat.id
    if sohbet_id not in kullanici_verileri:
        await context.bot.send_message(sohbet_id, "Şu anda aktif bir test yok. Testi başlatmak için bir test seçin.")
        return

    await quiz_bitir(update, context, sohbet_id)
    await context.bot.send_message(sohbet_id, "Test durduruldu!")

async def quiz_gonder(update: Update, context: CallbackContext, sohbet_id: int, bolum: str, quiz_idx: int, baslangic_idx: int, bitis_idx: int) -> None:
    if bolum not in quiz_katalogu or quiz_idx >= len(quiz_katalogu[bolum]):
        await context.bot.send_message(sohbet_id, "Hata! Seçilen test bulunamadı.")
        return

    quiz_verileri = quiz_katalogu[bolum][quiz_idx]
    toplam_soru = len(quiz_verileri["questions"])
    if baslangic_idx >= toplam_soru or bitis_idx > toplam_soru or baslangic_idx >= bitis_idx:
        await context.bot.send_message(sohbet_id, "Hata! Geçersiz aralık seçildi.")
        return

    await context.bot.send_message(sohbet_id, f"📌 {quiz_verileri['name']} testi başlıyor! ({baslangic_idx + 1}-{bitis_idx} sorular)")

    sorular = quiz_verileri["questions"][baslangic_idx:bitis_idx].copy()
    random.shuffle(sorular)

    kullanici_verileri[sohbet_id] = {
        "skor": 0,
        "mevcut_soru": 0,
        "bolum": bolum,
        "quiz_idx": quiz_idx,
        "start_idx": baslangic_idx,
        "end_idx": bitis_idx,
        "questions": sorular,
        "anket_mesajlari": {},
        "dogru_secenek_idleri": {},
        "son_zamanlayici_metin": ""
    }

    await sonraki_soruyu_gonder(update, context, sohbet_id)

async def sonraki_soruyu_gonder(update: Update, context: CallbackContext, sohbet_id: int) -> None:
    kullanici = kullanici_verileri.get(sohbet_id)
    if not kullanici:
        return

    if kullanici["mevcut_soru"] < len(kullanici["questions"]):
        soru = kullanici["questions"][kullanici["mevcut_soru"]]
        bekleme_suresi = soru.get("time", 10)

        secenekler = soru["answers"].copy()
        dogru_cevap = soru["correct_answer"]
        random.shuffle(secenekler)
        yeni_dogru_secenek_id = secenekler.index(soru["answers"][dogru_cevap])

        anket_mesaji = await context.bot.send_poll(
            chat_id=sohbet_id,
            question=soru["question"],
            options=secenekler,
            type=Poll.QUIZ,
            correct_option_id=yeni_dogru_secenek_id,
            is_anonymous=False
        )
        kullanici["anket_mesajlari"][anket_mesaji.poll.id] = kullanici["mevcut_soru"]
        kullanici["dogru_secenek_idleri"][anket_mesaji.poll.id] = yeni_dogru_secenek_id

        zamanlayici_mesaji = await context.bot.send_message(sohbet_id, f"Kalan süre: {bekleme_suresi} saniye")
        kullanici["son_zamanlayici_metin"] = f"Kalan süre: {bekleme_suresi} saniye"

        await gorevleri_temizle(sohbet_id)

        kullanici["mevcut_gorev"] = asyncio.create_task(soru_atlama(update, context, sohbet_id, bekleme_suresi))
        kullanici["zamanlayici_gorev"] = asyncio.create_task(zamanlayiciyi_guncelle(update, context, sohbet_id, zamanlayici_mesaji.message_id, bekleme_suresi))
    else:
        await quiz_bitir(update, context, sohbet_id)

async def zamanlayiciyi_guncelle(update: Update, context: CallbackContext, sohbet_id: int, mesaj_id: int, bekleme_suresi: int):
    try:
        kullanici = kullanici_verileri.get(sohbet_id)
        if not kullanici:
            return

        for kalan in range(bekleme_suresi, -1, -1):
            yeni_metin = f"Kalan süre: {kalan} saniye"
            if yeni_metin != kullanici.get("son_zamanlayici_metin"):
                await context.bot.edit_message_text(
                    chat_id=sohbet_id,
                    message_id=mesaj_id,
                    text=yeni_metin
                )
                kullanici["son_zamanlayici_metin"] = yeni_metin
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    except Exception as hata:
        print(f"Zamanlayıcı güncelleme hatası: {hata}")

async def soru_atlama(update: Update, context: CallbackContext, sohbet_id: int, bekleme_suresi: int):
    try:
        await asyncio.sleep(bekleme_suresi)
        kullanici = kullanici_verileri.get(sohbet_id)
        if kullanici and kullanici["mevcut_soru"] < len(kullanici["questions"]):
            await context.bot.send_message(sohbet_id, "Süre bitti! Bu soru yanlış olarak işaretlendi.")
            kullanici["mevcut_soru"] += 1
            await sonraki_soruyu_gonder(update, context, sohbet_id)
    except asyncio.CancelledError:
        pass

async def quiz_bitir(update: Update, context: CallbackContext, sohbet_id: int):
    kullanici = kullanici_verileri.get(sohbet_id)
    if not kullanici:
        return

    skor = kullanici["skor"]
    toplam = len(kullanici["questions"])
    await context.bot.send_message(
        chat_id=sohbet_id,
        text=f"Test tamamlandı! Sonucunuz: {skor}/{toplam}"
    )
    await gorevleri_temizle(sohbet_id)
    del kullanici_verileri[sohbet_id]

async def anket_cevap_yonetici(update: Update, context: CallbackContext) -> None:
    anket_id = update.poll_answer.poll_id
    cevap = update.poll_answer.option_ids[0]

    sohbet_id = None
    for cid, veri in kullanici_verileri.items():
        if anket_id in veri["anket_mesajlari"]:
            sohbet_id = cid
            break

    if sohbet_id is None:
        return

    kullanici = kullanici_verileri.get(sohbet_id)
    if not kullanici or anket_id not in kullanici["anket_mesajlari"]:
        await context.bot.send_message(sohbet_id, "Bu test zaten tamamlanmış veya başlatılmamış!")
        return

    await gorevleri_temizle(sohbet_id)

    dogru_secenek_id = kullanici["dogru_secenek_idleri"][anket_id]
    if cevap == dogru_secenek_id:
        kullanici["skor"] += 1
        await context.bot.send_message(sohbet_id, "Doğru cevap!")
    else:
        await context.bot.send_message(sohbet_id, "Yanlış cevap!")

    kullanici["mevcut_soru"] += 1
    await sonraki_soruyu_gonder(update, context, sohbet_id)

async def gorevleri_temizle(sohbet_id):
    if sohbet_id in kullanici_verileri:
        kullanici = kullanici_verileri[sohbet_id]
        if "mevcut_gorev" in kullanici and not kullanici["mevcut_gorev"].done():
            kullanici["mevcut_gorev"].cancel()
            try:
                await kullanici["mevcut_gorev"]
            except asyncio.CancelledError:
                pass
        if "zamanlayici_gorev" in kullanici and not kullanici["zamanlayici_gorev"].done():
            kullanici["zamanlayici_gorev"].cancel()
            try:
                await kullanici["zamanlayici_gorev"]
            except asyncio.CancelledError:
                pass

def main():
    uygulama = Application.builder().token(TOKEN).build()

    uygulama.add_handler(CommandHandler("start", start))
    uygulama.add_handler(CommandHandler("restart", yeniden_baslat))
    uygulama.add_handler(CommandHandler("stop", durdur))
    uygulama.add_handler(CommandHandler("quizlist", quiz_listesi))
    uygulama.add_handler(CallbackQueryHandler(dugme_yonetici))
    uygulama.add_handler(PollAnswerHandler(anket_cevap_yonetici))

    async def baslangic():
        await bot_komutlarini_ayarla(uygulama.bot)
    uygulama.job_queue.run_once(lambda context: baslangic(), 0)

    def kapatma():
        for sohbet_id in list(kullanici_verileri.keys()):
            asyncio.run_coroutine_threadsafe(gorevleri_temizle(sohbet_id), uygulama.loop)
            if sohbet_id in kullanici_verileri:
                del kullanici_verileri[sohbet_id]
    atexit.register(kapatma)

    def sinyal_yonetici(signum, frame):
        kapatma()
        raise SystemExit
    signal.signal(signal.SIGINT, sinyal_yonetici)
    signal.signal(signal.SIGTERM, sinyal_yonetici)

    print("Bot başlatıldı! 🚀")
    uygulama.run_polling()

if __name__ == "__main__":
    main()
