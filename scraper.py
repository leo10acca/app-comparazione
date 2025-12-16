import requests
from bs4 import BeautifulSoup
import re
import random
import time
import json
import toml
from supabase import create_client

# INIT SUPABASE (Needed for direct inserts from scraper)
try:
    secrets = toml.load(".streamlit/secrets.toml")
    url = secrets["supabase"]["url"]
    key = secrets["supabase"]["key"]
    supabase = create_client(url, key)
except:
    supabase = None # Fallback if run outside streamlit context without secrets

def clean_price(price_input):
    if not price_input: return 0.0
    s = str(price_input).replace('€', '').replace('&euro;', '').strip()
    if '.' in s and ',' not in s:
        try: return float(s)
        except: pass 
    s = s.replace('.', '').replace(',', '.').replace('\xa0', '').replace(' ', '')
    try: return float(s)
    except ValueError: return 0.0

def scrape_category(target_url, folder_id, owner_username):
    """
    Scrapes products from a category page and inserts them into the DB linked to folder_id.
    """
    if not supabase: return 0
    
    # 1. HEADERS REALISTICI (Chrome 91 - Specifico Richiesto)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.google.com/',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'cross-site',
        'Sec-Fetch-User': '?1'
    }

    all_products = []
    page_number = 1
    
    # Check if URL has query params
    separator = "&" if "?" in target_url else "?"

    while True:
        try:
            current_url = f"{target_url}{separator}page={page_number}"
            print(f"Scraping {current_url}...")
            
            response = requests.get(current_url, headers=headers, timeout=20)
            if response.status_code != 200: 
                print(f"Status {response.status_code} for {current_url}")
                break
                
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # SELEZIONE PRODOTTI (PrestaShop Standard + Fallbacks)
            # 1. Standard PS 1.7
            articles = soup.select("article.product-miniature")
            
            # 2. Fallback PS 1.7 (div)
            if not articles:
                articles = soup.select("div.product-miniature")

            # 3. Fallback PS 1.6 / irrigationdeals (div.product-container)
            if not articles:
                articles = soup.select("div.product-container")
            
            # 4. Fallback Generic
            if not articles:
                articles = soup.select(".ajax_block_product")

            if not articles: 
                print("Nessun prodotto trovato.")
                # DEBUG RICHIESTO
                if page_number == 1:
                    import streamlit as st
                    st.warning(f"Nessun prodotto trovato. Status Code: {response.status_code}")
                    with st.expander(f"Debug HTML ({current_url})"):
                        st.code(response.text[:1000], language='html')
                break
            
            products_on_page = []
            
            for article in articles:
                try:
                    # TITOLO
                    # Cerca .product-title a (PS 1.7) o .product-name (PS 1.6)
                    title_tag = article.select_one('.product-title a')
                    if not title_tag:
                         title_tag = article.select_one('.product-name')
                         # A volte è un <a> diretto con class product-name
                    
                    if not title_tag: 
                        # Ultimo tentativo: cerca un h3 o h5
                        title_tag = article.find(['h3', 'h4', 'h5'])
                        if title_tag and title_tag.find('a'):
                            title_tag = title_tag.find('a')

                    if not title_tag: continue
                    
                    name = title_tag.get_text(strip=True)
                    product_url = title_tag.get('href')
                    
                    # Se l'URL è relativo, aggiungi dominio (gestione base)
                    if product_url and not product_url.startswith('http'):
                        # Ricostruisci base url
                        from urllib.parse import urlparse
                        parsed_uri = urlparse(target_url)
                        domain = '{uri.scheme}://{uri.netloc}'.format(uri=parsed_uri)
                        product_url = f"{domain}{product_url}"

                    # PREZZO
                    price_tag = article.select_one('.price')
                    if not price_tag:
                        price_tag = article.select_one('.product-price')
                    if not price_tag:
                        price_tag = article.select_one('.content_price .price') # PS 1.6 list view

                    price = clean_price(price_tag.get_text(strip=True)) if price_tag else 0.0
                    
                    if not name: continue

                    # CODICE (SKU) - Logica Migliorata (Priorità Reference)
                    codice = None
                    
                    # 1. Cerca .product-reference span (Standard PS)
                    ref_tag = article.select_one('.product-reference span')
                    if not ref_tag: ref_tag = article.select_one('.product-reference')
                    if ref_tag: codice = ref_tag.get_text(strip=True)
                    
                    # 2. Cerca itemprop="sku"
                    if not codice:
                        sku_tag = article.select_one('[itemprop="sku"]')
                        if sku_tag: codice = sku_tag.get("content", "").strip() or sku_tag.get_text(strip=True)

                    # 3. Fallback: Cerca nel Titolo (Ultima parola alfanumerica se sembra un codice)
                    # Spesso il codice è alla fine del nome tipo "Irrigatore Pop-up 1804" -> 1804
                    if not codice:
                        import re
                        # Cerca token alfanumerici finali (almeno 2 caratteri, numeri e lettere)
                        tokens = name.split()
                        if tokens:
                            last_token = tokens[-1]
                            # Pulisci da parentesi
                            last_token = last_token.replace('(', '').replace(')', '')
                            # Se inizia con PRE-, scartalo (è interno nostro vecchio)
                            if not last_token.startswith("PRE-") and len(last_token) > 2 and any(c.isdigit() for c in last_token):
                                codice = last_token

                    # 4. Fallback estremo: Genera PRE- solo se proprio non troviamo nulla
                    if not codice:
                        codice = f"PRE-{random.randint(10000, 99999)}" 

                    products_on_page.append({
                        "folder_id": folder_id,
                        "codice": codice,
                        "categoria": "Imported",
                        "descrizione": name,
                        "marchio": "MondoIrrigazione", # O estrai se possibile
                        "prezzo": price,
                        "url": product_url, # FIX: competitor_url -> url
                        "is_tracked": False # Default tracked
                    })
                except Exception as e: 
                    print(f"Error parsing article: {e}")
                    continue
            
            if not products_on_page: break

            # UPSERT BATCH (Conservative)
            count = 0
            for p in products_on_page:
                # Check esistenza in questa cartella (per URL o Nome)
                # Preferiamo URL se disponibile, altrimenti Nome
                # Check esistenza nel contesto dell'utente specifico
                query = supabase.table("products").select("*").eq("folder_id", folder_id).eq("owner_username", owner_username)
                if p.get("url"):
                    query = query.eq("url", p["url"])
                else:
                    query = query.eq("descrizione", p["descrizione"])
                
                existing = query.execute()
                
                if existing.data:
                    # UPDATE (Mantieni is_tracked)
                    existing_prod = existing.data[0]
                    prod_id = existing_prod['id']
                    
                    update_payload = {
                        "prezzo": p["prezzo"],
                        "descrizione": p["descrizione"], # Aggiorna nome se cambiato
                        "marchio": p["marchio"]
                    }
                    # Non tocchiamo is_tracked!
                    
                    try:
                        # Update specifico per ID e Owner (sicurezza)
                        supabase.table("products").update(update_payload).eq("id", prod_id).eq("owner_username", owner_username).execute()
                        count += 1
                    except Exception as e:
                        print(f"Update error: {e}")
                else:
                    # INSERT (Nuovo prodotto)
                    payload = {
                        "folder_id": p["folder_id"],
                        "codice": p["codice"],
                        "categoria": p["categoria"],
                        "descrizione": p["descrizione"],
                        "marchio": p["marchio"],
                        "marchio": p["marchio"],
                        "prezzo": p["prezzo"],
                        "owner_username": owner_username,
                        "is_tracked": False # Default False per nuovi
                    }
                    if p.get("url"):
                        payload["url"] = p["url"]

                    try:
                        supabase.table("products").insert(payload).execute()
                        count += 1
                    except Exception as e:
                        print(f"Insert error: {e}")
            
            page_number += 1
            time.sleep(1)
            
            if page_number > 10: break

        except Exception as e:
            print(f"Error: {e}")
            break

    return 1

