import asyncio
from datetime import datetime
from playwright.async_api import async_playwright

DEFAULT_URL = "https://shop.ciaotickets.com/ecommerce/abbonamento/1559?lang=it"

class TicketChecker:
    def __init__(self, url: str = DEFAULT_URL, headless: bool = True):
        self.url = url
        self.headless = headless

    async def check_availability(self) -> dict:
        """
        Controlla la disponibilità dei biglietti su Ciaotickets.
        Ritorna un dizionario con i dettagli del controllo.
        """
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=self.headless,
                    args=["--no-sandbox", "--disable-setuid-sandbox"]
                )
                
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 800}
                )
                
                page = await context.new_page()
                
                # Navigazione con timeout di 45 secondi
                await page.goto(self.url, wait_until="networkidle", timeout=45000)
                
                # Attesa rendering Angular
                await asyncio.sleep(4)
                
                # Estrazione testo dai selettori rilevanti
                price_notes = await page.locator(".price-table-notes").all_text_contents()
                notes_text = " ".join([n.strip() for n in price_notes]).strip()
                
                # Controlla se è presente la scritta "Disponibilità terminata" o "Esaurito"
                is_sold_out = ("disponibil" in notes_text.lower() and "terminata" in notes_text.lower()) or ("esaurit" in notes_text.lower())
                
                # Verifichiamo anche elementi aggiuntivi (es. pulsanti Acquista, scelta quantità o aggiunta al carrello)
                buy_selectors = ".add-pre-cart, .custom-add-to-cart, .btn-acquista, a.btn-acquista, a[title='Acquista'], .biglietteria-abbonamento a"
                cart_buttons = await page.locator(buy_selectors).all_text_contents()
                cart_btn_text = " ".join([b.strip() for b in cart_buttons if b.strip()]).strip()
                
                # Verifichiamo la presenza di input quantità attivi, selettori di posto o pulsanti Acquista
                has_active_selectors = False
                qty_inputs = await page.locator(f"input[type='number'], select, .qty-btn, .counter, {buy_selectors}").count()
                if qty_inputs > 0:
                    has_active_selectors = True
                    
                await browser.close()
                
                # Determinazione dello stato
                if is_sold_out:
                    return {
                        "success": True,
                        "available": False,
                        "status_text": notes_text if notes_text else "Disponibilità terminata",
                        "details": f"Nota: {notes_text}",
                        "timestamp": now_str
                    }
                else:
                    status_msg = notes_text if notes_text else "Biglietti Disponibili!"
                    return {
                        "success": True,
                        "available": True,
                        "status_text": status_msg,
                        "details": f"Note: {notes_text} | Cart: {cart_btn_text}",
                        "timestamp": now_str
                    }
                    
        except Exception as e:
            return {
                "success": False,
                "available": False,
                "status_text": f"Errore durante il controllo: {str(e)}",
                "details": str(e),
                "timestamp": now_str
            }

if __name__ == "__main__":
    checker = TicketChecker()
    res = asyncio.run(checker.check_availability())
    print("Risultato test check:", res)
