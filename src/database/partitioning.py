"""PostgreSQL partitioning utilities (TODO #50).

Provides table partitioning for large tables to improve query performance.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from loguru import logger


class TablePartitioner:
    """Manage table partitions for PostgreSQL (TODO #50)."""

    def __init__(self, crud) -> None:
        self.crud = crud

    async def create_partitions(
        self,
        table_name: str,
        partition_column: str = "created_at",
        interval_days: int = 30,
        num_partitions: int = 12,
    ) -> list[str]:
        """Create time-based partitions for a table.

        Args:
            table_name: name of the table to partition.
            partition_column: column to partition on.
            interval_days: days per partition.
            num_partitions: number of partitions to create.

        Returns:
            List of created partition names.
        """
        created = []
        now = datetime.utcnow()

        for i in range(num_partitions):
            start = now + timedelta(days=i * interval_days)
            end = start + timedelta(days=interval_days)
            partition_name = f"{table_name}_{start.strftime('%Y%m%d')}"

            try:
                async with self.crud._session() as session:
                    # Use native PostgreSQL partitioning
                    await session.execute(f"""
                        CREATE TABLE IF NOT EXISTS {partition_name}
                        PARTITION OF {table_name}
                        FOR VALUES FROM ('{start.isoformat()}') TO ('{end.isoformat()}')
                    """)
                    await session.commit()
                    created.append(partition_name)
                    logger.debug(f"Created partition: {partition_name}")
            except Exception as e:
                logger.warning(f"Partition creation failed for {partition_name}: {e}")

        logger.info(f"Created {len(created)} partitions for {table_name}")
        return created

    async def drop_old_partitions(
        self,
        table_name: str,
        keep_months: int = 6,
    ) -> list[str]:
        """Drop partitions older than retention period.

        Args:
            table_name: name of the partitioned table.
            keep_months: months of data to keep.

        Returns:
            List of dropped partition names.
        """
        dropped = []
        cutoff = datetime.utcnow() - timedelta(days=keep_months * 30)

        try:
            async with self.crud._session() as session:
                # Get list of partitions
                result = await session.execute(f"""
                    SELECT tablename FROM pg_tables
                    WHERE tablename LIKE '{table_name}_%'
                    AND tablename ~ '{table_name}_\\d{{8}}'
                """)
                partitions = result.fetchall()

                for (pname,) in partitions:
                    # Extract date from partition name
                    try:
                        date_str = pname.replace(f"{table_name}_", "")
                        part_date = datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=UTC)
                        if part_date < cutoff:
                            await session.execute(f"DROP TABLE IF EXISTS {pname}")
                            dropped.append(pname)
                            logger.debug(f"Dropped old partition: {pname}")
                    except ValueError:
                        continue

                await session.commit()
        except Exception as e:
            logger.warning(f"Partition cleanup failed: {e}")

        if dropped:
            logger.info(f"Dropped {len(dropped)} old partitions from {table_name}")
        return dropped
