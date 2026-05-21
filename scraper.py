import requests
from bs4 import BeautifulSoup
import json
import time
import re
from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory

# Inisialisasi Sastrawi
stemmer = StemmerFactory().create_stemmer()
stop_factory = StopWordRemoverFactory()
stopword = stop_factory.create_stop_word_remover()

def preprocessing_backend(text):
    text = text.lower()
    text = stopword.remove(text)
    tokens = re.findall(r'\b\w+\b', text)
    return [stemmer.stem(t) for t in tokens]

def scrape_detik_health(target_count=500): # <-- Mengubah target kembali ke 500
    base_url = "https://www.detik.com/search/searchall"
    berita_raw = []
    berita_processed = []
    current_page = 1
    berita_id = 1

    print(f" Memulai scraping berita murni kesehatan... Target: {target_count} berita.")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    while len(berita_raw) < target_count:
        params = {
            'query': 'kesehatan',
            'sortby': 'time',
            'page': current_page
        }
        
        print(f"Mengambil data dari halaman indeks pencarian: {current_page}... (Total didapat: {len(berita_raw)}/{target_count})")
        
        try:
            response = requests.get(base_url, headers=headers, params=params)
            if response.status_code != 200:
                print(f"Gagal memuat halaman indeks {current_page}. Status: {response.status_code}. Mencoba halaman berikutnya...")
                current_page += 1
                time.sleep(3) 
                continue
                
            soup = BeautifulSoup(response.text, 'html.parser')
            articles = soup.find_all('article')
            
            if not articles:
                print("Tidak ada artikel lagi yang ditemukan di halaman indeks pencarian.")
                break

            for article in articles:
                if len(berita_raw) >= target_count:
                    break
                    
                link_tag = article.find('a')
                if not link_tag or 'href' not in link_tag.attrs:
                    continue
                    
                detail_url = link_tag['href']
                
                # --- FILTER KETAT: Hanya menerima tautan murni dari sub-domain health.detik.com ---
                if "health.detik.com" not in detail_url or "foto" in detail_url or "video" in detail_url:
                    continue
                
                try:
                    detail_response = requests.get(detail_url, headers=headers)
                    detail_soup = BeautifulSoup(detail_response.text, 'html.parser')
                    
                    title_tag = detail_soup.find('h1')
                    judul = title_tag.text.strip() if title_tag else None
                    
                    content_div = detail_soup.find('div', class_='detail__body-text') or detail_soup.find('div', class_='detail__text')
                    
                    if content_div:
                        for s in content_div(['table', 'script', 'style', 'div']):
                            s.decompose()
                        konten = " ".join(content_div.text.split())
                    else:
                        continue
                        
                    if judul and konten and len(konten) > 100:
                        if any(b['judul'] == judul for b in berita_raw):
                            continue
                            
                        berita_raw.append({
                            "id": berita_id,
                            "judul": judul,
                            "konten": konten,
                            "link": detail_url
                        })
                        
                        # Proses stemming Sastrawi
                        tokens_stemmed = preprocessing_backend(konten)
                        berita_processed.append(tokens_stemmed)
                        
                        print(f"[{len(berita_raw)}/{target_count}] Sukses + Stemming [HEALTH]: {judul[:40]}...")
                        berita_id += 1
                        
                        # Proteksi Anti-Blokir
                        if len(berita_raw) % 15 == 0:
                            print("Mengistirahatkan skrip sejenak agar IP aman...")
                            time.sleep(3.5)
                        else:
                            time.sleep(0.7)
                            
                except Exception:
                    continue
            
            current_page += 1
            
        except Exception as e:
            print(f"Error utama: {e}")
            break

    if berita_raw:
        with open('berita.json', 'w', encoding='utf-8') as f:
            json.dump(berita_raw, f, ensure_ascii=False, indent=4)
            
        with open('berita_processed.json', 'w', encoding='utf-8') as f:
            json.dump(berita_processed, f, ensure_ascii=False, indent=4)
            
        print(f"\n Luar biasa! Semua {len(berita_raw)} data berita murni kesehatan berhasil didapatkan dan disimpan.")
    else:
        print("\n Gagal mendapatkan berita. Silakan coba jalankan ulang skrip.")

if __name__ == '__main__':
    # Eksekusi langsung dengan target 500 berita murni kesehatan
    scrape_detik_health(target_count=500)