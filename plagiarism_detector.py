import string
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re

def clean_text(text):
    text = text.lower()
    text = re.sub(r'\d+', '', text)
    text = text.translate(str.maketrans('', '', string.punctuation))
    return text

def check_plagiarism(user_text, source_documents):
    if not user_text:
        return []

    documents = [user_text] + source_documents
    cleaned_documents = [clean_text(doc) for doc in documents]

    if len(cleaned_documents) < 2:
        return []

    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(cleaned_documents)

    user_vector = tfidf_matrix[0:1]
    similarity_scores = cosine_similarity(user_vector, tfidf_matrix[1:])

    results = []
    for i, score in enumerate(similarity_scores[0]):
        results.append({
            'source': source_documents[i],
            'similarity': f"{score * 100:.2f}%"
        })
    
    return results