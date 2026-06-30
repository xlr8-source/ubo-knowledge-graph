# ============================================================
# network_analytics.py – Local NetworkX Graph Analytics Engine
# ============================================================
import logging
import networkx as nx
from importlib.util import find_spec
from neo4j import GraphDatabase
import config

logger = logging.getLogger(__name__)

class NetworkAnalyticsEngine:
    """
    Syncs the active Neo4j database into a local NetworkX graph 
    to calculate PageRank, Centralities, and Communities,
    bypassing AuraDB Free GDS library limitations.
    """
    def __init__(self, driver):
        self.driver = driver
        self.nx_graph = nx.Graph()    # Undirected for general centralities & communities
        self.nx_di_graph = nx.DiGraph() # Directed for PageRank/ownership flows
        
        self.pagerank_scores = {}
        self.degree_centrality_scores = {}
        self.betweenness_scores = {}
        self.closeness_scores = {}
        self.node_communities = {}
        self.metadata = {}  # Store display names, types, and labels for node IDs

    def sync_graph(self) -> bool:
        """
        Pull all nodes and relationships from Neo4j and build local NetworkX representations.
        """
        self.nx_graph.clear()
        self.nx_di_graph.clear()
        self.metadata.clear()
        
        try:
            with self.driver.session() as session:
                # 1. Fetch all companies
                companies = session.run("MATCH (c:Company) RETURN c.company_number AS cn, c.name AS name, c.status AS status")
                for record in companies:
                    node_id = f"co_{record['cn']}"
                    label = record['name'] or f"Company {record['cn']}"
                    self.metadata[node_id] = {
                        "name": label,
                        "type": "Company",
                        "company_number": record['cn'],
                        "status": record['status']
                    }
                    self.nx_graph.add_node(node_id)
                    self.nx_di_graph.add_node(node_id)
                
                # 2. Fetch all Officers
                officers = session.run("MATCH (o:Officer) RETURN o.name AS name, o.role AS role")
                for record in officers:
                    node_id = f"off_{record['name']}"
                    self.metadata[node_id] = {
                        "name": record['name'],
                        "type": "Officer",
                        "role": record['role']
                    }
                    self.nx_graph.add_node(node_id)
                    self.nx_di_graph.add_node(node_id)

                # 3. Fetch all PSCs
                pscs = session.run("MATCH (p:PSC) RETURN p.name AS name, p.nature_of_control AS noc")
                for record in pscs:
                    node_id = f"psc_{record['name']}"
                    self.metadata[node_id] = {
                        "name": record['name'],
                        "type": "PSC",
                        "nature_of_control": record['noc']
                    }
                    self.nx_graph.add_node(node_id)
                    self.nx_di_graph.add_node(node_id)
                
                # 4. Fetch all relationships
                # HAS_OFFICER: Company -> Officer
                rels_off = session.run("MATCH (c:Company)-[r:HAS_OFFICER]->(o:Officer) RETURN c.company_number AS cn, o.name AS name")
                for record in rels_off:
                    u = f"co_{record['cn']}"
                    v = f"off_{record['name']}"
                    if u in self.metadata and v in self.metadata:
                        self.nx_graph.add_edge(u, v, type="HAS_OFFICER")
                        self.nx_di_graph.add_edge(u, v, type="HAS_OFFICER")

                # HAS_PSC: Company -> PSC
                rels_psc = session.run("MATCH (c:Company)-[r:HAS_PSC]->(p:PSC) RETURN c.company_number AS cn, p.name AS name")
                for record in rels_psc:
                    u = f"co_{record['cn']}"
                    v = f"psc_{record['name']}"
                    if u in self.metadata and v in self.metadata:
                        self.nx_graph.add_edge(u, v, type="HAS_PSC")
                        # Control flows FROM owner (PSC) to target (Company)
                        self.nx_di_graph.add_edge(v, u, type="HAS_PSC")
            
            logger.info(f"Synchronised Graph: {self.nx_graph.number_of_nodes()} nodes, {self.nx_graph.number_of_edges()} edges.")
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync graph to NetworkX: {e}")
            return False

    def run_analytics(self):
        """
        Run fast local NetworkX algorithms on startup/sync.
        Slow centralities (betweenness, closeness) are deferred to on-demand compute.
        """
        if self.nx_graph.number_of_nodes() == 0:
            return

        # 1. Degree Centrality (extremely fast)
        self.degree_centrality_scores = nx.degree_centrality(self.nx_graph)

        # 2. PageRank (fast)
        self.compute_pagerank()

        # 3. Community Detection (Louvain modularity - fast)
        try:
            from networkx.algorithms.community import louvain_communities
            communities = louvain_communities(self.nx_graph)
            for cid, community_nodes in enumerate(communities):
                for node in community_nodes:
                    self.node_communities[node] = cid
        except Exception:
            try:
                from networkx.algorithms.community import greedy_modularity_communities
                communities = greedy_modularity_communities(self.nx_graph)
                for cid, community_nodes in enumerate(communities):
                    for node in community_nodes:
                        self.node_communities[node] = cid
            except Exception as e:
                logger.warning(f"Community detection failed, falling back to connected components: {e}")
                components = list(nx.connected_components(self.nx_graph))
                for cid, comp in enumerate(components):
                    for node in comp:
                        self.node_communities[node] = cid

    def compute_pagerank(self):
        if self.nx_di_graph.number_of_nodes() == 0:
            return
        try:
            # NetworkX 3.x pagerank automatically uses scipy if available, or falls back to Python.
            self.pagerank_scores = nx.pagerank(self.nx_di_graph, alpha=0.85)
        except Exception as e:
            logger.warning(f"PageRank computation failed, using uniform default: {e}")
            self.pagerank_scores = {node: 1.0/len(self.nx_di_graph) for node in self.nx_di_graph}

    def compute_betweenness(self):
        if self.nx_graph.number_of_nodes() == 0:
            return
        try:
            # Approximate betweenness centrality using random nodes sampling to speed up load time
            k_val = min(100, self.nx_graph.number_of_nodes())
            self.betweenness_scores = nx.betweenness_centrality(self.nx_graph, k=k_val)
        except Exception as e:
            logger.warning(f"Betweenness centrality calculation failed: {e}")
            self.betweenness_scores = {node: 0.0 for node in self.nx_graph}

    def compute_closeness(self):
        if self.nx_graph.number_of_nodes() == 0:
            return
        try:
            # Closeness centrality computed on-demand
            self.closeness_scores = nx.closeness_centrality(self.nx_graph)
        except Exception as e:
            logger.warning(f"Closeness centrality calculation failed: {e}")
            self.closeness_scores = {node: 0.0 for node in self.nx_graph}

    def get_ranked_nodes(self, metric: str = "pagerank", limit: int = 50) -> list[dict]:
        """
        Returns sorted list of nodes with calculated metrics.
        metrics: 'pagerank', 'degree', 'betweenness', 'closeness'
        """
        if metric == "pagerank":
            if not self.pagerank_scores:
                self.compute_pagerank()
            scores = self.pagerank_scores
        elif metric == "betweenness":
            if not self.betweenness_scores:
                self.compute_betweenness()
            scores = self.betweenness_scores
        elif metric == "closeness":
            if not self.closeness_scores:
                self.compute_closeness()
            scores = self.closeness_scores
        else:
            scores = self.degree_centrality_scores
            
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        results = []
        for node_id, score in ranked[:limit]:
            meta = self.metadata.get(node_id, {})
            if not meta:
                continue
            
            results.append({
                "node_id": node_id,
                "name": meta.get("name"),
                "type": meta.get("type"),
                "company_number": meta.get("company_number", ""),
                "status": meta.get("status", ""),
                "score_value": score,
                "community": self.node_communities.get(node_id, 0)
            })
            
        return results
