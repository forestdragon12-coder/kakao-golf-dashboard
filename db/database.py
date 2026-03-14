import aiosqlite
import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "golf.db"

# ─────────────────────────────────────────────────────────────────
# 스키마: 신규 테이블 생성 (CREATE TABLE IF NOT EXISTS → 멱등)
# 기존 tee_time_snapshots 컬럼 추가는 migrate_db()에서 처리
# ─────────────────────────────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS courses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    created_at  TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS crawl_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    status          TEXT DEFAULT 'running',
    total_rows      INTEGER DEFAULT 0,
    error_msg       TEXT
);

CREATE TABLE IF NOT EXISTS tee_time_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    crawl_run_id    INTEGER,
    course_id       INTEGER,
    course_name     TEXT,
    collected_date  TEXT NOT NULL,
    play_date       TEXT NOT NULL,
    tee_time        TEXT NOT NULL,
    price_krw       INTEGER,
    course_sub      TEXT,
    membership_type TEXT,
    promo_flag      INTEGER DEFAULT 0,
    promo_text      TEXT,
    pax_condition   TEXT,
    price_type      TEXT,
    d_day           INTEGER,
    part_type       TEXT,
    season          TEXT,
    weekday_type    TEXT,
    source_channel  TEXT DEFAULT 'kakao_mobile',
    course_variant  TEXT,
    slot_identity_key TEXT,
    slot_identity_version INTEGER DEFAULT 1,
    slot_observation_key TEXT,
    slot_status     TEXT DEFAULT 'available',
    status_reason   TEXT,
    visible_flag    INTEGER DEFAULT 1,
    inventory_observed_flag INTEGER DEFAULT 1,
    listed_price_krw INTEGER,
    normal_price_krw INTEGER,
    sale_price_krw  INTEGER,
    price_badge     TEXT,
    previous_price_krw INTEGER,
    price_changed_flag INTEGER DEFAULT 0,
    price_change_delta_krw INTEGER,
    price_change_delta_pct REAL,
    price_change_count_7d INTEGER DEFAULT 0,
    first_discount_dday INTEGER,
    hash_key        TEXT UNIQUE,
    slot_group_key  TEXT
);

CREATE TABLE IF NOT EXISTS daily_summary (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id           INTEGER,
    course_name         TEXT,
    collected_date      TEXT,
    play_date           TEXT,
    d_day               INTEGER,
    remaining_total     INTEGER,
    remaining_part1     INTEGER,
    remaining_part2     INTEGER,
    min_price           INTEGER,
    max_price           INTEGER,
    avg_price           REAL,
    promo_count         INTEGER DEFAULT 0,
    season              TEXT,
    weekday_type        TEXT,
    UNIQUE(course_name, collected_date, play_date)
);

-- 가격 변동 이벤트 (전일 대비 동일 슬롯 가격 변화)
CREATE TABLE IF NOT EXISTS price_change_events (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    course_name      TEXT,
    play_date        TEXT,
    tee_time         TEXT,
    course_sub       TEXT,
    membership_type  TEXT,
    detected_at      TEXT,
    old_price_krw    INTEGER,
    new_price_krw    INTEGER,
    delta_price_krw  INTEGER,
    delta_pct        REAL,
    event_type       TEXT,          -- 인하 / 인상 / 특가부착 / 특가해제
    promo_flag_after INTEGER DEFAULT 0,
    promo_text_after TEXT
);

-- 가격 변동 후 잔여티 반응 측정
CREATE TABLE IF NOT EXISTS price_response_metrics (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    course_name          TEXT,
    play_date            TEXT,
    tee_time             TEXT,
    course_sub           TEXT,
    change_detected_at   TEXT,
    before_open_slots    INTEGER,
    after_open_slots_1d  INTEGER,
    after_open_slots_3d  INTEGER,
    after_open_slots_5d  INTEGER,
    response_speed       TEXT,
    response_grade       TEXT        -- 강함 / 보통 / 약함 / 없음
);

