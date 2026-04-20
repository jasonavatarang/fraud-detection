import os
import psycopg2
from dotenv import load_dotenv
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    from_json,
    when,
    count,
    sum as spark_sum,
    max as spark_max,
    to_timestamp, current_timestamp, expr
)
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    DoubleType
)


load_dotenv()

DB_HOST = os.getenv("POSTGRES_HOST", "db")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "frauddb")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

JDBC_URL = f"jdbc:postgresql://{DB_HOST}:{DB_PORT}/{DB_NAME}"
JDBC_PROPERTIES = {
    "user": DB_USER,
    "password": DB_PASSWORD,
    "driver": "org.postgresql.Driver",
}


def build_spark() -> SparkSession:
    return (
        SparkSession.builder
        .appName("fraud-risk-streaming-phase-4")
        .config(
            "spark.jars.packages",
            ",".join([
                "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1",
                "org.apache.kafka:kafka-clients:3.4.1",
                "org.postgresql:postgresql:42.7.3"
            ])
        )
        .getOrCreate()
    )


def get_pg_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def ensure_tables():
    conn = get_pg_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS raw_events_stream (
            event_id TEXT PRIMARY KEY,
            user_id TEXT,
            event_type TEXT,
            timestamp TEXT,
            ip_address TEXT,
            location TEXT,
            device_id TEXT,
            amount DOUBLE PRECISION,
            status TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_risk_summary_stream (
            user_id TEXT PRIMARY KEY,
            failed_login_count BIGINT,
            has_password_reset INT,
            has_withdrawal INT,
            has_mfa_disabled INT,
            has_large_withdrawal INT,
            event_count BIGINT,
            total_amount DOUBLE PRECISION,
            high_velocity_event_flag INT,
            password_reset_then_withdrawal_flag INT,
            risk_score BIGINT,
            risk_level TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS recent_burst_activity (
            user_id TEXT PRIMARY KEY,
            recent_event_count BIGINT,
            recent_failed_login_count BIGINT,
            has_recent_password_reset INT,
            has_recent_withdrawal INT,
            burst_score BIGINT,
            burst_level TEXT
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def upsert_user_summary(rows):
    conn = get_pg_connection()
    cur = conn.cursor()

    upsert_sql = """
        INSERT INTO user_risk_summary_stream (
            user_id,
            failed_login_count,
            has_password_reset,
            has_withdrawal,
            has_mfa_disabled,
            has_large_withdrawal,
            event_count,
            total_amount,
            high_velocity_event_flag,
            password_reset_then_withdrawal_flag,
            risk_score,
            risk_level
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id)
        DO UPDATE SET
            failed_login_count = EXCLUDED.failed_login_count,
            has_password_reset = EXCLUDED.has_password_reset,
            has_withdrawal = EXCLUDED.has_withdrawal,
            has_mfa_disabled = EXCLUDED.has_mfa_disabled,
            has_large_withdrawal = EXCLUDED.has_large_withdrawal,
            event_count = EXCLUDED.event_count,
            total_amount = EXCLUDED.total_amount,
            high_velocity_event_flag = EXCLUDED.high_velocity_event_flag,
            password_reset_then_withdrawal_flag = EXCLUDED.password_reset_then_withdrawal_flag,
            risk_score = EXCLUDED.risk_score,
            risk_level = EXCLUDED.risk_level
    """

    for row in rows:
        cur.execute(upsert_sql, (
            row["user_id"],
            row["failed_login_count"],
            row["has_password_reset"],
            row["has_withdrawal"],
            row["has_mfa_disabled"],
            row["has_large_withdrawal"],
            row["event_count"],
            row["total_amount"],
            row["high_velocity_event_flag"],
            row["password_reset_then_withdrawal_flag"],
            row["risk_score"],
            row["risk_level"],
        ))

    conn.commit()
    cur.close()
    conn.close()


def upsert_recent_bursts(rows):
    conn = get_pg_connection()
    cur = conn.cursor()

    upsert_sql = """
        INSERT INTO recent_burst_activity (
            user_id,
            recent_event_count,
            recent_failed_login_count,
            has_recent_password_reset,
            has_recent_withdrawal,
            burst_score,
            burst_level
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id)
        DO UPDATE SET
            recent_event_count = EXCLUDED.recent_event_count,
            recent_failed_login_count = EXCLUDED.recent_failed_login_count,
            has_recent_password_reset = EXCLUDED.has_recent_password_reset,
            has_recent_withdrawal = EXCLUDED.has_recent_withdrawal,
            burst_score = EXCLUDED.burst_score,
            burst_level = EXCLUDED.burst_level
    """

    for row in rows:
        cur.execute(upsert_sql, (
            row["user_id"],
            row["recent_event_count"],
            row["recent_failed_login_count"],
            row["has_recent_password_reset"],
            row["has_recent_withdrawal"],
            row["burst_score"],
            row["burst_level"],
        ))

    conn.commit()
    cur.close()
    conn.close()

def write_to_postgres(batch_df, batch_id):
    print(f"Processing micro-batch {batch_id}...")

    if batch_df.rdd.isEmpty():
        print("Empty batch, skipping.")
        return

    ensure_tables()

    # 1) Append raw events
    batch_df.write.jdbc(
        url=JDBC_URL,
        table="raw_events_stream",
        mode="append",
        properties=JDBC_PROPERTIES,
    )
    

    # 2) Recompute summaries from full raw event history
    spark = batch_df.sparkSession
    raw_df = spark.read.jdbc(
        url=JDBC_URL,
        table="raw_events_stream",
        properties=JDBC_PROPERTIES,
    )

    raw_df = raw_df.withColumn("event_ts", to_timestamp(col("timestamp")))

    recent_df = raw_df.filter(
        col("event_ts") >= expr("current_timestamp() - INTERVAL 5 MINUTES")
    )

    enriched_raw = (
        raw_df
        .withColumn("failed_login_flag", when(col("event_type") == "login_failed", 1).otherwise(0))
        .withColumn("password_reset_flag", when(col("event_type") == "password_reset", 1).otherwise(0))
        .withColumn("withdrawal_flag", when(col("event_type") == "withdrawal", 1).otherwise(0))
        .withColumn("mfa_disabled_flag", when(col("event_type") == "mfa_disabled", 1).otherwise(0))
        .withColumn(
            "large_withdrawal_flag",
            when((col("event_type") == "withdrawal") & (col("amount") >= 5000), 1).otherwise(0)
        )
    )

    user_summary = (
        enriched_raw
        .groupBy("user_id")
        .agg(
            spark_sum("failed_login_flag").alias("failed_login_count"),
            spark_max("password_reset_flag").alias("has_password_reset"),
            spark_max("withdrawal_flag").alias("has_withdrawal"),
            spark_max("mfa_disabled_flag").alias("has_mfa_disabled"),
            spark_max("large_withdrawal_flag").alias("has_large_withdrawal"),
            count("*").alias("event_count"),
            spark_sum("amount").alias("total_amount")
        )
        .withColumn("high_velocity_event_flag", when(col("event_count") >= 5, 1).otherwise(0))
        .withColumn(
            "password_reset_then_withdrawal_flag",
            when(
                (col("has_password_reset") == 1) & (col("has_withdrawal") == 1),
                1
            ).otherwise(0)
        )
        .withColumn(
            "risk_score",
            col("failed_login_count") * 8
            + col("has_password_reset") * 15
            + col("has_large_withdrawal") * 25
            + col("has_mfa_disabled") * 20
            + col("high_velocity_event_flag") * 12
            + col("password_reset_then_withdrawal_flag") * 25
        )
        .withColumn(
            "risk_level",
            when(col("risk_score") >= 70, "critical")
            .when(col("risk_score") >= 40, "high")
            .when(col("risk_score") >= 20, "medium")
            .otherwise("low")
        )
    )

    recent_burst_df = (
        recent_df
        .withColumn("recent_failed_login_flag", when(col("event_type") == "login_failed", 1).otherwise(0))
        .withColumn("recent_password_reset_flag", when(col("event_type") == "password_reset", 1).otherwise(0))
        .withColumn("recent_withdrawal_flag", when(col("event_type") == "withdrawal", 1).otherwise(0))
        .groupBy("user_id")
        .agg(
            count("*").alias("recent_event_count"),
            spark_sum("recent_failed_login_flag").alias("recent_failed_login_count"),
            spark_max("recent_password_reset_flag").alias("has_recent_password_reset"),
            spark_max("recent_withdrawal_flag").alias("has_recent_withdrawal"),
        )
        .withColumn(
            "burst_score",
            col("recent_event_count") * 5
            + col("recent_failed_login_count") * 10
            + col("has_recent_password_reset") * 15
            + col("has_recent_withdrawal") * 15
        )
        .withColumn(
            "burst_level",
            when(col("burst_score") >= 35, "high")
            .when(col("burst_score") >= 20, "medium")
            .otherwise("low")
        )
    )

    rows = [row.asDict() for row in user_summary.collect()]
    upsert_user_summary(rows)

    burst_rows = [row.asDict() for row in recent_burst_df.collect()]
    upsert_recent_bursts(burst_rows)

    print(f"Finished micro-batch {batch_id}")
    user_summary.show(truncate=False)


def main() -> None:
    spark = build_spark()
    spark.sparkContext.setLogLevel("WARN")

    schema = StructType([
        StructField("event_id", StringType(), True),
        StructField("user_id", StringType(), True),
        StructField("event_type", StringType(), True),
        StructField("timestamp", StringType(), True),
        StructField("ip_address", StringType(), True),
        StructField("location", StringType(), True),
        StructField("device_id", StringType(), True),
        StructField("amount", DoubleType(), True),
        StructField("status", StringType(), True),
    ])

    kafka_df = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", "kafka:9093")
        .option("subscribe", "fraud-events")
        .option("startingOffsets", "earliest")
        .load()
    )

    parsed_df = (
        kafka_df
        .selectExpr("CAST(value AS STRING)")
        .select(from_json(col("value"), schema).alias("data"))
        .select("data.*")
    )

    query = (
        parsed_df.writeStream
        .outputMode("append")
        .foreachBatch(write_to_postgres)
        .option("checkpointLocation", "/tmp/fraud-risk-checkpoint-phase-4")
        .start()
    )

    query.awaitTermination()


if __name__ == "__main__":
    main()