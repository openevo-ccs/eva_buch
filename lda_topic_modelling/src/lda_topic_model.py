
# Download spaCy language model
#!python -m spacy download en_core_web_sm


# Import libraries
import pandas as pd
import re
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
import pyLDAvis
import pyLDAvis.lda_model
import spacy
import os
import numpy as np
import pickle
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent)) 
print(sys.path[-1])
from config import RESULT_PATH, LDA_IN, LDA_OUT

OUT_DIR = LDA_OUT
KEYWORD_PATH = LDA_IN / "keywords_topic_modelling.txt"
DATA_PATH = RESULT_PATH
EXCLUDE_TERMS_PATH =  LDA_IN / "exclude_list.txt"

# Print confirmation message
print("All libraries successfully installed and imported!")

def load_data(file_path):
    """
    Load data from a CSV file.
    Assumes the text column is named 'text_excerpt' - adjust as needed.
    """
    df = pd.read_csv(file_path)
    return df

def get_excerpts(df, keyword=None):
    """
    Extract text excerpt belonging to a specific key word.
    Assumes the keyword column is named 'search_term' - adjust as needed.
    """
   
   # excerpts = list(df.loc[df["search_term"] == keyword, ["text_excerpt","subject"]])
    if keyword:
        excerpts = df.loc[df["search_term"] == keyword, ["text_excerpt", "state","school type","grade","year","subject"]].to_dict('records')
    else:
        excerpts = df[["text_excerpt", "state","school type","grade","year","subject"]].to_dict('records')
    
    if len(excerpts) != 0:
        print(f"{len(excerpts)} excerpts")
        return excerpts
    else:
        print("Keyword does not exist")
        return False

def preprocess_text(excerpts):
    """
    Preprocess text data: lowercase, remove special chars,
    remove stopwords, lemmatize using spaCy
    """
    # Load German language model
    nlp = spacy.load("de_core_news_sm")
    
    # Get German stopwords from spaCy
    stop_words = nlp.Defaults.stop_words

    with open(EXCLUDE_TERMS_PATH, "r") as f:
        content = f.read()
    exclude_terms = content.split(", ")
    print(f"{len(exclude_terms)} terms to exclude")
    
    processed_texts = []
    
    for item in excerpts:
        
        text = item['text_excerpt']
        
        if isinstance(text, str):
            # Remove special characters
            text = re.sub(r'[^a-zA-ZäöüÄÖÜßéèêëçñ\s]', '', text)
            
            # Process with spaCy
            doc = nlp(text)
            
            # Filter tokens: remove stopwords and short words, lemmatize and lowercase
            tokens = [token.lemma_.lower() for token in doc 
                      if token.text.lower() not in stop_words 
                      and token.lemma_.lower() not in exclude_terms
                      and token.text.lower() not in exclude_terms
                      and len(token.text) > 2]
            
            
            # Join tokens back to string
            processed_text = ' '.join(tokens)
            processed_texts.append(processed_text)
        else:
            processed_texts.append('')
            
    return processed_texts



# Create document-term matrix
def create_dtm(processed_texts, max_features=5000, min_df=5, max_df=.8):
    """
    Create document-term matrix using CountVectorizer
    """
    #print("Creating doc-term matrix")
    vectorizer = CountVectorizer(max_features=max_features, 
                                min_df=min_df,
                                max_df=max_df)
    dtm = vectorizer.fit_transform(processed_texts)
    
    return dtm, vectorizer


# Train LDA model
def train_lda(dtm, n_topics=10, random_state=42):
    """
    Train LDA model with specified number of topics
    """
    #print("Creating model")
    lda_model = LatentDirichletAllocation(n_components=n_topics,
                                          random_state=random_state,
                                          learning_method='online',
                                          max_iter=20)
    lda_output = lda_model.fit_transform(dtm)
    
    return lda_model, lda_output


