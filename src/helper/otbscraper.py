import requests
from bs4 import BeautifulSoup
import json
import re

def fetch_sitemap_links(sitemap_url):
    response = requests.get(sitemap_url)
    soup = BeautifulSoup(response.content, 'xml')
    links = [loc.text for loc in soup.find_all('loc') if '/en/product/' in loc.text]
    return links

def fetch_product_info(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    content = soup.find('div', {'id': 'Content'})
    if content:
        text = content.get_text()
        match = re.search(r'(\d+) electrodes', text, re.IGNORECASE)
        if match:
            return {
                'url': url,
                'product': soup.find('h1', {'class': 'product_title entry-title'}).text.strip() if soup.find('h1', {'class': 'product_title entry-title'}) else 'Unknown',
                'electrodes': int(match.group(1))
            }
    return None

def main():
    sitemap_url = "https://otbioelettronica.it/product-sitemap.xml"
    output_file = "../select_logic/otbioelettronica_products.json"

    print("Fetching sitemap links...")
    product_links = fetch_sitemap_links(sitemap_url)

    print(f"Found {len(product_links)} product links. Fetching product info...")
    products = []

    for link in product_links:
        print(f"Processing {link}...")
        product_info = fetch_product_info(link)
        if product_info:
            products.append(product_info)

    print(f"Saving {len(products)} products to {output_file}...")
    with open(output_file, 'w') as f:
        json.dump(products, f, indent=4)

    print("Done!")

if __name__ == "__main__":
    main()
