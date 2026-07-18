from pathlib import Path

root = Path(__file__).resolve().parent
files = [
    ('keyword_search/out/results.csv', 'docs/data/results.csv'),
    ('keyword_search/out/doc_word_counts.csv', 'docs/data/doc_word_counts.csv'),
    ('keyword_search/out/state_subject_count_matrix.csv', 'docs/data/state_subject_count_matrix.csv')
]
for src, dst in files:
    srcp = root / src
    dstp = root / dst
    dstp.parent.mkdir(parents=True, exist_ok=True)
    dstp.write_bytes(srcp.read_bytes())
    print('copied', src, '->', dst)

lda_root = root / 'lda_topic_modelling' / 'out'
for concept_dir in sorted([d for d in lda_root.iterdir() if d.is_dir()], key=lambda x: x.name):
    src_file = concept_dir / '10' / f'topic_terms_{concept_dir.name}_10.csv'
    if src_file.exists():
        dst_file = root / 'docs' / 'data' / 'lda' / concept_dir.name / '10' / src_file.name
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        dst_file.write_bytes(src_file.read_bytes())
        print('copied LDA', src_file, '->', dst_file)
    else:
        print('missing LDA file', src_file)
