"""
بوت المكتبة - نسخة مبنية بكود، بتسمح بتكرار اسم الزر بأكتر من مكان
لأنه كل زر مربوط برقم فريد (id) بالخلفية، مش بالاسم.

الأوامر:
  /start  -> يفتح للمستخدم قائمة الأقسام (تصفح المكتبة)
  /admin  -> يفتح لوحة تحكم الأدمن (إضافة/تعديل/حذف)، لأدمن واحد بس (ADMIN_ID)
"""
import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import database as db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])

# حالات المحادثة (لما البوت مستني منك تكتب نص)
ASK_CAT_NAME, ASK_SUBJ_NAME, ASK_SUBJ_CONTENT, ASK_NEW_NAME, ASK_NEW_CONTENT = range(5)


def is_admin(update: Update) -> bool:
    return update.effective_user and update.effective_user.id == ADMIN_ID


# ---------------------------------------------------------------- #
# تصفّح المكتبة (لكل المستخدمين)
# ---------------------------------------------------------------- #

def build_browse_keyboard(parent_id):
    rows = []
    for cat in db.get_categories(parent_id):
        rows.append([InlineKeyboardButton(cat["name"], callback_data=f"cat:{cat['id']}")])
    for subj in db.get_subjects(parent_id) if parent_id else []:
        pass  # subjects only shown once we're inside a category (handled in cat_open)
    if parent_id:
        parent = db.get_category(parent_id)
        back_to = parent["parent_id"] or 0
        rows.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"back:{back_to}")])
    return InlineKeyboardMarkup(rows)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 مرحباً بك في المكتبة، اختر القسم:",
        reply_markup=build_browse_keyboard(None),
    )


async def open_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = int(query.data.split(":")[1])
    category = db.get_category(cat_id)

    rows = []
    for sub_cat in db.get_categories(cat_id):
        rows.append([InlineKeyboardButton(sub_cat["name"], callback_data=f"cat:{sub_cat['id']}")])
    for subj in db.get_subjects(cat_id):
        rows.append([InlineKeyboardButton(subj["display_name"], callback_data=f"subj:{subj['id']}")])

    back_to = category["parent_id"] or 0
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"back:{back_to}")])

    await query.edit_message_text(
        f"📂 {category['name']}", reply_markup=InlineKeyboardMarkup(rows)
    )


async def go_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target = int(query.data.split(":")[1])
    if target == 0:
        await query.edit_message_text(
            "📚 مرحباً بك في المكتبة، اختر القسم:", reply_markup=build_browse_keyboard(None)
        )
    else:
        category = db.get_category(target)
        rows = []
        for sub_cat in db.get_categories(target):
            rows.append([InlineKeyboardButton(sub_cat["name"], callback_data=f"cat:{sub_cat['id']}")])
        for subj in db.get_subjects(target):
            rows.append([InlineKeyboardButton(subj["display_name"], callback_data=f"subj:{subj['id']}")])
        rows.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"back:{category['parent_id'] or 0}")])
        await query.edit_message_text(f"📂 {category['name']}", reply_markup=InlineKeyboardMarkup(rows))


async def open_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    subj_id = int(query.data.split(":")[1])
    subject = db.get_subject(subj_id)
    content = subject["content"] or "ما في محتوى مضاف لهاي المادة بعد."
    rows = [[InlineKeyboardButton("🔙 رجوع", callback_data=f"back:{subject['category_id']}")]]
    await query.edit_message_text(
        f"📄 {subject['display_name']}\n\n{content}", reply_markup=InlineKeyboardMarkup(rows)
    )


# ---------------------------------------------------------------- #
# لوحة تحكم الأدمن
# ---------------------------------------------------------------- #

