import sqlite3
conn = sqlite3.connect('database.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('All tables:', tables)

for table in [t[0] for t in tables]:
    cursor.execute(f"PRAGMA table_info({table})")
    cols = cursor.fetchall()
    print(f'{table} columns:', cols)

conn.close()