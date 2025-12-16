import requests
from bs4 import BeautifulSoup

url_home = "https://www.mondoirrigazione.it/"
url_target = "https://www.mondoirrigazione.it/4-centraline-e-programmatori"

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': 'https://www.google.com/',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}

print("Testing Session-based scraping...")
session = requests.Session()
session.headers.update(headers)

try:
    # 1. Visit Home to get cookies
    print(f"Visiting Home: {url_home}")
    resp_home = session.get(url_home, timeout=20)
    print(f"Home Status: {resp_home.status_code}")
    print(f"Cookies: {session.cookies.get_dict()}")
    
    # 2. Visit Target
    print(f"\nVisiting Target: {url_target}")
    resp_target = session.get(url_target, timeout=20)
    print(f"Target Status: {resp_target.status_code}")
    
    soup = BeautifulSoup(resp_target.content, 'html.parser')
    
    # Count products
    articles = soup.find_all(class_="product-miniature")
    print(f"Products found with Session: {len(articles)}")
    
    if len(articles) <= 1:
        print("Still finding <= 1 product.")
        # Check if there's a 'Load More' button or infinite scroll marker
        trigger = soup.find(class_="infinite-scroll-trigger")
        print(f"Infinite Scroll Trigger found: {bool(trigger)}")

except Exception as e:
    print(f"Error: {e}")
