eva_buch/
├── .git/                        
├── .vscode/
│   └── settings.json 
├── config.py                       # global variables
├── data/  
│   |   ├── LP_DE_2026_1
├── keyword_search/   
│   ├── in/  
│   |   ├── keywords.txt
│   ├── out/  
│   |   ├── doc_word_counts.csv
│   |   ├── results.csv
│   |   ├── state_subject_count_matrix.csv
│   |   ├── term_count.csv
│   ├── src/ 
│   |   ├── keyword_search.py
├── lda_topic_modelling/  
│   ├── in/  
│   |   ├── exclude_list.txt
│   |   ├── keywords_topic_modelling.txt
│   ├── out/  
│   |   ├── ...   
│   ├── src/    
│   |   ├── lda_topic_model.py   
├── bertopic/     
│   ├── .bertopic-env/              # BERTopic environment
│   ├── cache/ 
│   |   ├── embeddings_all.npy
│   |   ├── umap2d_all.npy
│   ├── in/  
│   |   ├── keywords.txt
│   ├── out/  
│   |   ├── ...
│   ├── src/ 
│   |   ├── bertopic_pipeline.py
│   |   ├── utils.py
│   |   ├── viz_umap_2d.py
│   ├── requirements.in             # BERTopic environment  
│   ├── requirements.txt            # BERTopic environment  
├── .gitignore
├── environment.yaml                # Keyword search + LDA environment (conda)
├── requirements_2.txt              # Keyword search + LDA environment (pip)
├── LICENSE
├── README.md