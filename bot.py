"""
بوت تليجرام لإدارة القروبات
طريقة الاستخدام: المشرف يرد (Reply) على رسالة العضو ويكتب كلمة عربية عادية بدون /

الكلمات المتاحة (للمشرفين فقط):
- قوانين      → عرض قوانين القروب (لا يحتاج رد)
- حذف         → حذف الرسالة المردود عليها
- كتم 20      → كتم العضو 20 دقيقة (المدة من 5 إلى 60، أي رقم يقبل)
- فك          → إلغاء كتم العضو
- طرد         → طرد العضو من القروب (يمكنه العودة بدعوة جديدة)
- حظر         → حظر العضو نهائيًا من القروب

ميزات أخرى:
- ترحيب بالأعضاء الجدد
- حذف تلقائي للروابط من غير المشرفين (اختياري)
"""

import os
import re
import logging
from datetime import timedelta
from telegram import Update, ChatPermissions
from telegram.ext import (
    Application,
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

# حدود مدة الكتم بالدقائق
MUTE_MIN_MINUTES = 5
MUTE_MAX_MINUTES = 60

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
    """يتحقق من صلاحية المشرف. يرجع True لو يقدر يكمل."""
    user_id = update.effective_user.id
    if not await is_admin(update, context, user_id):
        return False
    return True


def get_target_user(update: Update):
    """يرجع المستخدم المستهدف من الرسالة المردود عليها، أو None"""
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user
    return None


# ---------- الترحيب بالأعضاء الجدد ----------

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        name = member.full_name
        await update.message.reply_text(
            f"👋 أهلاً وسهلاً {name} في القروب!\n"
            f"اكتب كلمة \"قوانين\" لعرض قوانين القروب."
        )


# ---------- معالجة الكلمات الإدارية ----------

async def show_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(GROUP_RULES)


async def delete_message_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    target_msg = update.message.reply_to_message
    if not target_msg:
        await update.message.reply_text("⚠️ يجب الرد على الرسالة التي تريد حذفها.")
        return
    try:
        await target_msg.delete()
        await update.message.delete()
    except Exception as e:
        logger.error(f"خطأ بحذف الرسالة: {e}")
        await update.message.reply_text(f"⚠️ تعذّر الحذف: {e}")


async def mute_action(update: Update, context: ContextTypes.DEFAULT_TYPE, minutes: int):
    if not await require_admin(update, context):
        return

    target = get_target_user(update)
    if not target:
        await update.message.reply_text("⚠️ يجب الرد على رسالة العضو الذي تريد كتمه.")
        return

    if minutes < MUTE_MIN_MINUTES or minutes > MUTE_MAX_MINUTES:
        await update.message.reply_text(
            f"⚠️ مدة الكتم يجب أن تكون بين {MUTE_MIN_MINUTES} و {MUTE_MAX_MINUTES} دقيقة.\n"
            f"مثال: كتم 20"
        )
        return

    permissions = ChatPermissions(can_send_messages=False)
    until_date = update.message.date + timedelta(minutes=minutes)
    try:
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
            permissions=permissions,
            until_date=until_date,
        )
        await update.message.reply_text(
            f"🔇 تم كتم {target.full_name} لمدة {minutes} دقيقة."
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ فشل الكتم: {e}")


async def unmute_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return

    target = get_target_user(update)
    if not target:
        await update.message.reply_text("⚠️ يجب الرد على رسالة العضو الذي تريد إلغاء كتمه.")
        return

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


async def kick_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return

    target = get_target_user(update)
    if not target:
        await update.message.reply_text("⚠️ يجب الرد على رسالة العضو الذي تريد طرده.")
        return

    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target.id)
        await context.bot.unban_chat_member(update.effective_chat.id, target.id)  # طرد بدون حظر دائم
        await update.message.reply_text(f"👋 تم طرد {target.full_name} من القروب.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ فشل الطرد: {e}")


async def ban_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return

    target = get_target_user(update)
    if not target:
        await update.message.reply_text("⚠️ يجب الرد على رسالة العضو الذي تريد حظره.")
        return

    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target.id)
        await update.message.reply_text(f"⛔ تم حظر {target.full_name} من القروب.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ فشل الحظر: {e}")


# ---------- التوجيه الرئيسي للرسائل النصية ----------

# نمط "كتم" مع رقم بعدها، مثل: كتم 20
MUTE_PATTERN = re.compile(r"^كتم\s+(\d+)$")


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()

    # قوانين القروب - متاح لكل الأعضاء، بدون رد
    if text == "قوانين":
        await show_rules(update, context)
        return

    # كتم برقم دقائق، مثل: كتم 20
    mute_match = MUTE_PATTERN.match(text)
    if mute_match:
        minutes = int(mute_match.group(1))
        await mute_action(update, context, minutes)
        return

    # باقي الكلمات الإدارية (مطابقة دقيقة)
    if text == "حذف":
        await delete_message_action(update, context)
        return
    if text == "فك":
        await unmute_action(update, context)
        return
    if text == "طرد":
        await kick_action(update, context)
        return
    if text == "حظر":
        await ban_action(update, context)
        return

    # إن لم تكن كلمة إدارية، تحقق من وجود روابط للحذف التلقائي
    await auto_delete_links(update, context)


# ---------- حذف الروابط تلقائيًا ----------

async def auto_delete_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not AUTO_DELETE_LINKS:
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

    # الترحيب بالأعضاء الجدد
    app.add_handler(
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member)
    )

    # كل الرسائل النصية تذهب لدالة التوجيه الرئيسية
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    logger.info("البوت بدأ التشغيل...")
    app.run_polling()


if __name__ == "__main__":
    main()
