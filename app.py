import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client
import re
import time
from urllib.parse import quote_plus, urlparse
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io
import io
from datetime import datetime, timedelta
import base64

def get_img_as_base64(file_path):
    with open(file_path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()


def get_competitor_price_local(url):
    import requests
    from bs4 import BeautifulSoup
    import re
    
    if not url or "http" not in str(url): return 0.0
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code != 200: return 0.0
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Metodo Meta Tags (Più affidabile)
        price_meta = soup.find("meta", property="product:price:amount") or soup.find("meta", property="og:price:amount")
        if price_meta:
             clean = price_meta["content"].replace(',','.').replace('€','').strip()
             return float(clean)

        # 2. Metodo Visivo (Fallback)
        price_tag = soup.select_one('.current-price, .price, .product-price, [itemprop="price"]')
        if price_tag:
             # Pulizia prezzo "sporco" (es. € 2.200,50)
             raw = price_tag.get_text().strip().replace('€','').replace('&euro;','')
             if ',' in raw and '.' in raw: raw = raw.replace('.','') # Via i punti migliaia
             raw = raw.replace(',','.') # Virgola diventa punto
             found = re.findall(r"\d+\.\d+", raw)
             return float(found[0]) if found else 0.0
             
        return 0.0
    except Exception as e:
        print(f"Errore scraping {url}: {e}")
        return 0.0

# Configurazione pagina
st.set_page_config(
    page_title="PriceComparator",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CSS INJECTION (Hide Sidebar Completely) ---
st.markdown("""
    <style>
        /* Nasconde interamente il contenitore della sidebar */
        [data-testid="stSidebar"] {
            display: none;
        }
        /* Nasconde il pulsante per aprirla/chiuderla */
        [data-testid="collapsedControl"] {
            display: none;
        }
        /* Nasconde il pulsante fullscreen su tutte le immagini */
        button[title="View fullscreen"] {
            display: none !important; 
            visibility: hidden !important;
        }
        [data-testid="StyledFullScreenButton"] {
            display: none !important;
        }
        
        /* NUCLEAR OPTION: Disabilita interazione mouse sulla prima colonna (Logo) */
        [data-testid="column"]:first-of-type img {
            pointer-events: none !important;
        }
    </style>
""", unsafe_allow_html=True)


# Inizializzazione connessione Supabase
@st.cache_resource
def init_connection():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

try:
    supabase = init_connection()
    st.toast("Connessione al database stabilita con successo!", icon="✅")
except Exception as e:
    st.error(f"Errore di connessione al database: {e}")

# --- LOGIN SYSTEM (Ora con DB) ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

def check_login():
    username = st.session_state["username_input"]
    password = st.session_state["password_input"]
    
    try:
        # Cerca l'utente nel DB (match su username)
        response = supabase.table('users').select('*').eq('username', username).execute()
        
        if response.data and len(response.data) > 0:
            user_data = response.data[0]
            if user_data.get('password') == password:
                st.session_state.logged_in = True
                st.session_state['user'] = username # Salva username in sessione permanente
                # st.success("Accesso effettuato!") 
            else:
                st.session_state.logged_in = False
                st.error("Password errata")
        else:
            st.session_state.logged_in = False
            st.error("Utente non trovato")
    except Exception as e:
        st.error(f"Errore Login: {e}")

# Se non è loggato, mostra SOLO il login e ferma tutto il resto
if not st.session_state.logged_in:
    st.markdown("<br><br><br>", unsafe_allow_html=True) 
    col1, col2, col3 = st.columns([1, 2, 1]) 
    
    with col2:
        st.header("🔐 Accesso Richiesto")
             
        st.text_input("Username", key="username_input")
        st.text_input("Password", type="password", key="password_input")
        
        st.button("Accedi", on_click=check_login)
    
    st.stop()
# --- FINE LOGIN SYSTEM ---

# Titolo principale
# st.title("📊 PriceComparator") # Spostato in sidebar

# --- SIDEBAR REMOVED ---
# st.sidebar calls removed as requested

# Titolo main oscurato (lo teniamo nella sidebar)
# st.title("📊 Price Monitor Pro")

# --- AUTO-CHECK REPORTS (Alla prima esecuzione della sessione) ---



# Creazione dei tab (LAYOUT TOP BAR: Logo + Tabs)
# Creazione dei tab (LAYOUT TOP BAR: Logo + Tabs)
# Creazione dei tab (LAYOUT FULL WIDTH: Tabs occupano tutto lo spazio)
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "⚙️ Impostazioni", 
    "📦 Prodotti", 
    "🏢 Competitor", 
    "📈 Comparazione", 
    "📑 Report"
])

# --- Funzioni Helper Database ---

@st.cache_data(ttl=60)
def get_users():
    response = supabase.table("users").select("*").execute()
    return response.data

@st.cache_data(ttl=60)
def get_reference_site(owner):
    response = supabase.table("reference_site").select("*").eq("owner_username", owner).execute()
    return response.data

@st.cache_data(ttl=60)
def get_report_recipients(owner):
    response = supabase.table("report_recipients").select("*").eq("owner_username", owner).order("created_at", desc=True).execute()
    return response.data

@st.cache_data(ttl=60)
def get_competitors(owner):
    response = supabase.table("competitors").select("*").eq("owner_username", owner).execute()
    return response.data

def add_report_recipient(client_name, target_email, report_frequency, target_website, owner):
    try:
        supabase.table("report_recipients").insert({
            "client_name": client_name,
            "target_email": target_email,
            "report_frequency": report_frequency,
            "target_website": target_website,
            "owner_username": owner
        }).execute()
        return True, None
    except Exception as e:
        return False, str(e)

def add_user(username, password):
    try:
        supabase.table("users").insert({
            "username": username,
            "password": password
        }).execute()
        return True, None
    except Exception as e:
        return False, str(e)

def add_reference_site(nome, url, owner):
    try:
        supabase.table("reference_site").insert({
            "nome": nome,
            "url": url,
            "owner_username": owner
        }).execute()
        return True, None
    except Exception as e:
        return False, str(e)

def add_competitor(nome, url, note, owner):
    try:
        supabase.table("competitors").insert({
            "nome": nome,
            "url": url,
            "note": note,
            "owner_username": owner
        }).execute()
        return True, None
    except Exception as e:
        return False, str(e)

@st.cache_data(ttl=60)
def get_products(owner):
    response = supabase.table("products").select("*").eq("owner_username", owner).order("descrizione").execute()
    return response.data

def get_competitors_map(owner):
    """Ritorna un dizionario {competitor_id: competitor_name}"""
    try:
        data = supabase.table("competitors").select("id, nome").eq("owner_username", owner).execute().data
        return {c['id']: c['nome'] for c in data}
    except:
        return {}

def update_product_tracking(product_id, is_tracked):
    try:
        supabase.table("products").update({"is_tracked": is_tracked}).eq("id", product_id).execute()
        return True, None
    except Exception as e:
        return False, str(e)

# --- FOLDER HELPERS ---
@st.cache_data(ttl=60)
def get_folders(owner):
    response = supabase.table("folders").select("*").eq("owner_username", owner).order("created_at", desc=True).execute()
    return response.data

def create_folder(name, url, owner):
    try:
        supabase.table("folders").insert({
            "name": name,
            "source_url": url,
            "owner_username": owner
        }).execute()
        return True, None
    except Exception as e:
        return False, str(e)

def get_products_by_folder(folder_id, owner):
    response = supabase.table("products").select("*").eq("folder_id", folder_id).eq("owner_username", owner).order("id").execute()
    return response.data

def get_domain(url):
    try:
        parsed = urlparse(url)
        # Gestisce casi con o senza schema
        domain = parsed.netloc if parsed.netloc else parsed.path
        # Rimuove www. se presente per pulizia
        return domain.replace("www.", "")
    except:
        return ""

