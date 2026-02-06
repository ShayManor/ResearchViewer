import duckdb
from datasets import load_dataset, DatasetDict

conn = duckdb.connect('../data.db')
conn.execute("COPY papers TO 'papers.parquet' (FORMAT PARQUET)")
conn.execute("COPY authors TO 'authors.parquet' (FORMAT PARQUET)")
conn.close()
print("Loading parquet")
conn.execute("""
    COPY (SELECT * FROM papers) 
    TO 'papers' 
    (FORMAT PARQUET, PARTITION_BY (year), ROW_GROUP_SIZE 100000)
""")

papers = load_dataset('parquet', data_files='papers/**/*.parquet', split='train')
authors = load_dataset('parquet', data_files='authors.parquet', split='train')

dataset = DatasetDict({
    'papers': papers,
    'authors': authors
})
print("Pushing")
dataset.push_to_hub("ShayManor/Labeled-arXiv")
