from telegram import Update, ChatMember
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ChatMemberHandler,
)
import json
import os
import logging
from datetime import datetime, timedelta

BOT_TOKEN = "7957614353:AAFhjSgFs23dzPivb1aFL7aJtdRWb9Ob1Vg"
DATA_FILE = "checkins.json"
CHECKIN_DURATION = 20  # menit
LATE_THRESHOLD = 5  # menit terakhir = telat

logging.basicConfig(level=logging.INFO)

checkin_data = {
    "active": False,
    "start_time": None,
    "checkins": {},
    "late_counts": {},
    "badges": {}
}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(checkin_data, f)

def load_data():
    global checkin_data
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            checkin_data = json.load(f)

def reset_checkin():
    checkin_data["active"] = False
    checkin_data["start_time"] = None
    checkin_data["checkins"] = {}
    save_data()

async def start_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if checkin_data["active"]:
        await update.message.reply_text("⏳ Check-in masih berlangsung!")
        return

    checkin_data["active"] = True
    checkin_data["start_time"] = datetime.now().isoformat()
    checkin_data["checkins"] = {}
    await update.message.reply_text("✅ Check-in dimulai!\nKetik angka 1 untuk check-in.\nCheck-in otomatis berakhir dalam 20 menit.")
    await schedule_checkin_end(context)

async def end_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not checkin_data["active"]:
        await update.message.reply_text("🚫 Tidak ada sesi check-in yang aktif.")
        return

    await do_end_checkin(context, manual=True)
    await update.message.reply_text("🛑 Check-in telah diakhiri!")

async def schedule_checkin_end(context):
    await context.application.job_queue.run_once(do_end_checkin, when=CHECKIN_DURATION * 60)

async def do_end_checkin(context: ContextTypes.DEFAULT_TYPE, manual=False):
    if not checkin_data["active"]:
        return

    start_time = datetime.fromisoformat(checkin_data["start_time"])
    end_time = start_time + timedelta(minutes=CHECKIN_DURATION)
    late_deadline = end_time - timedelta(minutes=LATE_THRESHOLD)

    summary = "📋 *Rekap Check-in Hari Ini:*\n"
    for user_id, info in checkin_data["checkins"].items():
        name = info["name"]
        time_str = info["time"]
        checkin_time = datetime.fromisoformat(time_str)
        is_late = checkin_time > late_deadline

        if is_late:
            summary += f"❗ {name} - *Telat*\n"
            checkin_data["late_counts"][str(user_id)] = checkin_data["late_counts"].get(str(user_id), 0) + 1
        else:
            summary += f"✅ {name} - Tepat Waktu\n"

        if checkin_data["late_counts"].get(str(user_id), 0) >= 3:
            checkin_data["badges"][str(user_id)] = "🥱 Pemalas"
        else:
            checkin_data["badges"][str(user_id)] = "🏆 Rajin"

    await context.bot.send_message(chat_id=context._chat_id, text=summary, parse_mode="Markdown")
    reset_checkin()

async def handle_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not checkin_data["active"]:
        return

    if update.message.text != "1":
        return

    user = update.effective_user
    user_id = str(user.id)

    if user_id in checkin_data["checkins"]:
        await update.message.reply_text("⚠️ Kamu sudah check-in hari ini.")
        return

    now = datetime.now().isoformat()
    checkin_data["checkins"][user_id] = {"name": user.full_name, "time": now}
    save_data()
    await update.message.reply_text(f"✅ Terima kasih sudah check-in, {user.first_name}!")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🏅 *Leaderboard Badge:*\n"
    for uid, badge in checkin_data["badges"].items():
        name = checkin_data["checkins"].get(uid, {}).get("name", "User")
        text += f"{name}: {badge}\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def handle_member_leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    member = update.chat_member
    if member.status == ChatMember.LEFT:
        user_id = str(member.user.id)
        checkin_data["checkins"].pop(user_id, None)
        checkin_data["late_counts"].pop(user_id, None)
        checkin_data["badges"].pop(user_id, None)
        save_data()

if __name__ == "__main__":
    load_data()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("checkin", start_checkin))
    app.add_handler(CommandHandler("endcheckin", end_checkin))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^1$"), handle_checkin))
    app.add_handler(ChatMemberHandler(handle_member_leave, ChatMemberHandler.MY_CHAT_MEMBER | ChatMemberHandler.CHAT_MEMBER))

    app.run_polling()