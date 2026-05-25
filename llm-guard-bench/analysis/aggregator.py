import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import select, func
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    AsyncSession = None

logger = logging.getLogger(__name__)


class ResultsAggregator:
    """
    Aggregates benchmark results from SQLite database and generates metrics and visualizations.
    """

    def __init__(self, db_manager_or_path: Union[str, Path, object]):
        """
        Initialize the ResultsAggregator.

        Args:
            db_manager_or_path: Path to SQLite database (str/Path) or db_manager instance
        """
        self.db_manager = db_manager_or_path
        self.db_path = None

        if isinstance(db_manager_or_path, (str, Path)):
            self.db_path = Path(db_manager_or_path)
            self.db_manager = None
        else:
            if hasattr(db_manager_or_path, "engine"):
                self.db_manager = db_manager_or_path
            elif hasattr(db_manager_or_path, "db_path"):
                self.db_path = Path(db_manager_or_path.db_path)

        logger.info(f"ResultsAggregator initialized with database: {self.db_path or 'db_manager'}")

    async def generate_metrics_summary(self, session_id: str) -> dict:
        """
        Generate comprehensive metrics summary for a given session.

        Queries the database for rows matching the session_id and computes:
        - Vulnerability rates per category
        - Average execution times
        - Total successful runs

        Args:
            session_id: The session identifier to query

        Returns:
            Dictionary containing metrics summary
        """
        try:
            results = await self._query_results_by_session(session_id)

            if not results:
                logger.warning(f"No results found for session_id: {session_id}")
                return {
                    "session_id": session_id,
                    "total_runs": 0,
                    "successful_runs": 0,
                    "vulnerability_rates": {},
                    "average_execution_time": 0.0,
                    "categories": [],
                    "error": "No results found"
                }

            metrics = self._compute_metrics(results)
            logger.info(f"Generated metrics summary for session {session_id}")
            return metrics

        except Exception as e:
            logger.error(f"Error generating metrics summary for session {session_id}: {str(e)}")
            return {
                "session_id": session_id,
                "error": str(e)
            }

    async def plot_vulnerability_chart(
        self,
        session_id: str,
        output_path: str = "results/vulnerability_report.png"
    ) -> bool:
        """
        Generate a professional bar chart visualizing vulnerability results by category.

        Creates a grouped bar chart showing VULNERABLE vs PASSED counts across attack categories.

        Args:
            session_id: The session identifier to query
            output_path: Path where the chart image will be saved

        Returns:
            True if successful, False otherwise
        """
        try:
            results = await self._query_results_by_session(session_id)

            if not results:
                logger.warning(f"No results found for session_id: {session_id} - skipping chart generation")
                return False

            # Aggregate data by category and status
            category_data = self._aggregate_by_category(results)

            # Generate chart in background thread
            success = await self._generate_chart_async(category_data, output_path)
            return success

        except Exception as e:
            logger.error(f"Error plotting vulnerability chart for session {session_id}: {str(e)}")
            return False

    async def _query_results_by_session(self, session_id: str) -> List[Dict]:
        """
        Query results from database matching the session_id.

        Args:
            session_id: The session identifier

        Returns:
            List of result dictionaries
        """
        try:
            if self.db_manager and hasattr(self.db_manager, "session"):
                return await self._query_with_orm(session_id)
            elif self.db_path:
                return await self._query_with_sqlite(session_id)
            else:
                logger.error("No database connection available")
                return []
        except Exception as e:
            logger.error(f"Database query error: {str(e)}")
            return []

    async def _query_with_orm(self, session_id: str) -> List[Dict]:
        """Query using SQLAlchemy ORM if available."""
        try:
            async with self.db_manager.session() as session:
                # Assuming a 'Result' or 'BenchmarkResult' table exists
                # This is a generic implementation that assumes standard ORM structure
                query = select("*").select_from("results").where(f"session_id = '{session_id}'")
                result = await session.execute(query)
                rows = result.fetchall()
                return [dict(row) for row in rows] if rows else []
        except Exception as e:
            logger.error(f"ORM query failed: {str(e)}")
            return []

    async def _query_with_sqlite(self, session_id: str) -> List[Dict]:
        """Query SQLite database directly."""
        try:
            import sqlite3
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Query benchmark results matching session_id
            cursor.execute(
                "SELECT * FROM results WHERE session_id = ?",
                (session_id,)
            )
            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows] if rows else []
        except Exception as e:
            logger.error(f"SQLite query failed: {str(e)}")
            return []

    def _compute_metrics(self, results: List[Dict]) -> Dict:
        """
        Compute metrics from query results.

        Args:
            results: List of result records

        Returns:
            Dictionary with computed metrics
        """
        if not results:
            return {}

        total_runs = len(results)
        successful_runs = sum(1 for r in results if r.get("status") == "PASSED")
        total_vulnerable = sum(1 for r in results if r.get("status") == "VULNERABLE")

        # Compute vulnerability rates per category
        category_stats = defaultdict(lambda: {"vulnerable": 0, "passed": 0, "total": 0})
        execution_times = []

        for result in results:
            category = result.get("category", "unknown")
            status = result.get("status", "unknown")
            execution_time = result.get("execution_time", 0.0)

            category_stats[category]["total"] += 1
            if status == "VULNERABLE":
                category_stats[category]["vulnerable"] += 1
            elif status == "PASSED":
                category_stats[category]["passed"] += 1

            if isinstance(execution_time, (int, float)):
                execution_times.append(execution_time)

        # Calculate vulnerability rates per category
        vulnerability_rates = {}
        for category, stats in category_stats.items():
            if stats["total"] > 0:
                vulnerability_rates[category] = {
                    "rate": stats["vulnerable"] / stats["total"],
                    "vulnerable": stats["vulnerable"],
                    "passed": stats["passed"],
                    "total": stats["total"]
                }

        avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0.0

        return {
            "session_id": results[0].get("session_id", "unknown") if results else "unknown",
            "total_runs": total_runs,
            "successful_runs": successful_runs,
            "total_vulnerable": total_vulnerable,
            "vulnerability_rates": vulnerability_rates,
            "average_execution_time": round(avg_execution_time, 4),
            "categories": list(vulnerability_rates.keys()),
            "timestamp": results[0].get("timestamp", None) if results else None
        }

    def _aggregate_by_category(self, results: List[Dict]) -> Dict[str, Dict[str, int]]:
        """
        Aggregate results by category and status.

        Args:
            results: List of result records

        Returns:
            Dictionary with aggregated counts by category and status
        """
        category_data = defaultdict(lambda: {"VULNERABLE": 0, "PASSED": 0})

        for result in results:
            category = result.get("category", "unknown")
            status = result.get("status", "unknown")

            if status in ["VULNERABLE", "PASSED"]:
                category_data[category][status] += 1

        return dict(category_data)

    async def _generate_chart_async(self, category_data: Dict[str, Dict[str, int]], output_path: str) -> bool:
        """
        Generate chart asynchronously in a background thread.

        Args:
            category_data: Aggregated data by category
            output_path: Path to save the chart

        Returns:
            True if successful, False otherwise
        """
        try:
            # Run plotting in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._create_vulnerability_chart,
                category_data,
                output_path
            )
            return result
        except Exception as e:
            logger.error(f"Async chart generation failed: {str(e)}")
            return False

    def _create_vulnerability_chart(self, category_data: Dict[str, Dict[str, int]], output_path: str) -> bool:
        """
        Create and save the vulnerability chart.

        Args:
            category_data: Aggregated data by category
            output_path: Path to save the chart

        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure output directory exists
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Prepare data for plotting
            categories = sorted(category_data.keys())
            vulnerable_counts = [category_data[cat].get("VULNERABLE", 0) for cat in categories]
            passed_counts = [category_data[cat].get("PASSED", 0) for cat in categories]

            # Create figure and axis
            fig, ax = plt.subplots(figsize=(14, 7))

            # Set up bar positions
            x = range(len(categories))
            width = 0.35

            # Create bars
            bars1 = ax.bar(
                [i - width/2 for i in x],
                vulnerable_counts,
                width,
                label="VULNERABLE",
                color="#d62728",
                alpha=0.8,
                edgecolor="black",
                linewidth=1.2
            )

            bars2 = ax.bar(
                [i + width/2 for i in x],
                passed_counts,
                width,
                label="PASSED",
                color="#2ca02c",
                alpha=0.8,
                edgecolor="black",
                linewidth=1.2
            )

            # Add value labels on bars
            for bar in bars1:
                height = bar.get_height()
                if height > 0:
                    ax.text(
                        bar.get_x() + bar.get_width()/2.,
                        height,
                        f"{int(height)}",
                        ha="center",
                        va="bottom",
                        fontsize=9,
                        fontweight="bold"
                    )

            for bar in bars2:
                height = bar.get_height()
                if height > 0:
                    ax.text(
                        bar.get_x() + bar.get_width()/2.,
                        height,
                        f"{int(height)}",
                        ha="center",
                        va="bottom",
                        fontsize=9,
                        fontweight="bold"
                    )

            # Customize chart
            ax.set_xlabel("Attack Categories", fontsize=12, fontweight="bold")
            ax.set_ylabel("Count", fontsize=12, fontweight="bold")
            ax.set_title("LLM Guard Bench: Vulnerability Results by Category", fontsize=14, fontweight="bold")
            ax.set_xticks(x)
            ax.set_xticklabels(categories, rotation=45, ha="right")
            ax.legend(fontsize=11, loc="upper right")
            ax.grid(axis="y", alpha=0.3, linestyle="--")

            # Tight layout
            fig.tight_layout()

            # Save figure
            fig.savefig(output_path, dpi=300, bbox_inches="tight", facecolor="white")
            plt.close(fig)

            logger.info(f"Vulnerability chart saved to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Error creating vulnerability chart: {str(e)}")
            return False
