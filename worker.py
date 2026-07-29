import asyncio
import logging
import os
import sys
import threading
import time
from datetime import datetime
import requests
from checker import TicketChecker
from telegram_notifier import TelegramNotifier
from main import load_config

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Configurazione logging parlante in UTF-8
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)

config = load_config()
token = os.environ.get("TELEGRAM_BOT_TOKEN", config.get("telegram_bot_token", "")).strip().strip('"').strip("'")
chat_id = os.environ.get("TELEGRAM_CHAT_ID", config.get("telegram_chat_id", "")).strip().strip('"').strip("'")
url = config.get("url", "https://shop.ciaotickets.com/ecommerce/abbonamento/1559?lang=it")
interval = int(config.get("check_interval_seconds", 30))

notifier = TelegramNotifier(token, chat_id)
checker = TicketChecker(url=url, headless=True)

# 1. BOT TELEGRAM POLLING (Gestisce /status, /test, /help in tempo reale senza Webhook)
def telegram_polling_loop():
    if not notifier.is_configured():
        logging.warning("⚠️ Telegram Bot Token non configurato. Polling disattivato.")
        return

    # Cancella eventuali Webhook attivi per consentire il Polling diretto (getUpdates)
    try:
        requests.get(f"https://api.telegram.org/bot{token}/deleteWebhook", timeout=10)
        logging.info("✅ Webhook resettato. Attivato Polling Telegram getUpdates per comandi istantanei.")
    except Exception as e:
        logging.error(f"Errore reset webhook: {e}")

    offset = 0
    logging.info("🤖 Polling Telegram attivo! In ascolto su comandi /status, /test, /help...")

    while True:
        try:
            get_url = f"https://api.telegram.org/bot{token}/getUpdates"
            params = {"offset": offset, "timeout": 20}
            r = requests.get(get_url, params=params, timeout=25)
            data = r.json()

            if data.get("ok"):
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    msg = update.get("message") or update.get("channel_post") or {}
                    msg_chat_id = str(msg.get("chat", {}).get("id", ""))
                    raw_text = (msg.get("text") or "").strip().lower()
                    text = raw_text.split("@")[0] if "@" in raw_text else raw_text

                    if not msg_chat_id or not text:
                        continue

                    logging.info(f"📩 [TELEGRAM] Comando ricevuto '{raw_text}' da Chat ID: {msg_chat_id}")

                    if text in ["/start", "/help"]:
                        help_text = (
                            "🎟️ <b>Montelago Ticket Bot Commands</b>\n\n"
                            "• /status oppure /check - Controlla disponibilità in tempo reale su Montelago\n"
                            "• /test - Invia una notifica di prova con biglietti DISPONIBILI\n"
                            "• /help - Mostra questo messaggio"
                        )
                        notifier.send_message_to(msg_chat_id, help_text)

                    elif text in ["/status", "/check"]:
                        notifier.send_message_to(msg_chat_id, "🔍 <i>Esecuzione controllo in tempo reale su Ciaotickets...</i>")
                        res = asyncio.run(checker.check_availability())
                        emoji = "✅ DISPONIBILI!" if res.get("available") else "❌ Non Disponibili (Disponibilità terminata)"
                        status_msg = (
                            f"📊 <b>STATUS IN TEMPO REALE</b>\n\n"
                            f"<b>Stato:</b> {emoji}\n"
                            f"<b>Dettaglio:</b> {res.get('status_text')}\n"
                            f"<b>Timestamp:</b> {res.get('timestamp')}\n\n"
                            f"🔗 <a href='{url}'>Apri Ciaotickets</a>"
                        )
                        notifier.send_message_to(msg_chat_id, status_msg)

                    elif text == "/test":
                        notifier.send_message_to(msg_chat_id, "🧪 <i>Avvio test notifica su evento di prova...</i>")
                        test_url = "https://shop.ciaotickets.com/ecommerce/abbonamento/1609?lang=it"
                        test_checker = TicketChecker(url=test_url, headless=True)
                        res = asyncio.run(test_checker.check_availability())
                        
                        sample_alert = (
                            "🎉🎉 <b>TEST NOTIFICA: BIGLIETTI DISPONIBILI!</b> 🎉🎉\n\n"
                            "I biglietti sono stati rilevati come <b>DISPONIBILI</b>!\n\n"
                            f"👉 <b>Acquista subito qui:</b>\nhttps://www.ciaotickets.com/it/abbonamenti/abbonamento-3-giorni-emozioni-musica-rosetodegliabruzzi\n\n"
                            f"<i>Test eseguito con successo! ({res.get('timestamp')})</i>"
                        )
                        notifier.send_message_to(msg_chat_id, sample_alert)

        except Exception as e:
            logging.error(f"Errore ciclo Polling Telegram: {e}")
            time.sleep(2)

