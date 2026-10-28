import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

types = ["Medical", "Fire", "Crime"]
type_counts = [660, 660, 660]

plt.figure(figsize=(6,4))
plt.bar(types, type_counts)
plt.title("Incident Type Distribution")
plt.ylabel("Number of Records")
plt.savefig("incident_type_distribution.png", dpi=300)
plt.close()

severity = ["Low", "High", "Critical"]
severity_counts = [660, 660, 660]

plt.figure(figsize=(6,4))
plt.bar(severity, severity_counts)
plt.title("Severity Distribution")
plt.ylabel("Number of Records")
plt.savefig("severity_distribution.png", dpi=300)
plt.close()

print("Charts created")