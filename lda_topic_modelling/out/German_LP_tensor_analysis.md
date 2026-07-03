
## Part A: The Tensor Structure

Your data forms a 5-mode tensor **T** with dimensions:

```
T [ C × K × W × S × G ]

C = Concepts   (e.g., Mensch, Evolution, Verhalten, ...)     ~10–30 concepts
K = Topics     (1–10 per concept, non-shared across models)  ~10 per C
W = Terms      (top 10–30 per topic)                         ~20 per K
S = Subjects   (Biologie, Geographie, Ethik, ...)            ~8–15 subjects
G = States     (German Bundesländer)                         16 states
```

Each cell contains one or more of your three observed values: `corpus_freq`, `topic_freq`, `norm_prob`. This is not a dense tensor — it is **structurally sparse by design** because topics are concept-local (topic 3 in "Mensch" is not the same entity as topic 3 in "Evolution"). This sparsity is itself analytically meaningful, and the calculations below must respect it.

The **critical insight** before any calculation: topics and terms are the observed data; concepts, subjects, and states are the contextual metadata that conditions them. The information-theoretic measures flow *from* the (K, W) plane *upward* into the (C, S, G) structure.

---

## Part B: The Best Questions for This Space

---

### Level 1: The Term Layer (W within K within C)

**Q1.1 — Term concentration:** How evenly are the top terms distributed within a topic, and does this vary systematically across concepts, subjects, and states?
*This is an entropy question: H(W | K, C, S, G). High entropy = many terms roughly equal weight; low entropy = topic dominated by 1–2 terms.*

**Q1.2 — Term overlap across topics within a concept:** When two topics within the same concept model share terms, are those terms the concept name itself, generic pedagogical vocabulary, or genuinely substantive co-occurring terms?
*This is the within-concept topic similarity question. Shared high-lift terms signal genuine topical relatedness; shared low-lift terms signal only corpus noise.*

**Q1.3 — Cross-concept term recurrence (the "concept-as-term" question):** Which concept labels (Mensch, Evolution, Verhalten, etc.) appear as high-lift terms *inside the topics of other concept models*? Where they appear, in which topics and with what normalized probability?
*This is the empirical detection of conceptual co-occurrence: it tells you which concepts the curriculum actually links at the textual level, and whether those links are disciplinarily specific or universal.*

---

### Level 2: The Topic Layer (K within C, across S and G)

**Q2.1 — Topic prevalence variation across subjects:** Does the relative prevalence of each topic within a concept model vary significantly by subject? (e.g., does topic 4 of "Evolution" dominate in Biologie but nearly vanish in Geographie?)
*This is H(K | C, S): how much does subject membership predict which topic is active for a concept?*

**Q2.2 — Topic prevalence variation across states:** For a given concept × subject cell, do the 16 German states produce systematically different topic profiles?
*This is H(K | C, S, G): the geographic curriculum variation question. High entropy across states = high policy divergence; low entropy = national convergence despite federal structure.*

**Q2.3 — Topic stability as a measure of concept coherence:** Across the full C × S × G space, how consistently does a concept recruit the same topic profile? Concepts with high topic stability across subjects and states are strong candidates for "travelling concepts" in the OpenEvo sense — they have a coherent, transferable structure. Concepts with low stability are domain-locked.

---

### Level 3: The Concept Layer (C × C relationships, mediated by K and W)

**Q3.1 — Concept-level NMI via shared topic-term distributions:** For each pair of concepts (C₁, C₂), how similar are their topic-term distributions, measured across the full S × G space? This is the CMIT entry for this concept pair, estimated from your LDA outputs.

**Q3.2 — Asymmetric concept dependency (prerequisite strength):** For concept pairs with high NMI, which direction does the informational dependency run? Does knowing the topic profile of "Anpassung" substantially reduce uncertainty about the topic profile of "Evolution," or vice versa, or both?

**Q3.3 — Concept clustering structure:** Do concepts cluster into groups that share topic-term vocabulary, suggesting implicit disciplinary groupings that cross the concept labels? This reveals the actual latent structure of the curriculum as encoded in language, independently of how concepts are officially grouped.

---

### Level 4: The Subject and State Layers (S and G as conditioning variables)