def scrape_single_product_insert(url, folder_id, owner_username):
    """
    Scrapes a single product and inserts it into the folder.
    """
    if not supabase: return False, "DB Connection Failed"
    
    price = scrape_single_product(url)
    if price is None: return False, "Prezzo non trovato"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        title = soup.title.string
        h1 = soup.find('h1')
        if h1: title = h1.get_text(strip=True)
        
        # FIX: Usa 'url' invece di 'competitor_url'
        supabase.table("products").insert({
            "folder_id": folder_id,
            "codice": "MANUAL",
            "categoria": "Manual",
            "descrizione": title,
            "marchio": "Manual",
            "prezzo": price,
            "prezzo": price,
            "url": url, # FIX RICHIESTO
            "owner_username": owner_username,
            "is_tracked": False
        }).execute()
        return True, None
    except Exception as e:
        return False, str(e)

def scrape_single_product(url):
    """
    Scrapes a single product page to extract the current price.
    Uses JSON-LD (Schema.org) as priority, then Microdata/Selectors.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.google.com/',
        'Upgrade-Insecure-Requests': '1'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # STRATEGIA 1: JSON-LD (Schema.org)
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, list): items = data
                else: items = [data]
                
                for item in items:
                    if item.get('@type') == 'Product':
                        offers = item.get('offers')
                        if offers:
                            if isinstance(offers, list): price = offers[0].get('price')
                            else: price = offers.get('price')
                            if price: return float(price)
            except: continue

        # STRATEGIA 2: Meta Tags
        og_price = soup.find("meta", property="product:price:amount")
        if og_price: return float(og_price["content"])
            
        og_price_alt = soup.find("meta", property="og:price:amount")
        if og_price_alt: return float(og_price_alt["content"])

        # STRATEGIA 3: Selettori CSS
        selectors = ['.price', '.current-price', '.product-price', '#price', '[itemprop="price"]', '.amount', '.money']
        for sel in selectors:
            element = soup.select_one(sel)
            if element:
                price = clean_price(element.get_text(strip=True))
                if price > 0: return price
                    
        return None

    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None

def crawl_subcategories(parent_url):
    """
    Crawls a parent category page to find subcategories.
    Returns a list of dicts: [{'name': 'SubName', 'url': 'SubURL'}]
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    }
    
    try:
        print(f"Crawling parent: {parent_url}")
        response = requests.get(parent_url, headers=headers, timeout=20)
        if response.status_code != 200:
            return [], f"Status Code {response.status_code}"
            
        soup = BeautifulSoup(response.content, 'html.parser')
        subcategories = []
        links = []
        
        # STRATEGIA A RAGGIERA (Priorità)
        
        # Tentativo 1: Container con 'subcategor' nel nome (ID o Class)
        # Es. #subcategories, .subcategories, .category-subcategories
        container = soup.find(lambda tag: tag.name == 'div' and (
            (tag.get('id') and 'subcategor' in tag.get('id')) or 
            (tag.get('class') and any('subcategor' in c for c in tag.get('class')))
        ))
        
        if container:
            print("Trovato container per 'subcategor'")
            links = container.find_all("a")
            
        # Tentativo 2: Griglia Immagini (.subcategory-image a)
        if not links:
            print("Tentativo 2: .subcategory-image a")
            links = soup.select(".subcategory-image a")
            
        # Tentativo 3: Lista Testuale (ul.subcategory-view)
        if not links:
            print("Tentativo 3: ul.subcategory-view a")
            links = soup.select("ul.subcategory-view a")

        # Tentativo 4: Fallback generico (cerca h5 dentro li)
        if not links:
             print("Tentativo 4: li h5 a")
             links = soup.select("li h5 a")

        print(f"Trovati {len(links)} potenziali link.")
        if links:
            print(f"Esempio primo link: {links[0]}")

        seen_urls = set()
        
        from urllib.parse import urlparse, urljoin

        for link in links:
            # PULIZIA NOME
            name = link.get_text(strip=True)
            if not name:
                name = link.get('title', '').strip()
            
            name = name.replace('\n', ' ').strip()
            
            href = link.get('href')
            
            if not href or href == "#" or not name: continue
            
            # NORMALIZZAZIONE URL
            if not href.startswith('http'):
                # Usa urljoin per gestire correttamente slash e relativi
                href = urljoin(parent_url, href)
            
            if href not in seen_urls:
                subcategories.append({'name': name, 'url': href})
                seen_urls.add(href)
                
        if not subcategories:
            # DEBUG MIGLIORATO
            body = soup.find('body')
            classes = body.get('class', []) if body else []
            debug_info = f"Nessuna sottocategoria trovata.\nBody Classes: {classes}\n\nHTML Parziale:\n{soup.prettify()[:2000]}"
            return [], debug_info
            
        return subcategories, None

    except Exception as e:
        return [], str(e)

