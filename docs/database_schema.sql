-- Proposed SQLite schema. Apply to a NEW database, not data/app.db.
-- All connections must enable foreign_keys. No existing application tables are changed.
PRAGMA foreign_keys = ON;
BEGIN;

CREATE TABLE data_sources (
    source_id TEXT NOT NULL PRIMARY KEY,
    name TEXT NOT NULL,
    provider TEXT NOT NULL,
    source_kind TEXT NOT NULL CHECK(source_kind IN ('api','official_file','official_page','operator_page','derived','synthetic')),
    public_url TEXT,
    note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE ingestion_runs (
    run_id TEXT NOT NULL PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES data_sources,
    collected_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('complete','partial','failed','running','probe','synthetic')),
    request_scope_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(request_scope_json)),
    -- Request scope must never contain serviceKey, tokens or credentials.
    note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE source_files (
    file_id TEXT NOT NULL PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES ingestion_runs,
    relative_path TEXT NOT NULL,
    sha256 TEXT NOT NULL CHECK(length(sha256)=64),
    format TEXT NOT NULL,
    public_url TEXT,
    source_published_at TEXT,
    UNIQUE(run_id,relative_path)
);
CREATE TABLE raw_records (
    record_id TEXT NOT NULL PRIMARY KEY,
    file_id TEXT NOT NULL REFERENCES source_files,
    locator TEXT NOT NULL, -- e.g. 대전!A67:F67 or /response/body/items/item/0
    external_id TEXT,
    payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
    UNIQUE(file_id,locator)
);

CREATE TABLE regions (
    region_id TEXT NOT NULL PRIMARY KEY,
    name TEXT NOT NULL,
    level TEXT NOT NULL CHECK(level IN ('country','sido','sigungu')),
    parent_region_id TEXT REFERENCES regions
);
CREATE TABLE region_codes (
    code_system TEXT NOT NULL, -- visitor_admin, tour_area, tour_sigungu, legal_dong
    code TEXT NOT NULL,
    parent_code TEXT NOT NULL DEFAULT '', -- sigungu code is only unique within area
    valid_from TEXT NOT NULL,
    valid_to TEXT,
    region_id TEXT NOT NULL REFERENCES regions,
    evidence_record_id TEXT REFERENCES raw_records,
    PRIMARY KEY(code_system,code,parent_code,valid_from),
    CHECK(valid_to IS NULL OR valid_to>valid_from)
);
CREATE TABLE visitor_daily (
    run_id TEXT NOT NULL REFERENCES ingestion_runs,
    region_id TEXT NOT NULL REFERENCES regions,
    base_date TEXT NOT NULL CHECK(length(base_date)=10),
    visitor_type_code TEXT NOT NULL,
    visitor_type_name TEXT NOT NULL,
    visitor_value NUMERIC NOT NULL CHECK(visitor_value>=0),
    source_record_id TEXT NOT NULL REFERENCES raw_records,
    PRIMARY KEY(run_id,region_id,base_date,visitor_type_code)
);
CREATE TABLE regional_monthly_metrics (
    metric_id TEXT NOT NULL PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES ingestion_runs,
    region_id TEXT NOT NULL REFERENCES regions,
    month TEXT NOT NULL CHECK(length(month)=7),
    visitor_type_code TEXT NOT NULL,
    visitors NUMERIC CHECK(visitors>=0),
    overnight_pct REAL CHECK(overnight_pct BETWEEN 0 AND 100),
    observed_days INTEGER NOT NULL CHECK(observed_days BETWEEN 0 AND 31),
    expected_days INTEGER NOT NULL CHECK(expected_days BETWEEN 28 AND 31),
    coverage_status TEXT NOT NULL CHECK(coverage_status IN ('complete','incomplete','missing')),
    UNIQUE(run_id,region_id,month,visitor_type_code),
    CHECK(observed_days<=expected_days),
    CHECK(coverage_status<>'complete' OR (observed_days=expected_days AND visitors IS NOT NULL))
);
CREATE TABLE monthly_metric_inputs (
    metric_id TEXT NOT NULL REFERENCES regional_monthly_metrics,
    record_id TEXT NOT NULL REFERENCES raw_records,
    role TEXT NOT NULL CHECK(role IN ('visitor','overnight','coverage')),
    PRIMARY KEY(metric_id,record_id,role)
);

