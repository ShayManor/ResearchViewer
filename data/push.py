import duckdb
from datasets import Dataset, DatasetDict

conn = duckdb.connect('../data.db')
papers_df = conn.execute("SELECT * FROM papers").df()
authors_df = conn.execute("SELECT * FROM authors").df()
conn.close()

# Create dataset with both tables
dataset = DatasetDict({
    'papers': Dataset.from_pandas(papers_df),
    'authors': Dataset.from_pandas(authors_df)
})

dataset.push_to_hub("ShayManor/Labeled-arXiv")
