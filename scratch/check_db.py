from sqlalchemy import create_engine
import os

db_url = os.environ.get("DATABASE_URL", "postgresql+psycopg2://sleepuser:V$2y35GdfRTdfdDXVFjwT%BqJC@127.0.0.1:5432/sleepdb")
engine = create_engine(db_url)
with engine.connect() as conn:
    print("Severity/Qty:", conn.execute("SELECT count(*) FROM mood_activity_details WHERE severity IS NOT NULL OR quantity_numeric IS NOT NULL;").fetchone())
    print("Resting HR:", conn.execute("SELECT count(*) FROM garmin_resting_heart_rate_daily;").fetchone())
    print("Stress:", conn.execute("SELECT count(*) FROM garmin_stress_daily;").fetchone())
    print("Steps:", conn.execute("SELECT count(*) FROM garmin_steps_daily;").fetchone())
