"""Debug: check Qdrant payload schema."""
import json
import urllib.request

# Check first few points
data = json.dumps({"limit": 5, "with_payload": True, "with_vector": False}).encode()
req = urllib.request.Request(
    "http://localhost:6333/collections/knowledge_graph/points/scroll",
    data=data,
    headers={"Content-Type": "application/json"},
)
resp = urllib.request.urlopen(req)
result = json.loads(resp.read())

for pt in result["result"]["points"]:
    print(f"ID: {pt['id']}")
    print(f"  Keys: {list(pt['payload'].keys())}")
    print(f"  Type: {pt['payload'].get('type', 'MISSING')}")
    print(f"  Name: {pt['payload'].get('name', 'MISSING')}")
    print()

# Check if any points have type=entity
data2 = json.dumps({
    "filter": {"must": [{"key": "type", "match": {"value": "entity"}}]},
    "limit": 5,
    "with_payload": True,
    "with_vector": False,
}).encode()
req2 = urllib.request.Request(
    "http://localhost:6333/collections/knowledge_graph/points/scroll",
    data=data2,
    headers={"Content-Type": "application/json"},
)
resp2 = urllib.request.urlopen(req2)
result2 = json.loads(resp2.read())
print(f"Points with type=entity: {len(result2['result']['points'])}")

# Check what type values exist
data3 = json.dumps({
    "filter": {"must": [{"key": "type", "match": {"value": "chunk"}}]},
    "limit": 5,
    "with_payload": True,
    "with_vector": False,
}).encode()
req3 = urllib.request.Request(
    "http://localhost:6333/collections/knowledge_graph/points/scroll",
    data=data3,
    headers={"Content-Type": "application/json"},
)
resp3 = urllib.request.urlopen(req3)
result3 = json.loads(resp3.read())
print(f"Points with type=chunk: {len(result3['result']['points'])}")

# Check type=source
data4 = json.dumps({
    "filter": {"must": [{"key": "type", "match": {"value": "source"}}]},
    "limit": 5,
    "with_payload": True,
    "with_vector": False,
}).encode()
req4 = urllib.request.Request(
    "http://localhost:6333/collections/knowledge_graph/points/scroll",
    data=data4,
    headers={"Content-Type": "application/json"},
)
resp4 = urllib.request.urlopen(req4)
result4 = json.loads(resp4.read())
print(f"Points with type=source: {len(result4['result']['points'])}")
