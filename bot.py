import logging
import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from telegram.error import TelegramError

# ============================================================
# SOZLAMALAR
# ============================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_IDS = list(map(int, os.environ.get("ADMIN_IDS", "123456789").split(",")))
DATA_FILE = "data.json"

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# MA'LUMOTLARNI SAQLASH
# ============================================================

def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {
            "restaurants": {},
            "orders": [],
            "next_rest_id": 1,
            "next_food_id": 1
        }

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

db = load_data()

# ============================================================
# CONVERSATION STATES
# ============================================================
(
    REST_NAME, REST_PHONE, REST_ADDRESS, REST_PHOTO,
    FOOD_NAME, FOOD_DESC, FOOD_PRICE, FOOD_PHOTO,
    EDIT_PRICE
) = range(9)

# ============================================================
# YORDAMCHI FUNKSIYALAR
# ============================================================

def is_admin(user_id):
    return user_id in ADMIN_IDS

def main_menu_keyboard(is_adm=False):
    buttons = [
        [InlineKeyboardButton("🍽 Restoranlar", callback_data="restaurants")],
    ]
    if is_adm:
        buttons.append([InlineKeyboardButton("⚙️ Admin panel", callback_data="admin_panel")])
    return InlineKeyboardMarkup(buttons)

def back_keyboard(to="main"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data=f"back_{to}")]])

# ============================================================
# START
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    adm = is_admin(user.id)
    text = (
        f"🏘 *MAHALLA* botiga xush kelibsiz, {user.first_name}!\n\n"
        "Bu yerda mahallangizning barcha oshxonalari va ularning menyulari mavjud.\n\n"
        "Quyidagi tugmani bosing:"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard(adm))

# ============================================================
# RESTORANLAR RO'YXATI
# ============================================================

