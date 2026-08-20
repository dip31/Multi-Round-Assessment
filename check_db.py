import sqlite3
conn = sqlite3.connect('database.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%proctor%'")
tables = cursor.fetchall()
print('Proctoring tables:', tables)

cursor.execute("PRAGMA table_info(advanced_proctoring_events)")
cols = cursor.fetchall()
print('advanced_proctoring_events columns:', cols)

cursor.execute("PRAGMA table_info(proctoring_events)")
cols2 = cursor.fetchall()
print('proctoring_events columns:', cols2)

conn.close()