# 2. CICLO DI MONITORAGGIO 24/7 IN BACKGROUND (Ogni 30 secondi)
def bg_scanner_loop():
    logging.info(f"🚀 Avvio Monitoraggio 24/7 Montelago. Frequenza: {interval}s")
    if notifier.is_configured():
        sent = notifier.send_message(
            f"🤖 <b>MONTELAGO BOT ONLINE 24/7!</b>\n\n"
            f"📍 URL: {url}\n"
            f"⏱️ Controllo ogni: {interval}s\n"
            f"💬 Comandi attivi: /status e /test sia in chat privata che nei gruppi!"
        )
        logging.info(f"📢 Notifica di avvio inviata su Telegram (Successo: {sent})")

    last_available = False
    count = 0

    while True:
        count += 1
        logging.info(f"🔎 [CHECK #{count}] Avvio controllo Ciaotickets...")

        try:
            res = asyncio.run(checker.check_availability())
            if not res.get("success"):
                logging.error(f"❌ [CHECK #{count}] Errore durante il check: {res.get('status_text')}")
            else:
                is_avail = res.get("available", False)
                status_txt = res.get("status_text")
                
                if is_avail:
                    logging.info(f"🚨 [CHECK #{count}] BIGLIETTI DISPONIBILI! Status: {status_txt}")
                    if not last_available:
                        alert_msg = (
                            "🎉🎉 <b>BIGLIETTI DISPONIBILI PER MONTELAGO!</b> 🎉🎉\n\n"
                            "I biglietti sono tornati disponibili su Ciaotickets!\n\n"
                            f"👉 <b>Acquista subito qui:</b>\n{url}\n\n"
                            f"<i>Rilevato il: {res['timestamp']}</i>"
                        )
                        sent = notifier.send_message(alert_msg)
                        logging.info(f"📢 Notifica Telegram inviata con successo: {sent}")
                        last_available = True
                else:
                    logging.info(f"ℹ️ [CHECK #{count}] Stato: {status_txt} (Biglietti non ancora disponibili)")
                    if last_available:
                        notifier.send_message("ℹ️ <b>Montelago Bot</b>\nI biglietti risultano nuovamente esauriti su Ciaotickets.")
                        last_available = False

        except Exception as e:
            logging.error(f"⚠️ [CHECK #{count}] Eccezione non gestita: {e}")

        # Heartbeat orario nei log e su Telegram
        if count % 120 == 0 and notifier.is_configured():
            logging.info(f"💚 [HEARTBEAT] {count} controlli completati con successo.")
            notifier.send_message(f"💚 <b>Bot Montelago Sempre Attivo (Heartbeat)</b>\nEseguiti {count} controlli. Tutto regolare.", disable_notification=True)

        time.sleep(interval)

if __name__ == "__main__":
    # Avvia Polling Telegram in thread separato
    t_poll = threading.Thread(target=telegram_polling_loop, daemon=True)
    t_poll.start()

    # Avvia Scanner 24/7 nel thread principale
    bg_scanner_loop()
