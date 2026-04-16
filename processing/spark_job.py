import os
from dotenv import load_dotenv
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    when,
    to_timestamp,
    sum as spark_sum,
    max as spark_max,
    count as spark_count,
    countDistinct,
    avg
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
        .appName("fraud-risk-platform-phase-2")
        .config("spark.jars.packages", "org.postgresql:postgresql:42.7.3")
        .getOrCreate()
    )


def main() -> None:
    spark = build_spark()

    df = (
        spark.read.option("header", True).csv("/app/data/events.csv")
        .withColumn("timestamp", to_timestamp(col("timestamp")))
        .withColumn("amount", col("amount").cast("double"))
    )

    enriched = (
        df.withColumn("failed_login_flag", when(col("event_type") == "login_failed", 1).otherwise(0))
          .withColumn("password_reset_flag", when(col("event_type") == "password_reset", 1).otherwise(0))
          .withColumn("withdrawal_flag", when(col("event_type") == "withdrawal", 1).otherwise(0))
          .withColumn("mfa_disabled_flag", when(col("event_type") == "mfa_disabled", 1).otherwise(0))
          .withColumn("large_withdrawal_flag", when((col("event_type") == "withdrawal") & (col("amount") >= 5000), 1).otherwise(0))
    )

    user_summary = (
        enriched.groupBy("user_id")
        .agg(
            spark_sum("failed_login_flag").alias("failed_login_count"),
            spark_max("password_reset_flag").alias("has_password_reset"),
            spark_max("withdrawal_flag").alias("has_withdrawal"),
            spark_max("mfa_disabled_flag").alias("has_mfa_disabled"),
            spark_max("large_withdrawal_flag").alias("has_large_withdrawal"),
            spark_sum("amount").alias("total_amount"),
            countDistinct("device_id").alias("distinct_device_count"),
            countDistinct("location").alias("distinct_location_count"),
            spark_count("*").alias("event_count")
        )
        .withColumn("new_device_flag", when(col("distinct_device_count") > 1, 1).otherwise(0))
        .withColumn("new_location_flag", when(col("distinct_location_count") > 1, 1).otherwise(0))
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
            + col("new_device_flag") * 10
            + col("new_location_flag") * 10
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

    alerts = user_summary.filter(col("risk_level").isin("high", "critical"))

    risk_distribution = (
        user_summary.groupBy("risk_level")
        .agg(spark_count("*").alias("user_count"))
        .orderBy("risk_level")
    )

    risk_overview = (
        user_summary.agg(
            spark_count("*").alias("total_users"),
            avg("risk_score").alias("avg_risk_score"),
            spark_sum(when(col("risk_level") == "critical", 1).otherwise(0)).alias("critical_users"),
            spark_sum(when(col("risk_level").isin("high", "critical"), 1).otherwise(0)).alias("alerted_users")
        )
    )

    risk_by_location = (
        df.groupBy("location")
        .agg(
            spark_count("*").alias("event_count"),
            spark_sum(when(col("event_type") == "withdrawal", 1).otherwise(0)).alias("withdrawal_count"),
            spark_sum(when((col("event_type") == "withdrawal") & (col("amount") >= 5000), 1).otherwise(0)).alias("large_withdrawal_count")
        )
        .orderBy(col("large_withdrawal_count").desc(), col("event_count").desc())
    )

    event_type_summary = (
        df.groupBy("event_type")
        .agg(spark_count("*").alias("event_count"))
        .orderBy(col("event_count").desc())
    )

    user_summary.write.jdbc(
        url=JDBC_URL,
        table="user_risk_summary",
        mode="overwrite",
        properties=JDBC_PROPERTIES,
    )

    alerts.write.jdbc(
        url=JDBC_URL,
        table="alert_users",
        mode="overwrite",
        properties=JDBC_PROPERTIES,
    )

    risk_distribution.write.jdbc(
        url=JDBC_URL,
        table="risk_distribution",
        mode="overwrite",
        properties=JDBC_PROPERTIES,
    )

    risk_overview.write.jdbc(
        url=JDBC_URL,
        table="risk_overview",
        mode="overwrite",
        properties=JDBC_PROPERTIES,
    )

    risk_by_location.write.jdbc(
        url=JDBC_URL,
        table="risk_by_location",
        mode="overwrite",
        properties=JDBC_PROPERTIES,
    )

    event_type_summary.write.jdbc(
        url=JDBC_URL,
        table="event_type_summary",
        mode="overwrite",
        properties=JDBC_PROPERTIES,
    )

    print("Wrote tables:")
    print("- user_risk_summary")
    print("- alert_users")
    print("- risk_distribution")
    print("- risk_overview")
    print("- risk_by_location")
    print("- event_type_summary")

    user_summary.show(truncate=False)
    alerts.show(truncate=False)

    spark.stop()


if __name__ == "__main__":
    main()