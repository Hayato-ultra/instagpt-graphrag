import csv
import json
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()


class GraphExporter:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            auth=(
                os.getenv("NEO4J_USER", "neo4j"),
                os.getenv("NEO4J_PASSWORD", "password"),
            ),
        )

    def close(self):
        self.driver.close()

    def export_reel_json(self, reel_id: str) -> dict:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (r:Reel {id: $reel_id})
                OPTIONAL MATCH (r)-[rel]->(n)
                RETURN r AS reel,
                       collect(DISTINCT {
                           type: type(rel),
                           target_id: elementId(n),
                           target_labels: labels(n),
                           target_props: properties(n)
                       }) AS relationships
                """,
                reel_id=reel_id,
            )
            record = result.single()
            if not record:
                return {}

            reel_props = dict(record["reel"])
            relationships = record["relationships"]

            nodes = [{"id": reel_props.get("id"), "labels": ["Reel"], "properties": reel_props}]
            rel_list = []

            seen_nodes = {reel_props.get("id")}

            for rel in relationships:
                node_id = rel["target_id"]
                node_labels = rel["target_labels"]
                node_props = rel["target_props"]

                if node_id not in seen_nodes:
                    nodes.append({"id": node_id, "labels": node_labels, "properties": node_props})
                    seen_nodes.add(node_id)

                rel_list.append({
                    "source": reel_props.get("id"),
                    "target": node_id,
                    "type": rel["type"],
                })

            return {"reel_id": reel_id, "nodes": nodes, "relationships": rel_list}

    def export_reel_csv(self, reel_id: str, output_dir: str = "exports") -> dict:
        os.makedirs(output_dir, exist_ok=True)

        data = self.export_reel_json(reel_id)
        if not data:
            return {"error": "Reel not found"}

        nodes_file = os.path.join(output_dir, f"{reel_id}_nodes.csv")
        rels_file = os.path.join(output_dir, f"{reel_id}_relationships.csv")

        with open(nodes_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "labels", "properties"])
            for node in data["nodes"]:
                writer.writerow([
                    node["id"],
                    "|".join(node["labels"]),
                    json.dumps(node["properties"]),
                ])

        with open(rels_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["source", "target", "type"])
            for rel in data["relationships"]:
                writer.writerow([rel["source"], rel["target"], rel["type"]])

        return {"nodes_file": nodes_file, "relationships_file": rels_file}

    def export_full_graph_json(self) -> dict:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (n)
                OPTIONAL MATCH (n)-[r]->(m)
                RETURN collect(DISTINCT {
                    id: elementId(n),
                    labels: labels(n),
                    properties: properties(n)
                }) AS nodes,
                collect(DISTINCT {
                    source: elementId(n),
                    target: elementId(m),
                    type: type(r)
                }) AS relationships
                """
            )
            record = result.single()
            return {
                "nodes": record["nodes"],
                "relationships": [r for r in record["relationships"] if r["target"]],
            }

    def export_full_graph_csv(self, output_dir: str = "exports") -> dict:
        os.makedirs(output_dir, exist_ok=True)

        data = self.export_full_graph_json()

        nodes_file = os.path.join(output_dir, "all_nodes.csv")
        rels_file = os.path.join(output_dir, "all_relationships.csv")

        with open(nodes_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "labels", "properties"])
            for node in data["nodes"]:
                writer.writerow([
                    node["id"],
                    "|".join(node["labels"]),
                    json.dumps(node["properties"]),
                ])

        with open(rels_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["source", "target", "type"])
            for rel in data["relationships"]:
                writer.writerow([rel["source"], rel["target"], rel["type"]])

        return {"nodes_file": nodes_file, "relationships_file": rels_file}