**Q4.1 — Subject-state interaction:** Does the informativeness of subject identity (I(K ; S | C)) vary across states? Some states may have highly differentiated subject-specific concept treatments (high I); others may treat concepts uniformly across subjects (low I). This is a direct measure of curriculum specificity.

**Q4.2 — State-level curriculum entropy:** Across all concepts and subjects, which states produce the highest entropy topic profiles (most diverse, least predictable curriculum language) and which the lowest (most uniform, most constrained)?

**Q4.3 — Between-state NMI for a given concept × subject cell:** How similar are pairs of states in how they contextualize a specific concept within a specific subject? NMI close to 1 = near-identical curricular framing; NMI close to 0 = states are informationally independent in this cell.

---

### Level 5: Cross-cutting Structural Questions

**Q5.1 — Synergistic vs. redundant information across subjects for a concept:** For a target concept C and subject pair (S₁, S₂), how much information about C's topic profile is available only when *both* subjects are known jointly, versus from either alone? This is the partial information decomposition question and the strongest evidence for genuine interdisciplinary integration.

**Q5.2 — Concept-as-term cross-penetration score:** What fraction of concept C's top terms (by lift) appear in the top-term lists of other concept models, and with what average normalized probability? This produces a directed cross-penetration matrix: entry (Cᵢ → Cⱼ) = how much of Cᵢ's vocabulary shows up in Cⱼ's topics.

**Q5.3 — Federal curriculum divergence (KL divergence across states):** For each (C, S) cell, what is the average KL divergence between pairs of states' topic distributions? This is a more sensitive measure of divergence than NMI and preserves directionality — it can reveal which states are "outliers" relative to a national modal distribution.

---

## Part C: Specific Instructions for the NLP Specialist

### Data Preparation: Building the Distributional Objects

**Step 1: Construct the base distributions**

For each combination of (Concept C, Subject S, State G), you need a topic distribution vector:

```python
# For each (C, S, G) cell:
# - Filter the document-topic matrix (theta) to documents 
#   belonging to subject S and state G within concept model C
# - Average theta across those documents

theta_C_S_G = theta_C[  (doc_subject == S) & (doc_state == G)  ].mean(axis=0)
# Result: vector of length K (number of topics in concept C's model)
# Normalize to sum to 1 if not already
```

If a (C, S, G) cell has fewer than a minimum document threshold (suggest n ≥ 5), flag it as sparse and exclude from calculations or handle with Bayesian smoothing (add a small uniform prior α/K before normalizing).

**Step 2: Build the term-level distribution for each (C, K) pair**

From your topic_term_frequencies files:

```python
# For each (C, K):
phi_C_K = normalized_prob_column  # already in your files, sums to 1 over top-20 terms
# Store as dict: {term: norm_prob}
```

---

### Calculation Block 1: Term Entropy H(W | K, C)

```python
import numpy as np
from scipy.stats import entropy

def topic_term_entropy(phi_vec):
    """Shannon entropy of a normalized term probability vector."""
    phi = np.array([p for p in phi_vec if p > 0])
    return entropy(phi, base=2)

# For each (C, K):
H_W_given_K_C = {}
for concept in concepts:
    for topic_k in concept.topics:
        phi = phi_C_K[concept][topic_k]  # norm_prob values
        H_W_given_K_C[(concept, topic_k)] = topic_term_entropy(phi.values())
```

**Interpretation:** High H(W|K,C) means the topic is diffuse — many terms roughly equally weighted. Low H means the topic is "spiked" around 1–3 terms: highly specific. Compare across concepts: which concepts produce more or less concentrated topics? Compare across K: do early topics (higher prevalence) tend to be broader?

---

### Calculation Block 2: Concept-as-Term Cross-Penetration Matrix

```python
concept_labels = [c.lemmatized_label for c in concepts]
# e.g., ["mensch", "evolution", "verhalten", "anpassung", ...]

cross_penetration = np.zeros((len(concepts), len(concepts)))

for i, C_source in enumerate(concepts):
    for j, C_target in enumerate(concepts):
        if i == j:
            cross_penetration[i,j] = 1.0
            continue
        # Find the concept label of C_source in C_target's topic-term lists
        total_weight = 0.0
        for topic_k in C_target.topics:
            phi = phi_C_K[C_target][topic_k]
            if C_source.label in phi:
                # Weight by topic prevalence in C_target
                total_weight += prevalence[C_target][topic_k] * phi[C_source.label]
        cross_penetration[i,j] = total_weight
```

