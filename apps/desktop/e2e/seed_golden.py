"""Golden E2E fixture: deterministic DB seed, no network, no LLM.

Builds a small but complete dataset (source + transcript + moments with
features + review feedback + approved clips in an episode + a topic + a
completed job) so the UI can be asserted against known content.

    python e2e/seed_golden.py <db_path>
"""

import json
import sqlite3
import sys
from pathlib import Path

TITLE = "Golden Game Update Highlights"
TOPIC = "Golden Game Update"

SCHEMA_SQL = """
CREATE TABLE sources (
  id INTEGER PRIMARY KEY AUTOINCREMENT, provider VARCHAR(32), external_id VARCHAR(128),
  url TEXT, title TEXT, channel_id VARCHAR(128), channel_name VARCHAR(256),
  published_at DATETIME, duration FLOAT, view_count INTEGER, like_count INTEGER,
  comment_count INTEGER, category VARCHAR(64), description TEXT, thumbnail_url TEXT,
  trend_score FLOAT, discovered_at DATETIME, last_checked_at DATETIME,
  status VARCHAR(32) DEFAULT 'DISCOVERED');
CREATE TABLE trend_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, topic TEXT, description TEXT, score FLOAT,
  velocity FLOAT, region VARCHAR(8), category VARCHAR(64), first_detected_at DATETIME,
  last_detected_at DATETIME, status VARCHAR(32));
CREATE TABLE trend_sources (
  trend_id INTEGER REFERENCES trend_events(id),
  source_id INTEGER REFERENCES sources(id), relevance_score FLOAT,
  relationship_type VARCHAR(32), PRIMARY KEY (trend_id, source_id));
CREATE TABLE transcripts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, source_id INTEGER REFERENCES sources(id),
  language VARCHAR(16), model VARCHAR(64), text TEXT, segments_json TEXT,
  audio_sha256 VARCHAR(64) DEFAULT '', created_at DATETIME);
CREATE TABLE moments (
  id INTEGER PRIMARY KEY AUTOINCREMENT, source_id INTEGER REFERENCES sources(id),
  start_time FLOAT, end_time FLOAT, transcript_excerpt TEXT, moment_type VARCHAR(32),
  semantic_score FLOAT, emotion_score FLOAT, novelty_score FLOAT, visual_score FLOAT,
  editorial_score FLOAT, final_score FLOAT, status VARCHAR(32), notes TEXT,
  category VARCHAR(64), is_best BOOLEAN DEFAULT 0,
  features_json TEXT DEFAULT '');
CREATE TABLE episodes (
  id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, format VARCHAR(64), theme VARCHAR(128),
  target_duration FLOAT, actual_duration FLOAT, status VARCHAR(32),
  created_at DATETIME, updated_at DATETIME);
CREATE TABLE episode_segments (
  id INTEGER PRIMARY KEY AUTOINCREMENT, episode_id INTEGER REFERENCES episodes(id),
  moment_id INTEGER REFERENCES moments(id), sequence INTEGER, duration FLOAT,
  transition_type VARCHAR(32), commentary_text TEXT, context_text TEXT);
CREATE TABLE jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, type VARCHAR(64), status VARCHAR(32),
  priority INTEGER, payload_json TEXT, progress FLOAT, attempts INTEGER, error TEXT,
  created_at DATETIME, started_at DATETIME, completed_at DATETIME, next_run_at DATETIME);
CREATE TABLE rights_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT, source_id INTEGER REFERENCES sources(id),
  status VARCHAR(32), basis VARCHAR(64), owner VARCHAR(256), license VARCHAR(128),
  permission_reference TEXT, restrictions TEXT, territory VARCHAR(64),
  commercial_allowed BOOLEAN DEFAULT 0, notes TEXT, verified_at DATETIME,
  reviewer VARCHAR(128) DEFAULT '', expires_at DATETIME);
CREATE TABLE renders (
  id INTEGER PRIMARY KEY AUTOINCREMENT, episode_id INTEGER REFERENCES episodes(id),
  preset VARCHAR(32), resolution VARCHAR(32), fps INTEGER, codec VARCHAR(32),
  path TEXT, status VARCHAR(32), created_at DATETIME, completed_at DATETIME, error TEXT);
CREATE TABLE media_assets (
  id INTEGER PRIMARY KEY AUTOINCREMENT, source_id INTEGER REFERENCES sources(id),
  kind VARCHAR(32), path TEXT, width INTEGER, height INTEGER, duration FLOAT,
  codec VARCHAR(32), created_at DATETIME);
CREATE TABLE moment_feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT, moment_id INTEGER REFERENCES moments(id),
  decision VARCHAR(32), reason TEXT, original_start FLOAT, original_end FLOAT,
  adjusted_start FLOAT, adjusted_end FLOAT, created_at DATETIME);
CREATE TABLE source_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT, source_id INTEGER REFERENCES sources(id),
  view_count INTEGER, like_count INTEGER, comment_count INTEGER, taken_at DATETIME);
CREATE TABLE discovery_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, run_type VARCHAR(32), region VARCHAR(8),
  category VARCHAR(64), units_consumed INTEGER, source_count INTEGER,
  created_at DATETIME);
"""


