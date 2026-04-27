import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

conn = sqlite3.connect("database/db.py")

df = pd.read_sql_query("SELECT * FROM readings", conn)

# pH graph
plt.plot(df["timestamp"], df["ph"])
plt.xlabel("Time")
plt.ylabel("pH")
plt.title("pH vs Time")
plt.show()


#===== WILL NEED TO FIX THIS ======#