def get_price_from_url(url):
    import requests
    from bs4 import BeautifulSoup
    import re
    
    # Header anti-blocco
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200: return 0.0
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Cerca nei Meta Tags (Metodo più affidabile)
        price_meta = soup.find("meta", property="product:price:amount") or soup.find("meta", property="og:price:amount")
        if price_meta: 
            # Pulisci il prezzo usando la logica interna (rimuovi € e converti)
            # Assumiamo che clean_price sia disponibile o facciamo pulizia manuale come richiesto
            # User code used: return float(price_meta["content"].replace(',','.').replace('€','').strip())
            # Ma clean_price è definita in questo file? Sì, usiamola se possibile, ma l'utente ha dato codice specifico.
            # L'utente ha scritto: return float(price_meta["content"].replace(',','.').replace('€','').strip())
            try:
                return float(price_meta["content"].replace(',','.').replace('€','').strip())
            except:
                return 0.0

        # 2. Cerca JSON-LD (Fallback 1)
        # Se non trovi meta, cerca pattern di prezzo nel testo visibile
        price_tag = soup.select_one('.current-price, .price, .product-price, [itemprop="price"]')
        if price_tag:
             raw = price_tag.get_text().strip().replace('€','').replace('.','').replace(',','.') # Logica italiana semplificata
             # Cerca float
             match = re.search(r"\d+\.\d+", raw)
             return float(match.group(0)) if match else 0.0
             
        return 0.0
    except Exception as e:
        print(f"Scraping error: {e}")
        return 0.0
