import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# إعدادات logging (للمتابعة في حالة وجود أخطاء)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# استدعاء التوكن من متغيرات البيئة في Render
TOKEN = os.getenv("TOKEN")
# هنا تضع الـ ID الخاص بك كمطور (للحماية). قم بتغيير هذا الرقم.
ADMIN_IDS = [000000000]

# اسم ملف قاعدة البيانات
DATA_FILE = "data.json"

# حالة الأدمن المؤقتة لتوجيهه
admin_state = {}

# --- دوال إدارة البيانات ---
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# --- واجهة المستخدم العادية ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    keyboard = [[InlineKeyboardButton(dept, callback_data=f"dept:{dept}")] for dept in data.keys()]
    if not keyboard:
        await update.message.reply_text("لا يوجد محتوى حالياً.")
        return
    await update.message.reply_text("اختر التخصص:", reply_markup=InlineKeyboardMarkup(keyboard))

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split(':')
    context.user_data['path'] = parts[1:]
    
    current_data = load_data()
    for part in context.user_data['path']:
        current_data = current_data.get(part, {})

    if "Videos" in current_data or "Books" in current_data or "Professors" in current_data:
        # عرض المحتوى أو الأقسام الفرعية
        keyboard = []
        if "Videos" in current_data and current_data["Videos"]:
            keyboard.append([InlineKeyboardButton("📹 فيديوهات", callback_data=f"{query.data}:Videos")])
        if "Books" in current_data and current_data["Books"]:
            keyboard.append([InlineKeyboardButton("📚 كتب", callback_data=f"{query.data}:Books")])
        if "Professors" in current_data and current_data["Professors"]:
            prof_keys = list(current_data["Professors"].keys())
            for prof in prof_keys:
                keyboard.append([InlineKeyboardButton(f"👨‍🏫 {prof}", callback_data=f"{query.data}:Professors:{prof}")])
        
        # أزرار الرجوع
        back_path = ":".join(parts[:-1]) if len(parts) > 1 else "main_menu"
        keyboard.append([InlineKeyboardButton("⬅️ رجوع", callback_data=f"back:{back_path}")])

        await query.edit_message_text("اختر ما تريده:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.endswith(":Videos") or query.data.endswith(":Books"):
        # إرسال الملفات
        file_path = query.data.split(':')
        data_to_send = load_data()
        for part in file_path[1:]:
            data_to_send = data_to_send.get(part, {})
            
        file_type = "Videos" if query.data.endswith(":Videos") else "Books"
        for item in data_to_send.get(file_type, []):
            if file_type == "Videos":
                await context.bot.send_video(chat_id=update.effective_chat.id, video=item['file_id'], caption=item['title'])
            else:
                await context.bot.send_document(chat_id=update.effective_chat.id, document=item['file_id'], caption=item['title'])

    elif query.data.startswith("back:"):
        # الرجوع خطوة للخلف
        back_path = query.data.split(':')[1:]
        if not back_path or back_path[0] == "main_menu":
            await start(query, context)
        else:
            query.data = ":".join(back_path)
            await menu_handler(query, context)

# --- لوحة تحكم الأدمن (قائمة على الأزرار) ---
async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ غير مسموح لك بالوصول لهذه اللوحة.")
        return

    keyboard = [
        [InlineKeyboardButton("➕ إضافة محتوى جديد", callback_data="admin:add_content")],
        [InlineKeyboardButton("📁 إضافة فرع جديد", callback_data="admin:add_branch")],
        [InlineKeyboardButton("🗑️ حذف / تعديل محتوى", callback_data="admin:manage_content")]
    ]
    await update.message.reply_text("لوحة تحكم الأدمن:", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    admin_state[query.from_user.id] = query.data # حفظ حالة الأدمن
    parts = query.data.split(':')

    # مرحلة إضافة محتوى
    if parts[1] == "add_content":
        data = load_data()
        keyboard = [[InlineKeyboardButton(k, callback_data=f"admin_path:{k}")] for k in data.keys()]
        await query.edit_message_text("اختر القسم:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif parts[0] == "admin_path":
        # التنقل في الهيكل
        data = load_data()
        path_list = parts[1:]
        current_data = data
        for p in path_list:
            current_data = current_data.get(p, {})

        keyboard = []
        if isinstance(current_data, dict):
            for k, v in current_data.items():
                if isinstance(v, dict):
                    keyboard.append([InlineKeyboardButton(k, callback_data=f"admin_path:{':'.join(path_list)}:{k}")])
                elif isinstance(v, list) and (k == "Videos" or k == "Books"):
                    admin_state[query.from_user.id] = f"await_file:{':'.join(path_list)}:{k}"
                    await query.edit_message_text(f"الآن، أرسل الملف/الفيديو واكتب عنوانه في التعليق.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data="admin:add_content")]]))
                    return
        
        # أزرار الرجوع
        if len(path_list) > 1:
            back_path = ":".join(path_list[:-1])
            keyboard.append([InlineKeyboardButton("⬅️ رجوع", callback_data=f"admin_path:{back_path}")])
        else:
            keyboard.append([InlineKeyboardButton("⬅️ رجوع", callback_data="admin:add_content")])

        await query.edit_message_text("اختر الفرع أو النوع:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_admin_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in admin_state or not admin_state[user_id].startswith("await_file"):
        return

    state_parts = admin_state[user_id].split(':')
    file_path = state_parts[1:-1]
    file_type = state_parts[-1]
    file_title = update.message.caption if update.message.caption else "بدون عنوان"
    file_id = None

    if update.message.document:
        file_id = update.message.document.file_id
    elif update.message.video:
        file_id = update.message.video.file_id
    
    if not file_id:
        await update.message.reply_text("❌ لم يتم التعرف على ملف. الرجاء إرسال ملف أو فيديو.")
        return

    data = load_data()
    current_data = data
    for p in file_path:
        current_data = current_data.get(p, {})
        
    current_data[file_type].append({"title": file_title, "file_id": file_id})
    save_data(data)
    
    del admin_state[user_id]
    await update.message.reply_text(f"✅ تم إضافة {file_title} بنجاح!")


# --- دالة main لتشغيل البوت ---
def main():
    app = Application.builder().token(TOKEN).build()
    
    # أوامر المستخدم العادي
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(menu_handler, pattern="^(?!admin:).*"))

    # أوامر ولوحة تحكم الأدمن
    app.add_handler(CommandHandler("admin", admin_start))
    app.add_handler(CallbackQueryHandler(admin_handler, pattern="^admin:.*|^admin_path:.*"))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.ALL, handle_admin_file))

    # تشغيل البوت
    app.run_polling()

if __name__ == "__main__":
    main()
