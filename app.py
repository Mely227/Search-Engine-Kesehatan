from flask import Flask, render_template, request
import json, math, re, os
from collections import Counter
from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory

app = Flask(__name__)

# AMANKAN PROSES LOAD DATA (Mencegah Crash jika file belum ada)
data_berita = []
processed_docs = []

if os.path.exists('berita.json') and os.path.exists('berita_processed.json'):
    try:
        with open('berita.json', 'r', encoding='utf-8') as f:
            data_berita = json.load(f)
        with open('berita_processed.json', 'r', encoding='utf-8') as f:
            processed_docs = json.load(f)
    except Exception as e:
        print(f"⚠️ Gagal membaca JSON (mungkin file rusak/kosong): {e}")
else:
    print("⚠️ File berita.json atau berita_processed.json TIDAK DITEMUKAN!")
    print("Silakan jalankan scraper.py terlebih dahulu sampai selesai.")

# STEMMER + STOPWORD
stemmer = StemmerFactory().create_stemmer()
stop_factory = StopWordRemoverFactory()
stopword = stop_factory.create_stop_word_remover()

def preprocessing(text):
    if not text:
        return []
    text = text.lower()
    text = stopword.remove(text)
    tokens = re.findall(r'\b\w+\b', text)
    return [stemmer.stem(t) for t in tokens]

# PREPARE BM25 VARIABLES
N = len(data_berita)
doc_lengths = [len(doc) for doc in processed_docs]
avgdl = sum(doc_lengths) / N if N > 0 else 0

# INVERTED INDEX
inverted_index = {}
for idx, tokens in enumerate(processed_docs):
    for token in set(tokens):
        inverted_index.setdefault(token, []).append(idx)

# BM25 FUNCTION
def get_bm25_score(query, k1=1.5, b=0.75):
    if not query or N == 0:
        return [0] * max(1, N)

    query_tokens = preprocessing(query)
    scores = [0] * N

    for token in query_tokens:
        if token in inverted_index:
            df_t = len(inverted_index[token])
            idf = math.log((N - df_t + 0.5) / (df_t + 0.5) + 1)

            for idx in inverted_index[token]:
                tf = processed_docs[idx].count(token)
                num = tf * (k1 + 1)
                den = tf + k1 * (1 - b + b * (doc_lengths[idx] / avgdl))
                scores[idx] += idf * (num / den)
    return scores

# HOME
@app.route('/')
def index():
    return render_template('index.html')

# SEARCH
@app.route('/search', methods=['GET', 'POST'])
def search():
    query = request.form.get('query', '').strip() if request.method == 'POST' else request.args.get('query', '').strip()

    if N == 0:
        return render_template('results.html', results=[], query=query)

    scores = get_bm25_score(query)
    results = []

    for i, score in enumerate(scores):
        if score > 0 and i < len(data_berita):
            results.append({
                'id': data_berita[i]['id'],
                'judul': data_berita[i]['judul'],
                'konten': data_berita[i]['konten'],
                'link': data_berita[i]['link'],
                'skor': round(score, 2)
            })

    results = sorted(results, key=lambda x: x['skor'], reverse=True)
    return render_template('results.html', results=results, query=query)

# DETAIL BM25 & COSINE SIMILARITY
@app.route('/detail/<int:id>')
def detail(id):
    berita = None
    berita_idx = -1
    for idx, item in enumerate(data_berita):
        if item['id'] == id:
            berita = item
            berita_idx = idx
            break

    if berita is None:
        return "Berita tidak ditemukan"

    query = request.args.get('query', '').strip()
    
    # Inisialisasi Variabel BM25
    tf_t, df_t, idf_bm25, skor_bm25 = 0, 0, 0.0, 0.0
    
    # Inisialisasi Variabel Cosine Similarity
    tf_q_cosine, tf_d_cosine, idf_cosine = 0, 0, 0.0
    dot_product, normalisasi, skor_cosine = 0.0, 0.0, 0.0

    if query and berita_idx < len(processed_docs):
        query_tokens = preprocessing(query)
        doc_tokens = processed_docs[berita_idx]
        
        # 1. PERHITUNGAN METRIK BM25 (Eksisting)
        k1, b = 1.5, 0.75
        if query_tokens:
            token = query_tokens[0] # Mengambil kata pertama query untuk visualisasi tabel
            if token in inverted_index:
                df_t = len(inverted_index[token])
                idf_bm25 = math.log((N - df_t + 0.5) / (df_t + 0.5) + 1)
                tf_t = doc_tokens.count(token)
                
                if tf_t > 0 and avgdl > 0:
                    num = tf_t * (k1 + 1)
                    den = tf_t + k1 * (1 - b + b * (doc_lengths[berita_idx] / avgdl))
                    skor_bm25 = idf_bm25 * (num / den)

        # 2. PERHITUNGAN METRIK COSINE SIMILARITY (Tambahan Baru)
        if query_tokens and len(doc_tokens) > 0:
            # Hitung frekuensi kata unik gabungan untuk pembentukan ruang vektor
            unique_words = set(query_tokens + doc_tokens)
            
            counts_query = Counter(query_tokens)
            counts_doc = Counter(doc_tokens)
            
            # Ambil perwakilan 1 kata kunci teratas untuk visualisasi ringkas komponen di tabel HTML
            target_token = query_tokens[0]
            tf_q_cosine = counts_query[target_token]
            tf_d_cosine = counts_doc[target_token]
            
            # Hitung IDF Standar untuk Cosine Model Vektor: log(N / df)
            if target_token in inverted_index:
                df_c = len(inverted_index[target_token])
                idf_cosine = math.log(N / df_c) if df_c > 0 else 0.0
            
            # Proses hitung vektor TF-IDF menyeluruh untuk Cosine Similarity
            vec_query = []
            vec_doc = []
            
            for word in unique_words:
                # Menggunakan indeks frekuensi dokumen untuk menghitung bobot IDF kata terkait
                df_w = len(inverted_index[word]) if word in inverted_index else 0
                word_idf = math.log(N / df_w) if df_w > 0 else 0.0
                
                vec_query.append(counts_query[word] * word_idf)
                vec_doc.append(counts_doc[word] * word_idf)
            
            # Rumus matematika dot product & magnitude ruang vektor
            dot_product = sum(q * d for q, d in zip(vec_query, vec_doc))
            magnitude_q = math.sqrt(sum(q**2 for q in vec_query))
            magnitude_d = math.sqrt(sum(d**2 for d in vec_doc))
            
            normalisasi = magnitude_q * magnitude_d
            if normalisasi > 0:
                skor_cosine = dot_product / normalisasi

    return render_template(
        'detail.html',
        berita=berita,
        query=query,
        
        # Variabel Parameter BM25
        tf=tf_t,
        df=df_t,
        idf=round(idf_bm25, 2),
        skor=round(skor_bm25, 2),
        dl=doc_lengths[berita_idx] if berita_idx < len(doc_lengths) else 0,
        avdl=round(avgdl, 2),
        
        # Variabel Parameter Cosine Similarity Baru
        tf_q_cosine=tf_q_cosine,
        tf_d_cosine=tf_d_cosine,
        idf_cosine=round(idf_cosine, 2),
        dot_product=round(dot_product, 2),
        normalisasi=round(normalisasi, 2),
        skor_cosine=round(skor_cosine, 2)
    )

if __name__ == '__main__':
    app.run(debug=True)