def admin_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة قسم", callback_data="a_add_cat:0")],
        [InlineKeyboardButton("➕ إضافة مادة (زر)", callback_data="a_add_subj_pick")],
        [InlineKeyboardButton("✏️ تعديل مادة", callback_data="a_edit_pick")],
        [InlineKeyboardButton("🗑️ حذف مادة", callback_data="a_del_pick")],
        [InlineKeyboardButton("🗑️ حذف قسم", callback_data="a_del_cat_pick")],
    ])


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    await update.message.reply_text("⚙️ لوحة تحكم الأدمن:", reply_markup=admin_menu_keyboard())


def category_picker_keyboard(prefix, parent_id=0):
    """قائمة أقسام للاختيار منها، تدعم الدخول لقسم فرعي أثناء الاختيار."""
    rows = []
    for cat in db.get_categories(parent_id or None):
        rows.append([
            InlineKeyboardButton(f"📂 {cat['name']}", callback_data=f"{prefix}:{cat['id']}"),
        ])
    if parent_id:
        parent = db.get_category(parent_id)
        rows.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"{prefix}nav:{parent['parent_id'] or 0}")])
    if parent_id == 0 or parent_id is None:
        rows.append([InlineKeyboardButton("✅ اختر هذا المستوى (الرئيسي)", callback_data=f"{prefix}:0")])
    else:
        rows.append([InlineKeyboardButton("✅ اختر هذا القسم", callback_data=f"{prefix}:{parent_id}")])
    return InlineKeyboardMarkup(rows)


# ---- إضافة قسم ----

async def add_cat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    query = update.callback_query
    await query.answer()
    parent_id = int(query.data.split(":")[1])
    context.user_data["new_cat_parent"] = parent_id or None
    await query.edit_message_text("✏️ اكتب اسم القسم الجديد:")
    return ASK_CAT_NAME


async def add_cat_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    parent_id = context.user_data.get("new_cat_parent")
    db.add_category(name, parent_id)
    await update.message.reply_text(f"✅ تمت إضافة القسم: {name}", reply_markup=admin_menu_keyboard())
    return ConversationHandler.END


# ---- إضافة مادة (زر) ----

async def add_subj_pick_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📂 اختر القسم يلي بدك تضيف فيه المادة:",
        reply_markup=category_picker_keyboard("a_add_subj"),
    )


async def add_subj_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parent_id = int(query.data.split(":")[1])
    await query.edit_message_text(
        "📂 اختر القسم يلي بدك تضيف فيه المادة:",
        reply_markup=category_picker_keyboard("a_add_subj", parent_id),
    )


async def add_subj_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = int(query.data.split(":")[1])
    if cat_id == 0:
        await query.edit_message_text("⚠️ لازم تختار قسم فعلي (مش المستوى الرئيسي) لإضافة مادة فيه.")
        return ConversationHandler.END
    context.user_data["new_subj_cat"] = cat_id
    await query.edit_message_text("✏️ اكتب اسم المادة (الزر) - ممكن يتكرر مع أي اسم موجود:")
    return ASK_SUBJ_NAME


async def add_subj_got_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_subj_name"] = update.message.text.strip()
    await update.message.reply_text("📝 هلأ اكتب المحتوى (نص، رابط، الخ) - أو ارسل - لتركه فاضي حالياً:")
    return ASK_SUBJ_CONTENT


async def add_subj_got_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    content = update.message.text.strip()
    if content == "-":
        content = None
    name = context.user_data.pop("new_subj_name")
    cat_id = context.user_data.pop("new_subj_cat")
    db.add_subject(name, cat_id, content)
    await update.message.reply_text(f"✅ تمت إضافة المادة: {name}", reply_markup=admin_menu_keyboard())
    return ConversationHandler.END


# ---- تعديل / حذف مادة: اختيار القسم ثم المادة ----

async def pick_category_for(update: Update, context: ContextTypes.DEFAULT_TYPE, prefix, title):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(title, reply_markup=category_picker_keyboard(prefix))


