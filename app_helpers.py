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
    
    # 2. FALLBACK PAROLE CHIAVE (Priorità 2)
    # Prendi le prime 5 parole se non trovi un codice
    significant_words = [w for w in words if len(w) > 2]
    return " ".join(significant_words[:5])

# --- FOLDER HELPERS ---
def get_folders():
    # Nota: supabase deve essere passato o importato. 
    # Per semplicità, assumiamo che questi helper siano usati dove supabase è disponibile o li spostiamo in app.py
    # Ma dato che app.py è grande, meglio tenerli qui se possibile.
    # Tuttavia, app_helpers.py non ha l'oggetto supabase inizializzato.
    # Spostiamo questi helper direttamente in app.py per evitare problemi di dipendenze circolari o globali.
    pass

