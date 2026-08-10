import requests, time

r = requests.post("http://localhost:8000/api/video/analyze", json={"url": "https://www.instagram.com/reels/DawnK11ikdr/"})
print("Status:", r.status_code)
job_id = r.json()["analysis_id"]
print("Job:", job_id)

for i in range(20):
    time.sleep(10)
    s = requests.get(f"http://localhost:8000/api/video/analysis/{job_id}")
    data = s.json()
    print(f"[{i*10}s] status={data['status']} stage={data['stage']} error={data.get('error')}")
    if data["status"] in ("completed", "failed"):
        break
