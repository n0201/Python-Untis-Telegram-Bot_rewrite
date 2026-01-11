from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackContext, JobQueue, CallbackQueryHandler
import os
import datetime
import webuntis
TOKEN = os.getenv("UNTIS_BOT_TOKEN")
UNTIS_USER = os.getenv("UNTIS_USER")
UNTIS_PASSWORD = os.getenv("UNTIS_PASSWORD")
UNTIS_SCHOOL = os.getenv("UNTIS_SCHOOL")
UNTIS_SERVER = os.getenv("UNTIS_SERVER")
vertraetungstext = "eigenverantwortliches Arbeiten" #schulenabhängig anpassen
TELEGRAM_NUTZER_ID = os.getenv("TELEGRAM_NUTZER_ID")
gleicher_plan = ""


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
                                if letzte_stunde != (', '.join(su.long_name for su in period.subjects)):
                                    letzte_stunde = (', '.join(su.long_name for su in period.subjects))
                                    if period.substText == vertraetungstext:
                                        bot_text += ("<blockquote>")
                                        bot_text += (', '.join(su.long_name for su in period.subjects) + "   " + str(period.original_teachers[0]))
                                        bot_text += ("\nStartzeit: " + str(period.start).split()[-1][:-3])
                                        blockquote_offen = True
                                else:
                                    if blockquote_offen:
                                        bot_text +=("\nEndzeit: " + str(period.end).split()[-1][:-3] + "</blockquote>\n\n")
                                        blockquote_offen = False

                await context.bot.send_message(chat_id=TELEGRAM_NUTZER_ID, parse_mode="HTML", text=bot_text)


if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    application.job_queue.run_repeating(entfallCheck, interval=900, first=0)

    test_handler = CommandHandler('test', manuell_test)
    application.add_handler(test_handler)

    application.run_polling()
