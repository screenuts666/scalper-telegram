import requests
import sys
import logging

def force_log(msg):
    logging.info(msg)
    print(msg, flush=True)
    try:
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()
    except Exception:
        pass

class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.token = str(token).strip().strip('"').strip("'")
        self.chat_id = str(chat_id).strip().strip('"').strip("'")
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def is_configured(self) -> bool:
        return bool(self.token and self.chat_id and self.token != "IL_TUO_TELEGRAM_BOT_TOKEN")

    def send_message(self, text: str, disable_notification: bool = False) -> bool:
        return self.send_message_to(self.chat_id, text, disable_notification)

    def send_message_to(self, target_chat_id: str, text: str, disable_notification: bool = False) -> bool:
        force_log(f"[Telegram] INIZIO INVIO a {target_chat_id}, token length: {len(self.token)}")
        if not self.token:
            force_log("[Telegram] ❌ Token mancante. Impossibile inviare il messaggio.")
            return False

        target = str(target_chat_id).strip().strip('"').strip("'")
        url = f"{self.base_url}/sendMessage"
        
        payload_html = {
            "chat_id": target,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
            "disable_notification": disable_notification
        }

        try:
            force_log(f"[Telegram] Sto per eseguire requests.post a {url}")
            response = requests.post(url, json=payload_html, timeout=10)
            data = response.json()
            force_log(f"[Telegram] Risposta API: {data}")
            
            if data.get("ok"):
                force_log(f"[Telegram] ✅ Messaggio HTML inviato con successo a {target}!")
                return True
            else:
                err_desc = data.get("description", "Errore sconosciuto")
                force_log(f"[Telegram] ⚠️ Errore HTML per {target}: {err_desc}. Tentativo in testo semplice...")
                
                clean_text = text.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "").replace("<code>", "").replace("</code>", "").replace("<a>", "").replace("</a>", "")
                payload_plain = {
                    "chat_id": target,
                    "text": clean_text,
                    "disable_web_page_preview": False,
                    "disable_notification": disable_notification
                }
                resp_plain = requests.post(url, json=payload_plain, timeout=10)
                data_plain = resp_plain.json()
                force_log(f"[Telegram] Risposta API Plain Text: {data_plain}")
                
                if data_plain.get("ok"):
                    force_log(f"[Telegram] ✅ Messaggio in testo semplice inviato a {target}!")
                    return True
                else:
                    force_log(f"[Telegram] ❌ Errore finale invio a {target}: {data_plain.get('description')}")
                    return False
        except Exception as e:
            force_log(f"[Telegram] ❌ Eccezione invio a {target}: {e}")
            return False

    def send_test_message(self) -> bool:
        test_msg = "🚨 <b>Montelago Ticket Bot</b> 🚨\n\nQuesto è un messaggio di prova. Il bot Telegram è configurato correttamente!"
        return self.send_message(test_msg)

    def set_webhook(self, webhook_url: str) -> bool:
        if not self.token:
            return False
        url = f"{self.base_url}/setWebhook"
        try:
            response = requests.post(url, json={"url": webhook_url}, timeout=10)
            data = response.json()
            force_log(f"[Telegram Webhook]: {data}")
            return data.get("ok", False)
        except Exception as e:
            force_log(f"[Telegram Webhook Error]: {e}")
            return False