async def edit_pick_category(update, context):
    await pick_category_for(update, context, "a_edit_cat", "📂 من أي قسم بدك تعدّل مادة؟")

async def edit_pick_category_nav(update, context):
    query = update.callback_query
    await query.answer()
    parent_id = int(query.data.split(":")[1])
    await query.edit_message_text("📂 من أي قسم بدك تعدّل مادة؟", reply_markup=category_picker_keyboard("a_edit_cat", parent_id))

async def del_pick_category(update, context):
    await pick_category_for(update, context, "a_del_cat_of", "📂 من أي قسم بدك تحذف مادة؟")

async def del_pick_category_nav(update, context):
    query = update.callback_query
    await query.answer()
    parent_id = int(query.data.split(":")[1])
    await query.edit_message_text("📂 من أي قسم بدك تحذف مادة؟", reply_markup=category_picker_keyboard("a_del_cat_of", parent_id))


def subjects_keyboard(cat_id, prefix):
    rows = []
    for subj in db.get_subjects(cat_id):
        rows.append([InlineKeyboardButton(subj["display_name"], callback_data=f"{prefix}:{subj['id']}")])
    rows.append([InlineKeyboardButton("🔙 إلغاء", callback_data="admin_menu")])
    return InlineKeyboardMarkup(rows)


async def edit_list_subjects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = int(query.data.split(":")[1])
    if cat_id == 0:
        await query.edit_message_text("⚠️ اختر قسم فعلي فيه مواد.")
        return
    await query.edit_message_text("✏️ اختر المادة يلي بدك تعدلها:", reply_markup=subjects_keyboard(cat_id, "a_edit_s"))


async def edit_choose_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    subj_id = int(query.data.split(":")[1])
    context.user_data["edit_subj_id"] = subj_id
    rows = [
        [InlineKeyboardButton("✏️ تغيير الاسم", callback_data=f"a_edit_name:{subj_id}")],
        [InlineKeyboardButton("📝 تغيير المحتوى", callback_data=f"a_edit_content:{subj_id}")],
    ]
    await query.edit_message_text("شو بدك تعدّل؟", reply_markup=InlineKeyboardMarkup(rows))


async def edit_ask_new_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["edit_subj_id"] = int(query.data.split(":")[1])
    await query.edit_message_text("✏️ اكتب الاسم الجديد (ممكن يكون نفس أي اسم موجود، ما في مشكلة):")
    return ASK_NEW_NAME


async def edit_save_new_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subj_id = context.user_data.pop("edit_subj_id")
    db.update_subject_name(subj_id, update.message.text.strip())
    await update.message.reply_text("✅ تم تعديل الاسم.", reply_markup=admin_menu_keyboard())
    return ConversationHandler.END


async def edit_ask_new_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["edit_subj_id"] = int(query.data.split(":")[1])
    await query.edit_message_text("📝 اكتب المحتوى الجديد:")
    return ASK_NEW_CONTENT


async def edit_save_new_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subj_id = context.user_data.pop("edit_subj_id")
    db.update_subject_content(subj_id, update.message.text.strip())
    await update.message.reply_text("✅ تم تعديل المحتوى.", reply_markup=admin_menu_keyboard())
    return ConversationHandler.END


async def delete_list_subjects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = int(query.data.split(":")[1])
    if cat_id == 0:
        await query.edit_message_text("⚠️ اختر قسم فعلي فيه مواد.")
        return
    await query.edit_message_text("🗑️ اختر المادة يلي بدك تحذفها:", reply_markup=subjects_keyboard(cat_id, "a_del_s"))


async def delete_subject_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    subj_id = int(query.data.split(":")[1])
    subject = db.get_subject(subj_id)
    db.delete_subject(subj_id)
    await query.edit_message_text(f"🗑️ تم حذف: {subject['display_name']}", reply_markup=admin_menu_keyboard())


