
**Explanation of output files and metrics**

For each search term and each num_topics, you will find:

- **topic_term_frequencies**: contains the term frequencies for the top 20 terms for each topic

    *Columns*

    - overall_term_freq_all_topics: term frequency count across the entire ‘corpus’ (i.e. all ecxerpts containing that search term); it corresponds to the blue bar in the pyLDAvis visualization

    - estimated_term_freq_within_topic_before_normalization: the expected count of a the term within that topic; it is directly taken from the topic-term-matrix, which contains the term distribution over each topic; it is a (smoothed) Bayesian estimate, not an actual count; it corresponds to the red bar in the pyLDAvis visualization; this is what the order of the terms depends on

    - estimated_term_freq_within_topic: the estimated term frequency after normalization; it can be interpreted as the probability of "drawing" that term given that topic based on the term distribtution over that topic

- **stats** contains:

    - *global_summary*: 
        - number of documents, terms, tokens in the keyword corpus; 
        - perplexity and log_likelihood are the standard model fit metrics — lower perplexity and higher log likelihood indicate a better fitting model

    - *topic_summary*: 
        - prevalence_by_docs: topic prevalence is the column mean of the document-topic matrix; i.e. the average proportion of each topic across all documents
        - n_docs_where_dominant: number of documents for which this topic is the most prevalent
        - peakiness: how concentrated the topic is; low peakiness means the topic is more diffuse/vague, high peakiness means a few words stand out

- **doc_top_topics** contains: most prevalent topic with topic probability for each document

- **topic_terms** contains: list of top 20 terms for all topics