**Interpretation:** Entry (i,j) = the prevalence-weighted normalized probability of concept Cᵢ's label appearing as a term within concept Cⱼ's topic model. This is a **directed** matrix. High (i→j) but low (j→i) suggests Cᵢ is a contextual frame for understanding Cⱼ but not vice versa — a potential prerequisite signal at the linguistic level. The diagonal is 1 by definition (each concept's own label dominates its own topics). Off-diagonal values above ~0.02–0.05 are substantively meaningful given the top-20 term truncation.

---

### Calculation Block 3: Topic Distribution Entropy Across Subjects H(K | C, S)

```python
def topic_entropy(theta_vec):
    theta = np.array([p for p in theta_vec if p > 0])
    return entropy(theta / theta.sum(), base=2)

# Within-subject topic entropy for each (C, S):
H_K_given_C_S = {}
for C in concepts:
    for S in subjects:
        theta_vec = theta_C_S[C][S].mean(axis=0)  # mean over all docs in this C,S cell
        H_K_given_C_S[(C, S)] = topic_entropy(theta_vec)

# Marginal concept entropy (over all subjects):
H_K_given_C = {}
for C in concepts:
    theta_marginal = theta_C[C].mean(axis=0)
    H_K_given_C[C] = topic_entropy(theta_marginal)
```

Then compute **I(K ; S | C)**:

```python
def MI_topic_subject(C, subjects, theta_C_S, doc_counts_C_S):
    """Mutual information between topic and subject for concept C."""
    N_total = sum(doc_counts_C_S[C][S] for S in subjects)
    p_S = {S: doc_counts_C_S[C][S] / N_total for S in subjects}
    
    # Marginal topic distribution
    theta_marginal = sum(p_S[S] * theta_C_S[C][S].mean(axis=0) for S in subjects)
    H_K = entropy(theta_marginal, base=2)
    
    # Conditional topic entropy given subject
    H_K_given_S = sum(p_S[S] * topic_entropy(theta_C_S[C][S].mean(axis=0)) for S in subjects)
    
    return H_K - H_K_given_S  # = I(K ; S | C)
```

**Interpretation:** I(K ; S | C) answers: "How much does knowing the subject predict which topic is active for this concept?" Values near 0 = all subjects frame the concept identically. Values near H_K = subject is almost perfectly predictive of topic — complete disciplinary specialization. The ratio I(K;S|C) / H(K|C) gives a normalized version [0,1] analogous to NMI.

---

### Calculation Block 4: Between-State NMI for (C, S) Cells

```python
def NMI_states(theta_G1, theta_G2):
    """NMI between two topic distributions (for two states, same C and S)."""
    # Approximate MI from KL divergence and marginal entropy
    # Using the symmetric form: NMI = 2*I / (H1 + H2)
    H1 = entropy(theta_G1, base=2)
    H2 = entropy(theta_G2, base=2)
    theta_avg = (theta_G1 + theta_G2) / 2
    # MI approximated as H(avg) - 0.5*(H1 + H2)  [Jensen-Shannon basis]
    H_avg = entropy(theta_avg, base=2)
    MI_approx = H_avg - 0.5 * (H1 + H2)
    denom = 0.5 * (H1 + H2)
    return MI_approx / denom if denom > 0 else 0.0

# Build 16×16 NMI matrix for each (C, S) cell:
state_NMI = {}
for C in concepts:
    for S in subjects:
        mat = np.zeros((16, 16))
        for i, G1 in enumerate(states):
            for j, G2 in enumerate(states):
                theta_G1 = theta_C_S_G[C][S][G1]
                theta_G2 = theta_C_S_G[C][S][G2]
                mat[i,j] = NMI_states(theta_G1, theta_G2)
        state_NMI[(C,S)] = mat
```

**Note:** The Jensen-Shannon divergence basis used here for MI approximation is more numerically stable than the raw KL form when distributions may have zero entries, and produces the proper symmetric measure.

**Interpretation:** For each (C, S) cell, the 16×16 NMI matrix reveals whether Germany's federal structure produces genuinely different curricula (low off-diagonal NMI) or near-identical ones (high off-diagonal NMI) for this concept-subject combination. Cluster the states using hierarchical clustering on this matrix to reveal regional curriculum groupings (e.g., do former East vs. West German states cluster separately?).

---

### Calculation Block 5: Between-Concept NMI (Populating the CMIT)

```python
def concept_pair_NMI(C1, C2, subjects, states, theta_C_S_G, doc_counts):
    """
    NMI between two concept models, estimated from their 
    topic profiles across the shared S × G space.
    Uses Jensen-Shannon divergence as MI proxy.
    """
    js_values = []
    weights = []
    
    for S in subjects:
        for G in states:
            t1 = theta_C_S_G[C1][S][G]
            t2 = theta_C_S_G[C2][S][G]
            n = doc_counts[C1][S][G]  # use C1 doc count as weight
            if n < 5 or t1 is None or t2 is None:
                continue
            # Jensen-Shannon divergence approximates MI contribution
            avg = (t1 + t2) / 2
            js = entropy(avg, base=2) - 0.5*(entropy(t1,base=2) + entropy(t2,base=2))
            js_values.append(js)
            weights.append(n)
    
    # Weighted mean JS divergence as MI proxy
    if not weights:
        return np.nan
    MI_proxy = np.average(js_values, weights=weights)
    H1 = np.average([entropy(theta_C_S_G[C1][S][G],base=2) 
                     for S in subjects for G in states 
                     if doc_counts[C1][S][G] >= 5], 
                    weights=[doc_counts[C1][S][G] for S in subjects for G in states 
                             if doc_counts[C1][S][G] >= 5])
    H2 = np.average([entropy(theta_C_S_G[C2][S][G],base=2) ...], ...)
    return 2 * MI_proxy / (H1 + H2)  # symmetric NMI
```

**Interpretation:** This produces your **CMIT matrix** — an (n_concepts × n_concepts) symmetric matrix of NMI values. Values above 0.5 indicate strong conceptual co-embedding in the curriculum; values below 0.2 indicate near-independent treatment. Apply spectral clustering to recover the curriculum's latent knowledge modules. The eigenvectors of this matrix are your **Principal Information Components** — the abstract meta-concepts organizing the curriculum space.

---

### Calculation Block 6: KL Divergence for State Outlier Detection

```python
from scipy.special import kl_div

def state_KL_from_national(C, S, G_focal, theta_C_S_G, doc_counts):
    """KL divergence of one state's topic profile from the national mean."""
    # National mean (excluding focal state for unbiased comparison)
    other_states = [G for G in states if G != G_focal]
    weights = [doc_counts[C][S][G] for G in other_states]
    theta_national = np.average(
        [theta_C_S_G[C][S][G] for G in other_states], 
        weights=weights, axis=0)
    theta_focal = theta_C_S_G[C][S][G_focal]
    # Add small epsilon for numerical stability
    eps = 1e-10
    return np.sum(kl_div(theta_focal + eps, theta_national + eps))
```

**Interpretation:** For each (C, S, G) triple, this gives a scalar measuring how far a state's curriculum language deviates from the national modal treatment of that concept in that subject. Rank states by this score to identify systematic outliers — states that treat concepts unusually. High KL for many (C, S) cells = highly distinctive state curriculum policy; low KL across all cells = highly conforming state.

---

### Output Summary and Recommended Analysis Pipeline

The recommended order of operations for your NLP specialist is:

1. **Build theta_C_S_G** — the conditioned topic distributions for all tensor cells (flag sparse cells)
2. **Run Block 1** — term entropy per (C,K): characterize topic specificity
3. **Run Block 2** — cross-penetration matrix: identify conceptual co-occurrence structure
4. **Run Block 3** — I(K;S|C): measure subject-level disciplinary differentiation per concept
5. **Run Block 4** — state NMI matrices per (C,S): measure federal curriculum divergence
6. **Run Block 5** — concept-pair NMI (CMIT): recover curriculum knowledge graph
7. **Run Block 6** — state KL divergence: identify state-level outliers

The outputs feed directly into three deliverables: a **CMIT heatmap** (concept × concept NMI), a **state divergence profile** (state × concept KL scores), and a **subject differentiation profile** (I(K;S|C) per concept), which together constitute the core empirical Curriculum Information Graph for this corpus.