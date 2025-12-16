import toml
from supabase import create_client
from scraper import scrape_reference_site

# Load secrets
secrets = toml.load(".streamlit/secrets.toml")
url = secrets["supabase"]["url"]
key = secrets["supabase"]["key"]

supabase = create_client(url, key)

print("Clearing existing products...")
try:
    supabase.table("products").delete().neq("id", 0).execute()
except Exception as e:
    print(f"Error clearing table: {e}")

print("Starting scraper...")
# Target URL for pagination test (category with multiple pages if possible, or just the one requested)
# User suggested: "https://www.irrigarden-bo.it/2-home"
target_url = "https://shop.irrigarden-bo.it/2-home"
products = scrape_reference_site(target_url)

print(f"Scraping finished. Found {len(products)} products.")

if products:
    print("Saving to Supabase...")
    count = 0
    # Insert in batches to avoid issues if list is huge, though 100-200 is fine in one go usually.
    # Supabase might have a limit per request.
    
    # Let's insert one by one or in small batches to be safe and handle duplicates if any (though we cleared)
    for p in products:
        try:
            supabase.table("products").insert({
                "codice": p["codice"],
                "categoria": p["categoria"],
                "descrizione": p["descrizione"],
                "marchio": p["marchio"],
                "prezzo": p["prezzo"]
            }).execute()
            count += 1
        except Exception as e:
            print(f"Error inserting product {p['descrizione']}: {e}")
            
    print(f"Successfully saved {count} products.")
else:
    print("No products to save.")
