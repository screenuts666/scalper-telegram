import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from checker import TicketChecker
from telegram_notifier import TelegramNotifier

try:
    import winsound
except ImportError:
    winsound = None

CONFIG_FILE = "config.json"

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def load_config() -> dict:
    default_config = {
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "check_interval_seconds": 60,
        "sound_alarm": True,
        "headless": True,
        "url": "https://shop.ciaotickets.com/ecommerce/abbonamento/1559?lang=it"
    }

    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=2)
        return default_config

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Merge with defaults in case keys are missing
            for k, v in default_config.items():
                if k not in data:
                    data[k] = v
            
            token = os.environ.get("TELEGRAM_BOT_TOKEN", data.get("telegram_bot_token", ""))
            chat_id = os.environ.get("TELEGRAM_CHAT_ID", data.get("telegram_chat_id", ""))
            if token:
                data["telegram_bot_token"] = token
            if chat_id:
                data["telegram_chat_id"] = chat_id
                
            return data
    except Exception as e:
        print(f"[Config] Errore di lettura config.json: {e}")
        return default_config

def save_config(config: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print(f"[Config] Configurazione salvata in {CONFIG_FILE}")

def play_alarm():
    if winsound:
        try:
            # Esegue 5 bip sonori su Windows
            for _ in range(5):
                winsound.Beep(2000, 400)
                time.sleep(0.1)
        except Exception:
            pass

def interactive_setup(config: dict):
    print("\n--- ⚙️ CONFIGURAZIONE BOT TELEGRAM ---")
    token = input(f"Inserisci il Bot Token Telegram [{config.get('telegram_bot_token', '')}]: ").strip()
    if token:
        config["telegram_bot_token"] = token

    chat_id = input(f"Inserisci il tuo Chat ID Telegram [{config.get('telegram_chat_id', '')}]: ").strip()
    if chat_id:
        config["telegram_chat_id"] = chat_id

    interval = input(f"Intervallo di controllo in secondi [{config.get('check_interval_seconds', 60)}]: ").strip()
    if interval.isdigit():
        config["check_interval_seconds"] = int(interval)

    save_config(config)
    print("\n✅ Configurazione completata! Puoi testarla con: py main.py --test-telegram\n")

async def run_monitor():
    parser = argparse.ArgumentParser(description="Bot Monitor Disponibilità Biglietti Montelago Ciaotickets")
    parser.add_argument("--test-telegram", "-t", action="store_true", help="Invia un messaggio di prova su Telegram ed esce")
    parser.add_argument("--check-once", "-c", action="store_true", help="Esegue un solo controllo ed esce")
    parser.add_argument("--setup", "-s", action="store_true", help="Configura Token Telegram e Chat ID")
    args = parser.parse_args()

    config = load_config()

    if args.setup:
        interactive_setup(config)
        return

    notifier = TelegramNotifier(config["telegram_bot_token"], config["telegram_chat_id"])

    if args.test_telegram:
        if not notifier.is_configured():
            print("\n❌ Telegram non è configurato correttamente nel file config.json.")
            print("Esegui 'py main.py --setup' oppure modifica config.json con il tuo token e chat_id.\n")
            return
        print("\n[Test] Invio messaggio di prova su Telegram...")
        success = notifier.send_test_message()
        if success:
            print("✅ Test Telegram riuscito!")
        else:
            print("❌ Test Telegram fallito. Verifica Token e Chat ID.")
        return

    checker = TicketChecker(url=config["url"], headless=config.get("headless", True))

    if args.check_once:
        print(f"\n[Check Singolo] Controllo in corso per: {config['url']}")
        res = await checker.check_availability()
        print(f"Timestamp: {res['timestamp']}")
        print(f"Esito: {'✅ DISPONIBILI!' if res['available'] else '❌ Non Disponibili'}")
        print(f"Stato: {res['status_text']}")
        print(f"Dettagli: {res['details']}\n")
        return

    # Avvio ciclo di monitoraggio continuo
    print("=" * 65)
    print(" 🎟️ BOT MONITOR BIGLIETTI MONTELAGO CELTIC FESTIVAL (CIAOTICKETS)")
    print("=" * 65)
    print(f"📍 URL: {config['url']}")
    print(f"⏱️ Intervallo controlli: {config['check_interval_seconds']} secondi")
    print(f"📱 Telegram: {'CONFIGURATO' if notifier.is_configured() else '⚠️ NON CONFIGURATO (Modifica config.json)'}")
    print(f"🔔 Allarme sonoro PC: {'ATTIVO' if config.get('sound_alarm', True) else 'DISATTIVATO'}")
    print("=" * 65)
    print("Premere CTRL+C per fermare il bot.\n")

    last_available = False
    consecutive_errors = 0

    while True:
        timestamp_now = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp_now}] Controllo disponibilità...", end=" ", flush=True)

        res = await checker.check_availability()

        if not res["success"]:
            consecutive_errors += 1
            print(f"⚠️ ERRORE ({consecutive_errors}/3): {res['status_text']}")
            if consecutive_errors == 3 and notifier.is_configured():
                notifier.send_message(f"⚠️ <b>Montelago Bot - Avviso Errore</b>\nImpossibile accedere a Ciaotickets da 3 tentativi consecutivi.\nErrore: {res['status_text']}")
        else:
            consecutive_errors = 0
            is_avail = res["available"]

            if is_avail:
                print("🚨 BIGLIETTI DISPONIBILI! 🚨")
                if not last_available:
                    # Cambio stato: Da Esauriti a Disponibili!
                    alert_msg = (
                        "🎉🎉 <b>BIGLIETTI DISPONIBILI PER MONTELAGO!</b> 🎉🎉\n\n"
                        "I biglietti sono tornati disponibili su Ciaotickets!\n\n"
                        f"👉 <b>Acquista subito qui:</b>\n{config['url']}\n\n"
                        f"<i>Rilevato il: {res['timestamp']}</i>"
                    )
                    notifier.send_message(alert_msg)
                    if config.get("sound_alarm", True):
                        play_alarm()
                else:
                    print(" (Stato ancora disponibile - Notifica già inviata)")

                last_available = True
            else:
                print(f"❌ {res['status_text']}")
                if last_available:
                    print("ℹ️ I biglietti risultano di nuovo esauriti.")
                    notifier.send_message("ℹ️ <b>Montelago Bot</b>\nI biglietti risultano nuovamente esauriti su Ciaotickets.")
                last_available = False

        # Attesa prima del prossimo ciclo
        try:
            await asyncio.sleep(config.get("check_interval_seconds", 60))
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\n[Bot] Arresto richiesto dall'utente. Arrivederci!")
            break

if __name__ == "__main__":
    try:
        asyncio.run(run_monitor())
    except KeyboardInterrupt:
        print("\n[Bot] Programma terminato.")
