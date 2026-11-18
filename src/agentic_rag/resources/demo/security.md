# Security
All production API requests require a verified identity token. A principal has a tenant ID, user ID, roles, and groups. Tenant isolation is enforced before retrieval and after citation selection. Agent tools require server-side permission checks. Write operations require explicit human approval. Prompt injection in retrieved documents never becomes system instruction.
