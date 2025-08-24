import subprocess
import time
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Giới hạn cooldown 2 phút (120 giây)
cooldown = {}
COOLDOWN_TIME = 60
MAX_TIME = 200

# Hàng đợi
queue = asyncio.Queue()
is_running = False  # trạng thái có đang chạy tiến trình không

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Xin chào, tôi là bot spam SMS. Gõ /help để xem hướng dẫn sử dụng."
    )

# /help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hướng dẫn sử dụng:\n"
        "/sms <số điện thoại> <time> <delay> <luồng>\n\n"
        "Ví dụ:\n"
        "/sms 0123456789 60 1 5\n\n"
        f"⚠️ Lưu ý:\n- Thời gian tối đa {MAX_TIME} giây.\n- Mỗi người chỉ được chạy lại sau {COOLDOWN_TIME} giây.\n"
        "- Nếu có người đang chạy, yêu cầu của bạn sẽ được đưa vào hàng đợi."
    )

# Hàm xử lý tiến trình trong hàng đợi
async def worker():
    global is_running
    while True:
        chat_id, user_id, cmd, msg_context = await queue.get()
        is_running = True
        try:
            await msg_context.bot.send_message(
                chat_id=chat_id,
                text=f"Đang thực thi: {' '.join(cmd)}"
            )

            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            process.wait()  # chờ tool sms.py chạy xong

            await msg_context.bot.send_message(
                chat_id=chat_id,
                text="Hoàn thành yêu cầu."
            )
        except Exception as e:
            await msg_context.bot.send_message(
                chat_id=chat_id,
                text=f"Đã xảy ra lỗi: {e}"
            )
        finally:
            is_running = False
            queue.task_done()

# /sms command
async def sms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    now = time.time()

    # Kiểm tra cooldown
    if user_id in cooldown and now - cooldown[user_id] < COOLDOWN_TIME:
        remaining = int(COOLDOWN_TIME - (now - cooldown[user_id]))
        await update.message.reply_text(
            f"Bạn cần chờ thêm {remaining} giây nữa trước khi thực hiện lệnh tiếp theo."
        )
        return

    if len(context.args) != 4:
        await update.message.reply_text("Sai cú pháp! Vui lòng dùng: /sms <sdt> <time> <delay> <luồng>")
        return

    sdt, time_arg, delay, luong = context.args

    # Giới hạn time
    try:
        time_arg = int(time_arg)
    except ValueError:
        await update.message.reply_text("Tham số time phải là số nguyên.")
        return

    if time_arg > MAX_TIME:
        await update.message.reply_text(f"⚠️ Thời gian tối đa được phép là {MAX_TIME} giây.")
        return

    # Ghi nhận cooldown
    cooldown[user_id] = now

    # Tạo command
    cmd = ["python", "sms.py", sdt, str(time_arg), delay, luong]

    # Đưa vào hàng đợi
    await queue.put((update.message.chat_id, user_id, cmd, context))
    if is_running:
        await update.message.reply_text("Yêu cầu của bạn đã được đưa vào hàng đợi. Vui lòng chờ người trước chạy xong.")
    else:
        await update.message.reply_text("Yêu cầu của bạn đang được thực thi ngay.")

# Main
if __name__ == "__main__":
    TOKEN = "8256690182:AAHtDRmYxb1Y7BLIK96zrHLKVFIVX_XYaZ0"  # 🔥 Thay token bot ở đây
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("sms", sms))

    # chạy worker để xử lý queue
    app.job_queue.run_once(lambda ctx: asyncio.create_task(worker()), when=0)

    print("Bot đang chạy...")
    app.run_polling()