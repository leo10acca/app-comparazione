import requests

url = "https://www.mondoirrigazione.it/4-centraline-e-programmatori"
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': 'https://www.google.com/'
}

print(f"Deep Forensics on: {url}")
try:
    response = requests.get(url, headers=headers, timeout=20)
    html_content = response.text
    
    keyword = "product-miniature"
    count = html_content.count(keyword)
    print(f"Total occurrences of '{keyword}': {count}")
    
    start_index = 0
    for i in range(count):
        index = html_content.find(keyword, start_index)
        if index != -1:
            # Print surrounding context
            context_start = max(0, index - 50)
            context_end = min(len(html_content), index + 100)
            print(f"\n--- Occurrence {i+1} at index {index} ---")
            print(html_content[context_start:context_end])
            start_index = index + len(keyword)

except Exception as e:
    print(f"Error: {e}")
