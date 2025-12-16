from scraper import scrape_reference_site
import sys

# URL target (MondoIrrigazione)
url = "https://www.mondoirrigazione.it/4-centraline-e-programmatori"

print(f"Testing scraper on {url}...")
try:
    products = scrape_reference_site(url)
    print(f"\nTotal products found: {len(products)}")
    if products:
        print("First 3 products:")
        for p in products[:3]:
            print(p)
    else:
        print("No products found.")
except Exception as e:
    print(f"Error: {e}")
