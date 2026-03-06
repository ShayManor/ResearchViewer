import duckdb
from datasets import load_dataset

conn = duckdb.connect('../data.db')
conn.execute("COPY papers TO 'papers.parquet' (FORMAT PARQUET)")
conn.execute("COPY authors TO 'authors.parquet' (FORMAT PARQUET)")
conn.close()

print("Pushing papers")
papers = load_dataset('parquet', data_files='papers.parquet', split='train')
papers.push_to_hub("ShayManor/Labeled-arXiv", config_name="papers")

print("Pushing authors")
authors = load_dataset('parquet', data_files='authors.parquet', split='train')
authors.push_to_hub("ShayManor/Labeled-arXiv", config_name="authors")
