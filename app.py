import asyncio
import logging
import multiprocessing
import os
import sys
import time
from datetime import datetime
from flask import Flask, jsonify, request
from checker import TicketChecker
from telegram_notifier import TelegramNotifier
from main import load_config

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Configurazione logging parlante
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)

app = Flask(__name__)

config = load_config()
token = os.environ.get("TELEGRAM_BOT_TOKEN", config.get("telegram_bot_token", "")).strip().strip('"').strip("'")
chat_id = os.environ.get("TELEGRAM_CHAT_ID", config.get("telegram_chat_id", "")).strip().strip('"').strip("'")
url = config.get("url", "https://shop.ciaotickets.com/ecommerce/abbonamento/1559?lang=it")
interval = int(config.get("check_interval_seconds", 30))

notifier = TelegramNotifier(token, chat_id)
checker = TicketChecker(url=url, headless=True)

# Stato globale memorizzato in memoria
current_ticket_state = {
    "available": False,
    "status_text": "Monitor attivo su Ciaotickets",
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}

# 1. HEALTH CHECK HTTP ENDPOINT
@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "online",
        "service": "Montelago 24/7 Monitor & Ultra Fast Telegram Webhook",
        "state": current_ticket_state
    })

# 2. WEBHOOK TELEGRAM ISTANTANEO (<5ms response time, zero GIL locking)
@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    data = request.get_json(force=True, silent=True) or {}
    message = data.get("message") or data.get("channel_post") or {}
    msg_chat_id = str(message.get("chat", {}).get("id", ""))
    raw_text = (message.get("text") or "").strip().lower()
    text = raw_text.split("@")[0] if "@" in raw_text else raw_text

    if not msg_chat_id or not text:
        return jsonify({"ok": True})

    logging.info(f"⚡ [WEBHOOK ISTANTANEO] Comando ricevuto '{raw_text}' da Chat ID: {msg_chat_id}")

    if text in ["/start", "/help"]:
        help_msg = (
            "🎟️ <b>Montelago Ticket Bot Commands</b>\n\n"
            "• /status oppure /check - Stato attuale in tempo reale\n"
            "• /test - Simula una notifica di biglietto DISPONIBILE\n"
            "• /help - Mostra questo messaggio"
        )
        sent = notifier.send_message_to(msg_chat_id, help_msg)
        logging.info(f"📤 Risposta /help inviata a {msg_chat_id} (Esito: {sent})")

    elif text in ["/status", "/check"]:
        avail = current_ticket_state.get("available", False)
        emoji = "✅ DISPONIBILI!" if avail else "❌ Non Disponibili (Disponibilità terminata)"
        status_msg = (
            f"📊 <b>STATUS MONITOR MONTELAGO</b>\n\n"
            f"<b>Stato:</b> {emoji}\n"
            f"<b>Dettaglio:</b> {current_ticket_state.get('status_text')}\n"
            f"<b>Ultimo check:</b> {datetime.now().strftime('%H:%M:%S')}\n\n"
            f"🔗 <a href='{url}'>Apri Ciaotickets</a>"
        )
        sent = notifier.send_message_to(msg_chat_id, status_msg)
        logging.info(f"📤 Risposta /status inviata a {msg_chat_id} (Esito: {sent})")

    elif text == "/test":
        sample_alert = (
            "🎉🎉 <b>TEST NOTIFICA: BIGLIETTI DISPONIBILI!</b> 🎉🎉\n\n"
            "I biglietti sono stati rilevati come <b>DISPONIBILI</b>!\n\n"
            f"👉 <b>Acquista subito qui:</b>\nhttps://www.ciaotickets.com/it/abbonamenti/abbonamento-3-giorni-emozioni-musica-rosetodegliabruzzi\n\n"
            f"<i>Test eseguito con successo! ({datetime.now().strftime('%H:%M:%S')})</i>"
        )
        sent = notifier.send_message_to(msg_chat_id, sample_alert)
        logging.info(f"📤 Risposta /test inviata a {msg_chat_id} (Esito: {sent})")

    return jsonify({"ok": True})

# 3. SCANNER 24/7 IN PROCESSO SEPARATO (Zero GIL contention con Flask)
def bg_scanner_process():
    logging.info(f"🚀 [SCANNER PROCESSO INDIPENDENTE] Avviato monitoraggio Ciaotickets ogni {interval}s")
    if notifier.is_configured():
        notifier.send_message(
            f"🤖 <b>MONTELAGO BOT ONLINE 24/7!</b>\n\n"
            f"📍 URL: {url}\n"
            f"⏱️ Controllo ogni: {interval}s\n"
            f"💬 Risposte istantanee attive su /help, /status e /test!"
        )

    last_alert_sent = False
    count = 0

    while True:
        count += 1
        now_str = datetime.now().strftime("%H:%M:%S")
        logging.info(f"🔎 [CHECK #{count}] ({now_str}) Controllo Ciaotickets...")

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            res = loop.run_until_complete(checker.check_availability())
            loop.close()

            if res.get("success"):
                is_avail = res.get("available", False)
                status_txt = res.get("status_text")

                if is_avail:
                    logging.info(f"🚨 [CHECK #{count}] BIGLIETTI DISPONIBILI! {status_txt}")
                    if not last_alert_sent:
                        alert_msg = (
                            "🎉🎉 <b>BIGLIETTI DISPONIBILI PER MONTELAGO!</b> 🎉🎉\n\n"
                            "I biglietti sono tornati disponibili su Ciaotickets!\n\n"
                            f"👉 <b>Acquista subito qui:</b>\n{url}\n\n"
                            f"<i>Rilevato il: {res['timestamp']}</i>"
                        )
                        notifier.send_message(alert_msg)
                        last_alert_sent = True
                else:
                    logging.info(f"ℹ️ [CHECK #{count}] Stato: {status_txt}")
                    if last_alert_sent:
                        notifier.send_message("ℹ️ <b>Montelago Bot</b>\nI biglietti risultano nuovamente esauriti su Ciaotickets.")
                        last_alert_sent = False
                    
                    if count % 120 == 0:
                        low_prio_msg = (
                            f"ℹ️ <b>Aggiornamento Orario (Silenzioso)</b>\n\n"
                            f"Tutto procede regolarmente. Eseguiti {count} controlli.\n"
                            f"Stato attuale: ❌ Non Disponibili"
                        )
                        notifier.send_message(low_prio_msg, disable_notification=True)
            else:
                logging.error(f"❌ [CHECK #{count}] Errore: {res.get('status_text')}")

        except Exception as e:
            logging.error(f"⚠️ [CHECK #{count}] Eccezione: {e}")

        time.sleep(interval)

# AVVIO SCANNER IN PROCESSO SEPARATO
_proc_started = False
if not _proc_started:
    _proc_started = True
    p = multiprocessing.Process(target=bg_scanner_process, daemon=True)
    p.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    logging.info(f"🌐 Server HTTP avviato sulla porta {port}")
    app.run(host="0.0.0.0", port=port)
