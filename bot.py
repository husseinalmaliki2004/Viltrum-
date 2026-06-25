"""
بوت تليجرام لإدارة القروبات
الميزات:
- ترحيب بالأعضاء الجدد
- حذف رسائل (للمشرفين فقط، بالرد على الرسالة بـ /del)
- كتم عضو (/mute بالرد على رسالته)
- إلغاء كتم عضو (/unmute بالرد على رسالته)
- طرد عضو (/kick بالرد على رسالته)
- حظر عضو (/ban بالرد على رسالته)
- أمر /rules لعرض قوانين القروب
- حذف تلقائي للروابط من غير الأعضاء المشرفين (اختياري - مفعّل بشكل افتراضي)
"""

import os
import logging
from telegram import Update, ChatPermissions
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# التوكن يُقرأ من متغيّر البيئة BOT_TOKEN (يُضبط في Railway > Variables)
BOT_TOKEN = os.environ.get("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError(
        "لم يتم العثور على BOT_TOKEN. تأكد من إضافته في إعدادات Variables بـ Railway."
    )

# نص قوانين القروب، عدّله كما تريد
GROUP_RULES = """
📜 قوانين القروب:
1. الاحترام المتبادل بين جميع الأعضاء.
2. ممنوع نشر الروابط أو الإعلانات بدون إذن.
3. ممنوع السبام أو تكرار الرسائل.
4. الموضوعات يجب أن تكون متعلقة بهدف القروب.
"""

# تفعيل أو تعطيل حذف الروابط تلقائيًا من غير المشرفين
AUTO_DELETE_LINKS = True

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ---------- دوال مساعدة ----------

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    """تتحقق إذا كان المستخدم مشرفًا في القروب"""
    chat_admins = await context.bot.get_chat_administrators(update.effective_chat.id)
    admin_ids = [admin.user.id for admin in chat_admins]
    return user_id in admin_ids


async def require_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """يتحقق من صلاحية المشرف ويرسل رسالة رفض إن لم يكن مشرفًا. يرجع True لو يقدر يكمل."""
    user_id = update.effective_user.id
    if not await is_admin(update, context, user_id):
        await update.message.reply_text("⚠️ هذا الأمر للمشرفين فقط.")
        return False
    return True


# ---------- الترحيب بالأعضاء الجدد ----------

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        name = member.full_name
        await update.message.reply_text(
            f"👋 أهلاً وسهلاً {name} في القروب!\n"
            f"يرجى قراءة القوانين عن طريق الأمر /rules"
        )


# ---------- الأوامر ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ البوت يعمل الآن.\nاستخدم /help لعرض الأوامر المتاحة."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📋 الأوامر المتاحة:\n\n"
        "/rules - عرض قوانين القروب\n"
        "/del - حذف رسالة (بالرد عليها) - للمشرفين\n"
        "/mute - كتم عضو (بالرد على رسالته) - للمشرفين\n"
        "/unmute - إلغاء كتم عضو (بالرد على رسالته) - للمشرفين\n"
        "/kick - طرد عضو (بالرد على رسالته) - للمشرفين\n"
        "/ban - حظر عضو (بالرد على رسالته) - للمشرفين\n"
    )
    await update.message.reply_text(text)


async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(GROUP_RULES)


async def delete_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    if update.message.reply_to_message:
        try:
            await update.message.reply_to_message.delete()
            await update.message.delete()
        except Exception as e:
            logger.error(f"خطأ بحذف الرسالة: {e}")
    else:
        await update.message.reply_text("⚠️ يجب الرد على الرسالة التي تريد حذفها.")


async def mute_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ يجب الرد على رسالة العضو الذي تريد كتمه.")
        return

    target = update.message.reply_to_message.from_user
    permissions = ChatPermissions(can_send_messages=False)
    try:
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
            permissions=permissions,
        )
        await update.message.reply_text(f"🔇 تم كتم {target.full_name}.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ فشل الكتم: {e}")


async def unmute_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ يجب الرد على رسالة العضو الذي تريد إلغاء كتمه.")
        return

    target = update.message.reply_to_message.from_user
    permissions = ChatPermissions(
        can_send_messages=True,
        can_send_audios=True,
        can_send_documents=True,
        can_send_photos=True,
        can_send_videos=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
    )
    try:
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
            permissions=permissions,
        )
        await update.message.reply_text(f"🔊 تم إلغاء الكتم عن {target.full_name}.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ فشل إلغاء الكتم: {e}")


async def kick_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ يجب الرد على رسالة العضو الذي تريد طرده.")
        return

    target = update.message.reply_to_message.from_user
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target.id)
        await context.bot.unban_chat_member(update.effective_chat.id, target.id)  # طرد بدون حظر دائم
        await update.message.reply_text(f"👋 تم طرد {target.full_name} من القروب.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ فشل الطرد: {e}")


async def ban_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ يجب الرد على رسالة العضو الذي تريد حظره.")
        return

    target = update.message.reply_to_message.from_user
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target.id)
        await update.message.reply_text(f"⛔ تم حظر {target.full_name} من القروب.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ فشل الحظر: {e}")


# ---------- حذف الروابط تلقائيًا ----------

async def auto_delete_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not AUTO_DELETE_LINKS:
        return
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    if await is_admin(update, context, user_id):
        return  # لا تحذف روابط المشرفين

    text = update.message.text.lower()
    link_keywords = ["http://", "https://", "t.me/", "www."]
    if any(keyword in text for keyword in link_keywords):
        try:
            await update.message.delete()
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"🚫 تم حذف رسالة {update.effective_user.full_name} لاحتوائها على رابط.",
            )
        except Exception as e:
            logger.error(f"خطأ بحذف الرابط: {e}")


# ---------- تشغيل البوت ----------

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # الأوامر
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("rules", rules_command))
    app.add_handler(CommandHandler("del", delete_message))
    app.add_handler(CommandHandler("mute", mute_member))
    app.add_handler(CommandHandler("unmute", unmute_member))
    app.add_handler(CommandHandler("kick", kick_member))
    app.add_handler(CommandHandler("ban", ban_member))

    # الترحيب بالأعضاء الجدد
    app.add_handler(
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member)
    )

    # حذف الروابط تلقائيًا (يجب أن يكون آخر handler للرسائل النصية)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_delete_links))

    logger.info("البوت بدأ التشغيل...")
    app.run_polling()


if __name__ == "__main__":
    main()
