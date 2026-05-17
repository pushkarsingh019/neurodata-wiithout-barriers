CREATE TABLE datasets (
  id TEXT PRIMARY KEY,
  name TEXT,
  latest_version TEXT,
  doi TEXT,
  species TEXT,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ,
  modified_at TIMESTAMPTZ,
  indexed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE dataset_versions (
  dataset_id TEXT REFERENCES datasets(id),
  tag TEXT NOT NULL,
  description JSONB NOT NULL DEFAULT '{}',
  readme TEXT,
  summary JSONB NOT NULL DEFAULT '{}',
  file_tree_hash TEXT,
  PRIMARY KEY (dataset_id, tag)
);

CREATE TABLE files (
  dataset_id TEXT NOT NULL,
  version_tag TEXT NOT NULL,
  path TEXT NOT NULL,
  openneuro_file_id TEXT,
  size_bytes BIGINT,
  directory BOOLEAN NOT NULL DEFAULT false,
  annexed BOOLEAN,
  modality TEXT,
  bids_entities JSONB NOT NULL DEFAULT '{}',
  PRIMARY KEY (dataset_id, version_tag, path)
);

CREATE TABLE paradigms (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT,
  ontology_refs JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE dataset_paradigms (
  dataset_id TEXT REFERENCES datasets(id),
  paradigm_id TEXT REFERENCES paradigms(id),
  confidence REAL NOT NULL,
  evidence JSONB NOT NULL DEFAULT '[]',
  PRIMARY KEY (dataset_id, paradigm_id)
);

CREATE TABLE papers (
  id TEXT PRIMARY KEY,
  doi TEXT,
  pubmed_id TEXT,
  semantic_scholar_id TEXT,
  arxiv_id TEXT,
  title TEXT,
  year INTEGER,
  metadata JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE dataset_papers (
  dataset_id TEXT REFERENCES datasets(id),
  paper_id TEXT REFERENCES papers(id),
  relationship TEXT NOT NULL,
  provenance JSONB NOT NULL DEFAULT '[]',
  PRIMARY KEY (dataset_id, paper_id, relationship)
);

CREATE TABLE embeddings (
  object_id TEXT NOT NULL,
  object_type TEXT NOT NULL,
  model TEXT NOT NULL,
  text_hash TEXT NOT NULL,
  embedding vector(1536),
  metadata JSONB NOT NULL DEFAULT '{}',
  indexed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (object_id, object_type, model)
);

CREATE TABLE metadata_quality_reports (
  dataset_id TEXT REFERENCES datasets(id),
  version_tag TEXT NOT NULL,
  score REAL NOT NULL,
  missing_fields JSONB NOT NULL DEFAULT '[]',
  warnings JSONB NOT NULL DEFAULT '[]',
  validator_output JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (dataset_id, version_tag)
);
