from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackContext, JobQueue, CallbackQueryHandler, filters, ConversationHandler, MessageHandler
import os
import datetime
import webuntis
import pickle
TOKEN = os.getenv("UNTIS_BOT_TOKEN")
TELEGRAM_USER_ID = os.getenv("TELEGRAM_USER_ID")
UNTIS_ENABLED = os.getenv("UNTIS_ENABLED")
if UNTIS_ENABLED == "true": 
    UNTIS_USER = os.getenv("UNTIS_USER")
    UNTIS_PASSWORD = os.getenv("UNTIS_PASSWORD")
    UNTIS_SCHOOL = os.getenv("UNTIS_SCHOOL")
    UNTIS_SERVER = os.getenv("UNTIS_SERVER")
    vertraetungstext = os.getenv("UNTIS_VERTRAETUNGSTEXT") #schulenabhängig anpassen
    gleicher_plan = ""

ADD_KLAUSUR = 1
REMOVE_KLAUSUR = 2


def save_object(obj, filename):
    with open(filename, 'wb') as output:
        pickle.dump(obj, output, pickle.HIGHEST_PROTOCOL)

def load_object(filename):
    with open(filename, 'rb') as input:
        return pickle.load(input)


async def manuell_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await entfallCheck(context, eigenerplan="ja")

async def entfallCheck(context: ContextTypes.DEFAULT_TYPE, eigenerplan=None):
        global gleicher_plan
        global vertraetungstext
        with webuntis.Session(
            server = UNTIS_SERVER,
            username = UNTIS_USER,
            password = UNTIS_PASSWORD,
            school = UNTIS_SCHOOL,
            useragent='WebUntis Python Client'
        ).login() as s:
            today = datetime.date.today()
            table = s.my_timetable(start=today, end=today).to_table()
            if table != gleicher_plan or eigenerplan=="ja":
                gleicher_plan = table    
                bot_text = "Der Unterricht entfällt für folgende Fächer:\n\n"
                letzte_stunde = None
                blockquote_offen = False

                for time, row in table:
                    for date, cell in row:
                        for period in cell:
                            aktuelle_stunde = ', '.join(su.long_name for su in period.subjects)

                            if blockquote_offen and aktuelle_stunde != letzte_stunde:
                                bot_text += (
                                    "\nEndzeit: "
                                    + str(period.start).split()[-1][:-3]
                                    + "</blockquote>\n\n"
                                )
                                blockquote_offen = False

                            if period.substText == vertraetungstext:
                                if not blockquote_offen:
                                    bot_text += "<blockquote>"
                                    bot_text += (
                                        aktuelle_stunde
                                        + "   "
                                        + str(period.original_teachers[0])
                                    )
                                    bot_text += (
                                        "\nStartzeit: "
                                        + str(period.start).split()[-1][:-3]
                                    )
                                    blockquote_offen = True

                            letzte_stunde = aktuelle_stunde

                await context.bot.send_message(chat_id=TELEGRAM_USER_ID, parse_mode="HTML", text=bot_text)

