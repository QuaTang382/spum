import subprocess
import signal
import os
import threading
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = "8256690182:AAHtDRmYxb1Y7BLIK96zrHLKVFIVX_XYaZ0"   # thay token bot
KEY_FILE = "key.txt"
TOOL_FILE = "c25tool.py"

process = None
thread = None
phone_number = None


def tool_worker(process, chat_id, app):
    """Luồng đọc stdout của tool và auto nhập theo prompt"""
    global phone_number

    for line in process.stdout:
        line = line.strip()
        print("[TOOL] >", line)  # debug ra console

        # Tool hỏi key?
        if "key" in line or "nhập key" in line.lower():
            with open(KEY_FILE, "r") as f:
                key = f.read().strip()
            process.stdin.write(key + "\n")
            process.stdin.flush()

        # Tool hỏi nhập Số (option)
        elif "Nhập Số" in line or "option" in line.lower():
            process.stdin.write("3.5\n")
            process.stdin.flush()

        # Tool hỏi nhập số điện thoại
        elif "Nhập số điện thoại" in line or "phone" in line.lower():
            if phone_number:
                process.stdin.write(phone_number + "\n")
                process.stdin.flush()

        # Forward log tool ra telegram để theo dõi
        try:
            app.create_task(app.bot.send_message(chat_id=chat_id, text=f"📟 {line}"))
        except:
            pass


async def sms_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global process, thread, phone_number

    if process and process.poll() is None:
        await update.message.reply_text("⚠️ Tool đã chạy rồi!")
        return

    if len(context.args) == 0:
        await update.message.reply_text("❌ Sai cú pháp. Dùng: /sms <sdt>")
        return

    phone_number = context.args[0]

    # Mở tool
    process = subprocess.Popen(
        ["python", TOOL_FILE],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    # Chạy thread đọc output tool
    thread = threading.Thread(target=tool_worker, args=(process, update.effective_chat.id, context.application))
    thread.daemon = True
    thread.start()

    await update.message.reply_text(f"✅ Tool đã khởi động, sẽ nhập số điện thoại {phone_number} khi được yêu cầu.")


async def stop_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global process
    if not process or process.poll() is not None:
        await update.message.reply_text("⚠️ Tool chưa chạy.")
        return

    os.kill(process.pid, signal.SIGINT)  # gửi Ctrl+C
    process = None
    await update.message.reply_text("🛑 Tool đã dừng.")


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("sms", sms_handler))
    app.add_handler(CommandHandler("stop", stop_handler))
    app.run_polling()


if __name__ == "__main__":
    main()