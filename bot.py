import asyncio
import logging
import os
import sys
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

# 1. HTTP HEALTH CHECK SERVER ASINCRONO PER CLOUD RUN (<1ms response)
async def health_server_task():
    port = int(os.environ.get("PORT", 8080))
    
    async def handle_client(reader, writer):
        try:
            await reader.read(2048)
            response_body = b'{"status":"online","service":"Montelago 24/7 Bot"}'
            response = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: " + str(len(response_body)).encode() + b"\r\n"
                b"Connection: close\r\n\r\n" + response_body
            )
            writer.write(response)
            await writer.drain()
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

    try:
        server = await asyncio.start_server(handle_client, "0.0.0.0", port)
        logging.info(f"🌐 Server HTTP Health Check attivo sulla porta {port}")
        async with server:
            await server.serve_forever()
    except Exception as e:
        logging.error(f"Errore server HTTP health: {e}")

# 2. LISTENER COMANDI TELEGRAM REATTIVO E ISTANTANEO (<100ms)
async def telegram_polling_task():
    logging.info("🤖 [TELEGRAM TASK] Inizializzazione listener comandi...")
    
    # Resetta eventuali webhook attivi
    try:
        await asyncio.to_thread(requests.get, f"https://api.telegram.org/bot{token}/deleteWebhook", timeout=5)
        logging.info("✅ Webhook resettato con successo.")
    except Exception as e:
        logging.error(f"Errore reset webhook: {e}")

    # Sincronizza offset all'ultimo update per ignorare lo storico vecchio ed essere istantaneo
    offset = 0
    try:
        r = (await asyncio.to_thread(requests.get, f"https://api.telegram.org/bot{token}/getUpdates", params={"offset": -1}, timeout=5)).json()
        if r.get("ok") and r.get("result"):
            offset = r["result"][-1]["update_id"] + 1
            logging.info(f"✅ Offset sincronizzato sull'ultimo messaggio live (Offset: {offset})")
    except Exception as e:
        logging.error(f"Errore sync offset iniziale: {e}")

    logging.info("⚡ [TELEGRAM TASK] LISTENER ATTIVO IN REALE TEMPO! Invia /help, /status, /test per risposte istantanee.")

    while True:
        try:
            get_url = f"https://api.telegram.org/bot{token}/getUpdates"
            params = {"offset": offset, "timeout": 1}
            r = await asyncio.to_thread(requests.get, get_url, params=params, timeout=3)
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

                    logging.info(f"⚡ [TELEGRAM REATTIVO] Comando ricevuto '{raw_text}' da Chat ID: {msg_chat_id}")

                    if text in ["/start", "/help"]:
                        help_text = (
                            "🎟️ <b>Montelago Ticket Bot Commands</b>\n\n"
                            "• /status oppure /check - Controlla disponibilità in tempo reale su Montelago\n"
                            "• /test - Invia una notifica di prova con biglietti DISPONIBILI\n"
                            "• /help - Mostra questo messaggio"
                        )
                        await asyncio.to_thread(notifier.send_message_to, msg_chat_id, help_text)

                    elif text in ["/status", "/check"]:
                        await asyncio.to_thread(notifier.send_message_to, msg_chat_id, "🔍 <i>Esecuzione controllo in tempo reale su Ciaotickets...</i>")
                        res = await checker.check_availability()
                        emoji = "✅ DISPONIBILI!" if res.get("available") else "❌ Non Disponibili (Disponibilità terminata)"
                        status_msg = (
                            f"📊 <b>STATUS IN TEMPO REALE</b>\n\n"
                            f"<b>Stato:</b> {emoji}\n"
                            f"<b>Dettaglio:</b> {res.get('status_text')}\n"
                            f"<b>Timestamp:</b> {res.get('timestamp')}\n\n"
                            f"🔗 <a href='{url}'>Apri Ciaotickets</a>"
                        )
                        await asyncio.to_thread(notifier.send_message_to, msg_chat_id, status_msg)

                    elif text == "/test":
                        await asyncio.to_thread(notifier.send_message_to, msg_chat_id, "🧪 <i>Avvio test notifica su evento di prova...</i>")
                        test_url = "https://shop.ciaotickets.com/ecommerce/abbonamento/1609?lang=it"
                        test_checker = TicketChecker(url=test_url, headless=True)
                        res = await test_checker.check_availability()

                        sample_alert = (
                            "🎉🎉 <b>TEST NOTIFICA: BIGLIETTI DISPONIBILI!</b> 🎉🎉\n\n"
                            "I biglietti sono stati rilevati come <b>DISPONIBILI</b>!\n\n"
                            f"👉 <b>Acquista subito qui:</b>\nhttps://www.ciaotickets.com/it/abbonamenti/abbonamento-3-giorni-emozioni-musica-rosetodegliabruzzi\n\n"
                            f"<i>Test eseguito con successo! ({res.get('timestamp')})</i>"
                        )
                        await asyncio.to_thread(notifier.send_message_to, msg_chat_id, sample_alert)

        except Exception as e:
            # Silenzioso in caso di timeout normale per non intasare i log
            if "read timed out" not in str(e).lower():
                logging.error(f"Errore Telegram Listener: {e}")

        await asyncio.sleep(0.1)

# 3. SCANNER TICKET 24/7 MONTELAGO ASINCRONO
async def scanner_task():
    logging.info(f"🚀 [SCANNER TASK] Avvio Monitoraggio 24/7 Montelago (Intervallo {interval}s)...")
    if notifier.is_configured():
        sent = await asyncio.to_thread(
            notifier.send_message,
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
        logging.info(f"🔎 [SCANNER TASK] [CHECK #{count}] Controllo Ciaotickets...")

        try:
            res = await checker.check_availability()
            if not res.get("success"):
                logging.error(f"❌ [CHECK #{count}] Errore: {res.get('status_text')}")
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
                        await asyncio.to_thread(notifier.send_message, alert_msg)
                        last_available = True
                else:
                    logging.info(f"ℹ️ [CHECK #{count}] Stato: {status_txt}")
                    if last_available:
                        await asyncio.to_thread(notifier.send_message, "ℹ️ <b>Montelago Bot</b>\nI biglietti risultano nuovamente esauriti su Ciaotickets.")
                        last_available = False

        except Exception as e:
            logging.error(f"⚠️ [CHECK #{count}] Errore: {e}")

        await asyncio.sleep(interval)

async def main():
    logging.info("⚡ Avvio Bot Montelago 100% Reattivo ed Asincrono...")
    await asyncio.gather(
        health_server_task(),
        telegram_polling_task(),
        scanner_task()
    )

if __name__ == "__main__":
    asyncio.run(main())