def seed(db_path: str) -> None:
    target = Path(db_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    conn = sqlite3.connect(str(target))
    # a bare schema is enough for the fixture (the app only reads these rows)
    conn.executescript(
        """
        DROP TABLE IF EXISTS sources;
        DROP TABLE IF EXISTS trend_events;
        DROP TABLE IF EXISTS trend_sources;
        DROP TABLE IF EXISTS transcripts;
        DROP TABLE IF EXISTS moments;
        DROP TABLE IF EXISTS episodes;
        DROP TABLE IF EXISTS episode_segments;
        DROP TABLE IF EXISTS jobs;
        DROP TABLE IF EXISTS rights_records;
        DROP TABLE IF EXISTS renders;
        DROP TABLE IF EXISTS media_assets;
        DROP TABLE IF EXISTS moment_feedback;
        DROP TABLE IF EXISTS source_snapshots;
        DROP TABLE IF EXISTS discovery_runs;
        """)
    conn.executescript(SCHEMA_SQL)
    conn.executescript(
        """
        DELETE FROM moment_feedback; DELETE FROM moments;
        DELETE FROM transcripts;  DELETE FROM media_assets;
        DELETE FROM episode_segments; DELETE FROM episodes;
        DELETE FROM trend_sources; DELETE FROM trend_events;
        DELETE FROM renders; DELETE FROM jobs; DELETE FROM rights_records;
        DELETE FROM source_snapshots; DELETE FROM sources;
        """)
    conn.execute(
        "INSERT INTO sources (id, provider, external_id, url, title, channel_id,"
        " channel_name, published_at, duration, view_count, like_count,"
        " comment_count, category, description, thumbnail_url, trend_score,"
        " discovered_at, last_checked_at, status) VALUES"
        " (1,'youtube','golden01','https://x','%s','ch','Golden Channel',"
        " NULL, 30.0, 2500000, 50000, 5000, 'gaming', 'desc', '', 88.5,"
        " CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'DISCOVERED')" % TITLE)
    conn.execute(
        "INSERT INTO rights_records (source_id, status, basis, commercial_allowed)"
        " VALUES (1, 'UNKNOWN', '', 0)")
    conn.execute(
        "INSERT INTO transcripts (source_id, language, model, text,"
        " segments_json, audio_sha256, created_at) VALUES"
        " (1,'en','golden','golden caption transcript', '%s', 'goldensha',"
        " CURRENT_TIMESTAMP)"
        % json.dumps([{"start": 0.0, "end": 12.0, "text": "golden caption",
                       "words": [{"start": 0.0, "end": 12.0,
                                  "word": " golden", "probability": 0.99}]}]))
    for i, (start, end, score) in enumerate([
            (0.0, 12.0, 91.0), (12.0, 24.0, 74.0), (24.0, 30.0, 55.0)]):
        conn.execute(
            "INSERT INTO moments (source_id, start_time, end_time,"
            " transcript_excerpt, moment_type, semantic_score, emotion_score,"
            " novelty_score, visual_score, editorial_score, final_score,"
            " status, notes, category, is_best, features_json) VALUES"
            " (1, ?, ?, ?, 'highlight', 0.8, 0.9, 0.7, 0.0, 0.85, ?,"
            " ?, '', '', 0, '%s')"
            % json.dumps({"hook": 0.9, "relevance": 0.5, "novelty": 0.6,
                          "emotion": 0.9, "payoff": 0.2, "completeness": 1.0,
                          "dead_air": 0.1, "context_dependency": 0.0,
                          "duration": end - start, "wps": 1.5,
                          "semantic_relevance": 0.8, "semantic_novelty": 0.7,
                          "visual": 0.0, "llm": 0.0}),
            (start, end, f"golden clip {i}", score,
             "APPROVED" if i < 2 else "CANDIDATE"))
    conn.execute(
        "INSERT INTO episodes (title, format, theme, target_duration,"
        " actual_duration, status, created_at, updated_at) VALUES"
        " ('Golden Episode', 'daily_highlights', 'golden', 1200.0, 24.0,"
        " 'DRAFT', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)")
    conn.execute(
        "INSERT INTO episode_segments (episode_id, moment_id, sequence,"
        " duration, transition_type, commentary_text, context_text) VALUES"
        " (1, 1, 0, 12.0, 'cut', 'fixture', ''),"
        " (1, 2, 1, 12.0, 'cut', 'fixture', '')")
    conn.execute(
        "INSERT INTO moment_feedback (moment_id, decision, reason,"
        " original_start, original_end, adjusted_start, adjusted_end)"
        " VALUES (1,'APPROVED','golden fixture', 0.0, 12.0, 0.0, 12.0)")
    conn.execute(
        "INSERT INTO trend_events (topic, description, score, velocity, region,"
        " category, first_detected_at, last_detected_at, status) VALUES"
        " ('%s','golden trend topic', 91.5, 12000.0, 'US', 'gaming',"
        " CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'ACTIVE')" % TOPIC)
    conn.execute(
        "INSERT INTO trend_sources (trend_id, source_id, relevance_score,"
        " relationship_type) VALUES (1, 1, 0.95, 'primary')")
    conn.execute(
        "INSERT INTO jobs (type, status, priority, payload_json, progress,"
        " attempts, error, created_at, started_at, completed_at, next_run_at)"
        " VALUES ('CLUSTER','COMPLETED',30,'{}',1.0,1,'',"
        " CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, NULL)")
    conn.commit()
    conn.close()
    print(f"golden fixture written: {target}")


if __name__ == "__main__":
    seed(sys.argv[1])