async def show_restaurants(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    rests = db.get("restaurants", {})
    if not rests:
        await query.edit_message_text("😔 Hozircha restoranlar yo'q.", reply_markup=back_keyboard("main"))
        return

    buttons = []
    for rid, r in rests.items():
        buttons.append([InlineKeyboardButton(f"🍴 {r['name']}", callback_data=f"rest_{rid}")])
    buttons.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")])

    await query.edit_message_text(
        "🍽 *Restoranlar ro'yxati:*\nQuyidagilardan birini tanlang:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def show_restaurant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rid = query.data.split("_")[1]
    r = db["restaurants"].get(rid)
    if not r:
        await query.edit_message_text("Restoran topilmadi.")
        return

    foods = r.get("foods", {})
    food_count = len(foods)

    caption = (
        f"🍴 *{r['name']}*\n\n"
        f"📍 Manzil: {r.get('address', 'Ko\'rsatilmagan')}\n"
        f"📞 Telefon: `{r.get('phone', 'Ko\'rsatilmagan')}`\n"
        f"🍜 Taomlar soni: {food_count} ta\n\n"
        "Menyu ko'rish uchun quyidagi tugmani bosing:"
    )

    buttons = [
        [InlineKeyboardButton("📋 Menyuni ko'rish", callback_data=f"menu_{rid}")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="restaurants")]
    ]

    try:
        if r.get("photo"):
            await query.message.reply_photo(
                photo=r["photo"],
                caption=caption,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            await query.message.delete()
        else:
            await query.edit_message_text(caption, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
    except:
        await query.edit_message_text(caption, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rid = query.data.split("_")[1]
    r = db["restaurants"].get(rid)
    if not r:
        return

    foods = r.get("foods", {})
    if not foods:
        await query.edit_message_text(
            f"😔 *{r['name']}* restoranida hozircha taomlar yo'q.",
            parse_mode="Markdown",
            reply_markup=back_keyboard(f"rest_{rid}")
        )
        return

    buttons = []
    for fid, food in foods.items():
        buttons.append([InlineKeyboardButton(
            f"🍜 {food['name']} — {food['price']:,} so'm",
            callback_data=f"food_{rid}_{fid}"
        )])
    buttons.append([InlineKeyboardButton("🔙 Orqaga", callback_data=f"rest_{rid}")])

    await query.edit_message_text(
        f"📋 *{r['name']}* menyusi:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def show_food(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, rid, fid = query.data.split("_")
    r = db["restaurants"].get(rid)
    food = r["foods"].get(fid) if r else None
    if not food:
        return

    caption = (
        f"🍜 *{food['name']}*\n\n"
        f"📝 Tarkibi: {food.get('desc', 'Ko\'rsatilmagan')}\n"
        f"💰 Narxi: *{food['price']:,} so'm*\n\n"
        f"📞 Buyurtma uchun: `{r.get('phone', '')}`"
    )

    buttons = [[InlineKeyboardButton("🔙 Menyuga qaytish", callback_data=f"menu_{rid}")]]

    try:
        if food.get("photo"):
            await query.message.reply_photo(
                photo=food["photo"],
                caption=caption,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            await query.message.delete()
        else:
            await query.edit_message_text(caption, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
    except:
        await query.edit_message_text(caption, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

# ============================================================
# ADMIN PANEL
# ============================================================

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    buttons = [
        [InlineKeyboardButton("➕ Restoran qo'shish", callback_data="admin_add_rest")],
        [InlineKeyboardButton("🗑 Restoran o'chirish", callback_data="admin_del_rest")],
        [InlineKeyboardButton("🍜 Taom qo'shish", callback_data="admin_add_food")],
        [InlineKeyboardButton("✏️ Narx o'zgartirish", callback_data="admin_edit_price")],
        [InlineKeyboardButton("🗑 Taom o'chirish", callback_data="admin_del_food")],
        [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")],
    ]
    await query.edit_message_text("⚙️ *Admin panel*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rests = db.get("restaurants", {})
    total_foods = sum(len(r.get("foods", {})) for r in rests.values())

    text = (
        f"📊 *Statistika*\n\n"
        f"🍴 Restoranlar: *{len(rests)}* ta\n"
        f"🍜 Jami taomlar: *{total_foods}* ta\n"
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_keyboard("admin_panel"))

# ============================================================
# RESTORAN QO'SHISH
# ============================================================

async def admin_add_rest_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["action"] = "add_rest"
    await query.edit_message_text("🏷 Restoran *nomini* kiriting:", parse_mode="Markdown")
    return REST_NAME

async def rest_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_rest"] = {"name": update.message.text}
    await update.message.reply_text("📞 Restoran *telefon raqamini* kiriting:\nMasalan: +998901234567", parse_mode="Markdown")
    return REST_PHONE

async def rest_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_rest"]["phone"] = update.message.text
    await update.message.reply_text("📍 Restoran *manzilini* kiriting:", parse_mode="Markdown")
    return REST_ADDRESS

async def rest_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_rest"]["address"] = update.message.text
    await update.message.reply_text("📸 Restoran *rasmini* yuboring (yoki /skip yozing):", parse_mode="Markdown")
    return REST_PHOTO

async def rest_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_id = None
    if update.message.photo:
        photo_id = update.message.photo[-1].file_id
    
    rid = str(db["next_rest_id"])
    db["next_rest_id"] += 1
    db["restaurants"][rid] = {
        **context.user_data["new_rest"],
        "photo": photo_id,
        "foods": {},
        "created": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    save_data(db)

    await update.message.reply_text(
        f"✅ *{context.user_data['new_rest']['name']}* restoran qo'shildi!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Admin panel", callback_data="admin_panel")]])
    )
    return ConversationHandler.END

async def skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.setdefault("new_rest", {})
    rid = str(db["next_rest_id"])
    db["next_rest_id"] += 1
    db["restaurants"][rid] = {
        **context.user_data["new_rest"],
        "photo": None,
        "foods": {},
        "created": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    save_data(db)
    await update.message.reply_text(
        f"✅ Restoran qo'shildi!",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Admin panel", callback_data="admin_panel")]])
    )
    return ConversationHandler.END

# ============================================================
# RESTORAN O'CHIRISH
# ============================================================

async def admin_del_rest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rests = db.get("restaurants", {})
    if not rests:
        await query.edit_message_text("Restoranlar yo'q.", reply_markup=back_keyboard("admin_panel"))
        return

    buttons = []
    for rid, r in rests.items():
        buttons.append([InlineKeyboardButton(f"🗑 {r['name']}", callback_data=f"delrest_{rid}")])
    buttons.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")])
    await query.edit_message_text("Qaysi restoranni o'chirmoqchisiz?", reply_markup=InlineKeyboardMarkup(buttons))

async def confirm_del_rest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rid = query.data.split("_")[1]
    r = db["restaurants"].pop(rid, None)
    save_data(db)
    name = r["name"] if r else "Noma'lum"
    await query.edit_message_text(
        f"✅ *{name}* o'chirildi!",
        parse_mode="Markdown",
        reply_markup=back_keyboard("admin_panel")
    )

# ============================================================
# TAOM QO'SHISH
# ============================================================

async def admin_add_food_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rests = db.get("restaurants", {})
    if not rests:
        await query.edit_message_text("Avval restoran qo'shing!", reply_markup=back_keyboard("admin_panel"))
        return ConversationHandler.END

    buttons = []
    for rid, r in rests.items():
        buttons.append([InlineKeyboardButton(f"🍴 {r['name']}", callback_data=f"selectrest_{rid}")])
    buttons.append([InlineKeyboardButton("🔙 Bekor qilish", callback_data="admin_panel")])
    await query.edit_message_text("Qaysi restoranga taom qo'shmoqchisiz?", reply_markup=InlineKeyboardMarkup(buttons))
    return FOOD_NAME

async def select_rest_for_food(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rid = query.data.split("_")[1]
    context.user_data["selected_rest"] = rid
    await query.edit_message_text("🍜 Taom *nomini* kiriting:", parse_mode="Markdown")
    return FOOD_NAME

async def food_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_food"] = {"name": update.message.text}
    await update.message.reply_text("📝 Taom *tarkibini* kiriting (masalan: Go'sht, sabzavot, guruch):", parse_mode="Markdown")
    return FOOD_DESC

async def food_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_food"]["desc"] = update.message.text
    await update.message.reply_text("💰 Taom *narxini* kiriting (faqat raqam, so'mda):\nMasalan: 25000", parse_mode="Markdown")
    return FOOD_PRICE

async def food_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = int(update.message.text.replace(" ", "").replace(",", ""))
        context.user_data["new_food"]["price"] = price
        await update.message.reply_text("📸 Taom *rasmini* yuboring (yoki /skip yozing):", parse_mode="Markdown")
        return FOOD_PHOTO
    except:
        await update.message.reply_text("❌ Faqat raqam kiriting! Masalan: 25000")
        return FOOD_PRICE

async def food_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_id = None
    if update.message.photo:
        photo_id = update.message.photo[-1].file_id

    rid = context.user_data["selected_rest"]
    fid = str(db["next_food_id"])
    db["next_food_id"] += 1
    db["restaurants"][rid]["foods"][fid] = {
        **context.user_data["new_food"],
        "photo": photo_id,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    save_data(db)

    r_name = db["restaurants"][rid]["name"]
    food_name_str = context.user_data["new_food"]["name"]
    await update.message.reply_text(
        f"✅ *{food_name_str}* taomi *{r_name}* ga qo'shildi!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Admin panel", callback_data="admin_panel")]])
    )
    return ConversationHandler.END

async def skip_food_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rid = context.user_data["selected_rest"]
    fid = str(db["next_food_id"])
    db["next_food_id"] += 1
    db["restaurants"][rid]["foods"][fid] = {
        **context.user_data["new_food"],
        "photo": None,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    save_data(db)
    await update.message.reply_text(
        "✅ Taom qo'shildi!",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Admin panel", callback_data="admin_panel")]])
    )
    return ConversationHandler.END

# ============================================================
# NARX O'ZGARTIRISH
# ============================================================

async def admin_edit_price_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rests = db.get("restaurants", {})
    buttons = []
    for rid, r in rests.items():
        buttons.append([InlineKeyboardButton(f"🍴 {r['name']}", callback_data=f"editrest_{rid}")])
    buttons.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")])
    await query.edit_message_text("Qaysi restoranning taomini o'zgartirmoqchisiz?", reply_markup=InlineKeyboardMarkup(buttons))
    return EDIT_PRICE

async def select_rest_for_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rid = query.data.split("_")[1]
    context.user_data["edit_rest"] = rid
    r = db["restaurants"][rid]
    buttons = []
    for fid, food in r["foods"].items():
        buttons.append([InlineKeyboardButton(f"{food['name']} — {food['price']:,} so'm", callback_data=f"editfood_{fid}")])
    buttons.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")])
    await query.edit_message_text("Qaysi taomni o'zgartirmoqchisiz?", reply_markup=InlineKeyboardMarkup(buttons))
    return EDIT_PRICE

async def select_food_for_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    fid = query.data.split("_")[1]
    context.user_data["edit_food"] = fid
    await query.edit_message_text("💰 Yangi narxni kiriting (faqat raqam):")
    return EDIT_PRICE

async def save_new_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = int(update.message.text.replace(" ", "").replace(",", ""))
        rid = context.user_data["edit_rest"]
        fid = context.user_data["edit_food"]
        db["restaurants"][rid]["foods"][fid]["price"] = price
        save_data(db)
        food_name_str = db["restaurants"][rid]["foods"][fid]["name"]
        await update.message.reply_text(
            f"✅ *{food_name_str}* narxi *{price:,} so'm* ga o'zgartirildi!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Admin panel", callback_data="admin_panel")]])
        )
        return ConversationHandler.END
    except:
        await update.message.reply_text("❌ Faqat raqam kiriting!")
        return EDIT_PRICE

# ============================================================
# TAOM O'CHIRISH
# ============================================================

async def admin_del_food(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rests = db.get("restaurants", {})
    buttons = []
    for rid, r in rests.items():
        buttons.append([InlineKeyboardButton(f"🍴 {r['name']}", callback_data=f"delfoodrest_{rid}")])
    buttons.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")])
    await query.edit_message_text("Qaysi restoranning taomini o'chirmoqchisiz?", reply_markup=InlineKeyboardMarkup(buttons))

async def del_food_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rid = query.data.split("_")[1]
    context.user_data["del_rest"] = rid
    r = db["restaurants"][rid]
    buttons = []
    for fid, food in r["foods"].items():
        buttons.append([InlineKeyboardButton(f"🗑 {food['name']}", callback_data=f"delfood_{fid}")])
    buttons.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin_del_food")])
    await query.edit_message_text("Qaysi taomni o'chirmoqchisiz?", reply_markup=InlineKeyboardMarkup(buttons))

async def confirm_del_food(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    fid = query.data.split("_")[1]
    rid = context.user_data.get("del_rest")
    food = db["restaurants"][rid]["foods"].pop(fid, None)
    save_data(db)
    name = food["name"] if food else "Noma'lum"
    await query.edit_message_text(
        f"✅ *{name}* o'chirildi!",
        parse_mode="Markdown",
        reply_markup=back_keyboard("admin_panel")
    )

# ============================================================
# BACK BUTTONS
# ============================================================

async def back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    dest = query.data.replace("back_", "")

    if dest == "main":
        adm = is_admin(query.from_user.id)
        await query.edit_message_text(
            "🏘 *MAHALLA* — Bosh menyu:",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(adm)
        )
    elif dest == "admin_panel":
        buttons = [
            [InlineKeyboardButton("➕ Restoran qo'shish", callback_data="admin_add_rest")],
            [InlineKeyboardButton("🗑 Restoran o'chirish", callback_data="admin_del_rest")],
            [InlineKeyboardButton("🍜 Taom qo'shish", callback_data="admin_add_food")],
            [InlineKeyboardButton("✏️ Narx o'zgartirish", callback_data="admin_edit_price")],
            [InlineKeyboardButton("🗑 Taom o'chirish", callback_data="admin_del_food")],
            [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")],
        ]
        await query.edit_message_text("⚙️ *Admin panel*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ Bekor qilindi.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Bosh menyu", callback_data="back_main")]])
    )
    return ConversationHandler.END

# ============================================================
# MAIN
# ============================================================

def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN o'rnatilmagan!")

    app = Application.builder().token(BOT_TOKEN).build()

    # Restoran qo'shish conversation
    add_rest_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_rest_start, pattern="^admin_add_rest$")],
        states={
            REST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, rest_name)],
            REST_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, rest_phone)],
            REST_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, rest_address)],
            REST_PHOTO: [
                MessageHandler(filters.PHOTO, rest_photo),
                CommandHandler("skip", skip_photo),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Taom qo'shish conversation
    add_food_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_food_start, pattern="^admin_add_food$")],
        states={
            FOOD_NAME: [
                CallbackQueryHandler(select_rest_for_food, pattern="^selectrest_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, food_name),
            ],
            FOOD_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, food_desc)],
            FOOD_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, food_price)],
            FOOD_PHOTO: [
                MessageHandler(filters.PHOTO, food_photo),
                CommandHandler("skip", skip_food_photo),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Narx o'zgartirish conversation
    edit_price_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_edit_price_start, pattern="^admin_edit_price$")],
        states={
            EDIT_PRICE: [
                CallbackQueryHandler(select_rest_for_edit, pattern="^editrest_"),
                CallbackQueryHandler(select_food_for_edit, pattern="^editfood_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_new_price),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(add_rest_conv)
    app.add_handler(add_food_conv)
    app.add_handler(edit_price_conv)

    app.add_handler(CallbackQueryHandler(show_restaurants, pattern="^restaurants$"))
    app.add_handler(CallbackQueryHandler(show_restaurant, pattern="^rest_"))
    app.add_handler(CallbackQueryHandler(show_menu, pattern="^menu_"))
    app.add_handler(CallbackQueryHandler(show_food, pattern="^food_"))
    app.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_panel$"))
    app.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_del_rest, pattern="^admin_del_rest$"))
    app.add_handler(CallbackQueryHandler(confirm_del_rest, pattern="^delrest_"))
    app.add_handler(CallbackQueryHandler(admin_del_food, pattern="^admin_del_food$"))
    app.add_handler(CallbackQueryHandler(del_food_list, pattern="^delfoodrest_"))
    app.add_handler(CallbackQueryHandler(confirm_del_food, pattern="^delfood_"))
    app.add_handler(CallbackQueryHandler(back_handler, pattern="^back_"))

    logger.info("🏘 MAHALLA bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
