import os
from dotenv import load_dotenv
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, when, to_timestamp, sum as spark_sum, max as spark_max

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
        .appName("fraud-risk-platform")
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
        )
        .withColumn(
            "risk_score",
            col("failed_login_count") * 10
            + col("has_password_reset") * 20
            + col("has_large_withdrawal") * 30
            + col("has_mfa_disabled") * 25
        )
        .withColumn(
            "risk_level",
            when(col("risk_score") >= 60, "critical")
            .when(col("risk_score") >= 35, "high")
            .when(col("risk_score") >= 15, "medium")
            .otherwise("low")
        )
    )

    alerts = user_summary.filter(col("risk_level").isin("high", "critical"))

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

    print("Wrote tables: user_risk_summary, alert_users")
    user_summary.show(truncate=False)
    alerts.show(truncate=False)

    spark.stop()


if __name__ == "__main__":
    main()