-- 구간 단위 할인 이벤트
CREATE TABLE IF NOT EXISTS discount_events (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    event_date             TEXT,
    course_name            TEXT,
    play_date              TEXT,
    part_type              TEXT,
    membership_type        TEXT,
    weekday_type           TEXT,
    d_day                  INTEGER,
    event_type             TEXT,      -- 가격인하형 / 특가확대형 / 복합할인형
    baseline_open_slots    INTEGER,
    baseline_avg_price_krw INTEGER,
    baseline_min_price_krw INTEGER,
    baseline_promo_ratio   REAL,
    price_delta_krw        INTEGER,
    price_delta_pct        REAL,
    promo_ratio_delta      REAL,
    control_part_type      TEXT,
    confidence_grade       TEXT,
    holdout_reason         TEXT
);

-- 구간 단위 할인 반응 측정 결과
CREATE TABLE IF NOT EXISTS discount_response_metrics (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    event_date               TEXT,
    course_name              TEXT,
    play_date                TEXT,
    part_type                TEXT,
    membership_type          TEXT,
    event_type               TEXT,
    baseline_open_slots      INTEGER,
    open_slots_d1            INTEGER,
    open_slots_d3            INTEGER,
    open_slots_d5            INTEGER,
    open_slots_d7            INTEGER,
    drop_rate_d1             REAL,
    drop_rate_d3             REAL,
    drop_rate_d5             REAL,
    drop_rate_d7             REAL,
    control_part_type        TEXT,
    control_drop_rate_d3     REAL,
    control_drop_rate_d7     REAL,
    historical_drop_rate_d3  REAL,
    historical_drop_rate_d7  REAL,
    response_score           REAL,
    response_grade           TEXT,      -- 강함 / 보통 / 약함 / 판단보류
    confidence_grade         TEXT,      -- high / medium / low
    holdout_reason           TEXT
);

-- 일일 집계 (멤버십·파트 분리)
CREATE TABLE IF NOT EXISTS daily_course_metrics (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date           TEXT,
    course_name           TEXT,
    play_date             TEXT,
    season                TEXT,
    weekday_type          TEXT,
    part_type             TEXT,
    membership_type       TEXT,    -- '대중제' / '회원제' / NULL(단일구조)
    d_day                 INTEGER,
    observed_open_slots   INTEGER,
    avg_price_krw         REAL,
    min_price_krw         INTEGER,
    max_price_krw         INTEGER,
    promo_slot_count      INTEGER DEFAULT 0,
    greenfee_slot_count   INTEGER DEFAULT 0,
    cart_extra_slot_count INTEGER DEFAULT 0,
    pax_3plus_count       INTEGER DEFAULT 0,
    discount_event_flag   INTEGER DEFAULT 0,
    -- 회원제 오픈 판단 (골드레이크·해피니스 전용)
    -- 1=회원제 슬롯이 해당 play_date에 공개됨, 0=미공개, NULL=판단불가(단일구조)
    member_open_flag      INTEGER DEFAULT NULL,
    confidence_score      REAL,
    UNIQUE(course_name, report_date, play_date, part_type, membership_type)
);

-- 회원제 오픈 이력 (골드레이크·해피니스 전용)
-- daily_course_metrics에서 파생 가능하지만 조회 편의를 위해 별도 관리
CREATE TABLE IF NOT EXISTS member_open_events (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    course_name       TEXT,
    play_date         TEXT,
    detected_at       TEXT,      -- 최초 회원제 슬롯이 관측된 수집일
    member_slot_count INTEGER,   -- 관측된 회원제 슬롯 수
    member_sub_names  TEXT,      -- 관측된 서브코스 이름 (JSON array)
    min_price_krw     INTEGER,
    max_price_krw     INTEGER,
    promo_flag        INTEGER DEFAULT 0  -- 오픈 시 특가 여부
);

-- 예약율 추정용 기준선
CREATE TABLE IF NOT EXISTS baseline_models (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    course_name       TEXT,
    season            TEXT,
    weekday_type      TEXT,
    part_type         TEXT,
    membership_type   TEXT,
    expected_slot_count INTEGER,
    confidence_score  REAL,
    updated_at        TEXT,
    UNIQUE(course_name, season, weekday_type, part_type, membership_type)
);