async def Klausur_Hinzufuegen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teile = update.message.text.split('\n')

    if len(teile) != 4:
        await update.message.reply_text(text="Format faösch. 4 Zeilen erwartet.")
        return ADD_KLAUSUR
    
    fach, datum, schulstunde, raum = teile

    try:
        datum_zeit = datetime.datetime.strptime(datum, "%d.%m.%Y")
        schulstunde = int(schulstunde)
        if schulstunde < 1 or schulstunde > 10:
            raise ValueError
    except ValueError:
        await update.message.reply_text(text="Datum oder Schulstunde ungültig!")
        return ADD_KLAUSUR
    
    try:
        klausuren = load_object("klausuren.pkl")
    except:
        klausuren = []
    schulstunden = {1: "08:00", 2: "08:45", 3: "09:50", 4: "10:40", 5: "11:45", 6: "12:35", 7: "13:50", 8: "14:40", 9: "15:30", 10: "16:15"}
    schulstundenzeit = datetime.datetime.strptime(schulstunden[schulstunde], "%H:%M")
    klausuren.append([fach, datum_zeit, schulstunde, schulstundenzeit, raum])
    save_object(klausuren, "klausuren.pkl")

    await update.message.reply_text(text=f"Klausur in {fach} am {datum} während der {schulstunde} in Raum {raum} wurde hinzugefügt.")
    application.job_queue.run_once(
        send_klausuren_errinerung,
        when=datetime.datetime(
            datum_zeit.year,
            datum_zeit.month,
            datum_zeit.day,
            schulstundenzeit.hour,
            schulstundenzeit.minute
        ) - datetime.timedelta(minutes=30),
        data={
            "fach": fach,
            "schulstunde": schulstunde,
            "raum": raum,
            "typ": "30min",
            "schulstundenzeit": schulstundenzeit,
            "datum_zeit": datum_zeit,
        },
        name=f"{fach}_{schulstunde}_30min"
    )
    application.job_queue.run_once(
        send_klausuren_errinerung,
        when=datetime.datetime(
            datum_zeit.year,
            datum_zeit.month,
            datum_zeit.day,
            schulstundenzeit.hour,
            schulstundenzeit.minute
        ) - datetime.timedelta(days=1),
        data={
            "fach": fach,
            "schulstunde": schulstunde,
            "raum": raum,
            "typ": "einTag",
            "schulstundenzeit": schulstundenzeit,
            "datum_zeit": datum_zeit,
        },
        name=f"{fach}_{schulstunde}_einTag"
    )
    application.job_queue.run_once(
        send_klausuren_errinerung,
        when=datetime.datetime(
            datum_zeit.year,
            datum_zeit.month,
            datum_zeit.day,
            schulstundenzeit.hour,
            schulstundenzeit.minute
        ) - datetime.timedelta(days=3),
        data={
            "fach": fach,
            "schulstunde": schulstunde,
            "raum": raum,
            "typ": "dreiTage",
            "schulstundenzeit": schulstundenzeit,
            "datum_zeit": datum_zeit,
        },
        name=f"{fach}_{schulstunde}_dreiTage"
    )
    application.job_queue.run_once(
        send_klausuren_errinerung,
        when=datetime.datetime(
            datum_zeit.year,
            datum_zeit.month,
            datum_zeit.day,
            schulstundenzeit.hour,
            schulstundenzeit.minute
        ) - datetime.timedelta(weeks=1),
        data={
            "fach": fach,
            "schulstunde": schulstunde,
            "raum": raum,
            "typ": "eineWoche",
            "schulstundenzeit": schulstundenzeit,
            "datum_zeit": datum_zeit,
        },
        name=f"{fach}_{schulstunde}_eineWoche"
    )
    
    return ConversationHandler.END