def clean_search_query(description):
    if not description:
        return ""
    
    # 1. ESTRAZIONE CODICE MODELLO (Priorità 1)
    # Regex Inclusiva: Cerca parole con almeno un numero, lunghe min 3 caratteri
    # Es. "HC-601i-E", "PHC1201E", "ESP-ME-4", "RZX4"
    code_pattern = r'\b(?=[A-Za-z]*\d)[A-Za-z0-9-]{3,}\b'
    match = re.search(code_pattern, description)
    
    # Prepara le parole di testa (Brand/Tipo) - Prime 2 parole
    words = description.split()
    head_words = " ".join(words[:2]) if len(words) >= 2 else description
    
    if match:
        code = match.group(0)
        # Ignora falsi positivi comuni (es. voltaggi, misure semplici se non sembrano codici)
        if code.lower() not in ['24v', '220v', '12v', '1/2"', '3/4"']:
                # COSTRUZIONE QUERY: Brand + Codice
                return f"{head_words} {code}"
    
    # --- 2. FALLBACK PAROLE CHIAVE (Priorità 2)
    # Prendi le prime 5 parole se non trovi un codice
    significant_words = [w for w in words if len(w) > 2]
    return " ".join(significant_words[:5])


# --- FUNZIONI REPORT EMAIL ---