CREATE TABLE venues (
    venue_id TEXT NOT NULL PRIMARY KEY,
    name TEXT NOT NULL,
    address TEXT NOT NULL,
    region_id TEXT REFERENCES regions,
    latitude REAL CHECK(latitude BETWEEN -90 AND 90),
    longitude REAL CHECK(longitude BETWEEN -180 AND 180),
    location_record_id TEXT REFERENCES raw_records,
    official_url TEXT,
    phone TEXT,
    review_status TEXT NOT NULL DEFAULT 'pending' CHECK(review_status IN ('pending','reviewed','conflict','rejected')),
    CHECK((latitude IS NULL)=(longitude IS NULL))
);
CREATE TABLE venue_source_keys (
    source_id TEXT NOT NULL REFERENCES data_sources,
    external_id TEXT NOT NULL,
    venue_id TEXT NOT NULL REFERENCES venues,
    evidence_record_id TEXT NOT NULL REFERENCES raw_records,
    PRIMARY KEY(source_id,external_id)
    -- Registry row numbers belong to snapshots, never use them as permanent venue IDs.
);
CREATE TABLE food_registrations (
    registration_id TEXT NOT NULL PRIMARY KEY,
    venue_id TEXT NOT NULL REFERENCES venues,
    source_record_id TEXT NOT NULL UNIQUE REFERENCES raw_records,
    registry_as_of TEXT NOT NULL,
    source_row_number INTEGER NOT NULL,
    licensing_authority_raw TEXT,
    licensing_authority_resolved TEXT,
    resolution_note TEXT,
    business_type TEXT NOT NULL,
    source_note TEXT,
    -- Multiple licenses can refer to one venue: 콩월 is registered under two types.
    CHECK(licensing_authority_resolved IS NULL OR licensing_authority_raw IS NOT NULL OR resolution_note IS NOT NULL)
);
CREATE TABLE offerings (
    offering_id TEXT NOT NULL PRIMARY KEY,
    venue_id TEXT NOT NULL REFERENCES venues,
    name TEXT NOT NULL,
    category TEXT NOT NULL CHECK(category IN ('lodging','restaurant','activity')),
    scope_type TEXT NOT NULL CHECK(scope_type IN ('room','space','program','unresolved')),
    participation_mode TEXT NOT NULL DEFAULT 'unknown' CHECK(participation_mode IN ('dog_participates','accompany','unknown')),
    serves_meals INTEGER CHECK(serves_meals IN (0,1)),
    recurring INTEGER CHECK(recurring IN (0,1)),
    duration_minutes INTEGER CHECK(duration_minutes>0),
    checkin_minute INTEGER CHECK(checkin_minute BETWEEN 0 AND 1439),
    checkout_minute INTEGER CHECK(checkout_minute BETWEEN 0 AND 1439),
    enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1)),
    evidence_record_id TEXT REFERENCES raw_records,
    note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE pet_policy_versions (
    policy_id TEXT NOT NULL PRIMARY KEY,
    offering_id TEXT NOT NULL REFERENCES offerings,
    checked_at TEXT NOT NULL,
    effective_from TEXT, -- publication/check date is NOT necessarily the effective date
    effective_to TEXT,   -- exclusive
    is_current INTEGER NOT NULL DEFAULT 1 CHECK(is_current IN (0,1)),
    review_status TEXT NOT NULL CHECK(review_status IN ('pending','partial','verified','conflict','rejected')),
    pet_allowed INTEGER CHECK(pet_allowed IN (0,1)), -- NULL unknown, 0 explicitly forbidden
    dogs_limit_state TEXT NOT NULL DEFAULT 'unknown' CHECK(dogs_limit_state IN ('unknown','limited','unlimited')),
    max_dogs INTEGER,
    weight_limit_state TEXT NOT NULL DEFAULT 'unknown' CHECK(weight_limit_state IN ('unknown','limited','unlimited')),
    max_weight_kg REAL,
    weight_operator TEXT CHECK(weight_operator IN ('lt','lte')),
    note TEXT NOT NULL DEFAULT '',
    CHECK((dogs_limit_state='limited' AND max_dogs IS NOT NULL AND max_dogs>=1) OR (dogs_limit_state<>'limited' AND max_dogs IS NULL)),
    CHECK((weight_limit_state='limited' AND max_weight_kg IS NOT NULL AND max_weight_kg>0 AND weight_operator IS NOT NULL) OR (weight_limit_state<>'limited' AND max_weight_kg IS NULL AND weight_operator IS NULL)),
    CHECK(effective_to IS NULL OR effective_from IS NULL OR effective_to>effective_from)
);
CREATE UNIQUE INDEX one_current_policy ON pet_policy_versions(offering_id) WHERE is_current=1;
CREATE TABLE policy_evidence (
    policy_id TEXT NOT NULL REFERENCES pet_policy_versions,
    record_id TEXT NOT NULL REFERENCES raw_records,
    supports_field TEXT NOT NULL, -- pet_allowed, max_dogs, scope, etc.
    evidence_summary TEXT NOT NULL,
    PRIMARY KEY(policy_id,record_id,supports_field)
);
CREATE TABLE policy_conditions (
    condition_id TEXT NOT NULL PRIMARY KEY,
    policy_id TEXT NOT NULL REFERENCES pet_policy_versions,
    condition_type TEXT NOT NULL CHECK(condition_type IN ('height_cm','breed','vaccination','registration','age_months','leash','diaper','reservation','resident_priority','other')),
    operator TEXT CHECK(operator IN ('lt','lte','gt','gte','eq','in','not_in','required')),
    value_json TEXT NOT NULL CHECK(json_valid(value_json)),
    unit TEXT,
    enforcement TEXT NOT NULL CHECK(enforcement IN ('machine','manual','informational')),
    summary TEXT NOT NULL,
    evidence_record_id TEXT NOT NULL REFERENCES raw_records
);
CREATE TABLE opening_hours (
    hours_id TEXT NOT NULL PRIMARY KEY,
    offering_id TEXT NOT NULL REFERENCES offerings,
    weekday INTEGER NOT NULL CHECK(weekday BETWEEN 0 AND 6), -- Monday=0
    season_start_mmdd TEXT NOT NULL DEFAULT '01-01',
    season_end_mmdd TEXT NOT NULL DEFAULT '12-31',
    opens_minute INTEGER NOT NULL CHECK(opens_minute BETWEEN 0 AND 1439),
    closes_minute INTEGER NOT NULL CHECK(closes_minute BETWEEN 1 AND 1440),
    last_entry_minute INTEGER CHECK(last_entry_minute BETWEEN 0 AND 1440),
    evidence_record_id TEXT NOT NULL REFERENCES raw_records,
    CHECK(opens_minute<closes_minute),
    CHECK(last_entry_minute IS NULL OR last_entry_minute BETWEEN opens_minute AND closes_minute)
    -- Split lunch/dinner and overnight windows. Winter Oct-Mar uses two seasonal rows.
);
CREATE TABLE schedule_exceptions (
    exception_id TEXT NOT NULL PRIMARY KEY,
    offering_id TEXT NOT NULL REFERENCES offerings,
    starts_at TEXT NOT NULL, -- local Asia/Seoul ISO datetime
    ends_at TEXT NOT NULL,   -- exclusive
    exception_type TEXT NOT NULL CHECK(exception_type IN ('closed','session','changed_hours')),
    capacity_dogs INTEGER CHECK(capacity_dogs>=0),
    booking_url TEXT,
    note TEXT NOT NULL,
    evidence_record_id TEXT NOT NULL REFERENCES raw_records,
    CHECK(ends_at>starts_at)
    -- capacity_dogs is session capacity, never the per-party max_dogs.
);
CREATE TABLE review_issues (
    issue_id TEXT NOT NULL PRIMARY KEY,
    venue_id TEXT REFERENCES venues,
    offering_id TEXT REFERENCES offerings,
    record_id TEXT REFERENCES raw_records,
    field_name TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','resolved','rejected')),
    opened_at TEXT NOT NULL,
    resolution_record_id TEXT REFERENCES raw_records,
    CHECK(venue_id IS NOT NULL OR offering_id IS NOT NULL OR record_id IS NOT NULL),
    CHECK(status<>'resolved' OR resolution_record_id IS NOT NULL)
);

