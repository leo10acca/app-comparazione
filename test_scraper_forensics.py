import requests
from bs4 import BeautifulSoup
import re

url = "https://www.mondoirrigazione.it/4-centraline-e-programmatori"
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': 'https://www.google.com/'
}

print(f"Forensics on: {url}")
try:
    response = requests.get(url, headers=headers, timeout=20)
    print(f"Status Code: {response.status_code}")
    
    html_content = response.text
    
    # 2. ANALISI TESTUALE (Raw Count)
    count_miniature = html_content.count("product-miniature")
    count_article = html_content.count("<article")
    count_euro = html_content.count("€") + html_content.count("&euro;")
    
    print("\n--- RAW TEXT ANALYSIS ---")
    print(f"'product-miniature' count: {count_miniature}")
    print(f"'<article' count: {count_article}")
    print(f"'€' symbol count: {count_euro}")
    
    # 3. ANALISI STRUTTURALE (Soup)
    soup = BeautifulSoup(html_content, 'html.parser')
    
    print("\n--- SOUP ANALYSIS ---")
    
    # Cerca div con parola "products" nella classe
    products_divs = soup.find_all("div", class_=lambda x: x and "products" in x)
    print(f"Divs with 'products' in class: {len(products_divs)}")
    for i, div in enumerate(products_divs):
        print(f"  Div {i} classes: {div.get('class')}")
        # Count children
        children = div.find_all(recursive=False)
        print(f"  Div {i} direct children count: {len(children)}")
        
    # Count articles
    articles = soup.find_all('article')
    print(f"Total 'article' tags found: {len(articles)}")
    
    # Check specific ID
    js_list = soup.find(id="js-product-list")
    if js_list:
        print("Found #js-product-list")
        print(f"  #js-product-list children count: {len(js_list.find_all(recursive=False))}")
    else:
        print("NOT Found #js-product-list")

except Exception as e:
    print(f"Error: {e}")