def generate_pdf_report(user_id, owner, folder_id=None, is_test=False, custom_data=None):
    """
    Genera un PDF con il riepilogo della comparazione (Versione Robusta).
    Salva il file in /tmp e ritorna il path.
    """
    # --- DEBUG START ---
    st.write("--- INIZIO GENERAZIONE PDF (Robust Mode) ---")
    # --- DEBUG END ---

    try:
        # 1. FETCH DATI
        products = []
        df_merged = pd.DataFrame()
        
        if custom_data:
            st.write(f"DEBUG PDF: Utilizzo {len(custom_data)} righe custom (Test Mode)")
            # Logica Dummy per Test
            prod_map = {}
            p_list = []
            l_list = []
            for i, row in enumerate(custom_data):
                p_name = row.get('product_name', 'N/A')
                if p_name not in prod_map:
                    pid = i + 1000
                    prod_map[p_name] = pid
                    p_list.append({'id': pid, 'descrizione': p_name, 'prezzo': row.get('user_price', 0.0)})
                pid = prod_map[p_name]
                l_list.append({'product_id': pid, 'last_price': row.get('competitor_price', 0.0), 'competitor_name_resolved': row.get('competitor_name', 'N/A')})
            products = p_list
            df_merged = pd.DataFrame(l_list)
            
        elif not owner:
            st.error("ERRORE PDF: Nessun proprietario specificato.")
            return None
        else:
            # Fetch Reale
            query = supabase.table("products").select("*").eq("owner_username", owner)
            if folder_id: query = query.eq("folder_id", folder_id)
            else: query = query.eq("is_tracked", True)
            products = query.execute().data
            
            if products:
                p_ids = [p['id'] for p in products]
                # FIX QUERY: Richiedi esplicitamente competitor_id
                links_resp = supabase.table("competitor_links").select("id, product_id, competitor_id, competitor_url, last_price").in_("product_id", p_ids).execute()
                links_data = links_resp.data
                
                # Fetch Competitor (Explicit Request: Map Names manually)
                comps_resp = supabase.table("competitors").select("id, nome").eq("owner_username", owner).execute()
                comps_data = comps_resp.data
                
                # 1. RECUPERA MAPPA NOMI (FORZATA STRINGA)
                comp_map = {}
                if comps_data:
                    # FIX: Forziamo ID a stringa
                    comp_map = {str(c['id']): c['nome'] for c in comps_data}
                    st.write("🔍 DEBUG MAPPA COMPETITOR:", comp_map)
                
                df_links = pd.DataFrame(links_data)
                
                # FIX DEBUG: Stampa colonne trovate
                if not df_links.empty:
                    st.write("🔍 DEBUG DF LINKS (COLONNE):", df_links.columns.tolist())
                    st.write("🔍 DEBUG DF LINKS (HEAD):", df_links.head(2))
                
                # 2. APPLICA MAPPATURA
                if not df_links.empty:
                    # Non facciamo più affidamento sul merge pandas se vogliamo controllo totale
                    # Usiamo il ciclo sotto per fare il lookup
                    df_merged = df_links
                else:
                    df_merged = pd.DataFrame() # Vuoto se no links
 
        # 2. CONTROLLO DATI VUOTI (Regola Sicurezza #2)
        if not products:
            st.error("❌ ERRORE PDF: Nessun prodotto trovato per questo utente!")
            return None
        else:
            st.write(f"✅ Dati trovati: {len(products)} prodotti.")

        # 3. CREAZIONE CANVAS
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"/tmp/report_prezzi_{timestamp}.pdf"
        c = canvas.Canvas(filename, pagesize=letter)
        
        # --- GESTIONE LOGO SICURA (Regola Sicurezza #1) ---
        try:
            # Prova a cercare logo.png nella root corrente
            logo_path = "logo.png" 
            if os.path.exists(logo_path):
                # Disegna logo (x, y, width, height) - Adatta coordinate se necessario
                c.drawImage(logo_path, 50, 760, width=50, height=50, preserveAspectRatio=True, mask='auto')
                st.write("✅ Logo inserito.")
                # Spostiamo un po' i margini se c'è il logo
                header_x = 110
            else:
                st.warning("⚠️ Logo 'logo.png' non trovato, proseguo senza.")
                header_x = 50
        except Exception as e_logo:
            st.error(f"⚠️ Errore inserimento logo (ignorato): {e_logo}")
            header_x = 50 # Fallback

        # Intestazione
        c.setFont("Helvetica-Bold", 16)
        c.drawString(header_x, 780, "Report Comparazione Prezzi") 
        c.setFont("Helvetica", 10)
        c.drawString(header_x, 765, f"Generato il: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        
        y = 730 # INIZIALIZZAZIONE Y (Fondamentale)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y, "Prodotto")
        c.drawString(300, y, "Tuo Prezzo")
        c.drawString(380, y, "Competitor")
        c.drawString(500, y, "Gap")
        y -= 20
        c.setFont("Helvetica", 9)
        
        # 4. CICLO PRODOTTI
        for p in products:
            p_id = p['id']
            my_price = p.get('prezzo', 0.0) or 0.0
            p_name = p.get('descrizione', 'N/A')[:35]
            
            competitor_rows = []
            if not df_merged.empty and 'product_id' in df_merged.columns:
                subset = df_merged[df_merged['product_id'] == p_id]
                valid_subset = subset[subset['last_price'] > 0]
                if not valid_subset.empty:
                    valid_subset = valid_subset.sort_values(by='last_price')
                    for _, row in valid_subset.iterrows():
                        # FIX RIGIDO: Lookup manuale con string conversion
                        raw_id = row.get('competitor_id')
                        try:
                            # Gestione decimali (es. 5.0 -> "5")
                            str_id = str(raw_id).replace('.0', '')
                            # Lookup
                            c_name = comp_map.get(str_id, f"Sconosciuto (ID: {str_id})")
                        except Exception:
                            c_name = "Err. Tipo"
                        
                        competitor_rows.append((c_name, row['last_price']))

            # Rendering Righe
            if not competitor_rows:
                if y < 50:
                    c.showPage()
                    y = 750
                c.setFillColorRGB(0, 0, 0)
                c.drawString(50, y, p_name)
                c.drawString(300, y, f"€ {my_price:.2f}")
                c.drawString(380, y, "-")
                c.drawString(500, y, "-")
                y -= 15
            else:
                first_line = True
                for c_name, c_price in competitor_rows:
                    if y < 50:
                        c.showPage()
                        y = 750
                    
                    gap = my_price - c_price
                    gap_perc = (gap / c_price) * 100
                    gap_str = f"{gap_perc:.1f}%"
                    
                    # Colore Gap
                    if gap > 0: c.setFillColorRGB(1, 0, 0) # Rosso
                    else: c.setFillColorRGB(0, 0.5, 0) # Verde
                    
                    if first_line:
                        c.setFillColorRGB(0, 0, 0)
                        c.drawString(50, y, p_name)
                        c.drawString(300, y, f"€ {my_price:.2f}")
                        first_line = False
                        
                        # Ripristina colore per dati competitor
                        if gap > 0: c.setFillColorRGB(1, 0, 0) 
                        else: c.setFillColorRGB(0, 0.5, 0)

                    c.drawString(380, y, f"{c_name}: € {c_price:.2f}")
                    c.drawString(500, y, gap_str)
                    y -= 15
            
            c.setFillColorRGB(0, 0, 0)
            y -= 5

        c.save()
        st.write(f"✅ PDF salvato correttamente: {filename}")
        return filename

    except Exception as e:
        # TRACEBACK ERRORI (Regola Sicurezza #3)
        st.error(f"❌ CRASH TECNICO GENERAZIONE PDF: {e}")
        st.write("Traceback errore:", e)
        import traceback
        st.code(traceback.format_exc())
        return None

def send_email_report(user_email, pdf_path):
    # --- DEBUG START ---
    st.write(f"Inizio procedura invio email a: {user_email}")
    # --- DEBUG END ---
    
    try:
        # 1. Recupero Credenziali (Nuova Logica)
        email_config = st.secrets.get("email")
        if not email_config:
            st.error("Configurazione email mancante nei Secrets!")
            return False, "Missing config"

        smtp_server = email_config.get("smtp_server", "smtp.gmail.com")
        smtp_port = email_config.get("smtp_port", 587)
        sender_email = email_config.get("address")
        password = email_config.get("password")
        
        # Debug Output (Password Nascosta)
        st.write(f"Configurazione SMTP: {smtp_server}:{smtp_port} | Sender: {sender_email}")
        
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = user_email
        msg['Subject'] = "📊 Report Automatico - PriceComparator"
        
        body = "Ciao,\n\nIn allegato trovi il report aggiornato della comparazione prezzi.\n\nSaluti,\nPriceComparator Bot"
        msg.attach(MIMEText(body, 'plain'))
        
        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                attach = MIMEApplication(f.read(), _subtype="pdf")
                attach.add_header('Content-Disposition', 'attachment', filename=os.path.basename(pdf_path))
                msg.attach(attach)
        
        # Connessione SMTP con gestione errori dettagliata
        st.write("Tentativo connessione SMTP...")
        try:
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(sender_email, password)
                server.send_message(msg)
                st.success("Email inviata correttamente al server SMTP.")
                return True, None
        except smtplib.SMTPAuthenticationError as e:
            st.error(f"Errore Autenticazione SMTP: {e}")
            return False, str(e)
        except smtplib.SMTPConnectError as e:
            st.error(f"Errore Connessione SMTP: {e}")
            return False, str(e)
        except Exception as e:
             st.error(f"Errore Generico Invio SMTP: {e}")
             return False, str(e)

    except Exception as e:
        st.error(f"Errore procedura invio email: {e}")
        return False, str(e)

def check_and_send_scheduled_reports(user_id, user_email):
    """
    Controlla se è il momento di inviare il report e, nel caso, lo invia.
    """
    try:
        # Recupera preferenze utente
        user_data = supabase.table("users").select("username, report_frequency, last_report_sent").eq("id", user_id).single().execute().data
        if not user_data: return
        
        freq = user_data.get('report_frequency', 'Mai')
        last_sent_str = user_data.get('last_report_sent')
        
        if freq == 'Mai':
            return
            
        should_send = False
        now = datetime.now()
        
        if not last_sent_str:
            should_send = True
        else:
            last_sent = datetime.fromisoformat(last_sent_str.replace('Z', '+00:00')).replace(tzinfo=None) # Semplificazione TZ
            
            if freq == 'Giornaliero':
                if (now - last_sent).days >= 1:
                    should_send = True
            elif freq == 'Settimanale':
                if (now - last_sent).days >= 7:
                    should_send = True
                    
        if should_send:
            # Fetch username for report generation
            u_name = user_data.get('username') # user_data query below needs update to fetch username
            # Note: The query at line 587 selects "report_frequency, last_report_sent". We need username too.
            # Let's fix the query first. See replacement below.
            
            pdf_path = generate_pdf_report(user_id, owner=u_name)
            if pdf_path:
                success, msg = send_email_report(user_email, pdf_path)
                if success:
                    # Aggiorna DB
                    supabase.table("users").update({"last_report_sent": now.isoformat()}).eq("id", user_id).execute()
                    st.toast(f"📧 Report automatico inviato a {user_email}!")
                else:
                     print(f"Errore invio report automatico: {msg}")
                
    except Exception as e:
        print(f"Errore check report: {e}")

# --- Interfaccia Utente ---

# --- AUTO-CHECK REPORTS (Alla prima esecuzione della sessione) ---
if "reports_checked" not in st.session_state:
    try:
        all_users = supabase.table("users").select("*").execute().data
        if all_users:
            for u in all_users:
                check_and_send_scheduled_reports(u['id'], u['email'])
        st.session_state["reports_checked"] = True
    except Exception as e:
        print(f"Errore auto-check reports: {e}")

with tab1:
    st.header("Impostazioni")
    st.info("Qui potrai configurare le impostazioni dell'applicazione.")

    # 1. GESTIONE UTENTI
    # 1. MODIFICA PASSWORD (Ex 2, ora primo blocco visibile)



    # 2. MODIFICA PASSWORD (Nuovo Blocco)
    with st.expander("🔐 Modifica Password Personale", expanded=False):
        st.subheader("Aggiorna Password")
        with st.form("change_pwd_form"):
            current_user = st.session_state.get("username_input", "")
            st.code(f"Utente connesso: {current_user}")
            
            old_pwd = st.text_input("Vecchia Password", type="password")
            new_pwd = st.text_input("Nuova Password", type="password")
            confirm_pwd = st.text_input("Conferma Nuova Password", type="password")
            
            if st.form_submit_button("Aggiorna Password"):
                # Recupera user da sessione permanente (priorità) o input widget
                user = st.session_state.get("user") or st.session_state.get("username_input")
                
                if not user:
                    st.error("Errore sessione: Utente non identificato. Esegui il login di nuovo.")
                    st.stop()

                if new_pwd != confirm_pwd:
                    st.error("Le nuove password non coincidono.")
                elif not new_pwd:
                    st.warning("Inserisci una nuova password.")
                else:
                    try:
                        # Verifica se l'utente esiste (match su username)
                        response = supabase.table("users").update({"password": new_pwd}).eq("username", user).execute()
                        
                        # Controlla se ha aggiornato qualcosa
                        if response.data:
                            st.success("Password aggiornata con successo! Al prossimo login usa la nuova password.")
                        else:
                            st.error(f"Impossibile aggiornare. L'utente '{user}' non è stato trovato nel database.")
                    except Exception as e:
                        st.error(f"Errore aggiornamento password: {e}")
    
    # 3. GESTIONE DESTINATARI REPORT (Nuovo)
    with st.expander("📧 Gestione Destinatari Report (Clienti)", expanded=False):
        st.subheader("Aggiungi Nuovo Destinatario")
        with st.form("recipient_form", clear_on_submit=True):
            rc1, rc2 = st.columns(2)
            with rc1:
                r_client = st.text_input("Nome Cliente / Riferimento")
                r_email = st.text_input("Email Destinatario")
            with rc2:
                r_website = st.text_input("Sito Web (Opzionale)")
                r_freq = st.selectbox("Frequenza Report", ["Mai", "Giornaliero", "Settimanale", "Mensile"])
            
            if st.form_submit_button("Salva Destinatario"):
                if r_client and r_email:
                    success, msg = add_report_recipient(r_client, r_email, r_freq, r_website, st.session_state['user'])
                    if success:
                        st.success("Destinatario aggiunto!")
                        get_report_recipients.clear()
                        st.rerun()
                    else:
                        st.error(f"Errore salvataggio: {msg}")
                else:
                    st.warning("Nome Cliente ed Email sono obbligatori.")

        st.divider()
        st.subheader("Lista Destinatari")
        recipients = get_report_recipients(st.session_state['user'])
        
        if recipients:
            df_recip = pd.DataFrame(recipients)
            
            edited_recip = st.data_editor(
                df_recip,
                column_config={
                    "id": st.column_config.NumberColumn(disabled=True),
                    "created_at": st.column_config.DatetimeColumn(disabled=True, format="D MMM YYYY, h:mm a"),
                    "client_name": st.column_config.TextColumn("Cliente", required=True),
                    "target_email": st.column_config.TextColumn("Email", required=True),
                    "report_frequency": st.column_config.SelectboxColumn("Frequenza", options=["Mai", "Giornaliero", "Settimanale", "Mensile"], required=True),
                    "target_website": st.column_config.LinkColumn("Sito Web")
                },
                column_order=["client_name", "target_email", "report_frequency", "target_website", "created_at"],
                num_rows="dynamic",
                key="recipients_editor",
                hide_index=True
            )
            
            if st.button("💾 Salva Modifiche Destinatari"):
                try:
                    changes = st.session_state["recipients_editor"]
                    
                    # 1. DELETE
                    if changes["deleted_rows"]:
                        ids_to_del = df_recip.iloc[changes["deleted_rows"]]["id"].tolist()
                        if ids_to_del:
                            supabase.table("report_recipients").delete().in_("id", ids_to_del).execute()
                            st.toast(f"Eliminati: {len(ids_to_del)} destinatari", icon="🗑️")

                    # 2. UPDATE
                    for idx, updates in changes["edited_rows"].items():
                        rid = df_recip.iloc[int(idx)]["id"]
                        supabase.table("report_recipients").update(updates).eq("id", rid).eq("owner_username", st.session_state['user']).execute()
                        st.toast(f"Aggiornato ID: {rid}", icon="✅")
                    
                    if changes["deleted_rows"] or changes["edited_rows"]:
                        time.sleep(1)
                        get_report_recipients.clear()
                        st.rerun()
                    
                except Exception as e:
                    st.error(f"Errore salvataggio modifiche: {e}")
        else:
            st.info("Nessun destinatario configurato.")

    # 4. COMPETITOR
    with st.expander("🏢 Gestione Competitor", expanded=False):
        st.subheader("Lista Competitor")
        st.info("Aggiungi, Modifica o Elimina i competitor direttamente dalla tabella.")
        
        competitors = get_competitors(st.session_state['user'])
        if competitors:
            df_comp = pd.DataFrame(competitors)
        else:
            df_comp = pd.DataFrame(columns=["id", "nome", "url", "note"])
        
        # Configurazione Data Editor
        edited_comp_df = st.data_editor(
            df_comp,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "nome": st.column_config.TextColumn("Nome Competitor", required=True),
                "url": st.column_config.LinkColumn("URL Sito", required=True),
                "note": st.column_config.TextColumn("Note")
            },
            column_order=["nome", "url", "note"], # Nascondi ID ma usalo per logica
            num_rows="dynamic",
            key="competitor_editor",
            hide_index=True
        )

        if st.button("💾 Salva Modifiche Competitor"):
            try:
                changes = st.session_state["competitor_editor"]
                print(f"DEBUG CHANGES: {changes}")
                
                # 1. ADDED ROWS
                for row in changes["added_rows"]:
                    # row è un dict con le colonne popolate
                    if "nome" in row and row["nome"]:
                        supabase.table("competitors").insert({
                            "nome": row.get("nome"),
                            "url": row.get("url", ""),
                            "note": row.get("note", ""),
                            "owner_username": st.session_state['user']
                        }).execute()
                
                # 2. DELETED ROWS
                # changes["deleted_rows"] è una lista di indici (int) riferiti al DF originale
                if changes["deleted_rows"]:
                    # Recupera gli ID da eliminare
                    ids_to_delete = df_comp.iloc[changes["deleted_rows"]]["id"].tolist()
                    if ids_to_delete:
                        supabase.table("competitors").delete().in_("id", ids_to_delete).execute()

                # 3. EDITED ROWS
                # changes["edited_rows"] è un dict {index: {col: val}}
                for idx, updates in changes["edited_rows"].items():
                    # Recupera ID
                    comp_id = df_comp.iloc[int(idx)]["id"]
                    supabase.table("competitors").update(updates).eq("id", comp_id).eq("owner_username", st.session_state['user']).execute()
                
                st.success("Modifiche salvate con successo!")
                get_competitors.clear()
                time.sleep(1)
                st.rerun()
                
            except Exception as e:
                st.error(f"Errore durante il salvataggio: {e}")