CREATE TABLE analysis_runs (
    analysis_id TEXT NOT NULL PRIMARY KEY,
    analysis_type TEXT NOT NULL CHECK(analysis_type IN ('demand','pet_supply')),
    start_month TEXT NOT NULL,
    end_month TEXT NOT NULL,
    created_at TEXT NOT NULL,
    parameters_json TEXT NOT NULL CHECK(json_valid(parameters_json)),
    input_files_json TEXT NOT NULL CHECK(json_valid(input_files_json)), -- [{file_id,sha256}]
    code_version TEXT NOT NULL,
    CHECK(end_month>=start_month)
);
CREATE TABLE analysis_region_results (
    analysis_id TEXT NOT NULL REFERENCES analysis_runs,
    region_id TEXT NOT NULL REFERENCES regions,
    metric_name TEXT NOT NULL, -- score_base, shortage_index, rank_base, counts, etc.
    metric_value NUMERIC,
    value_status TEXT NOT NULL CHECK(value_status IN ('observed','no_registered_facility','missing')),
    PRIMARY KEY(analysis_id,region_id,metric_name),
    CHECK(value_status<>'missing' OR metric_value IS NULL)
);
CREATE TABLE analysis_facility_memberships (
    analysis_id TEXT NOT NULL REFERENCES analysis_runs,
    venue_id TEXT NOT NULL REFERENCES venues,
    source_record_id TEXT NOT NULL REFERENCES raw_records,
    assigned_region_id TEXT REFERENCES regions,
    category TEXT NOT NULL CHECK(category IN ('lodging','restaurant')),
    included INTEGER NOT NULL CHECK(included IN (0,1)),
    classification_method TEXT NOT NULL,
    exclusion_reason TEXT,
    PRIMARY KEY(analysis_id,source_record_id),
    CHECK(included=0 OR assigned_region_id IS NOT NULL),
    CHECK(included=1 OR exclusion_reason IS NOT NULL)
);
CREATE INDEX raw_external_lookup ON raw_records(external_id);
CREATE INDEX venues_region_lookup ON venues(region_id);
CREATE INDEX offerings_venue_lookup ON offerings(venue_id);
CREATE INDEX policies_offering_lookup ON pet_policy_versions(offering_id,checked_at);
CREATE INDEX issues_open_lookup ON review_issues(status,offering_id);
COMMIT;