async def del_cat_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await pick_category_for(update, context, "a_del_cat_confirm", "🗑️ اختر القسم يلي بدك تحذفه (رح يحذف كل يلي فيه):")

async def del_cat_pick_nav(update, context):
    query = update.callback_query
    await query.answer()
    parent_id = int(query.data.split(":")[1])
    await query.edit_message_text("🗑️ اختر القسم يلي بدك تحذفه:", reply_markup=category_picker_keyboard("a_del_cat_confirm", parent_id))

async def del_cat_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = int(query.data.split(":")[1])
    if cat_id == 0:
        await query.edit_message_text("⚠️ ما في قسم رئيسي وحيد للحذف - اختر قسم فرعي فعلي.")
        return
    category = db.get_category(cat_id)
    db.delete_category(cat_id)
    await query.edit_message_text(f"🗑️ تم حذف القسم: {category['name']} وكل يلي فيه.", reply_markup=admin_menu_keyboard())


async def back_to_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("⚙️ لوحة تحكم الأدمن:", reply_markup=admin_menu_keyboard())


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ تم الإلغاء.", reply_markup=admin_menu_keyboard())
    return ConversationHandler.END


def main():
    db.init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    # تصفّح المستخدم
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(open_category, pattern=r"^cat:"))
    app.add_handler(CallbackQueryHandler(go_back, pattern=r"^back:"))
    app.add_handler(CallbackQueryHandler(open_subject, pattern=r"^subj:"))

    # لوحة الأدمن
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(back_to_admin_menu, pattern=r"^admin_menu$"))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(add_cat_start, pattern=r"^a_add_cat:")],
        states={ASK_CAT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_cat_save)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    app.add_handler(CallbackQueryHandler(add_subj_pick_category, pattern=r"^a_add_subj_pick$"))
    app.add_handler(CallbackQueryHandler(add_subj_nav, pattern=r"^a_add_subjnav:"))
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(add_subj_start, pattern=r"^a_add_subj:")],
        states={
            ASK_SUBJ_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_subj_got_name)],
            ASK_SUBJ_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_subj_got_content)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    app.add_handler(CallbackQueryHandler(edit_pick_category, pattern=r"^a_edit_pick$"))
    app.add_handler(CallbackQueryHandler(edit_pick_category_nav, pattern=r"^a_edit_catnav:"))
    app.add_handler(CallbackQueryHandler(edit_list_subjects, pattern=r"^a_edit_cat:"))
    app.add_handler(CallbackQueryHandler(edit_choose_field, pattern=r"^a_edit_s:"))
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_ask_new_name, pattern=r"^a_edit_name:")],
        states={ASK_NEW_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_save_new_name)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_ask_new_content, pattern=r"^a_edit_content:")],
        states={ASK_NEW_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_save_new_content)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    app.add_handler(CallbackQueryHandler(del_pick_category, pattern=r"^a_del_pick$"))
    app.add_handler(CallbackQueryHandler(del_pick_category_nav, pattern=r"^a_del_cat_ofnav:"))
    app.add_handler(CallbackQueryHandler(delete_list_subjects, pattern=r"^a_del_cat_of:"))
    app.add_handler(CallbackQueryHandler(delete_subject_confirm, pattern=r"^a_del_s:"))

    app.add_handler(CallbackQueryHandler(del_cat_pick, pattern=r"^a_del_cat_pick$"))
    app.add_handler(CallbackQueryHandler(del_cat_pick_nav, pattern=r"^a_del_cat_confirmnav:"))
    app.add_handler(CallbackQueryHandler(del_cat_confirm, pattern=r"^a_del_cat_confirm:"))

    port = int(os.environ.get("PORT", "10000"))
    webhook_url = os.environ["WEBHOOK_URL"]  # مثال: https://your-app.onrender.com
    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=BOT_TOKEN,
        webhook_url=f"{webhook_url}/{BOT_TOKEN}",
    )


if __name__ == "__main__":
    main()
