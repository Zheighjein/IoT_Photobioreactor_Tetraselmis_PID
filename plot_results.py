import pandas as pd
import matplotlib.pyplot as plt

# ========================
# LOAD DATA
# ========================
df_pid = pd.read_csv("pid_log.csv")
df_onoff = pd.read_csv("onoff_log.csv")

# ========================
# PLOT pH COMPARISON
# ========================
plt.figure()

plt.plot(df_pid["time"], df_pid["ph"], label="PID")
plt.plot(df_onoff["time"], df_onoff["ph"], label="ON/OFF")

# Plot setpoint (from PID file)
plt.plot(df_pid["time"], df_pid["setpoint"], linestyle="--", label="Setpoint")

plt.xlabel("Time (s)")
plt.ylabel("pH")
plt.title("PID vs ON/OFF pH Control Comparison")
plt.legend()
plt.grid()

plt.show()

# ========================
# CALCULATE IAE
# ========================
iae_pid = df_pid["error"].sum()
iae_onoff = df_onoff["error"].sum()

print("\n=== PERFORMANCE COMPARISON ===")
print(f"PID IAE: {iae_pid:.4f}")
print(f"ON/OFF IAE: {iae_onoff:.4f}")

# ========================
# ERROR PLOT
# ========================
plt.figure()

plt.plot(df_pid["time"], df_pid["error"], label="PID Error")
plt.plot(df_onoff["time"], df_onoff["error"], label="ON/OFF Error")

plt.xlabel("Time (s)")
plt.ylabel("Error")
plt.title("Error Comparison (PID vs ON/OFF)")
plt.legend()
plt.grid()

plt.show()