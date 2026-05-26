import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from http import HTTPStatus

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from openai import OpenAI

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment Variables (Configured on Render)
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL")  # Render provides this automatically
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client
ai_client = OpenAI(api_key=OPENAI_API_KEY)

# Conversation States
GET_TEXT, SELECT_TONE = range(2)

# --- TELEGRAM BOT LOGIC ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation and asks the user for the text to rewrite."""
    await update.message.reply_text(
        "👋 Welcome to **AISEO Article Rewriter & Spinner**!\n\n"
        "Please send or paste the article/text you want me to spin."
    )
    return GET_TEXT

async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the text and presents tone options using Inline Buttons."""
    context.user_data["original_text"] = update.message.text
    
    keyboard = [
        [
            InlineKeyboardButton("🧠 Academic/Professional", callback_data="professional"),
            InlineKeyboardButton("🚀 SEO Optimized", callback_data="seo"),
        ],
        [
            InlineKeyboardButton("🎉 Casual/Witty", callback_data="casual"),
            InlineKeyboardButton("🔥 Persuasive/Copywriter", callback_data="persuasive"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("Great! Now choose the target tone or persona:", reply_markup=reply_markup)
    return SELECT_TONE

async def handle_tone_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Triggers OpenAI API to spin the text based on selected style."""
    query = update.callback_query
    await query.answer()
    
    tone = query.data
    original_text = context.user_data.get("original_text")
    
    await query.edit_message_text(text="🔄 *Spinning and rewriting your article... Please wait.*", parse_mode="Markdown")
    
    # Prompt Construction
    system_prompt = (
        "You are an expert AISEO article spinner and rewriter. Your task is to completely rewrite "
        "the provided text to make it entirely unique, avoiding plagiarism, while retaining the core meaning. "
    )
    
    if tone == "professional":
        system_prompt += "Rewrite using a formal, academic, and highly professional tone."
    elif tone == "seo":
        system_prompt += "Rewrite it to be highly SEO-optimized, engaging, clear, and structured with great readability."
    elif tone == "casual":
        system_prompt += "Rewrite it in a casual, witty, friendly, and conversational persona."
    elif tone == "persuasive":
        system_prompt += "Rewrite it like an elite copywriter—compelling, persuasive, and action-oriented."

    try:
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini", # Cost-effective and highly capable
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Rewrite this text:\n\n{original_text}"}
            ],
            temperature=0.7
        )
        rewritten_text = response.choices[0].message.content
        
        await query.message.reply_text(f"✨ **Here is your rewritten article ({tone} style):**\n\n{rewritten_text}", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"OpenAI Error: {e}")
        await query.message.reply_text("❌ Sorry, something went wrong while spinning your article. Please try again.")

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    await update.message.reply_text("Operation cancelled. Send /start to begin again.")
    return ConversationHandler.END

# Initialize Application framework
ptb_app = Application.builder().token(TOKEN).updater(None).build()

# Setup handlers
conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        GET_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text)],
        SELECT_TONE: [CallbackQueryHandler(handle_tone_selection)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
ptb_app.add_handler(conv_handler)

# --- FASTAPI WEBHOOK INTEGRATION ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles webhook setup on startup and teardown on shutdown."""
    await ptb_app.initialize()
    await ptb_app.start()
    # Set webhook pointing to Render's public URL
    webhook_target = f"{WEBHOOK_URL}/telegram-webhook"
    logger.info(f"Setting webhook to: {webhook_target}")
    await ptb_app.bot.set_webhook(url=webhook_target)
    
    yield
    
    logger.info("Stopping bot app...")
    await ptb_app.stop()
    await ptb_app.shutdown()

app = FastAPI(lifespan=lifespan)

@app.post("/telegram-webhook")
async def receive_update(request: Request):
    """Endpoint where Telegram sends user messages."""
    req_json = await request.json()
    update = Update.de_json(req_json, ptb_app.bot)
    await ptb_app.process_update(update)
    return Response(status_code=HTTPStatus.OK)

@app.get("/")
async def health_check():
    """Keeps the Render instance happy."""
    return {"status": "healthy", "bot": "AISEO Rewriter"}
