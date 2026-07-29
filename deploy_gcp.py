import subprocess
import sys
import os
import json

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def run_command_live(cmd, check=True):
    print(f"\n[Esecuzione]: {cmd}\n" + "-" * 50)
    process = subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    full_output = []
    try:
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                print(line, end="", flush=True)
                full_output.append(line)
    except KeyboardInterrupt:
        process.kill()
        print("\n⚠️ Esecuzione interrotta dall'utente.")
        sys.exit(1)

    returncode = process.poll()
    print("-" * 50)

    if check and returncode != 0:
        print(f"\n❌ Errore durante l'esecuzione del comando (Exit code: {returncode})")
        sys.exit(returncode)

    return "".join(full_output)

def main():
    print("=" * 60)
    print(" DEPLOY WORKER 24/7 MONTELAGO SU GOOGLE CLOUD PLATFORM")
    print("=" * 60)

    config_file = "config.json"
    default_token = ""
    default_chat_id = ""

    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                default_token = cfg.get("telegram_bot_token", "")
                default_chat_id = cfg.get("telegram_chat_id", "")
        except Exception:
            pass

    token_prompt = f"Inserisci Telegram Bot Token [{default_token}]: " if default_token else "Inserisci Telegram Bot Token: "
    token = input(token_prompt).strip() or default_token

    chat_id_prompt = f"Inserisci Telegram Chat ID [{default_chat_id}]: " if default_chat_id else "Inserisci Telegram Chat ID: "
    chat_id = input(chat_id_prompt).strip() or default_chat_id

    if not token or not chat_id:
        print("❌ ERRORE: Token e Chat ID sono obbligatori!")
        sys.exit(1)

    print("\n1. Abilitazione servizi Google Cloud...")
    run_command_live("gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com")

    print("\n2. Configurazione permessi IAM...")
    project_id = "tap-roulette-app"
    sa_email = "121045798088-compute@developer.gserviceaccount.com"
    run_command_live(f'gcloud projects add-iam-policy-binding {project_id} --member="serviceAccount:{sa_email}" --role="roles/storage.objectAdmin" --quiet', check=False)
    run_command_live(f'gcloud projects add-iam-policy-binding {project_id} --member="serviceAccount:{sa_email}" --role="roles/artifactregistry.writer" --quiet', check=False)

    print("\n3. Rimuovo eventuali vecchi Cloud Scheduler...")
    run_command_live('gcloud scheduler jobs delete montelago-job --location=europe-west1 --quiet', check=False)

    print("\n4. Deploy del Worker 24/7 su Google Cloud Run...")
    deploy_cmd = (
        f'gcloud run deploy montelago-checker '
        f'--source . '
        f'--region europe-west1 '
        f'--set-env-vars TELEGRAM_BOT_TOKEN="{token}",TELEGRAM_CHAT_ID="{chat_id}" '
        f'--no-cpu-throttling '
        f'--min-instances 1 '
        f'--memory 1Gi '
        f'--cpu 1'
    )
    run_command_live(deploy_cmd)

    print("\n" + "=" * 60)
    print(" ✅ BOT WORKER ATTIVATO CON SUCCESSO SU GOOGLE CLOUD!")
    print("=" * 60)
    print("\nIl worker sta girando in ciclo continuo (30s) nei server Google Cloud!")
    print("Controlla Telegram: hai appena ricevuto il messaggio di AVVIO del Bot!")
    print("Puoi spegnere il tuo PC. Riceverai notifiche istantanee non appena i biglietti aprono!\n")

if __name__ == "__main__":
    main()
