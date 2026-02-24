from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackContext, JobQueue, CallbackQueryHandler, filters, ConversationHandler, MessageHandler
import os
import datetime
import webuntis
import pickle
from functools import wraps
import gettext
import asyncio
TOKEN = os.getenv("UNTIS_BOT_TOKEN")
TELEGRAM_USER_ID = os.getenv("TELEGRAM_USER_ID")
UNTIS_ENABLED = os.getenv("UNTIS_ENABLED")
UNTIS_LANGUAGE = os.getenv("UNTIS_LANGUAGE")
if UNTIS_ENABLED == "true": 
    UNTIS_USER = os.getenv("UNTIS_USER")
    UNTIS_PASSWORD = os.getenv("UNTIS_PASSWORD")
    UNTIS_SCHOOL = os.getenv("UNTIS_SCHOOL")
    UNTIS_SERVER = os.getenv("UNTIS_SERVER")
    vertraetungstext = os.getenv("UNTIS_VERTRAETUNGSTEXT") #schulenabhängig anpassen
    gleicher_plan = ""

klausuren_lock = asyncio.Lock()

locale_dir = "./locale"
gettext.bindtextdomain("main", locale_dir)
gettext.textdomain("main")

if UNTIS_LANGUAGE == "en":
    try:
        lang = gettext.translation("main", localedir=locale_dir, languages=["en"])
        lang.install()
        _ = lang.gettext
    except (FileNotFoundError, OSError):
        _ = lambda s: s
else:
    _ = lambda s: s

ADD_KLAUSUR = 1
REMOVE_KLAUSUR = 2
WAITING_FOR_CHOICE = 3


