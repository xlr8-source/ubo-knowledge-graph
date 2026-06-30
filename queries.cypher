// ============================================================
// queries.cypher – UBO Knowledge Graph: Reference Query Library
// ============================================================
// Run these in:
//   • Neo4j Browser (https://browser.neo4j.io)
//   • Neo4j Bloom (custom saved queries)
//   • neo4j-admin cypher-shell
//
// Replace parameter placeholders (e.g. $personName) with
// literal values when running interactively, e.g.:
//   WHERE o.name = "SMITH, John"
// ============================================================


// ────────────────────────────────────────────────────────────
// QUERY 1 – Find all companies where a person is officer or PSC
// ────────────────────────────────────────────────────────────
// Replace $personName with the exact name from the graph,
// e.g. "MUSK, Elon" (Companies House stores names SURNAME, Forename).
//
// Returns: company name, their role, and whether they appear
// as an Officer, PSC, or both.

MATCH (c:Company)
WHERE (c)-[:HAS_OFFICER]->(:Officer {name: $personName})
   OR (c)-[:HAS_PSC]->(:PSC {name: $personName})
OPTIONAL MATCH (c)-[:HAS_OFFICER]->(o:Officer {name: $personName})
OPTIONAL MATCH (c)-[:HAS_PSC]->(p:PSC {name: $personName})
RETURN
    c.company_number           AS company_number,
    c.name                     AS company_name,
    c.status                   AS status,
    o.role                     AS officer_role,
    o.appointed_date           AS officer_appointed,
    p.nature_of_control        AS psc_nature_of_control,
    CASE WHEN o IS NOT NULL AND p IS NOT NULL THEN "Officer + PSC"
         WHEN o IS NOT NULL THEN "Officer"
         ELSE "PSC"
    END AS relationship_type
ORDER BY company_name;


// ────────────────────────────────────────────────────────────
// QUERY 2 – Trace the full ownership chain for a company
// ────────────────────────────────────────────────────────────
// Uses variable-length paths to walk upstream through PSC links.
// A corporate PSC can itself be a Company in the graph – this
// query finds those chains up to 5 hops deep.
//
// NOTE: Companies House data links corporate PSCs by name only.
// The MATCH below works when the PSC name matches a Company name.

MATCH path = (start:Company {company_number: $companyNumber})
             -[:HAS_PSC*1..5]->(owner)
RETURN
    [node IN nodes(path) | coalesce(node.name, node.company_number)]
        AS ownership_chain,
    length(path)               AS chain_depth,
    labels(owner)[0]           AS owner_type,
    owner.name                 AS ultimate_owner_name,
    owner.nature_of_control    AS control_basis
ORDER BY chain_depth;


// ────────────────────────────────────────────────────────────
// QUERY 3 – Find companies with shared officers (connected companies)
// ────────────────────────────────────────────────────────────
// Detects "director networks" – pairs of companies that share
// at least one officer.  Useful for spotting beneficial ownership
// clusters and corporate families.

MATCH (c1:Company)-[:HAS_OFFICER]->(o:Officer)<-[:HAS_OFFICER]-(c2:Company)
WHERE c1.company_number < c2.company_number   // avoid duplicate pairs
RETURN
    c1.name                    AS company_a,
    c1.company_number          AS number_a,
    c2.name                    AS company_b,
    c2.company_number          AS number_b,
    collect(o.name)            AS shared_officers,
    count(o)                   AS shared_officer_count
ORDER BY shared_officer_count DESC
LIMIT 50;


// ────────────────────────────────────────────────────────────
// QUERY 4 – Find the Ultimate Beneficial Owner (UBO) of a company
// ────────────────────────────────────────────────────────────
// The UBO is the PSC at the end of the chain who is an individual
// (not a company / legal entity).  Walk all PSC hops; pick the
// last node that is a :PSC (individual) not a :Company.
//
// A PSC whose `kind` is "individual-person-with-significant-control"
// is a natural person – the true UBO.

MATCH path = (start:Company {company_number: $companyNumber})
             -[:HAS_PSC*1..10]->(ubo)
WHERE NOT (ubo)-[:HAS_PSC]->()          // leaf node = end of chain
RETURN
    start.name                 AS company,
    ubo.name                   AS ultimate_beneficial_owner,
    ubo.kind                   AS owner_kind,
    ubo.nature_of_control      AS how_they_control_it,
    ubo.nationality            AS nationality,
    ubo.country_of_residence   AS country_of_residence,
    length(path)               AS hops_from_company
ORDER BY hops_from_company;


// ────────────────────────────────────────────────────────────
// QUERY 5 – Neo4j Bloom visualisation query
// ────────────────────────────────────────────────────────────
// Returns a subgraph centred on one company that Bloom can render
// as an interactive graph.  The $companyName parameter is a
// case-insensitive substring match – perfect for Bloom search boxes.
//
// In Bloom: create a Search Phrase "Show ownership of {company}"
// and map $company → company_name parameter.

MATCH (c:Company)
WHERE toLower(c.name) CONTAINS toLower($companyName)
OPTIONAL MATCH (c)-[r1:HAS_OFFICER]->(o:Officer)
OPTIONAL MATCH (c)-[r2:HAS_PSC]->(p:PSC)
RETURN c, r1, o, r2, p
LIMIT 200;


// ────────────────────────────────────────────────────────────
// QUERY 6 – Database statistics dashboard
// ────────────────────────────────────────────────────────────
// Quick counts to verify your import worked and understand the
// shape of your knowledge graph.

MATCH (c:Company)  WITH count(c)  AS total_companies
MATCH (o:Officer)  WITH total_companies, count(o) AS total_officers
MATCH (p:PSC)      WITH total_companies, total_officers, count(p) AS total_pscs
MATCH ()-[r:HAS_OFFICER]->() WITH total_companies, total_officers, total_pscs,
                                   count(r) AS officer_relationships
MATCH ()-[r:HAS_PSC]->()
RETURN
    total_companies,
    total_officers,
    total_pscs,
    officer_relationships,
    count(r)                   AS psc_relationships,
    total_companies + total_officers + total_pscs AS total_nodes;


// ────────────────────────────────────────────────────────────
// BONUS QUERY – Most connected individuals (top directors)
// ────────────────────────────────────────────────────────────
// Find officers who sit on the most boards – often indicators
// of complex ownership structures.

MATCH (o:Officer)<-[:HAS_OFFICER]-(c:Company)
RETURN
    o.name                     AS officer_name,
    o.role                     AS role,
    count(distinct c)          AS number_of_companies,
    collect(c.name)[..5]       AS example_companies
ORDER BY number_of_companies DESC
LIMIT 20;


// ────────────────────────────────────────────────────────────
// BONUS QUERY – Companies with no registered PSC
// ────────────────────────────────────────────────────────────
// Companies with no PSC on record may indicate incomplete
// filings – a potential red flag in AML/KYC workflows.

MATCH (c:Company)
WHERE NOT (c)-[:HAS_PSC]->()
RETURN
    c.company_number,
    c.name,
    c.status,
    c.incorporation_date
ORDER BY c.incorporation_date DESC
LIMIT 50;