CREATE TABLE IF NOT EXISTS slot_status_history (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_identity_key     TEXT NOT NULL,
    slot_observation_key  TEXT NOT NULL UNIQUE,
    course_id             INTEGER,
    course_name           TEXT,
    play_date             TEXT NOT NULL,
    tee_time              TEXT NOT NULL,
    part_type             TEXT,
    course_variant        TEXT,
    source_channel        TEXT,
    collected_date        TEXT NOT NULL,
    slot_status           TEXT NOT NULL,
    status_reason         TEXT,
    visible_flag          INTEGER DEFAULT 1,
    inventory_observed_flag INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS price_change_facts (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    price_change_event_id INTEGER,
    slot_identity_key     TEXT NOT NULL,
    course_id             INTEGER,
    course_name           TEXT,
    play_date             TEXT NOT NULL,
    tee_time              TEXT NOT NULL,
    part_type             TEXT,
    course_variant        TEXT,
    source_channel        TEXT,
    change_detected_at    TEXT NOT NULL,
    previous_price_krw    INTEGER,
    current_price_krw     INTEGER,
    delta_krw             INTEGER,
    delta_pct             REAL,
    change_type           TEXT,
    promo_flag_before     INTEGER DEFAULT 0,
    promo_flag_after      INTEGER DEFAULT 0,
    price_badge_before    TEXT,
    price_badge_after     TEXT,
    price_change_count_7d INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS slot_velocity_facts (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    price_change_event_id    INTEGER,
    slot_identity_key        TEXT NOT NULL,
    before_change_open_slots INTEGER,
    after_change_open_slots_1d INTEGER,
    after_change_open_slots_3d INTEGER,
    after_change_open_slots_7d INTEGER,
    slot_velocity_before     REAL,
    slot_velocity_after_1d   REAL,
    slot_velocity_after_3d   REAL,
    slot_velocity_after_7d   REAL,
    discount_response_grade  TEXT,
    response_confidence      TEXT
);

CREATE TABLE IF NOT EXISTS course_segment_daily_facts (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date              TEXT NOT NULL,
    course_id                INTEGER,
    course_name              TEXT,
    season                   TEXT,
    weekday_type             TEXT,
    part_type                TEXT,
    membership_type          TEXT,
    source_channel           TEXT,
    listed_avg_price_krw     REAL,
    normal_avg_price_krw     REAL,
    sale_avg_price_krw       REAL,
    observed_open_slots      INTEGER,
    promo_slot_count         INTEGER,
    slot_status_available_count INTEGER,
    slot_status_sold_out_count INTEGER,
    slot_status_hidden_count INTEGER,
    slot_status_not_open_count INTEGER,
    slot_status_removed_unknown_count INTEGER,
    UNIQUE(report_date, course_name, season, weekday_type, part_type, membership_type, source_channel)
);

CREATE TABLE IF NOT EXISTS competitive_segment_facts (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date              TEXT NOT NULL,
    part_type                TEXT,
    weekday_type             TEXT,
    season                   TEXT,
    competitor_group         TEXT,
    course_name              TEXT,
    avg_price_rank           INTEGER,
    defense_rank             INTEGER,
    discount_dependency_rank INTEGER,
    position_label           TEXT,
    UNIQUE(report_date, competitor_group, course_name, part_type, weekday_type, season)
);

CREATE INDEX IF NOT EXISTS idx_snap_play       ON tee_time_snapshots(play_date);
CREATE INDEX IF NOT EXISTS idx_snap_course     ON tee_time_snapshots(course_name);
CREATE INDEX IF NOT EXISTS idx_snap_collect    ON tee_time_snapshots(collected_date);
CREATE INDEX IF NOT EXISTS idx_snap_identity   ON tee_time_snapshots(slot_identity_key);
CREATE INDEX IF NOT EXISTS idx_snap_status     ON tee_time_snapshots(slot_status);
CREATE INDEX IF NOT EXISTS idx_sum_play        ON daily_summary(play_date);
CREATE INDEX IF NOT EXISTS idx_sum_course      ON daily_summary(course_name);
CREATE INDEX IF NOT EXISTS idx_pce_play        ON price_change_events(play_date);
CREATE INDEX IF NOT EXISTS idx_pce_course      ON price_change_events(course_name);
CREATE INDEX IF NOT EXISTS idx_dcm_date        ON daily_course_metrics(report_date);
CREATE INDEX IF NOT EXISTS idx_de_event_date   ON discount_events(event_date);
CREATE INDEX IF NOT EXISTS idx_de_course       ON discount_events(course_name);
CREATE INDEX IF NOT EXISTS idx_drm_event_date  ON discount_response_metrics(event_date);
CREATE INDEX IF NOT EXISTS idx_drm_course      ON discount_response_metrics(course_name);
"""

# 기존 DB에 신규 컬럼 추가 (ALTER TABLE은 컬럼 없을 때만 시도)
MIGRATIONS = [
    ("tee_time_snapshots",    "membership_type",  "TEXT"),
    ("tee_time_snapshots",    "promo_text",       "TEXT"),
    ("tee_time_snapshots",    "pax_condition",    "TEXT"),
    ("tee_time_snapshots",    "price_type",       "TEXT"),
    ("tee_time_snapshots",    "slot_group_key",   "TEXT"),
    ("tee_time_snapshots",    "source_channel",   "TEXT DEFAULT 'kakao_mobile'"),
    ("tee_time_snapshots",    "course_variant",   "TEXT"),
    ("tee_time_snapshots",    "slot_identity_key", "TEXT"),
    ("tee_time_snapshots",    "slot_identity_version", "INTEGER DEFAULT 1"),
    ("tee_time_snapshots",    "slot_observation_key", "TEXT"),
    ("tee_time_snapshots",    "slot_status",      "TEXT DEFAULT 'available'"),
    ("tee_time_snapshots",    "status_reason",    "TEXT"),
    ("tee_time_snapshots",    "visible_flag",     "INTEGER DEFAULT 1"),
    ("tee_time_snapshots",    "inventory_observed_flag", "INTEGER DEFAULT 1"),
    ("tee_time_snapshots",    "listed_price_krw", "INTEGER"),
    ("tee_time_snapshots",    "normal_price_krw", "INTEGER"),
    ("tee_time_snapshots",    "sale_price_krw",   "INTEGER"),
    ("tee_time_snapshots",    "price_badge",      "TEXT"),
    ("tee_time_snapshots",    "previous_price_krw", "INTEGER"),
    ("tee_time_snapshots",    "price_changed_flag", "INTEGER DEFAULT 0"),
    ("tee_time_snapshots",    "price_change_delta_krw", "INTEGER"),
    ("tee_time_snapshots",    "price_change_delta_pct", "REAL"),
    ("tee_time_snapshots",    "price_change_count_7d", "INTEGER DEFAULT 0"),
    ("tee_time_snapshots",    "first_discount_dday", "INTEGER"),
    ("daily_course_metrics",  "member_open_flag", "INTEGER DEFAULT NULL"),
]


def make_hash(course_name, collected_date, play_date, tee_time, course_sub=""):
    """수집 고유키: course_sub 포함 → 동일 시간 복수 코스 충돌 방지"""
    raw = f"{course_name}|{collected_date}|{play_date}|{tee_time}|{course_sub or ''}"
    return hashlib.md5(raw.encode()).hexdigest()

def make_slot_key(course_name, play_date, tee_time, course_sub=""):
    """슬롯 고유키: collected_date 제외 → 날짜 간 동일 슬롯 추적용"""
    raw = f"{course_name}|{play_date}|{tee_time}|{course_sub or ''}"
    return hashlib.md5(raw.encode()).hexdigest()


def normalize_course_variant(course_sub=None, membership_type=None, price_type=None):
    parts = []
    if course_sub:
        parts.append(str(course_sub).strip())
    if membership_type:
        parts.append(str(membership_type).strip())
    if price_type:
        cleaned = str(price_type).strip()
        if cleaned:
            parts.append(cleaned)
    if not parts:
        return "standard"
    return "|".join(parts)


def make_slot_identity_key(course_id, play_date, tee_time, part_type, course_variant, source_channel):
    raw = f"{course_id}|{play_date}|{tee_time}|{part_type or ''}|{course_variant or 'standard'}|{source_channel or 'unknown_channel'}"
    return hashlib.md5(raw.encode()).hexdigest()


def make_slot_observation_key(slot_identity_key, collected_date):
    raw = f"{slot_identity_key}|{collected_date}"
    return hashlib.md5(raw.encode()).hexdigest()


async def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()
    await migrate_db()

async def migrate_db():
    """기존 DB에 신규 컬럼과 파생 키를 안전하게 보정한다."""
    async with aiosqlite.connect(DB_PATH) as db:
        existing_columns: dict[str, set[str]] = {}
        for table, col, col_type in MIGRATIONS:
            if table not in existing_columns:
                async with db.execute(f"PRAGMA table_info({table})") as cur:
                    existing_columns[table] = {row[1] for row in await cur.fetchall()}
            if col not in existing_columns[table]:
                await db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
                existing_columns[table].add(col)

        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_snap_slot_key ON tee_time_snapshots(slot_group_key)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_snap_identity_key ON tee_time_snapshots(slot_identity_key)"
        )
        await _backfill_snapshot_keys(db)
        await db.commit()


async def _backfill_snapshot_keys(db: aiosqlite.Connection):
    """과거 데이터에 누락된 파생 키와 구조 필드를 채운다."""
    async with db.execute(
        """
        SELECT id, course_id, course_name, collected_date, play_date, tee_time, course_sub,
               membership_type, price_type, part_type, price_krw,
               hash_key, slot_group_key, source_channel, course_variant,
               slot_identity_key, slot_observation_key, slot_status,
               visible_flag, inventory_observed_flag, listed_price_krw,
               sale_price_krw, price_badge
        FROM tee_time_snapshots
        WHERE hash_key IS NULL
           OR slot_group_key IS NULL
           OR source_channel IS NULL
           OR course_variant IS NULL
           OR slot_identity_key IS NULL
           OR slot_observation_key IS NULL
           OR slot_status IS NULL
           OR visible_flag IS NULL
           OR inventory_observed_flag IS NULL
           OR listed_price_krw IS NULL
           OR sale_price_krw IS NULL
        """
    ) as cur:
        rows = await cur.fetchall()

    for row in rows:
        snapshot = {
            "id": row[0],
            "course_id": row[1],
            "course_name": row[2],
            "collected_date": row[3],
            "play_date": row[4],
            "tee_time": row[5],
            "course_sub": row[6],
            "membership_type": row[7],
            "price_type": row[8],
            "part_type": row[9],
            "price_krw": row[10],
            "hash_key": row[11],
            "slot_group_key": row[12],
            "source_channel": row[13],
            "course_variant": row[14],
            "slot_identity_key": row[15],
            "slot_observation_key": row[16],
            "slot_status": row[17],
            "visible_flag": row[18],
            "inventory_observed_flag": row[19],
            "listed_price_krw": row[20],
            "sale_price_krw": row[21],
            "price_badge": row[22],
        }
        prepared = _prepare_snapshot_row(snapshot)
        await db.execute(
            """
            UPDATE tee_time_snapshots
            SET hash_key = ?, slot_group_key = ?, source_channel = ?, course_variant = ?,
                slot_identity_key = ?, slot_observation_key = ?, slot_status = ?,
                status_reason = COALESCE(status_reason, ?), visible_flag = ?, inventory_observed_flag = ?,
                listed_price_krw = ?, sale_price_krw = ?, price_badge = COALESCE(price_badge, ?)
            WHERE id = ?
            """,
            (
                prepared["hash_key"],
                prepared["slot_group_key"],
                prepared["source_channel"],
                prepared["course_variant"],
                prepared["slot_identity_key"],
                prepared["slot_observation_key"],
                prepared["slot_status"],
                prepared["status_reason"],
                prepared["visible_flag"],
                prepared["inventory_observed_flag"],
                prepared["listed_price_krw"],
                prepared["sale_price_krw"],
                prepared["price_badge"],
                prepared["id"],
            ),
        )


def _prepare_snapshot_row(row: dict) -> dict:
    prepared = dict(row)
    course_sub = prepared.get("course_sub") or ""
    source_channel = prepared.get("source_channel") or "kakao_mobile"
    price_krw = prepared.get("price_krw")
    listed_price = prepared.get("listed_price_krw")
    sale_price = prepared.get("sale_price_krw")
    course_variant = prepared.get("course_variant") or normalize_course_variant(
        course_sub=course_sub or None,
        membership_type=prepared.get("membership_type"),
        price_type=prepared.get("price_type"),
    )
    part_type = prepared.get("part_type")
    prepared["source_channel"] = source_channel
    prepared["course_variant"] = course_variant
    prepared["hash_key"] = prepared.get("hash_key") or make_hash(
        prepared["course_name"],
        prepared["collected_date"],
        prepared["play_date"],
        prepared["tee_time"],
        course_sub,
    )
    prepared["slot_group_key"] = prepared.get("slot_group_key") or make_slot_key(
        prepared["course_name"],
        prepared["play_date"],
        prepared["tee_time"],
        course_sub,
    )
    prepared["slot_identity_key"] = prepared.get("slot_identity_key") or make_slot_identity_key(
        prepared.get("course_id"),
        prepared["play_date"],
        prepared["tee_time"],
        part_type,
        course_variant,
        source_channel,
    )
    prepared["slot_identity_version"] = prepared.get("slot_identity_version") or 1
    prepared["slot_observation_key"] = prepared.get("slot_observation_key") or make_slot_observation_key(
        prepared["slot_identity_key"],
        prepared["collected_date"],
    )
    prepared["slot_status"] = prepared.get("slot_status") or "available"
    prepared["status_reason"] = prepared.get("status_reason") or "observed_in_listing"
    prepared["visible_flag"] = prepared.get("visible_flag", 1)
    prepared["inventory_observed_flag"] = prepared.get("inventory_observed_flag", 1)
    prepared["listed_price_krw"] = listed_price if listed_price is not None else price_krw
    prepared["normal_price_krw"] = prepared.get("normal_price_krw")
    prepared["sale_price_krw"] = sale_price if sale_price is not None else price_krw
    prepared["price_badge"] = prepared.get("price_badge") or prepared.get("promo_text")
    prepared["previous_price_krw"] = prepared.get("previous_price_krw")
    prepared["price_changed_flag"] = prepared.get("price_changed_flag", 0)
    prepared["price_change_delta_krw"] = prepared.get("price_change_delta_krw")
    prepared["price_change_delta_pct"] = prepared.get("price_change_delta_pct")
    prepared["price_change_count_7d"] = prepared.get("price_change_count_7d", 0)
    prepared["first_discount_dday"] = prepared.get("first_discount_dday")
    return prepared

async def get_or_create_course(name: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO courses (name) VALUES (?)", (name,)
        )
        await db.commit()
        async with db.execute(
            "SELECT id FROM courses WHERE name=?", (name,)
        ) as cur:
            row = await cur.fetchone()
            return row[0]

async def start_run() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE crawl_runs
            SET finished_at = ?, status = 'aborted', error_msg = COALESCE(error_msg, 'interrupted before completion')
            WHERE status = 'running'
            """,
            (datetime.now().isoformat(),)
        )
        cur = await db.execute(
            "INSERT INTO crawl_runs (started_at) VALUES (?)",
            (datetime.now().isoformat(),)
        )
        await db.commit()
        return cur.lastrowid

async def finish_run(run_id: int, status: str, total: int, error: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE crawl_runs SET finished_at=?, status=?, total_rows=?, error_msg=? WHERE id=?",
            (datetime.now().isoformat(), status, total, error, run_id)
        )
        await db.commit()

async def insert_snapshots(rows: list[dict]) -> int:
    if not rows:
        return 0
    count = 0
    async with aiosqlite.connect(DB_PATH) as db:
        previous_total_changes = db.total_changes
        for r in rows:
            try:
                prepared = _prepare_snapshot_row(r)
                await db.execute("""
                    INSERT OR IGNORE INTO tee_time_snapshots
                    (crawl_run_id, course_id, course_name, collected_date, play_date,
                     tee_time, price_krw, course_sub, membership_type,
                     promo_flag, promo_text, pax_condition, price_type,
                     d_day, part_type, season, weekday_type, source_channel,
                     course_variant, slot_identity_key, slot_identity_version, slot_observation_key,
                     slot_status, status_reason, visible_flag, inventory_observed_flag,
                     listed_price_krw, normal_price_krw, sale_price_krw, price_badge,
                     previous_price_krw, price_changed_flag, price_change_delta_krw, price_change_delta_pct,
                     price_change_count_7d, first_discount_dday, hash_key, slot_group_key)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    prepared["crawl_run_id"], prepared["course_id"], prepared["course_name"],
                    prepared["collected_date"], prepared["play_date"], prepared["tee_time"],
                    prepared.get("price_krw"), prepared.get("course_sub"), prepared.get("membership_type"),
                    prepared.get("promo_flag", 0), prepared.get("promo_text"),
                    prepared.get("pax_condition"), prepared.get("price_type"),
                    prepared["d_day"], prepared["part_type"], prepared["season"], prepared["weekday_type"],
                    prepared["source_channel"], prepared["course_variant"], prepared["slot_identity_key"],
                    prepared["slot_identity_version"], prepared["slot_observation_key"], prepared["slot_status"],
                    prepared["status_reason"], prepared["visible_flag"], prepared["inventory_observed_flag"],
                    prepared["listed_price_krw"], prepared.get("normal_price_krw"), prepared["sale_price_krw"],
                    prepared.get("price_badge"), prepared.get("previous_price_krw"), prepared["price_changed_flag"],
                    prepared.get("price_change_delta_krw"), prepared.get("price_change_delta_pct"),
                    prepared["price_change_count_7d"], prepared.get("first_discount_dday"),
                    prepared["hash_key"], prepared.get("slot_group_key"),
                ))
                await db.execute(
                    """
                    INSERT OR IGNORE INTO slot_status_history
                    (slot_identity_key, slot_observation_key, course_id, course_name, play_date,
                     tee_time, part_type, course_variant, source_channel, collected_date,
                     slot_status, status_reason, visible_flag, inventory_observed_flag)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        prepared["slot_identity_key"], prepared["slot_observation_key"], prepared.get("course_id"),
                        prepared["course_name"], prepared["play_date"], prepared["tee_time"], prepared["part_type"],
                        prepared["course_variant"], prepared["source_channel"], prepared["collected_date"],
                        prepared["slot_status"], prepared["status_reason"], prepared["visible_flag"],
                        prepared["inventory_observed_flag"],
                    ),
                )
                if db.total_changes > previous_total_changes:
                    count += 1
                    previous_total_changes = db.total_changes
            except sqlite3.IntegrityError:
                continue
            except Exception as exc:
                raise RuntimeError(
                    f"snapshot insert failed for {r.get('course_name')} {r.get('play_date')} {r.get('tee_time')}"
                ) from exc
        await db.commit()
    return count

async def upsert_daily_summary(rows: list[dict]):
    if not rows:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        for r in rows:
            await db.execute("""
                INSERT INTO daily_summary
                (course_id, course_name, collected_date, play_date, d_day,
                 remaining_total, remaining_part1, remaining_part2,
                 min_price, max_price, avg_price, promo_count, season, weekday_type)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(course_name, collected_date, play_date) DO UPDATE SET
                    remaining_total=excluded.remaining_total,
                    remaining_part1=excluded.remaining_part1,
                    remaining_part2=excluded.remaining_part2,
                    min_price=excluded.min_price,
                    max_price=excluded.max_price,
                    avg_price=excluded.avg_price,
                    promo_count=excluded.promo_count,
                    season=excluded.season,
                    weekday_type=excluded.weekday_type
            """, (
                r["course_id"], r["course_name"], r["collected_date"],
                r["play_date"], r["d_day"], r["remaining_total"],
                r["remaining_part1"], r["remaining_part2"],
                r.get("min_price"), r.get("max_price"), r.get("avg_price"),
                r.get("promo_count", 0), r["season"], r["weekday_type"]
            ))
        await db.commit()
