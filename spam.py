import nest_asyncio
nest_asyncio.apply()
import subprocess
import time
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.helpers import mention_html

# Giới hạn tối đa cho tham số time
MAX_TIME = 200

# Hàng đợi
queue = asyncio.Queue()
is_running = False  # trạng thái có đang chạy tiến trình không

# Lưu thời điểm user được chạy tiếp (theo delay riêng)
next_available = {}   # {user_id: timestamp}


# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Xin chào {mention_html(user.id, user.first_name)}, tôi là bot panel SMS.\nGõ /help để xem hướng dẫn sử dụng.",
        parse_mode="HTML",
        reply_to_message_id=update.message.message_id
    )


# /help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            "Hướng dẫn sử dụng:\n"
            "/sms <số điện thoại> <time> <delay> <luồng>\n\n"
            "Ví dụ:\n"
            "/sms 0123456789 60 5 10\n\n"
            f"⚠️ Lưu ý:\n- Thời gian tối đa {MAX_TIME} giây.\n"
            "- Delay (thời gian chờ trước khi dùng lại) được tính riêng cho từng user.\n"
            "- Bot chỉ hoạt động trong group.\n"
            "- Nếu có người đang chạy, yêu cầu của bạn sẽ được đưa vào hàng đợi."
        ),
        reply_to_message_id=update.message.message_id
    )


# Hàm xử lý tiến trình trong hàng đợi
async def worker():
    global is_running
    while True:
        chat_id, user_id, cmd, msg_context, msg_id, user_name = await queue.get()
        is_running = True
        try:
            await msg_context.bot.send_message(
                chat_id=chat_id,
                text=f"🚀 Đang thực thi yêu cầu của {mention_html(user_id, user_name)}:\n<code>{' '.join(cmd)}</code>",
                parse_mode="HTML",
                reply_to_message_id=msg_id
            )

            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            process.wait()  # chờ tool sms.py chạy xong

            await msg_context.bot.send_message(
                chat_id=chat_id,
                text=f"✅ Hoàn thành yêu cầu của {mention_html(user_id, user_name)}.",
                parse_mode="HTML"
            )

            # Nếu còn job trong hàng đợi thì báo user tiếp theo có thể chạy
            if not queue.empty():
                await msg_context.bot.send_message(
                    chat_id=chat_id,
                    text="📌 Người tiếp theo trong hàng đợi sẽ được chạy ngay."
                )
            else:
                await msg_context.bot.send_message(
                    chat_id=chat_id,
                    text="📌 Hiện không còn yêu cầu trong hàng đợi."
                )

        except Exception as e:
            await msg_context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ Đã xảy ra lỗi: {e}"
            )
        finally:
            is_running = False
            queue.task_done()


# /sms command
async def sms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type not in ["group", "supergroup"]:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⚠️ Lệnh này chỉ dùng trong group.",
            reply_to_message_id=update.message.message_id
        )
        return

    user = update.message.from_user
    user_id = user.id
    now = time.time()

    if len(context.args) != 4:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⚠️ Sai cú pháp! Dùng: /sms <sdt> <time> <delay> <luồng>",
            reply_to_message_id=update.message.message_id
        )
        return

    sdt, time_arg, delay, luong = context.args

    # Giới hạn time + delay
    try:
        time_arg = int(time_arg)
        delay_int = int(delay)
    except ValueError:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⚠️ Tham số time/delay phải là số nguyên.",
            reply_to_message_id=update.message.message_id
        )
        return

    if time_arg > MAX_TIME:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"⚠️ Thời gian tối đa {MAX_TIME} giây.",
            reply_to_message_id=update.message.message_id
        )
        return

    # Kiểm tra delay riêng từng user
    if user_id in next_available and now < next_available[user_id]:
        remaining = int(next_available[user_id] - now)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"⏳ {mention_html(user_id, user.first_name)}, bạn cần chờ thêm {remaining} giây trước khi chạy tiếp.",
            parse_mode="HTML",
            reply_to_message_id=update.message.message_id
        )
        return

    # Lưu thời điểm user được phép chạy tiếp theo
    next_available[user_id] = now + delay_int

    # Tạo command
    cmd = ["python", "sms.py", sdt, str(time_arg), str(delay_int), luong]

    # Đưa vào hàng đợi
    await queue.put((update.message.chat_id, user_id, cmd, context, update.message.message_id, user.first_name))
    if is_running:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"📌 {mention_html(user_id, user.first_name)}, yêu cầu của bạn đã vào hàng đợi.",
            parse_mode="HTML",
            reply_to_message_id=update.message.message_id
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"🚀 {mention_html(user_id, user.first_name)}, yêu cầu của bạn đang chạy ngay.",
            parse_mode="HTML",
            reply_to_message_id=update.message.message_id
        )


# Main
async def main():
    TOKEN = "8256690182:AAHtDRmYxb1Y7BLIK96zrHLKVFIVX_XYaZ0"  # 🔥 thay token thật vào
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("sms", sms))

    # chạy worker song song
    asyncio.create_task(worker())

    print("Bot đang chạy...")
    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())