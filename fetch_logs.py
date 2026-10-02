import requests
import zipfile
import io

repo = "RevanthN12/VisionGuard-Project"
runs_url = f"https://api.github.com/repos/{repo}/actions/runs?per_page=5"

res = requests.get(runs_url)
runs = res.json().get("workflow_runs", [])

failed_runs = [r for r in runs if r["conclusion"] == "failure"]
if not failed_runs:
    print("No failed runs found.")
    exit(0)

latest_failed = failed_runs[0]
print(f"Latest failed run: {latest_failed['id']}")

logs_url = latest_failed["logs_url"]
print(f"Fetching logs from {logs_url}...")

# Public repos allow downloading logs without auth, but let's check
log_res = requests.get(logs_url)
if log_res.status_code == 200:
    with zipfile.ZipFile(io.BytesIO(log_res.content)) as z:
        for filename in z.namelist():
            if "docker-build" in filename.lower() or "build" in filename.lower():
                print(f"--- {filename} ---")
                content = z.read(filename).decode("utf-8", errors="ignore")
                lines = content.splitlines()
                print("\n".join(lines[-100:])) # last 100 lines
else:
    print(f"Failed to download logs: {log_res.status_code}")
    print(log_res.text)
