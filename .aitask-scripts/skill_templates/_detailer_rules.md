1. Be maximally specific. Instead of "create the database schema," write
   "create migrations/001_create_users.sql with columns: id (UUID PK),
   email (VARCHAR(255) UNIQUE NOT NULL), created_at (TIMESTAMPTZ DEFAULT
   NOW())."
2. Reference exact file paths from the codebase context. Do not invent paths
   that don't match the project's conventions.
3. Every assumption from the node's YAML must map to at least one
   verification step.
4. If the codebase context reveals patterns (naming conventions, directory
   structure, testing framework), follow them exactly.
5. Do not include architectural discussion — that belongs in the proposal.
   The plan is purely operational: what to do, in what order, how to verify.
