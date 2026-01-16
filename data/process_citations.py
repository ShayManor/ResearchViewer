import duckdb

conn = duckdb.connect('../data.db')
res = conn.execute('SELECT * FROM papers LIMIT 1;').fetchdf()
print(res)

