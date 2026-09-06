-- CaseFill-AI SQLite Schema
-- Core tables for users, cases, documents, and cross-checks

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- Users table (all account types: admin, fso, family)
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    cnic TEXT UNIQUE NOT NULL,  -- 13-digit format: XXXXX-XXXXXXX-X
    phone TEXT,
    email TEXT,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'fso', 'family')),
    account_type TEXT NOT NULL CHECK(account_type IN ('official', 'family')),
    designation TEXT,
    badge TEXT,
    fso_id TEXT,  -- Links to fsos table if role='fso'
    assigned_region_ids TEXT,  -- JSON array of region IDs
    area_address TEXT,
    city TEXT,
    assigned_region_id TEXT,  -- For family accounts
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- FSO (Field Support Officer) roster
CREATE TABLE IF NOT EXISTS fsos (
    id TEXT PRIMARY KEY,  -- FSO-PK-NNN
    user_id TEXT,
    name TEXT NOT NULL,
    cnic TEXT,
    email TEXT,
    phone TEXT,
    badge TEXT,
    assigned_region_ids TEXT,  -- JSON array
    active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- Regions (operational clusters)
CREATE TABLE IF NOT EXISTS regions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    urdu_name TEXT,
    assigned_fso_id TEXT,
    keywords TEXT,  -- JSON array of location keywords
    active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (assigned_fso_id) REFERENCES fsos(id) ON DELETE SET NULL
);

-- Session tokens for authentication
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Cases (main case records)
CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY,
    case_number TEXT UNIQUE NOT NULL,  -- OFSP-YYYY-NNNN
    status TEXT NOT NULL CHECK(status IN ('draft', 'pending_verification', 'flagged', 'verified', 'rejected', 'unassigned')),
    submission_source TEXT,
    family_id TEXT,
    region_id TEXT,
    assigned_fso_id TEXT,
    routing_confidence REAL,
    routing_reason TEXT,
    created_by_user_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    submitted_at TEXT,
    last_altered_at TEXT,
    alteration_count INTEGER DEFAULT 0,
    alteration_reason TEXT,
    verified_at TEXT,
    verified_by_fso_id TEXT,
    fso_review_notes TEXT,
    flag_reason TEXT,
    compiled_json TEXT,  -- Full CompiledCaseRecord snapshot
    child_crc TEXT,  -- Denormalized for duplicate detection
    mother_cnic TEXT,  -- Denormalized for duplicate detection
    father_cnic TEXT,  -- Denormalized for duplicate detection
    intake_duration_seconds REAL,
    average_confidence REAL,
    donor_arranged INTEGER NOT NULL DEFAULT 0,  -- Yes/No donor status (FSO controlled only)
    aid_transfer_log TEXT NOT NULL DEFAULT '[]',  -- JSON list of {date, amount} entries (FSO controlled only)
    child_user_id TEXT,  -- Linked read-only child login user
    child_username TEXT,  -- Child's B-Form/CNIC registration number used as username
    child_password TEXT,  -- Generated password, shown on the child's profile screen
    child_login_generated_at TEXT,
    submitted_by_fso_id TEXT,  -- FSO who submitted the case (attribution)
    FOREIGN KEY (family_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (region_id) REFERENCES regions(id) ON DELETE SET NULL,
    FOREIGN KEY (assigned_fso_id) REFERENCES fsos(id) ON DELETE SET NULL
);

-- Indexes for duplicate detection
CREATE INDEX IF NOT EXISTS idx_cases_child_crc ON cases(child_crc);
CREATE INDEX IF NOT EXISTS idx_cases_mother_cnic ON cases(mother_cnic);
CREATE INDEX IF NOT EXISTS idx_cases_father_cnic ON cases(father_cnic);
CREATE INDEX IF NOT EXISTS idx_cases_region_id ON cases(region_id);
CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
CREATE INDEX IF NOT EXISTS idx_cases_family_id ON cases(family_id);
CREATE INDEX IF NOT EXISTS idx_cases_assigned_fso_id ON cases(assigned_fso_id);

-- Case documents (6 image types + 2 text slots)
CREATE TABLE IF NOT EXISTS case_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    doc_type TEXT NOT NULL CHECK(doc_type IN ('child_picture', 'result_card', 'b_form', 'death_certificate', 'mother_cnic', 'father_cnic', 'address', 'mother_education')),
    status TEXT NOT NULL CHECK(status IN ('empty', 'uploading', 'extracting', 'done', 'error', 'not_provided')),
    file_path TEXT,
    original_filename TEXT,
    extracted_json TEXT,
    manual_edits_json TEXT,
    not_provided_reason TEXT,
    extracted_at TEXT,
    extraction_ms INTEGER,
    model TEXT,
    FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE,
    UNIQUE(case_id, doc_type)
);

-- Cross-check audit log
CREATE TABLE IF NOT EXISTS cross_check_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    results_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
);