# Display topics
def get_topic_terms(model, feature_names, keyword, n_top_words, n_topics, out_dir, dtm):
    """
    Display top words for each topic
    """
    topics = {}

    # Overall term frequency across all documents (i.e. all excerpts containing this keyword) and all topics
    overall_term_freq = np.asarray(dtm.sum(axis=0)).flatten()

    # Normalize model components to get estimated term frequency per topic
    # components_[i, j] = (expected count of word j in topic i) + α_prior => pseudo-counts (smoothed Bayesian estimates)
    # components_[i, j] = Given a topic i, how likey is word j: smoothed expected counts 
    
    topic_term_freq = model.components_ / model.components_.sum(axis=1, keepdims=True) #p(word | topic)
    
    topic_term_freq_out_dir = os.path.join(out_dir,"topic_term_frequencies")
    
    if not os.path.exists(topic_term_freq_out_dir):
        os.makedirs(topic_term_freq_out_dir)
        print(f"Folder created at {topic_term_freq_out_dir}")
    else:
        print(f"{topic_term_freq_out_dir} already exists")
    
    for topic_idx, topic in enumerate(model.components_):
        top_word_indices = topic.argsort()[:-n_top_words - 1:-1]

        topic_data = []
        for rank, i in enumerate(top_word_indices, start=1):
            topic_data.append({
                'rank': rank,
                'term': feature_names[i],
                'overall_term_freq_all_topics': overall_term_freq[i],
                'estimated_term_freq_within_topic_before_normalization': model.components_[topic_idx, i],
                'estimated_term_freq_within_topic': topic_term_freq[topic_idx, i]
            })
        
        topics[topic_idx] = [d['term'] for d in topic_data]
        
        # Save per-topic frequency data
        df_freq = pd.DataFrame(topic_data)
        df_freq.to_csv(f"{topic_term_freq_out_dir}/topic_term_freq_{keyword}_topic{topic_idx+1}_{n_topics}.csv", index=False)
        
    df = pd.DataFrame(topics)
    df.columns = [f"Topic_{i+1}" for i in range(len(topics))]
    df.index = [f"Term_{i+1}" for i in range(n_top_words)]
    print(f"\nTop terms per topic")
    #display(df)
    df.to_csv(f"{out_dir}/topic_terms_{keyword}_{n_topics}.csv", index=None)
    
    return topics

def get_document_topics(model, dtm, topic_terms, excerpts, keyword, n_top_topics, out_dir, n_topics):
    import pandas as pd
    # Get topic probabilities
    doc_topic_probs = model.transform(dtm)

    # Create long format DataFrame
    results = []
   
    top_topics_per_doc = []
    for doc_idx, doc_probs in enumerate(doc_topic_probs):
        top_topic_indices = doc_probs.argsort()[-n_top_topics:][::-1]
        top_topics_with_probs = [(idx, doc_probs[idx]) for idx in top_topic_indices]
        top_topics_per_doc.append(top_topics_with_probs)
        
    #     for rank, topic_idx in enumerate(top_topic_indices, 1):
    #         results.append({
    #             'document_id': doc_idx,
    #             'topic_rank': rank,
    #             'topic_id': topic_idx+1,
    #             'topic_probability': doc_probs[topic_idx],
    #             **excerpts[doc_idx],
    #         })
            

    # df_long = pd.DataFrame(results)
    # print(f"\nTop {n_top_topics} topics per document")
    # display(df_long.head(9))  # Shows first 3 documents
    # df_long.to_csv(f"{out_dir}/doc_topics_{keyword}.csv",index=None)

    # Print results
    # for doc_idx, topics in enumerate(top_topics_per_doc):
    #     print(f"Document {doc_idx}:")
    #     print(excerpts[doc_idx])
    #     for topic_idx, prob in topics:
    #         print(f"  Topic {topic_idx+1}: {prob:.3f} | {topic_terms[topic_idx][:5]}")


    # Summary
    results = []
    for doc_idx, doc_probs in enumerate(doc_topic_probs):
        top_topic_index = doc_probs.argmax()  # This is a single integer
        
        results.append({
            'document_id': doc_idx,
            'most_prevalent_topic_id': top_topic_index+1,  # Use the single index directly
            'most_prevalent_topic_probability': doc_probs[top_topic_index],
            **excerpts[doc_idx]
        })
    summary_df = pd.DataFrame(results)
    print(f"\nTop topic per document")
    #display(summary_df)
    summary_df.to_csv(f"{out_dir}/doc_top_topics_{keyword}_{n_topics}.csv",index=None)

    

# Create pyLDAvis visualization
def create_pyldavis(model, dtm, vectorizer, keyword, n_topics, out_dir):
    """
    Create interactive pyLDAvis visualization
    """
    print("Creating visualization")

    vis_data = pyLDAvis.lda_model.prepare(model, dtm, vectorizer, mds='tsne', sort_topics=False)
    
    out_path = f"{out_dir}/lda_vis_{keyword}_{n_topics}.html"
    pyLDAvis.save_html(vis_data, out_path)
    print(f"Saved at {out_path}")
    return vis_data