def restricted(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if str(user_id) != TELEGRAM_USER_ID:
            # Optionally log or send a message
            await update.message.reply_text(_("Du bist nicht autorisiert, diesen Bot zu benutzen."))
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

async def save_object(obj, filename):
    async with klausuren_lock:
        with open(f"data/{filename}", "wb") as output:
            pickle.dump(obj, output, pickle.HIGHEST_PROTOCOL)

async def load_object(filename):
    async with klausuren_lock:
        with open(f"data/{filename}", "rb") as input:
            return pickle.load(input)

@restricted
async def manuell_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton(_("Entfall heute"), callback_data="send: entfall_heute"),
            InlineKeyboardButton(_("Entfall morgen"), callback_data="send: entfall_morgen"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text=_('Wähle eine Option:'), reply_markup=reply_markup)
    return WAITING_FOR_CHOICE
    await entfallCheck(context, eigenerplan="ja")

async def entfallCheck(context: ContextTypes.DEFAULT_TYPE, eigenerplan=None, morgen=False):
        global gleicher_plan
        global vertraetungstext
        with webuntis.Session(
            server = UNTIS_SERVER,
            username = UNTIS_USER,
            password = UNTIS_PASSWORD,
            school = UNTIS_SCHOOL,
            useragent='WebUntis Python Client'
        ).login() as s:
            if morgen:
                timeframe = (datetime.datetime.now() + datetime.timedelta(days=1)).date()
            else:
                timeframe = datetime.datetime.now().date()
            table = s.my_timetable(start=timeframe, end=timeframe).to_table()
            if table != gleicher_plan or eigenerplan=="ja":
                gleicher_plan = table    
                bot_text = _("Der Unterricht entfällt für folgende Fächer:\n\n")
                letzte_stunde = None
                blockquote_offen = False

                for time, row in table:
                    for date, cell in row:
                        for period in cell:
                            aktuelle_stunde = ', '.join(su.long_name for su in period.subjects)

                            if blockquote_offen and aktuelle_stunde != letzte_stunde:
                                bot_text += (
                                    "\nEndzeit: "
                                    + str(period.end).split()[-1][:-3]
                                    + "</blockquote>\n\n"
                                )
                                blockquote_offen = False

                            if period.substText == vertraetungstext:
                                if not blockquote_offen:
                                    bot_text += "<blockquote>"
                                    bot_text += (
                                        aktuelle_stunde
                                        + "   "
                                    )
                                    bot_text += (
                                        "\nStartzeit: "
                                        + str(period.start).split()[-1][:-3]
                                    )
                                    blockquote_offen = True
                                
                                if blockquote_offen and aktuelle_stunde != letzte_stunde:
                                    bot_text += "</blockquote>\n\n"
                                    bot_text += "<blockquote>"
                                    bot_text += (
                                        aktuelle_stunde
                                        + "   "
                                    )
                                    bot_text += (
                                        "\nStartzeit: "
                                        + str(period.start).split()[-1][:-3]
                                    )
                                    blockquote_offen = True

                            letzte_stunde = aktuelle_stunde

                # Close any remaining open blockquote
                if blockquote_offen:
                    bot_text += (
                        "\nEndzeit: "
                        + str(period.end).split()[-1][:-3]
                        + "</blockquote>\n\n"
                    )

                if bot_text.endswith("</blockquote>\n\n"):
                    await context.bot.send_message(chat_id=TELEGRAM_USER_ID, parse_mode="HTML", text=bot_text)
                elif eigenerplan=="ja":
                    if morgen:
                        await context.bot.send_message(chat_id=TELEGRAM_USER_ID, text=_("Morgen fällt kein Unterricht aus."))
                    else:
                        await context.bot.send_message(chat_id=TELEGRAM_USER_ID, text=_("Heute fällt kein Unterricht aus."))

@restricted
async def Klausur_Hinzufuegen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teile = update.message.text.split('\n')

    if len(teile) != 4:
        await update.message.reply_text(text=_("Format falsch. 4 Zeilen erwartet."))
        return ADD_KLAUSUR
    
    fach, datum, schulstunde, raum = teile

    fach = fach.strip()
    datum = datum.strip()
    schulstunde = schulstunde.strip()
    raum = raum.strip()

    try:
        datum_zeit = datetime.datetime.strptime(datum, "%d.%m.%Y")
        schulstunde = int(schulstunde)
        if schulstunde < 1 or schulstunde > 10:
            raise ValueError
    except ValueError:
        await update.message.reply_text(text=_("Datum oder Schulstunde ungültig!"))
        return ADD_KLAUSUR
    
    try:
        klausuren = await load_object("klausuren.pkl")
    except FileNotFoundError:
        klausuren = []
    schulstunden = {1: "08:00", 2: "08:45", 3: "09:50", 4: "10:40", 5: "11:45", 6: "12:35", 7: "13:50", 8: "14:40", 9: "15:30", 10: "16:15"}
    schulstundenzeit = datetime.datetime.strptime(schulstunden[schulstunde], "%H:%M")
    klausuren.append([fach, datum_zeit, schulstunde, schulstundenzeit, raum])
    await save_object(klausuren, "klausuren.pkl")
    
    message = _("Klausur in {fach} am {datum} während der {schulstunde}. Schulstunde in Raum {raum} wurde hinzugefügt.")
    await update.message.reply_text(text=message.format(fach=fach, datum=datum, schulstunde=schulstunde, raum=raum))
    context.application.job_queue.run_once(
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
    context.application.job_queue.run_once(
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
    context.application.job_queue.run_once(
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
    context.application.job_queue.run_once(
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
        message = _("Erinnerung: In 30 Minuten hast du eine Klausur in {fach} in Raum {raum} um {schulstundenzeit}. Viel erfolg!")
        await context.bot.send_message(
            chat_id=TELEGRAM_USER_ID,
            text=message.format(fach=fach, raum=raum, schulstundenzeit=schulstundenzeit)
        )
        await entferne_klausur_helper(fach, schulstunde, datum_zeit, context)
    elif erinnerungszeit == "einTag":
        message = _("Erinnerung: Morgen hast du eine Klausur in {fach} in Raum {raum} während der {schulstunde}. Schulstunde.")
        await context.bot.send_message(
            chat_id=TELEGRAM_USER_ID,
            text=message.format(fach=fach, raum=raum, schulstunde=schulstunde)
        )
    elif erinnerungszeit == "dreiTage":
        message = _("Erinnerung: in drei Tagen hast du eine Klausur in {fach} in Raum {raum} während der {schulstunde}. Schulstunde.")
        await context.bot.send_message(
            chat_id=TELEGRAM_USER_ID,
            text=message.format(fach=fach, raum=raum, schulstunde=schulstunde)
        )
    elif erinnerungszeit == "eineWoche":
        message = _("Erinnerung: In einer Woche hast du eine Klausur in {fach} in Raum {raum} während der {schulstunde}. Schulstunde.")
        await context.bot.send_message(
            chat_id=TELEGRAM_USER_ID,
            text=message.format(fach=fach, raum=raum, schulstunde=schulstunde)
        )
    else:
        await context.bot.send_message(chat_id=TELEGRAM_USER_ID, text=_("Fehler beim Erinnern. Du solltest deine Klausurtermine überprüfen."))

@restricted
async def Klausuren(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton(_("Klausuren anzeigen"), callback_data="send: klausuren"),
            InlineKeyboardButton(_("Klausur hinzufügen"), callback_data="add: klausur"),
            InlineKeyboardButton(_("Klausur entfernen"), callback_data="remove: klausur"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text=_('Wähle eine Option:'), reply_markup=reply_markup)
    return WAITING_FOR_CHOICE

@restricted
async def entferne_klausur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teile = update.message.text.split('\n')
    if len(teile) != 3:
        await update.message.reply_text(text=_("Format falsch. 3 Zeilen erwartet."))
        return REMOVE_KLAUSUR
    
    fach, datum, schulstunde = teile

    fach = fach.strip()
    datum = datum.strip()
    schulstunde = schulstunde.strip()
    
    try:
        datum_zeit = datetime.datetime.strptime(datum, "%d.%m.%Y")
        schulstunde = int(schulstunde)
    except ValueError:
        await update.message.reply_text(text=_("Datum oder Schulstunde ungültig!"))
        return REMOVE_KLAUSUR

    if await entferne_klausur_helper(fach, schulstunde, datum_zeit, context):
        message = _("Klausur in {fach} am {datum} während der {schulstunde}. Schulstunde wurde entfernt.")
        await update.message.reply_text(text=message.format(fach=fach, datum=datum, schulstunde=schulstunde))
    else:
        await update.message.reply_text(text=_("Klausur nicht gefunden."))

    return ConversationHandler.END

async def entferne_klausur_helper(fach, schulstunde, datum, context=None):

    try:
        klausuren = await load_object("klausuren.pkl")
    except FileNotFoundError:
        return False

    original_len = len(klausuren)

    klausuren = [
        k for k in klausuren
        if not (k[0] == fach and k[2] == int(schulstunde) and k[1].date() == datum.date())
    ]

    if len(klausuren) == original_len:
        return False

    await save_object(klausuren, "klausuren.pkl")

    if context and context.application:
        for zeit in ["30min", "einTag", "dreiTage", "eineWoche"]:
            for job in context.application.job_queue.get_jobs_by_name(f"{fach}_{schulstunde}_{zeit}"):
                job.schedule_removal()

    return True

@restricted
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.message.edit_reply_markup(None)

    if query.data == "add: klausur":
        await query.message.edit_text(
            _("Format:\n\n")
            + _("Fach\n")
            + _("Datum (TT.MM.JJJJ)\n")
            + _("Schulstunde\n")
            + _("Raum")
        )
        return ADD_KLAUSUR

    elif query.data == "remove: klausur":
        await query.message.edit_text(
            _("Format:\n\n")
            + _("Fach\n")
            + _("Datum (TT.MM.JJJJ)\n")
            + _("Schulstunde")
        )
        return REMOVE_KLAUSUR
    elif query.data == "send: klausuren":
        await send_klausuren(update, context)
        return ConversationHandler.END
    
    elif query.data == "send: entfall_heute":
        try:
            await entfallCheck(context, eigenerplan="ja", morgen=False)
        except Exception as e:
            await query.message.reply_text(f"Fehler: {str(e)}")
        return ConversationHandler.END
    
    elif query.data == "send: entfall_morgen":
        try:
            await entfallCheck(context, eigenerplan="ja", morgen=True)
        except Exception as e:
            await query.message.reply_text(f"Fehler: {str(e)}")
        return ConversationHandler.END

    return ConversationHandler.END



async def send_klausuren(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        Klausuren = await load_object("klausuren.pkl")
    except FileNotFoundError:
        Klausuren = []
    if not Klausuren:
        await query.edit_message_text(_("Keine Klausuren gefunden."))
        return
    bot_text = _("Deine Klausuren:\n\n")
    for klausur in Klausuren:
        bot_text += (
            f"<blockquote>"
            f"{_('Fach')}: {klausur[0]}\n"
            f"{_('Datum')}: {klausur[1].strftime('%d.%m.%Y')}\n"
            f"{_('Schulstunde')}: {klausur[2]}\n"
            f"{_('Raum')}: {klausur[4]}"
            f"</blockquote>\n\n"
        )

    await query.edit_message_text(bot_text, parse_mode="HTML")

async def recover_klausuren_jobs(application):
    try:
        klausuren = await load_object("klausuren.pkl")
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

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = _(
        _("Willkommen zum Untis Bot!\n\n")+
        _("Verfügbare Befehle:\n")+
        _("/start - Zeigt diese Hilfemeldung an\n")
    )
    if UNTIS_ENABLED == "true": 
        help_text += _(
            _("/test - Führt einen manuellen Test auf Unterrichtsausfälle durch\n")
        )
    help_text += _(
        _("/klausuren - Verwalte deine Klausuren (hinzufügen, entfernen, anzeigen)\n")
    )
    await update.message.reply_text(help_text)

if __name__ == '__main__':
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    
    application = ApplicationBuilder().token(TOKEN).post_init(recover_klausuren_jobs).build()

    start_handler = CommandHandler('start', help)
    application.add_handler(start_handler)

    if UNTIS_ENABLED == "true": 
        application.job_queue.run_repeating(entfallCheck, interval=900, first=0)
        
        test_conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler('test', manuell_test),
            ],
            states={
                WAITING_FOR_CHOICE: [
                    CallbackQueryHandler(button_callback)
                ],
            },
            fallbacks=[],
            per_user=True,
        )
        application.add_handler(test_conv_handler)

    conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler(_('klausuren'), Klausuren),
    ],
    states={
        WAITING_FOR_CHOICE: [
            CallbackQueryHandler(button_callback)
        ],
        ADD_KLAUSUR: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, Klausur_Hinzufuegen)
        ],
        REMOVE_KLAUSUR: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, entferne_klausur)
        ],
    },
    fallbacks=[CommandHandler(_('klausuren'), Klausuren)],
    per_user=True,
    )

    application.add_handler(conv_handler)

    application.run_polling()