from flask import Flask, render_template, request
import json, math, re
from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory

app = Flask(__name__)

# LOAD DATA
# menyimpan data berita di json
with open('berita.json', 'r', encoding='utf-8') as f:
    data_berita = json.load(f)

# STEMMER + STOPWORD
# untu
stemmer = StemmerFactory().create_stemmer()

stop_factory = StopWordRemoverFactory()
stopword = stop_factory.create_stop_word_remover()

# PREPROCESSING
def preprocessing(text):

    text = text.lower()

    # stopword removal
    text = stopword.remove(text)

    # tokenizing
    tokens = re.findall(r'\b\w+\b', text)

    # stemming
    return [stemmer.stem(t) for t in tokens]

# PREPARE BM25
documents = [d['konten'] for d in data_berita]

N = len(documents)

processed_docs = [preprocessing(doc) for doc in documents]

doc_lengths = [len(doc) for doc in processed_docs]

avgdl = sum(doc_lengths) / N if N > 0 else 0

# INVERTED INDEX
inverted_index = {}

for idx, tokens in enumerate(processed_docs):

    for token in set(tokens):

        inverted_index.setdefault(token, []).append(idx)

# BM25 FUNCTION
def get_bm25_score(query, k1=1.5, b=0.75):

    if not query:
        return [0] * N

    query_tokens = preprocessing(query)

    scores = [0] * N

    for token in query_tokens:

        if token in inverted_index:

            df_t = len(inverted_index[token])

            idf = math.log(
                (N - df_t + 0.5) / (df_t + 0.5) + 1
            )

            for idx in inverted_index[token]:

                tf = processed_docs[idx].count(token)

                num = tf * (k1 + 1)

                den = tf + k1 * (
                    1 - b + b * (doc_lengths[idx] / avgdl)
                )

                scores[idx] += idf * (num / den)

    return scores

# HOME
@app.route('/')
def index():

    return render_template('index.html')

# SEARCH
@app.route('/search', methods=['GET', 'POST'])
def search():

    if request.method == 'POST':

        query = request.form.get('query', '').strip()

    else:

        query = request.args.get('query', '').strip()

    scores = get_bm25_score(query)

    results = []

    for i, score in enumerate(scores):

        if score > 0:

            results.append({

                'id': data_berita[i]['id'],

                'judul': data_berita[i]['judul'],

                'konten': data_berita[i]['konten'],

                'link': data_berita[i]['link'],

                'skor': round(score, 2)

            })

    # ranking
    results = sorted(
        results,
        key=lambda x: x['skor'],
        reverse=True
    )

    return render_template(
        'results.html',
        results=results,
        query=query
    )

# DETAIL BM25 (REVISI DINAMIS)
@app.route('/detail/<int:id>')
def detail(id):
    # 1. Cari berita berdasarkan ID
    berita = None
    berita_idx = -1
    for idx, item in enumerate(data_berita):
        if item['id'] == id:
            berita = item
            berita_idx = idx
            break

    if berita is None:
        return "Berita tidak ditemukan"

    # 2. Ambil query dari parameter URL (?query=...)
    query = request.args.get('query', '').strip()
    
    # Nilai default jika query kosong atau tidak ada kata yang cocok
    tf_t = 0
    df_t = 0
    idf = 0.0
    skor = 0.0

    if query:
        query_tokens = preprocessing(query)
        doc_tokens = processed_docs[berita_idx]
        
        # Gunakan k1 dan b yang sama dengan saat pencarian
        k1 = 1.5
        b = 0.75
        
        # Di sini kita ambil token/kata pertama dari query untuk simulasi detail di UI
        # (Sebab di UI kamu saat ini hanya menyediakan satu kotak untuk TF, DF, dan IDF)
        if query_tokens:
            token = query_tokens[0] # Mengambil kata pertama dari hasil preprocessing query
            
            if token in inverted_index:
                # Hitung Document Frequency (DF) & IDF asli untuk kata tersebut
                df_t = len(inverted_index[token])
                idf = math.log((N - df_t + 0.5) / (df_t + 0.5) + 1)
                
                # Hitung Term Frequency (TF) asli di dalam dokumen ini
                tf_t = doc_tokens.count(token)
                
                if tf_t > 0:
                    num = tf_t * (k1 + 1)
                    den = tf_t + k1 * (1 - b + b * (doc_lengths[berita_idx] / avgdl))
                    skor = idf * (num / den)

    return render_template(
        'detail.html',
        berita=berita,
        query=query,
        tf=tf_t,
        df=df_t,
        idf=round(idf, 2),
        skor=round(skor, 2)
    )

# RUN APP
if __name__ == '__main__':

    app.run(debug=True)