def get_stats(lda_model, dtm, keyword, out_dir):
    # Corpus-level stats
    n_documents = dtm.shape[0]
    n_terms = dtm.shape[1]
    n_tokens = int(dtm.sum())
    n_topics = lda_model.components_.shape[0]
    avg_doc_length = n_tokens / n_documents

    # Document-topic matrix (if not already computed)
    doc_topic_matrix = lda_model.transform(dtm)

    # Per-topic stats
    topic_prevalence = doc_topic_matrix.mean(axis=0)
    topic_prevalence_token_weighted = lda_model.components_.sum(axis=1) / lda_model.components_.sum()
    topic_coherence_proxy = lda_model.components_.max(axis=1) / lda_model.components_.mean(axis=1)  # peakiness
    n_docs_per_topic = (doc_topic_matrix.argmax(axis=1)[:, None] == np.arange(n_topics)).sum(axis=0)  # dominant topic count

    # Global summary
    global_summary = {
        "n_documents": int(n_documents),
        "n_terms": int(n_terms),
        "n_tokens": int(n_tokens),
        "n_topics": int(n_topics),
        "avg_doc_length": round(avg_doc_length, 1),
        "perplexity": round(lda_model.perplexity(dtm), 2),
        "log_likelihood": round(lda_model.score(dtm), 2),
    }

    # Per-topic summary
    topic_summary = pd.DataFrame({
        "topic_id": range(1, n_topics + 1),
        "topic_prevalence": topic_prevalence,
        "n_docs_where_dominant": n_docs_per_topic,
        "peakiness": topic_coherence_proxy,
    }).round(4).sort_values("topic_prevalence", ascending=False)
    topic_summary.insert(0, "topic_rank", range(1, n_topics + 1))

    stats_out_dir = os.path.join(out_dir,"stats")
    
    if not os.path.exists(stats_out_dir):
        os.makedirs(stats_out_dir)
        print(f"Folder created at {stats_out_dir}")
    else:
        print(f"{stats_out_dir} already exists")

    # Save to CSV
    global_summary_df = pd.Series(global_summary).reset_index().rename(columns={"index": "metric", 0: "value"})
    global_summary_df.to_csv(f"{stats_out_dir}/global_summary_{keyword}_{n_topics}.csv", index=False)
    topic_summary.to_csv(f"{stats_out_dir}/topic_summary_{keyword}_{n_topics}.csv", index=False)
    

def topic_model(df, out_dir, keyword=None, n_topics = 10, n_top_words=10, n_top_topics=3, max_df=.95, min_df=5):
    """
    Create topic model
    """
    print(f"Topic model for {keyword}")
    # Get excerpts
    excerpts = get_excerpts(df, keyword)
    # Preprocess text
    preprocessed = preprocess_text(excerpts)
    # Create document term matrix
    dtm, vectorizer = create_dtm(preprocessed, max_df=max_df, min_df=min_df)
    # Get feature names
    feature_names = vectorizer.get_feature_names_out()
    # Create LDA model
    lda_model, lda_output = train_lda(dtm, n_topics)
    # Get top terms per topic
   
    topic_terms = get_topic_terms(lda_model,feature_names,keyword,n_top_words, n_topics, out_dir, dtm)
    # Get top topics per document
    
    doc_topics = get_document_topics(lda_model, dtm, topic_terms, excerpts, keyword, n_top_topics, out_dir, n_topics)
    # Create visualization
    vis = create_pyldavis(lda_model, dtm, vectorizer, keyword, n_topics, out_dir)

    stats = get_stats(lda_model, dtm, keyword, out_dir)
    
    return topic_terms, lda_model, lda_output, dtm, excerpts, vis, feature_names

def load_keywords(keyword_path):
    with open(keyword_path, 'r') as f:
        keywords = f.readlines()
        keywords = [word.strip() for word in keywords]
    return keywords

def run_lda(keywords, result_df):
    
    #n_topics = 10 # Number of topics
    num_topics = [10]

    for keyword in keywords:
        if keyword != "Mensch":
            continue
        # if keyword in ["Rationalität", "Anpassung", "Bedürfnis"]:
        # out_dir_tm = os.path.join(OUT_DIR, keyword)
        # if not os.path.exists(out_dir_tm):
        #     os.makedirs(out_dir_tm)
        #     print(f"Folder created at {out_dir_tm}")
        # else:
        #     print(f"{OUT_DIR} already exists")
        # Topic model
        for n_topics in num_topics:
            
            out_dir_tm_n = OUT_DIR / keyword / str(n_topics)
            out_dir_tm_n.mkdir(parents=True, exist_ok=True)
            print(f"Folder created at {out_dir_tm_n}")
            
            topic_terms, lda_model, lda_output, dtm, excerpts, vis, feature_names = topic_model(
                result_df, 
                keyword=keyword, 
                out_dir=out_dir_tm_n,
                n_topics = n_topics, 
                n_top_words=20,
                n_top_topics=3,
                max_df=.8,
                min_df=5,
                )
                # feature_names_dict[keyword] = feature_names
                # topic_term_matrices[keyword] = lda_model.components_/lda_model.components_.sum(axis=1, keepdims=True)
                # document_topic_matrices[keyword] = lda_output

            # except:
            #     print("Could not find term")

    # Save dict of numpy arrays
    # np.savez(os.path.join(out_dir_models,"topic_term_matrices.npz"), **topic_term_matrices)
    # np.savez(os.path.join(out_dir_models,"document_topic_matrices.npz"), **document_topic_matrices)

    # # Save dict of np string arrays
    # with open(os.path.join(out_dir_models,"feature_names.pkl"), "wb") as f:
    #     pickle.dump(feature_names_dict, f)



def main():
    keywords = load_keywords(KEYWORD_PATH)
    result_df = load_data(DATA_PATH)
    run_lda(keywords, result_df)

if __name__ == "__main__":
    main()
