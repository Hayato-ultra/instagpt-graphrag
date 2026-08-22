import requests
d = requests.get("http://localhost:8000/api/graph/").json()
print(f"nodes: {len(d['nodes'])}, edges: {len(d['edges'])}")
for n in d["nodes"][:5]:
    print(f"  node: id={n['id'][:50]}, type={n['type']}, label={n['label']}")
print("---")
for e in d["edges"][:8]:
    print(f"  edge: src={e['source'][:50]}, tgt={e['target'][:50]}, type={e.get('type','?')}")

# Check if edge source/target match node ids
node_ids = {n["id"] for n in d["nodes"]}
broken = 0
for e in d["edges"]:
    if e["source"] not in node_ids:
        print(f"  BROKEN src: {e['source']}")
        broken += 1
    if e["target"] not in node_ids:
        print(f"  BROKEN tgt: {e['target']}")
        broken += 1
print(f"Broken: {broken}/{len(d['edges'])}")
