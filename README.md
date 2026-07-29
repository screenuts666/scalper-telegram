# 🎟️ Bot Monitor Biglietti Montelago (Ciaotickets) - Cloud 24/7

Bot in Python con **Playwright** per controllare in tempo reale la disponibilità dei biglietti per **Montelago Celtic Festival** su Ciaotickets e inviare notifiche su **Telegram** 24/7 tramite **Google Cloud Platform (GCP)** senza dover tenere il PC acceso!

URL Monitorato:
`https://shop.ciaotickets.com/ecommerce/abbonamento/1559?lang=it`

---

## ☁️ Esecuzione 24/7 su Google Cloud (A PC Spento)

Il progetto è configurato per funzionare tramite **Google Cloud Run** + **Google Cloud Scheduler**.

### 1. Requisiti per il Deploy
- **Google Cloud SDK (`gcloud`)** installato (già presente sul tuo PC).
- **Token Telegram Bot** e **Chat ID** (vedi guida sotto).

### 2. Esegui il Deploy in 1 Click
Esegui nel terminale:
```cmd
py deploy_gcp.py
```
oppure fai doppio clic sul file `deploy_gcp.bat`.
Il programma ti chiederà di inserire:
1. Il tuo **Telegram Bot Token**
2. Il tuo **Telegram Chat ID**

Lo script abiliterà i servizi Google Cloud, costruirà il container Playwright in Cloud Run e pianificherà il controllo automatico **ogni 5 minuti** per 0€/mese.

---

## 📱 Guida Rapida Telegram (Se non hai ancora Token e Chat ID)

1. Apri Telegram e cerca **`@BotFather`**.
2. Invia `/newbot` e dai un nome al bot per ottenere il **Token HTTP API**.
3. Cerca su Telegram il bot **`@userinfobot`** ed inviagli un messaggio per ottenere il tuo **Chat ID** numerico.

---

## 💻 Test in Locale sul tuo PC (Opzionale)

Se desideri testarlo prima sul PC prima di metterlo su Google Cloud:
```bash
# Test notifica Telegram
py main.py --test-telegram

# Check singolo istantaneo
py main.py --check-once

# Monitoraggio continuo locale
py main.py
```