async def send_klausuren_errinerung(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    fach = data["fach"]
    schulstunde = data["schulstunde"]
    raum = data["raum"]
    erinnerungszeit = data["typ"]
    schulstundenzeit = data["schulstundenzeit"]
    datum_zeit = data["datum_zeit"]

    if erinnerungszeit == "30min":
        await context.bot.send_message(
            chat_id=TELEGRAM_USER_ID,
            text=f"Erinnerung: In 30 Minuten hast du eine Klausur in {fach} in Raum {raum} um {schulstundenzeit.strftime('%H:%M')}. Viel erfolg!"
        )
        entferne_klausur_helper(fach, schulstunde, datum_zeit)
    elif erinnerungszeit == "einTag":
        await context.bot.send_message(
            chat_id=TELEGRAM_USER_ID,
            text=f"Erinnerung: Morgen hast du eine Klausur in {fach} in Raum {raum} während der {schulstunde}."
        )
    elif erinnerungszeit == "dreiTage":
        await context.bot.send_message(
            chat_id=TELEGRAM_USER_ID,
            text=f"Erinnerung: in drei Tagen hast du eine Klausur in {fach} in Raum {raum} während der {schulstunde}."
        )
    elif erinnerungszeit == "eineWoche":
        await context.bot.send_message(
            chat_id=TELEGRAM_USER_ID,
            text=f"Erinnerung: In einer Woche hast du eine Klausur in {fach} in Raum {raum} während der {schulstunde}."
        )
    else:
        await context.bot.send_message(chat_id=TELEGRAM_USER_ID, text="Fehler beim Erinnern. Du solltest deine Klausurtermine überprüfen.")


async def Klausuren(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("Klausuren anzeigen", callback_data="send: klausuren"),
            InlineKeyboardButton("Klausur hinzufügen", callback_data="add: klausur"),
            InlineKeyboardButton("Klausur entfernen", callback_data="remove: klausur"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text='Wähle eine Option:', reply_markup=reply_markup)

async def entferne_klausur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teile = update.message.text.split('\n')
    if len(teile) != 3:
        await update.message.reply_text(text="Format falsch. 3 Zeilen erwartet.")
        return REMOVE_KLAUSUR
    
    fach, datum, schulstunde = teile
    
    try:
        datum_zeit = datetime.datetime.strptime(datum, "%d.%m.%Y")
        schulstunde = int(schulstunde)
    except ValueError:
        await update.message.reply_text(text="Datum oder Schulstunde ungültig!")
        return REMOVE_KLAUSUR

    if entferne_klausur_helper(fach, schulstunde, datum_zeit):
        await update.message.reply_text(text=f"Klausur in {fach} am {datum} während der {schulstunde} wurde entfernt.")
    else:
        await update.message.reply_text(text="Klausur nicht gefunden.")

    return ConversationHandler.END

def entferne_klausur_helper(fach, schulstunde, datum):
    try:
        klausuren = load_object("klausuren.pkl")
    except:
        return False

    original_len = len(klausuren)

    klausuren = [
        k for k in klausuren
        if not (k[0] == fach and k[2] == schulstunde and k[1].date() == datum.date())
    ]

    if len(klausuren) == original_len:
        return False

    save_object(klausuren, "klausuren.pkl")

    for zeit in ["30min", "einTag", "dreiTage", "eineWoche"]:
        for job in application.job_queue.get_jobs_by_name(f"{fach}_{schulstunde}_{zeit}"):
            job.schedule_removal()

    return True


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "add: klausur":
        await query.message.edit_text(
            "Format:\n\n"
            "Fach\n"
            "Datum (TT.MM.JJJJ)\n"
            "Schulstunde\n"
            "Raum"
        )
        return ADD_KLAUSUR

    if query.data == "remove: klausur":
        await query.message.edit_text(
            "Format:\n\n"
            "Fach\n"
            "Datum (TT.MM.JJJJ)\n"
            "Schulstunde"
        )
        return REMOVE_KLAUSUR
    elif query.data == "send: klausuren":
        await send_klausuren(update, context)

    return ConversationHandler.END



async def send_klausuren(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        Klausuren = load_object("klausuren.pkl")
    except FileNotFoundError:
        Klausuren = []
    if not Klausuren:
        await query.edit_message_text("Keine Klausuren gefunden.")
        return
    bot_text = "Deine Klausuren:\n\n"
    for klausur in Klausuren:
        bot_text += f"<blockquote>Fach: {klausur[0]}\nDatum: {klausur[1].strftime('%d.%m.%Y')}\nSchulstunde: {klausur[2]}\nRaum: {klausur[4]}</blockquote>\n\n"
    await query.edit_message_text(bot_text, parse_mode="HTML")

async def recover_klausuren_jobs(application):
    try:
        klausuren = load_object("klausuren.pkl")
    except FileNotFoundError:
        return
    
    now = datetime.datetime.now()

    for fach, datum_zeit, schulstunde, schulstundenzeit, raum in klausuren:
        start_dt = datetime.datetime(
            datum_zeit.year,
            datum_zeit.month,
            datum_zeit.day,
            schulstundenzeit.hour,
            schulstundenzeit.minute
        )

        errinnerungen = [
            ("30min", start_dt - datetime.timedelta(minutes=30)),
            ("einTag", start_dt - datetime.timedelta(days=1)),
            ("dreiTage", start_dt - datetime.timedelta(days=3)),
            ("eineWoche", start_dt - datetime.timedelta(weeks=1)),
        ]

        for typ, when in errinnerungen:
            if when >= now:
                job_name = f"{fach}_{schulstunde}_{typ}"

                if not application.job_queue.get_jobs_by_name(job_name):
                    application.job_queue.run_once(
                        send_klausuren_errinerung,
                        when=when,
                        data={
                            "fach": fach,
                            "schulstunde": schulstunde,
                            "raum": raum,
                            "typ": typ,
                            "schulstundenzeit": schulstundenzeit,
                            "datum_zeit": datum_zeit,
                        },
                        name=job_name
                    )


if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).post_init(recover_klausuren_jobs).build()

    if UNTIS_ENABLED == "true": 
        test_handler = CommandHandler('test', manuell_test)
        application.add_handler(test_handler)

        application.job_queue.run_repeating(entfallCheck, interval=900, first=0)

    klausuren_handler = CommandHandler('klausuren', Klausuren)
    application.add_handler(klausuren_handler)

    conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(button_callback)],
    states={
        ADD_KLAUSUR: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, Klausur_Hinzufuegen)
        ],
        REMOVE_KLAUSUR: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, entferne_klausur)
        ],
    },
    fallbacks=[],
    per_user=True,
    )

    application.add_handler(conv_handler)

    application.run_polling()
