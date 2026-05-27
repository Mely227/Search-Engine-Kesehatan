import requests
from bs4 import BeautifulSoup
import json
import time
import re
import os
from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory

# Inisialisasi Sastrawi
stemmer = StemmerFactory().create_stemmer()
stop_factory = StopWordRemoverFactory()
stopword = stop_factory.create_stop_word_remover()

def preprocessing_backend(text):
    if not text:
        return []
    text = text.lower()
    text = stopword.remove(text)
    tokens = re.findall(r'\b\w+\b', text)
    return [stemmer.stem(t) for t in tokens]

def load_existing_data():
    """Memuat data lama jika skrip pernah dijalankan sebelumnya (fitur cicil data)"""
    berita_raw = []
    berita_processed = []
    if os.path.exists('berita.json') and os.path.exists('berita_processed.json'):
        try:
            with open('berita.json', 'r', encoding='utf-8') as f:
                berita_raw = json.load(f)
            with open('berita_processed.json', 'r', encoding='utf-8') as f:
                berita_processed = json.load(f)
            print(f"🔄 Berhasil memuat {len(berita_raw)} data lama dari file lokal.")
        except Exception:
            print("⚠️ Gagal memuat data lama, memulai dari awal.")
    return berita_raw, berita_processed

def save_data(berita_raw, berita_processed):
    """Menyimpan data ke dalam JSON"""
    with open('berita.json', 'w', encoding='utf-8') as f:
        json.dump(berita_raw, f, ensure_ascii=False, indent=4)
    with open('berita_processed.json', 'w', encoding='utf-8') as f:
        json.dump(berita_processed, f, ensure_ascii=False, indent=4)
    print(f"💾 Data berhasil dicadangkan sementara. Total saat ini: {len(berita_raw)} berita.")

def scrape_multi_source(target_count=10000):
    berita_raw, berita_processed = load_existing_data()
    berita_id = len(berita_raw) + 1
    
    # Kumpulan kata kunci agar pencarian melimpah dan variatif
    keywords = ['kesehatan', 'penyakit', 'virus', 'obat', 'gejala', 'pandemi', 'dokter', 'rumahsakit', 'diet', 'jantung']
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    print(f"🚀 Memulai Mega-Scraping Kesehatan. Target: {target_count} berita.")

    for keyword in keywords:
        if len(berita_raw) >= target_count:
            break
            
        print(f"\n🔎 Beralih ke Kata Kunci: [{keyword.upper()}]")
        
        # Jalankan scraping untuk beberapa halaman per kata kunci
        for page in range(1, 150): 
            if len(berita_raw) >= target_count:
                break
                
            print(f"📄 Memproses Halaman {page} untuk kata kunci '{keyword}'... (Progress: {len(berita_raw)}/{target_count})")
            
            # --- SUMBER 1: DETIK HEALTH ---
            url_detik = f"https://www.detik.com/search/searchall?query={keyword}&sortby=time&page={page}"
            try:
                res = requests.get(url_detik, headers=headers, timeout=5)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, 'html.parser')
                    for article in soup.find_all('article'):
                        link_tag = article.find('a')
                        if link_tag and 'href' in link_tag.attrs:
                            url = link_tag['href']
                            # Filter ketat sub-domain kesehatan
                            if "health.detik.com" in url and not any(x in url for x in ["foto", "video", "infografis"]):
                                if any(b['link'] == url for b in berita_raw): continue
                                
                                # Tarik Konten Detail
                                det_res = requests.get(url, headers=headers, timeout=5)
                                det_soup = BeautifulSoup(det_res.text, 'html.parser')
                                title = det_soup.find('h1')
                                body = det_soup.find('div', class_='detail__body-text') or det_soup.find('div', class_='detail__text')
                                
                                if title and body:
                                    for s in body(['table', 'script', 'style', 'div']): s.decompose()
                                    txt_konten = " ".join(body.text.split())
                                    if len(txt_konten) > 150:
                                        berita_raw.append({"id": berita_id, "judul": title.text.strip(), "konten": txt_konten, "link": url})
                                        berita_processed.append(preprocessing_backend(txt_konten))
                                        print(f"✅ [DETIK] Berhasil #{berita_id}: {title.text.strip()[:40]}...")
                                        berita_id += 1
                                time.sleep(0.5)
            except Exception:
                pass

            # --- SUMBER 2: KOMPAS HEALTH ---
            url_kompas = f"https://search.kompas.com/search/?q={keyword}&page={page}"
            try:
                res = requests.get(url_kompas, headers=headers, timeout=5)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, 'html.parser')
                    # Kompas menggunakan komponen class 'article__link'
                    for a_tag in soup.find_all('a', class_='article__link'):
                        url = a_tag['href']
                        if "health.kompas.com" in url:
                            if any(b['link'] == url for b in berita_raw): continue
                            
                            det_res = requests.get(url, headers=headers, timeout=5)
                            det_soup = BeautifulSoup(det_res.text, 'html.parser')
                            title = det_soup.find('h1', class_='read__title')
                            body = det_soup.find('div', class_='read__content')
                            
                            if title and body:
                                for s in body(['table', 'script', 'style', 'div', 'aside']): s.decompose()
                                txt_konten = " ".join(body.text.split())
                                if len(txt_konten) > 150:
                                    berita_raw.append({"id": berita_id, "judul": title.text.strip(), "konten": txt_konten, "link": url})
                                    berita_processed.append(preprocessing_backend(txt_konten))
                                    print(f"✅ [KOMPAS] Berhasil #{berita_id}: {title.text.strip()[:40]}...")
                                    berita_id += 1
                            time.sleep(0.5)
            except Exception:
                pass

            # --- PROTEKSI DAN AUTO-SAVE SETIAP HALAMAN ---
            if page % 5 == 0:
                save_data(berita_raw, berita_processed)
                print("⏳ Istirahat 3 detik guna menghindari IP Banned...")
                time.sleep(3)

    # Simpan final data akhir
    save_data(berita_raw, berita_processed)
    print(f"\n🎉 Selesai! Berhasil mengumpulkan total {len(berita_raw)} berita kesehatan.")

if __name__ == '__main__':
    # Eksekusi dengan target 10.000 data
    scrape_multi_source(target_count=10000)