with tab2:
    st.header("Gestione Cartelle e Prodotti")
    
    # Layout: Sidebar (Sinistra) per Cartelle, Main (Destra) per Prodotti
    col_folders, col_products = st.columns([1, 3])
    
    with col_folders:
        st.subheader("📂 Cartelle")
        
        # 0. IMPORTAZIONE MASSIVA (CSV / CRAWLER)
        with st.expander("📂 Importazione Massiva (Crea Macro-Categorie: es. Elettronica)", expanded=False):
            st.info("Configura l'importazione automatica delle sottocartelle.")
            st.markdown("💡 **Consiglio**: Usa l'importazione massiva per creare **Macro-Categorie** (es. 'Elettronica', 'Abbigliamento') organizzate per gruppi.")
            with st.form("crawler_form"):
                 # NOTA: L'utente chiedeva di modificare st.file_uploader, ma qui abbiamo un text_input per URL.
                 # Adatto il testo qui per coerenza con la richiesta.
                parent_url = st.text_input("URL Categoria / CSV (Se disponibile)", placeholder="https://...")
                group_name = st.text_input("Nome Gruppo (Prefisso)", placeholder="es. Irrigatori")
                
                if st.form_submit_button("Analizza e Crea Sottocartelle"):
                    if parent_url and group_name:
                        with st.spinner(f"Analisi di {parent_url}..."):
                            try:
                                from scraper import crawl_subcategories, scrape_category
                                subs, debug_html = crawl_subcategories(parent_url)
                                
                                if not subs:
                                    st.error("Nessuna sottocategoria trovata.")
                                    if debug_html:
                                        with st.expander("Debug HTML"):
                                            st.code(debug_html, language='html')
                                else:
                                    st.success(f"Trovate {len(subs)} sottocategorie! Inizio elaborazione...")
                                    
                                    progress_bar = st.progress(0)
                                    status_text = st.empty()
                                    
                                    for i, sub in enumerate(subs):
                                        sub_name = sub['name']
                                        sub_url = sub['url']
                                        full_folder_name = f"{group_name} > {sub_name}"
                                        
                                        status_text.text(f"Elaborazione: {sub_name}...")
                                        
                                        # 1. Crea Cartella
                                        success, msg = create_folder(full_folder_name, sub_url, st.session_state['user'])
                                        if success:
                                            # Recupera ID appena creato (o esistente)
                                            # create_folder non ritorna ID, quindi lo recuperiamo
                                            f_resp = supabase.table("folders").select("id").eq("name", full_folder_name).execute()
                                            if f_resp.data:
                                                fid = f_resp.data[0]['id']
                                                
                                                # 2. Scrape Prodotti
                                                count = scrape_category(sub_url, fid, st.session_state['user'])
                                                st.toast(f"✅ {sub_name}: Creati {count} prodotti", icon="📦")
                                            
                                        progress_bar.progress((i + 1) / len(subs))
                                        time.sleep(1)
                                    
                                    status_text.text("Importazione Massiva Completata!")
                                    st.success("Tutte le sottocartelle sono state create e popolate.")
                                    time.sleep(2)
                                    st.rerun()

                            except Exception as e:
                                st.error(f"Errore Crawler: {e}")
                    else:
                        st.warning("Compila tutti i campi.")

        # 1. CREA NUOVA CARTELLA
        with st.expander("➕ Nuova Cartella (Singola)", expanded=False):
            with st.form("new_folder_form", clear_on_submit=True):
                new_folder_name = st.text_input(
                    "Nome Cartella", 
                    placeholder="Es. Smartphone Android (Sottocategoria o Prodotto Specifico)",
                    help="Crea una cartella per un gruppo specifico di prodotti."
                )
                new_folder_url = st.text_input("URL Categoria", placeholder="https://...")
                
                if st.form_submit_button("Crea"):
                    if new_folder_name:
                        success, msg = create_folder(new_folder_name, new_folder_url, st.session_state['user'])
                        if success:
                            st.success("Creata!")
                            get_folders.clear()
                            st.rerun()
                            
                        else:
                            st.error(msg)
                    else:
                        st.warning("Nome obbligatorio")
        
        # 2. LISTA CARTELLE (Selezione Gerarchica)
        folders = get_folders(st.session_state['user'])
        selected_folder_id = None
        selected_folder = None
        
        if folders:
            # Logica Gerarchica: "Gruppo > Sottocartella"
            hierarchy = {}
            for f in folders:
                name = f['name']
                fid = f['id']
                if " > " in name:
                    parts = name.split(" > ", 1)
                    group = parts[0]
                    sub = parts[1]
                else:
                    group = "Altro"
                    sub = name
                
                if group not in hierarchy:
                    hierarchy[group] = {}
                hierarchy[group][sub] = fid
            
            # Step 1: Seleziona Gruppo
            sorted_groups = sorted(hierarchy.keys())
            # Metti "Altro" in fondo se esiste
            if "Altro" in sorted_groups:
                sorted_groups.remove("Altro")
                sorted_groups.append("Altro")
                
            selected_group = st.selectbox("📂 Filtra per Gruppo", options=sorted_groups)
            
            # Step 2: Seleziona Sottocartella
            if selected_group:
                subfolders = hierarchy[selected_group]
                sorted_subs = sorted(subfolders.keys())
                selected_sub_name = st.selectbox("Sottocartella", options=sorted_subs)
                selected_folder_id = subfolders[selected_sub_name]
                
                # Trova oggetto folder
                selected_folder = next((f for f in folders if f['id'] == selected_folder_id), None)

        else:
            st.info("Nessuna cartella. Creane una.")

    with col_products:
        if selected_folder:
            # HEADER
            st.subheader(f"📁 {selected_folder['name']}")
            st.caption(f"URL Monitorato: {selected_folder.get('source_url', 'Nessuno')}")
            
            # PANNELLO GESTIONE (Visibile e Prominente)
            with st.container(border=True):
                st.markdown("#### ⚙️ Gestione Cartella")
                gc1, gc2 = st.columns([2, 1])
                
                with gc1:
                    with st.form("edit_folder_form"):
                        new_name = st.text_input("Nome Cartella", value=selected_folder['name'])
                        new_url = st.text_input("URL Categoria", value=selected_folder.get('source_url', ''))
                        
                        if st.form_submit_button("💾 Salva Modifiche"):
                            try:
                                supabase.table("folders").update({
                                    "name": new_name,
                                    "source_url": new_url
                                }).eq("id", selected_folder_id).eq("owner_username", st.session_state['user']).execute()
                                st.success("Modifiche salvate!")
                                get_folders.clear()
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Errore salvataggio: {e}")
                
                with gc2:
                    st.error("Zona Pericolo")
                    if st.button("🗑️ ELIMINA CARTELLA", type="primary", help="Elimina la cartella e tutti i suoi prodotti. Irreversibile."):
                        try:
                            # 1. Elimina prodotti
                            supabase.table("products").delete().eq("folder_id", selected_folder_id).execute()
                            # 2. Elimina cartella
                            supabase.table("folders").delete().eq("id", selected_folder_id).execute()
                            st.success("Cartella eliminata!")
                            get_folders.clear()
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Errore eliminazione: {e}")

            st.divider()
            
            # AZIONI RAPIDE (Scrape / Add)
            c1, c2 = st.columns(2)
            
            # A. SCARICA PRODOTTI (Bulk)
            if c1.button("🔄 Scarica Prodotti da URL"):
                target_url = selected_folder.get('source_url')
                if target_url:
                    with st.spinner(f"Scraping di {target_url}..."):
                        try:
                            # Importa qui per evitare problemi circolari se scraper usa app
                            from scraper import scrape_category
                            
                            # Chiama scraper passando folder_id e owner_username
                            count = scrape_category(target_url, selected_folder_id, st.session_state['user'])
                            
                            if count > 0:
                                st.success(f"Trovati {count} nuovi prodotti!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.warning("Nessun nuovo prodotto trovato.")
                        except Exception as e:
                            st.error(f"Errore scraping: {e}")
                else:
                    st.warning("Questa cartella non ha un URL categoria impostato.")

            # B. AGGIUNGI SINGOLO (Manual)
            with c2.popover("➕ Aggiungi Prodotto Singolo"):
                single_url = st.text_input("URL Prodotto Singolo")
                if st.button("Analizza e Aggiungi"):
                    if single_url:
                        with st.spinner("Analisi prodotto..."):
                            try:
                                from scraper import scrape_single_product_insert
                                success, msg = scrape_single_product_insert(single_url, selected_folder_id, st.session_state['user'])
                                if success:
                                    st.success("Prodotto aggiunto!")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error(f"Errore: {msg}")
                            except Exception as e:
                                st.error(f"Errore: {e}")
            
            st.divider()
            
            # TABELLA PRODOTTI DELLA CARTELLA
            folder_products = get_products_by_folder(selected_folder_id, st.session_state['user'])
            
            if folder_products:
                st.caption("💡 **Tip**: Per eliminare un prodotto, seleziona la riga (clicca a sinistra) e premi `Canc` (o usa l'icona cestino se visibile). Ricorda di salvare.")
                
                df_fp = pd.DataFrame(folder_products)
                
                # Gestione is_tracked
                if "is_tracked" not in df_fp.columns:
                    df_fp["is_tracked"] = False
                else:
                    df_fp["is_tracked"] = df_fp["is_tracked"].fillna(False)

                # Editor
                edited_df = st.data_editor(
                    df_fp,
                    column_config={
                        "is_tracked": st.column_config.CheckboxColumn("Monitora", width="small", default=False),
                        "descrizione": st.column_config.TextColumn("Prodotto", width="large"),
                        "prezzo": st.column_config.NumberColumn("Prezzo", format="€ %.2f"),
                        "codice": st.column_config.TextColumn("Codice"),
                        "url": st.column_config.LinkColumn("Link"),
                    },
                    column_order=["is_tracked", "codice", "descrizione", "prezzo", "url"],
                    hide_index=True,
                    num_rows="dynamic", # Abilita eliminazione
                    use_container_width=True,
                    key="editor_products" # Chiave fissa come richiesto
                )
                
                if st.button("💾 Conferma Modifiche/Eliminazioni"):
                    # 1. Gestione Eliminazioni
                    editor_state = st.session_state.get("editor_products")
                    
                    deleted_count = 0
                    if editor_state and "deleted_rows" in editor_state:
                        for idx in editor_state["deleted_rows"]:
                            # Recupera ID dal dataframe originale usando l'indice
                            if idx < len(df_fp):
                                pid_to_del = df_fp.iloc[idx]['id']
                                try:
                                    supabase.table("products").delete().eq("id", pid_to_del).execute()
                                    deleted_count += 1
                                except Exception as e:
                                    st.error(f"Errore eliminazione: {e}")

                    # 2. Gestione Aggiornamenti (is_tracked)
                    updated = 0
                    for index, row in edited_df.iterrows():
                        if 'id' in row and pd.notna(row['id']):
                            pid = row['id']
                            tracked = row['is_tracked']
                            supabase.table("products").update({"is_tracked": tracked}).eq("id", pid).eq("owner_username", st.session_state['user']).execute()
                            updated += 1
                    
                    if deleted_count > 0:
                        st.success(f"🗑️ Eliminati {deleted_count} prodotti.")
                    st.success(f"✅ Aggiornati {updated} prodotti.")
                    time.sleep(1)
                    st.rerun()
                    
            else:
                st.info("Cartella vuota. Scarica prodotti o aggiungine uno manualmente.")
        
        else:
            st.info("👈 Seleziona una cartella dalla barra laterale per vedere i prodotti.")

# HELPER: Navigazione Gerarchica Standardizzata
def render_hierarchical_sidebar(key_suffix):
    """
    Renderizza la selezione gerarchica (Gruppo > Sottocartella).
    Ritorna (selected_folder_id, selected_folder_obj, selected_group)
    """
    folders_response = supabase.table("folders").select("*").eq("owner_username", st.session_state['user']).execute()
    folders = folders_response.data
    
    if not folders:
        st.warning("Nessuna cartella trovata.")
        return None, None, None

    # Logica Gerarchica
    hierarchy = {}
    for f in folders:
        name = f['name']
        fid = f['id']
        if " > " in name:
            parts = name.split(" > ", 1)
            group = parts[0]
            sub = parts[1]
        else:
            group = "Altro"
            sub = name
        
        if group not in hierarchy:
            hierarchy[group] = {}
        hierarchy[group][sub] = fid
    
    # Layout a 2 colonne
    c1, c2 = st.columns(2)
    
    # Step 1: Gruppo
    sorted_groups = sorted(hierarchy.keys())
    if "Altro" in sorted_groups:
        sorted_groups.remove("Altro")
        sorted_groups.append("Altro")
        
    selected_group = c1.selectbox("📂 Filtra per Gruppo", options=sorted_groups, key=f"group_{key_suffix}")
    
    selected_folder_id = None
    selected_folder = None
    
    # Step 2: Sottocartella
    if selected_group:
        subfolders = hierarchy[selected_group]
        sorted_subs = sorted(subfolders.keys())
        selected_sub_name = c2.selectbox("Sottocartella", options=sorted_subs, key=f"sub_{key_suffix}")
        selected_folder_id = subfolders[selected_sub_name]
        
        # Recupera oggetto folder
        selected_folder = next((f for f in folders if f['id'] == selected_folder_id), None)
        
    return selected_folder_id, selected_folder, selected_group

with tab3:
    st.header("Gestione Competitor (Multi-Link)")
    
    # HELPER: Gestione Database Link
    def get_competitor_links(product_id):
        try:
            response = supabase.table("competitor_links").select("*").eq("product_id", product_id).eq("owner_username", st.session_state['user']).execute()
            return response.data
        except Exception as e:
            st.error(f"Errore recupero link: {e}")
            return []

    def add_competitor_link(product_id, comp_name, comp_url):
        try:
            supabase.table("competitor_links").insert({
                "product_id": product_id,
                "competitor_name": comp_name,
                "competitor_url": comp_url,
                "owner_username": st.session_state['user']
            }).execute()
            return True
        except Exception as e:
            st.error(f"Errore salvataggio link: {e}")
            return False

    # 1. SELEZIONE CARTELLA (Standardizzata)
    selected_folder_id, selected_folder, selected_group = render_hierarchical_sidebar("tab3")
    
    # GESTIONE GRUPPO (Eliminazione Massiva)
    if selected_group and selected_group != "Altro":
        with st.expander(f"🗑️ Gestione Gruppo '{selected_group}'", expanded=False):
            st.warning("⚠️ Attenzione: Cancellare il gruppo eliminerà TUTTE le sottocartelle e i prodotti contenuti.")
            if st.button("CONFERMA CANCELLAZIONE GRUPPO", type="primary", key="del_group_btn"):
                # Cancella tutte le cartelle che iniziano con questo nome
                # Nota: Assicurati che il nome gruppo sia corretto per il filtro
                try:
                    # Delete folders (Cascade should handle products if configured, otherwise we might leave orphans if no cascade)
                    # User requested this specific logic:
                    supabase.table('folders').delete().ilike('name', f"{selected_group}%").eq("owner_username", st.session_state['user']).execute()
                    
                    # Optional: Delete products manually if cascade isn't on?
                    # The user's code didn't include product deletion, assuming cascade or just folder deletion is enough.
                    # But to be safe let's stick to their code which only deletes folders.
                    # Wait, if I delete folders, products with that folder_id might remain if no cascade.
                    # But the user said "Cancella tutte le cartelle...".
                    # Let's trust the user's "Senior Python Developer" instruction.
                    
                    st.success("Gruppo eliminato.")
                    get_folders.clear()
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore eliminazione gruppo: {e}")

    if selected_folder_id:
        # PANNELLO GESTIONE (Copia da Tab 2)
        with st.expander("⚙️ Gestione Cartella (Elimina)", expanded=False):
             st.error("Zona Pericolo")
             if st.button("🗑️ ELIMINA CARTELLA", key="del_folder_t3", type="primary", help="Elimina la cartella e tutti i suoi prodotti."):
                try:
                    supabase.table("products").delete().eq("folder_id", selected_folder_id).execute()
                    supabase.table("folders").delete().eq("id", selected_folder_id).execute()
                    st.success("Cartella eliminata!")
                    get_folders.clear()
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore eliminazione: {e}")
    else:
        st.warning("Seleziona una cartella per iniziare.")

    # 2. RECUPERA PRODOTTI TRACCIATI (Filtrati per Cartella)
    if selected_folder_id:
        try:
            # Filtra per is_tracked=True E folder_id
            response = supabase.table("products").select("*").eq("is_tracked", True).eq("folder_id", selected_folder_id).order("id").execute()
            tracked_products = response.data
        except Exception as e:
            st.error(f"Errore nel recupero dei prodotti: {e}")
            tracked_products = []

        if not tracked_products:
            st.info("Nessun prodotto tracciato in questa cartella. Vai nel Tab 'Prodotti' per selezionare i prodotti da monitorare.")
        else:
            st.info(f"Gestisci i link dei competitor per i {len(tracked_products)} prodotti tracciati in questa cartella.")
            
            # 2. ITERA SUI PRODOTTI (Espandibili)
            for p in tracked_products:
                product_id = p['id']
                product_name = p['descrizione']
                product_code = p.get('codice', 'N/A')
                
                with st.expander(f"📦 {product_name} ({product_code})"):
                    
                    # A. Mostra Link Esistenti
                    links = get_competitor_links(product_id)
                    if links:
                        st.markdown("##### Link Salvati")
                        df_links = pd.DataFrame(links)
                        # Mostra solo colonne utili
                        cols_show = ["competitor_name", "competitor_url", "last_price"]
                        # Filtra quelle che esistono
                        cols_show = [c for c in cols_show if c in df_links.columns]
                        
                        st.dataframe(
                            df_links[cols_show],
                            column_config={
                                "competitor_url": st.column_config.LinkColumn("URL"),
                                "last_price": st.column_config.NumberColumn("Ultimo Prezzo", format="€ %.2f")
                            },
                            hide_index=True,
                            use_container_width=True
                        )
                    else:
                        st.info("Nessun competitor associato a questo prodotto.")

                    st.divider()
                    
                    # B. Aggiungi Nuovo Competitor
                    # B. Aggiungi Nuovo Competitor (Workflow: Seleziona -> Cerca -> Salva)
                    st.markdown("##### Aggiungi Nuovo Link")
                    
                    # 1. PREPARAZIONE DATI COMPETITOR
                    # Recupera lista competitor dal DB (cache)
                    competitors_list = get_competitors(st.session_state['user'])
                    if not competitors_list:
                        st.warning("Nessun competitor configurato. Vai in 'Impostazioni' per aggiungerne uno.")
                    else:
                        # Mappa Nome -> URL per automazione
                        comp_map = {c['nome']: c['url'] for c in competitors_list}
                        comp_names = list(comp_map.keys())

                        # Layout a 3 Colonne
                        c1, c2, c3 = st.columns([2, 2, 3])
                        
                        # Col 1: Selectbox Competitor
                        selected_comp_name = c1.selectbox("Scegli Competitor", options=comp_names, key=f"sel_comp_{product_id}")
                        
                        # Col 2: Anteprima Dominio (Auto-calcolato)
                        selected_comp_url = comp_map.get(selected_comp_name, "")
                        domain = get_domain(selected_comp_url)
                        c2.text_input("Dominio (Auto)", value=domain, disabled=True, key=f"domain_disp_{product_id}")
                        
                        # Col 3: URL Prodotto (Input Manuale)
                        new_url_input = c3.text_input("Incolla URL Prodotto", key=f"url_{product_id}")

                        # C. Pulsante SMART SEARCH (Appare subito)
                        if domain:
                            search_query = clean_search_query(product_name)
                            google_q = quote_plus(f"site:{domain} {search_query}")
                            google_url = f"https://www.google.com/search?q={google_q}"
                            
                            # Mostra pulsante sotto la selectbox
                            c1.link_button(f"🔎 Cerca su {selected_comp_name}", google_url)

                        # D. Pulsante SALVA
                        if c3.button("➕ Aggiungi Link", key=f"btn_add_{product_id}"):
                            if new_url_input:
                                if add_competitor_link(product_id, selected_comp_name, new_url_input):
                                    st.success("Link aggiunto!")
                                    time.sleep(0.5)
                                    st.rerun()
                            else:
                                st.warning("Incolla l'URL del prodotto.")
                    
                    st.divider()
                    # E. ELIMINAZIONE PRODOTTO (Singolo)
                    if st.button("🗑️ Elimina Prodotto definitivamente", key=f"del_prod_t3_{product_id}"):
                        try:
                            supabase.table("products").delete().eq("id", product_id).eq("owner_username", st.session_state['user']).execute()
                            st.success("Prodotto eliminato!")
                            time.sleep(0.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Errore eliminazione: {e}")
    else:
        st.info("Seleziona una cartella per iniziare.")
with tab4:
    st.header("Comparazione Prezzi")
    
    # 1. SELEZIONE CARTELLA (Standardizzata)
    selected_folder_id_t4, selected_folder_t4, _ = render_hierarchical_sidebar("tab4")
    
    if not selected_folder_id_t4:
        st.info("Seleziona una cartella per vedere la comparazione.")
    else:
        st.caption(f"Analisi per: {selected_folder_t4['name']}")

        # 2. RECUPERO DATI (Join Products + Links) - FILTRATO
        try:
            # Fetch Products (Filtrati per Cartella)
            products_resp = supabase.table("products").select("id, descrizione, prezzo, codice").eq("is_tracked", True).eq("folder_id", selected_folder_id_t4).eq("owner_username", st.session_state['user']).execute()
            products_data = products_resp.data
            
            if not products_data:
                st.warning("Nessun prodotto tracciato in questa cartella.")
            else:
                # ... (Resto della logica invariato, usa products_data filtrato)
                product_ids = [p['id'] for p in products_data]
                links_resp = supabase.table("competitor_links").select("*").in_("product_id", product_ids).eq("owner_username", st.session_state['user']).execute()
                links_data = links_resp.data
                
                # Creazione DataFrame Comparazione (1 Riga per LINK)
                rows = []
                for p in products_data:
                    p_links = [l for l in links_data if l['product_id'] == p['id']]
                    
                    if not p_links:
                        continue

                    for link in p_links:
                        comp_price = link['last_price']
                        my_price = p['prezzo']
                        last_check = link.get('last_check', 'Mai')
                        
                        gap = None
                        gap_perc = None
                        status = "N/A"
                        
                        if my_price and comp_price and comp_price > 0:
                            gap = my_price - comp_price
                            gap_perc = (gap / comp_price) * 100
                            
                            if gap > 0:
                                status = "❌ Perdiamo"
                            elif gap < 0:
                                status = "✅ Vinciamo"
                            else:
                                status = "⚖️ Pari"
                        elif comp_price == 0:
                             status = "⚠️ Prezzo 0"

                        rows.append({
                            "id": p['id'], # Aggiunto ID per eliminazione
                            "Codice": p.get('codice', ''),
                            "Prodotto": p['descrizione'],
                            "Tuo Prezzo": float(my_price) if my_price else 0.0,
                            "Competitor": link.get('competitor_name', 'Sconosciuto'),
                            "Prezzo Competitor": float(comp_price) if comp_price else 0.0,
                            "Gap %": gap_perc,
                            "Status": status,
                            "Link": link['competitor_url'],
                            "Ultimo Controllo": last_check
                        })
                
                if not rows:
                     st.warning("Nessun dato di comparazione disponibile (aggiungi link ai prodotti).")
                else:
                    df_compare = pd.DataFrame(rows)
                    
                    # --- 3. CALCOLO KPI GLOBALI (Basati su PRODOTTI UNICI) ---
                    unique_products = df_compare["Prodotto"].unique()
                    total_products = len(unique_products)
                    
                    winning_count = 0
                    losing_count = 0
                    tie_count = 0
                    
                    # Analisi per prodotto (Best Competitor Price)
                    product_stats = {} # Cache per dopo
                    
                    for prod in unique_products:
                        subset = df_compare[df_compare["Prodotto"] == prod]
                        my_price = subset.iloc[0]["Tuo Prezzo"]
                        
                        # Filtra prezzi validi (>0)
                        valid_competitors = subset[subset["Prezzo Competitor"] > 0]
                        
                        if not valid_competitors.empty:
                            best_comp_price = valid_competitors["Prezzo Competitor"].min()
                            
                            if my_price < best_comp_price:
                                winning_count += 1
                                p_status = "✅"
                            elif my_price > best_comp_price:
                                losing_count += 1
                                p_status = "🔴"
                            else:
                                tie_count += 1
                                p_status = "⚖️"
                        else:
                            best_comp_price = 0
                            p_status = "⚠️" # Solo prezzi 0
                            
                        product_stats[prod] = {
                            "best_price": best_comp_price,
                            "status_icon": p_status,
                            "my_price": my_price
                        }

                    # Render KPI
                    k1, k2, k3 = st.columns(3)
                    k1.metric("Prodotti Tracciati", total_products)
                    k2.metric("Vinciamo su", f"{winning_count} prodotti")
                    k3.metric("Perdiamo su", f"{losing_count} prodotti")
                    
                    st.divider()
                    
                    # --- 4. VISUALIZZAZIONE RAGGRUPPATA (Expanders) ---
                    # Ordina prodotti: Prima i PERDENTI (Urgenti), poi gli altri
                    # Creiamo una lista di tuple (status_priority, prod_name)
                    # Priority: 🔴=0, ⚠️=1, ⚖️=2, ✅=3
                    def get_priority(icon):
                        if icon == "🔴": return 0
                        if icon == "⚠️": return 1
                        if icon == "⚖️": return 2
                        return 3
                        
                    sorted_prods = sorted(unique_products, key=lambda p: (get_priority(product_stats[p]["status_icon"]), p))
                    
                    for prod in sorted_prods:
                        stats = product_stats[prod]
                        icon = stats["status_icon"]
                        my_p = stats["my_price"]
                        best_p = stats["best_price"]
                        
                        # Titolo Expander
                        if best_p > 0:
                            title = f"{icon} {prod} | Tuo: {my_p:.2f}€ | Best Competitor: {best_p:.2f}€"
                        else:
                            title = f"{icon} {prod} | Tuo: {my_p:.2f}€ | Competitor: N/A"
                            
                        with st.expander(title):
                            # Subset DataFrame
                            subset = df_compare[df_compare["Prodotto"] == prod].copy()
                            
                            # Recupera ID Prodotto (dalla prima riga del subset)
                            # Nota: Dobbiamo aver aggiunto 'id' al dataframe rows prima!
                            # Se non c'è, lo recuperiamo ora o modifichiamo la creazione rows.
                            # Modifichiamo rows sopra per includere 'id'.
                            
                            # Layout: Spacer + Delete Button
                            c_space, c_del = st.columns([0.85, 0.15])
                            with c_del:
                                # Recupera ID dal subset (assumendo che lo aggiungeremo a rows)
                                if "id" in subset.columns:
                                    pid = subset.iloc[0]["id"]
                                    if st.button("🗑️ Elimina", key=f"del_comp_{pid}", type="primary", help="Cancella questo prodotto e tutti i link associati"):
                                        try:
                                            supabase.table("products").delete().eq("id", int(pid)).eq("owner_username", st.session_state['user']).execute()
                                            st.toast("Prodotto eliminato!", icon="🗑️")
                                            time.sleep(1)
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Errore eliminazione: {e}")
                            
                            # Colonne da mostrare
                            cols_to_show = ["Competitor", "Prezzo Competitor", "Gap %", "Link", "Ultimo Controllo"]
                            
                            # Styling
                            st.dataframe(
                                subset[cols_to_show],
                                column_config={
                                    "Prezzo Competitor": st.column_config.NumberColumn("Prezzo", format="€ %.2f"),
                                    "Gap %": st.column_config.NumberColumn("Gap %", format="%.1f%%"),
                                    "Link": st.column_config.LinkColumn("Vai al sito"),
                                    "Ultimo Controllo": st.column_config.DatetimeColumn("Aggiornato", format="D MMM, HH:mm")
                                },
                                hide_index=True,
                                use_container_width=True
                            )
                
                st.divider()
                
                # 5. PULSANTE AGGIORNA PREZZI (MIRATO)
                folder_name = selected_folder_t4['name']
                if st.button(f"🔄 Aggiorna Prezzi: {folder_name}"):
                    with st.spinner("Aggiornamento prezzi competitor in corso..."):
                        # Logica scraping mirato
                        # Recupera SOLO i link di questa cartella
                        # (Già filtrati sopra in links_data)
                        total_links = len(links_data)
                        updated_count = 0
                        
                        progress_bar = st.progress(0)
                        
                        # from scraper import get_price_from_url (RIMOSSO)
                        
                        for i, link in enumerate(links_data):
                            url = link['competitor_url']
                            lid = link['id']
                            
                            new_price = get_competitor_price_local(url)
                            if new_price:
                                supabase.table("competitor_links").update({"last_price": new_price, "last_check": "now()"}).eq("id", lid).execute()
                                updated_count += 1
                            
                            progress_bar.progress((i + 1) / total_links)
                            time.sleep(0.5) # Gentilezza
                            
                        st.success(f"Aggiornati {updated_count}/{total_links} link.")
                        time.sleep(1)
                        st.rerun()

                # 4. VISUALIZZAZIONE STYLING
                def style_gap_column(val):
                    if pd.isna(val): return ""
                    if val < -10: return "background-color: #d4edda; color: green; font-weight: bold" # Verde scuro (Vinciamo bene)
                    if -10 <= val < 0: return "background-color: #e2e6ea; color: green" # Verde chiaro
                    if 0 <= val < 10: return "background-color: #fff3cd; color: orange" # Giallo (Attenzione)
                    return "background-color: #f8d7da; color: red; font-weight: bold" # Rosso (Perdiamo)

                cols_display = ["Codice", "Prodotto", "Tuo Prezzo", "Prezzo Competitor", "Gap %", "Status"]
                
                st.dataframe(
                    df_compare[cols_display].style.map(style_gap_column, subset=['Gap %']).format({
                        "Tuo Prezzo": "€ {:.2f}", 
                        "Prezzo Competitor": "€ {:.2f}", 
                        "Gap %": "{:.1f}%"
                    }),
                    use_container_width=True,
                    height=600
                )

        except Exception as e:
            st.error(f"Errore caricamento dati: {e}")




with tab5:
    st.header("Reportistica")
    
    st.markdown("### 📧 Impostazioni Report Automatici")
    st.info("Configura la frequenza con cui ricevere il report PDF via email.")
    
    # Selettore Destinatario (Da tabella report_recipients)
    recipients = get_report_recipients(st.session_state['user'])
    # DEBUG DESTINATARI
    if recipients:
        st.write(f"Trovati {len(recipients)} destinatari configurati.")
    else:
        st.warning("Nessun destinatario trovato per questo utente. Controlla il Tab 1.")
    
    if not recipients:
        st.warning("Nessun destinatario trovato. Creane uno in 'Gestione Destinatari Report' (Tab 1).")
    else:
        # Crea dizionario label -> recipient object
        recipient_options = {}
        for r in recipients:
            c_name = r.get('client_name', 'Sconosciuto')
            c_email = r.get('target_email', 'No Email')
            label = f"{c_name} ({c_email})"
            recipient_options[label] = r
        
        selected_recipient_label = st.selectbox("Seleziona Destinatario per Test Report", options=list(recipient_options.keys()))
        
        if selected_recipient_label:
            current_recipient = recipient_options[selected_recipient_label]
            # user_id per generare il report? Usiamo l'ID del destinatario o un ID fittizio?
            # La funzione generate_pdf_report accetta user_id per eventuali personalizzazioni, ma qui usiamo dati globali.
            # Passiamo l'ID del destinatario come riferimento
            recipient_id = current_recipient['id']
            target_email = current_recipient['target_email']
            
            st.info(f"Report configurato per: {target_email} (Frequenza: {current_recipient.get('report_frequency', 'N/A')})")
            
            st.divider()
            
            # AREA TEST DIAGNOSTICA
            st.markdown("### 🛠️ Area Test")
            st.info("Usa questa sezione per verificare se le email partono correttamente.")
            
            st.markdown("---")
            st.subheader("🔧 Area Tecnica")

            if st.button("TEST CONNESSIONE EMAIL (Debug SMTP)"):
                import smtplib
                try:
                    # 1. Recupero credenziali
                    email_conf = st.secrets.get("email")
                    if not email_conf:
                        st.error("ERRORE CRITICO: La sezione [email] non esiste nei secrets!")
                        st.stop()
                        
                    smtp_server = email_conf.get("smtp_server", "smtp.gmail.com")
                    smtp_port = email_conf.get("smtp_port", 587)
                    email_address = email_conf.get("address")
                    email_password = email_conf.get("password")
                    
                    st.info(f"Tentativo connessione a: {smtp_server}:{smtp_port} con utente: {email_address}")
                    
                    # 2. Connessione al Server
                    server = smtplib.SMTP(smtp_server, smtp_port)
                    st.write("✅ Connessione al server SMTP riuscita.")
                    
                    # 3. Avvio TLS
                    server.starttls()
                    st.write("✅ Canale sicuro (TLS) attivato.")
                    
                    # 4. Login
                    server.login(email_address, email_password)
                    st.success("🎉 LOGIN RIUSCITO! Password accettata. Il problema non sono le credenziali.")
                    server.quit()
                    
                except Exception as e:
                    st.error(f"❌ FALLITO: {e}")
                    st.write("Se l'errore è 'Username and Password not accepted', verifica l'App Password.")
            
            if st.button("📨 Invia Email di Prova ADESSO"):
                import smtplib
                # Nomi import per sicurezza, anche se già importati globalmente
                from email.mime.multipart import MIMEMultipart
                from email.mime.text import MIMEText
                from email.mime.application import MIMEApplication
                
                # 1. Recupero Configurazione (Copia esatta del test funzionante)
                email_conf = st.secrets.get("email")
                if not email_conf:
                    st.error("Configurazione email mancante.")
                    st.stop()
                    
                smtp_server = email_conf.get("smtp_server", "smtp.gmail.com")
                smtp_port = email_conf.get("smtp_port", 587)
                email_address = email_conf.get("address")
                email_password = email_conf.get("password")

                # 2. Recupero Destinatario dal menu a tendina
                if not selected_recipient_label: # Verifica che sia stato selezionato qualcuno
                    st.warning("Seleziona prima un destinatario dal menu in alto.")
                    st.stop()
                
                # Estraggo nome ed email dall'oggetto current_recipient
                selected_recipient_name = current_recipient.get('client_name')
                selected_recipient_email = current_recipient.get('target_email')
                    
                st.info(f"Avvio procedura per: {selected_recipient_name}...")

                try:
                    # 3. Generazione PDF (REALE - Usiamo la funzione esistente)
                    st.write("📄 Generazione PDF in corso...")
                    # Chiamiamo la funzione standard (senza custom_data)
                    # Per essere sicuri che includa dati, passiamo l'owner corrente
                    pdf_path = generate_pdf_report(recipient_id, owner=st.session_state['user'])
                    
                    if not pdf_path or not os.path.exists(pdf_path):
                        st.error("Errore: Il PDF non è stato generato (cerca di capire perché dai log sopra).")
                        st.stop()

                    # Leggi i bytes del PDF per MIMEApplication
                    with open(pdf_path, "rb") as f:
                        pdf_bytes = f.read()
                        
                    st.write(f"✅ PDF Generato: {os.path.basename(pdf_path)}")

                    # 4. Composizione Email
                    msg = MIMEMultipart()
                    msg['From'] = email_address
                    msg['To'] = selected_recipient_email 
                    msg['Subject'] = f"Report Prezzi - {selected_recipient_name}"
                    
                    body = "In allegato il report aggiornato dei prezzi."
                    msg.attach(MIMEText(body, 'plain'))
                    
                    # Allegato
                    part = MIMEApplication(pdf_bytes, Name=f"Report_{selected_recipient_name}.pdf")
                    part['Content-Disposition'] = f'attachment; filename="Report_{selected_recipient_name}.pdf"'
                    msg.attach(part)

                    # 5. Invio Effettivo
                    st.write(f"📤 Connessione a {smtp_server}...")
                    try:
                        server = smtplib.SMTP(smtp_server, smtp_port)
                        server.starttls()
                        server.login(email_address, email_password)
                        server.send_message(msg)
                        server.quit()
                        
                        st.success(f"🚀 EMAIL INVIATA con successo a {selected_recipient_email}!")
                        st.balloons()
                    except Exception as smtp_e:
                        st.error(f"❌ Errore SMTP: {smtp_e}")
                        
                except Exception as e:
                    st.error(f"❌ Errore Generico: {e}")
                    st.write("Dettaglio errore:", e)



