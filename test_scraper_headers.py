import requests
from bs4 import BeautifulSoup

url = "https://www.mondoirrigazione.it/4-centraline-e-programmatori"

# Hail Mary Headers: Mimic a real Chrome on macOS request exactly
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer': 'https://www.mondoirrigazione.it/',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
    'Cache-Control': 'max-age=0'
}

print(f"Testing Advanced Headers on: {url}")
try:
    session = requests.Session()
    response = session.get(url, headers=headers, timeout=20)
    print(f"Status Code: {response.status_code}")
    
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Count products
    articles = soup.find_all(class_="product-miniature")
    print(f"Products found: {len(articles)}")
    
    if len(articles) <= 1:
        print("Still finding <= 1 product.")

except Exception as e:
    print(f"Error: {e}")
