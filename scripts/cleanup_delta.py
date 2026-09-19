from pyspark.sql import SparkSession

DELTA_PATH = "/app/storage/delta_tables/youtube_enriched"

spark = (
    SparkSession.builder
    .appName("Delta7DayCleanup")
    .master("local[*]")
    .config(
        "spark.sql.extensions",
        "io.delta.sql.DeltaSparkSessionExtension"
    )
    .config(
        "spark.sql.catalog.spark_catalog",
        "org.apache.spark.sql.delta.catalog.DeltaCatalog"
    )
    .config(
        "spark.jars",
        "jars/delta-core_2.12-2.4.0.jar,"
        "jars/delta-storage-2.4.0.jar,"
        "jars/spark-sql-kafka-0-10_2.12-3.4.1.jar,"
        "jars/spark-token-provider-kafka-0-10_2.12-3.4.1.jar,"
        "jars/kafka-clients-3.4.1.jar,"
        "jars/commons-pool2-2.11.1.jar"
    )
    .config(
        "spark.databricks.delta.retentionDurationCheck.enabled",
        "false"
    )
    .getOrCreate()
)

spark.sparkContext.setLogLevel("WARN")

print("Deleting records older than 7 days...")

spark.sql(f"""
    DELETE FROM delta.`{DELTA_PATH}`
    WHERE CAST(collected_at AS TIMESTAMP)
          < current_timestamp() - INTERVAL 7 DAYS
""")

print("Running VACUUM...")

spark.sql(f"""
    VACUUM delta.`{DELTA_PATH}` RETAIN 0 HOURS
""")

print("7-day Delta cleanup completed.")

spark.stop()
