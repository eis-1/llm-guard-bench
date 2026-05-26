"""
Results aggregation and metrics computation for LLM Guard Bench.

Queries SQLite database for benchmark results and generates metrics and visualizations.
Includes fallback to JSON files if database queries fail.
"""

import asyncio
import json
import logging
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Union
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


class ResultsAggregator:
    """
    Aggregates benchmark results from SQLite database with JSON fallback.
    Generates metrics and vulnerability visualizations.
    """

    def __init__(self, db_manager_or_path: Union[str, Path, object]):
        """
        Initialize the ResultsAggregator.

        Args:
            db_manager_or_path: Database manager instance, path, or file path string
        """
        self.db_manager = None
        self.db_path = None

        if isinstance(db_manager_or_path, (str, Path)):
            self.db_path = Path(db_manager_or_path)
        elif hasattr(db_manager_or_path, "_db_path"):
            self.db_manager = db_manager_or_path
            self.db_path = db_manager_or_path._db_path
        else:
            self.db_manager = db_manager_or_path
            if hasattr(db_manager_or_path, "_db_path"):
                self.db_path = db_manager_or_path._db_path

        logger.info(
            f"ResultsAggregator initialized with database: {self.db_path}"
        )

    async def generate_metrics_summary(self, session_id: str) -> dict:
        """
        Generate comprehensive metrics summary for a given session.

        Args:
            session_id: The session identifier to query

        Returns:
            Dictionary containing metrics summary with fallback to JSON if DB fails
        """
        try:
            results = await self._query_results_by_session(session_id)

            if not results:
                logger.warning(
                    f"No results found in database for session {session_id}, trying JSON fallback"
                )
                results = self._load_results_from_json(session_id)

            if not results:
                logger.warning(f"No results found for session_id: {session_id}")
                return {
                    "session_id": session_id,
                    "total_runs": 0,
                    "successful_runs": 0,
                    "total_vulnerable": 0,
                    "vulnerability_rates": {},
                    "average_execution_time": 0.0,
                    "categories": [],
                    "error": "No results found in database or JSON files",
                }

            metrics = self._compute_metrics(results, session_id)
            logger.info(f"Generated metrics summary for session {session_id}")
            return metrics

        except Exception as e:
            logger.error(
                f"Error generating metrics summary for session {session_id}: {str(e)}"
            )
            return {
                "session_id": session_id,
                "error": str(e),
                "total_runs": 0,
            }

    async def plot_vulnerability_chart(
        self, session_id: str, output_path: str = "results/vulnerability_report.png"
    ) -> bool:
        """
        Generate vulnerability results chart.

        Creates a grouped bar chart showing VULNERABLE vs PASSED counts by category.

        Args:
            session_id: The session identifier to query
            output_path: Path where the chart image will be saved

        Returns:
            True if successful, False otherwise
        """
        try:
            results = await self._query_results_by_session(session_id)

            if not results:
                logger.warning(
                    f"No database results for session {session_id}, trying JSON fallback"
                )
                results = self._load_results_from_json(session_id)

            if not results:
                logger.warning(
                    f"No results found for session {session_id} - creating empty placeholder chart"
                )
                # Create an empty chart as placeholder
                success = await self._generate_chart_async({}, output_path)
                return success

            # Aggregate data by category and status
            category_data = self._aggregate_by_category(results)

            # Generate chart in background thread
            success = await self._generate_chart_async(category_data, output_path)
            return success

        except Exception as e:
            logger.error(
                f"Error plotting vulnerability chart for session {session_id}: {str(e)}"
            )
            # Attempt to create placeholder chart even on error
            try:
                success = await self._generate_chart_async({}, output_path)
                return success
            except Exception as e2:
                logger.error(f"Failed to create placeholder chart: {str(e2)}")
                return False

    async def _query_results_by_session(self, session_id: str) -> List[Dict]:
        """
        Query results from database matching the session_id with timeout protection.

        Args:
            session_id: The session identifier

        Returns:
            List of result dictionaries from database, or empty list on failure
        """
        try:
            if not self.db_path:
                logger.debug("Database path is None")
                return []
            
            if not self.db_path.exists():
                logger.debug(f"Database file not found at {self.db_path}")
                return []
            
            # Add timeout to prevent indefinite database queries
            try:
                results = await asyncio.wait_for(
                    self._query_sqlite(session_id),
                    timeout=15.0
                )
                return results if results else []
            except asyncio.TimeoutError:
                logger.error(f"Database query timed out after 15 seconds for session {session_id}")
                return []
                
        except Exception as e:
            logger.error(f"Database query error ({type(e).__name__}): {str(e)}")
            return []

    async def _query_sqlite(self, session_id: str) -> List[Dict]:
        """
        Query SQLite database directly for results.

        Args:
            session_id: The session identifier

        Returns:
            List of result dictionaries
        """
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None, self._sync_query_sqlite, session_id
            )
            return results if results else []
        except Exception as e:
            logger.error(f"Async SQLite query failed: {str(e)}")
            return []

    def _sync_query_sqlite(self, session_id: str) -> List[Dict]:
        """
        Synchronous SQLite query (runs in executor).

        Args:
            session_id: The session identifier

        Returns:
            List of result dictionaries
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Query test_results table with correct column names (v3.0)
            cursor.execute(
                """
                SELECT 
                    session_id, timestamp, model_name, attack_id, category,
                    adversarial_prompt, system_prompt, raw_llm_response,
                    evaluation_status, evaluation_stage, judge_verdict,
                    judge_parse_error, execution_time_ms, total_time_ms,
                    prompt_tokens, completion_tokens, error_message
                FROM test_results 
                WHERE session_id = ?
                ORDER BY timestamp ASC
                """,
                (session_id,),
            )
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                logger.debug(f"No test_results found for session {session_id}")
                return []

            results = [dict(row) for row in rows]
            logger.info(f"Loaded {len(results)} results from database for session {session_id}")
            return results

        except Exception as e:
            logger.error(f"SQLite query error: {str(e)}")
            return []

    def _load_results_from_json(self, session_id: str) -> List[Dict]:
        """
        Load results from JSON files in results/ directory as fallback.

        Args:
            session_id: The session identifier

        Returns:
            List of result dictionaries from JSON files
        """
        try:
            results_dir = Path("results")
            jsonl_file = results_dir / f"session_{session_id}.jsonl"

            if not jsonl_file.exists():
                logger.debug(f"JSON file not found: {jsonl_file}")
                return []

            results = []
            with open(jsonl_file, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        if line.strip():
                            record = json.loads(line)
                            results.append(record)
                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"Failed to parse JSON line {line_num} in {jsonl_file}: {str(e)}"
                        )

            logger.info(
                f"Loaded {len(results)} results from JSON file {jsonl_file}"
            )
            return results

        except Exception as e:
            logger.error(f"JSON loading error: {str(e)}")
            return []

    def _compute_metrics(self, results: List[Dict], session_id: str) -> Dict:
        """
        Compute metrics from results.

        Args:
            results: List of result records
            session_id: Session identifier

        Returns:
            Dictionary with computed metrics
        """
        if not results:
            return {
                "session_id": session_id,
                "total_runs": 0,
                "successful_runs": 0,
                "total_vulnerable": 0,
                "vulnerability_rates": {},
                "average_execution_time": 0.0,
                "categories": [],
            }

        total_runs = len(results)
        successful_runs = sum(
            1 for r in results if r.get("evaluation_status") == "PASSED"
        )
        total_vulnerable = sum(
            1 for r in results if r.get("evaluation_status") == "VULNERABLE"
        )

        # Compute vulnerability rates per category
        category_stats = defaultdict(
            lambda: {"vulnerable": 0, "passed": 0, "total": 0}
        )
        execution_times = []

        for result in results:
            category = result.get("category", "unknown")
            status = result.get("evaluation_status", "unknown")
            execution_time = result.get("execution_time_ms", 0)

            category_stats[category]["total"] += 1
            if status == "VULNERABLE":
                category_stats[category]["vulnerable"] += 1
            elif status == "PASSED":
                category_stats[category]["passed"] += 1

            if isinstance(execution_time, (int, float)) and execution_time > 0:
                execution_times.append(execution_time / 1000.0)

        # Calculate vulnerability rates per category
        vulnerability_rates = {}
        for category, stats in category_stats.items():
            if stats["total"] > 0:
                vulnerability_rates[category] = {
                    "rate": round(
                        stats["vulnerable"] / stats["total"] * 100, 2
                    ),
                    "vulnerable": stats["vulnerable"],
                    "passed": stats["passed"],
                    "total": stats["total"],
                }

        avg_execution_time = (
            round(sum(execution_times) / len(execution_times), 2)
            if execution_times
            else 0.0
        )

        return {
            "session_id": session_id,
            "total_runs": total_runs,
            "successful_runs": successful_runs,
            "total_vulnerable": total_vulnerable,
            "vulnerability_rates": vulnerability_rates,
            "average_execution_time": avg_execution_time,
            "categories": list(vulnerability_rates.keys()),
        }

    def _aggregate_by_category(
        self, results: List[Dict]
    ) -> Dict[str, Dict[str, int]]:
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
            status = result.get("evaluation_status", "unknown")

            if status in ["VULNERABLE", "PASSED"]:
                category_data[category][status] += 1

        return dict(category_data)

    async def _generate_chart_async(
        self, category_data: Dict[str, Dict[str, int]], output_path: str
    ) -> bool:
        """
        Generate chart asynchronously in executor.

        Args:
            category_data: Aggregated data by category
            output_path: Path to save the chart

        Returns:
            True if successful, False otherwise
        """
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._create_vulnerability_chart, category_data, output_path
            )
            return result
        except Exception as e:
            logger.error(f"Async chart generation failed: {str(e)}")
            return False

    def _create_vulnerability_chart(
        self, category_data: Dict[str, Dict[str, int]], output_path: str
    ) -> bool:
        """
        Create and save the vulnerability chart with explicit error handling.

        Args:
            category_data: Aggregated data by category
            output_path: Path to save the chart

        Returns:
            True if successful, False otherwise
        """
        output_file = None
        fig = None
        try:
            logger.debug(f"Starting chart creation for output: {output_path}")
            
            # Ensure output directory exists
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Output directory ready: {output_file.parent.resolve()}")

            # Create figure and axis
            fig, ax = plt.subplots(figsize=(14, 7))
            logger.debug("Matplotlib figure created")

            if category_data:
                # Prepare data for plotting
                categories = sorted(category_data.keys())
                vulnerable_counts = [
                    category_data[cat].get("VULNERABLE", 0) for cat in categories
                ]
                passed_counts = [
                    category_data[cat].get("PASSED", 0) for cat in categories
                ]

                # Set up bar positions
                x = range(len(categories))
                width = 0.35

                # Create bars
                bars1 = ax.bar(
                    [i - width / 2 for i in x],
                    vulnerable_counts,
                    width,
                    label="VULNERABLE",
                    color="#d62728",
                    alpha=0.8,
                    edgecolor="black",
                    linewidth=1.2,
                )

                bars2 = ax.bar(
                    [i + width / 2 for i in x],
                    passed_counts,
                    width,
                    label="PASSED",
                    color="#2ca02c",
                    alpha=0.8,
                    edgecolor="black",
                    linewidth=1.2,
                )

                # Add value labels on bars
                for bar in bars1:
                    height = bar.get_height()
                    if height > 0:
                        ax.text(
                            bar.get_x() + bar.get_width() / 2.0,
                            height,
                            f"{int(height)}",
                            ha="center",
                            va="bottom",
                            fontsize=9,
                            fontweight="bold",
                        )

                for bar in bars2:
                    height = bar.get_height()
                    if height > 0:
                        ax.text(
                            bar.get_x() + bar.get_width() / 2.0,
                            height,
                            f"{int(height)}",
                            ha="center",
                            va="bottom",
                            fontsize=9,
                            fontweight="bold",
                        )

                # Customize chart
                ax.set_xlabel("Attack Categories", fontsize=12, fontweight="bold")
                ax.set_ylabel("Count", fontsize=12, fontweight="bold")
                ax.set_title(
                    "LLM Guard Bench: Vulnerability Results by Category",
                    fontsize=14,
                    fontweight="bold",
                )
                ax.set_xticks(x)
                ax.set_xticklabels(categories, rotation=45, ha="right")
                ax.legend(fontsize=11, loc="upper right")
                ax.grid(axis="y", alpha=0.3, linestyle="--")
            else:
                # Empty chart placeholder
                ax.text(
                    0.5,
                    0.5,
                    "No Results Available",
                    ha="center",
                    va="center",
                    fontsize=16,
                    fontweight="bold",
                    transform=ax.transAxes,
                )
                ax.set_title(
                    "LLM Guard Bench: Vulnerability Results by Category",
                    fontsize=14,
                    fontweight="bold",
                )
                ax.axis("off")

            # Tight layout and save
            fig.tight_layout()
            fig.savefig(
                output_path, dpi=300, bbox_inches="tight", facecolor="white"
            )
            logger.debug(f"Chart saved to {output_path}")
            plt.close(fig)
            plt.clf()

            logger.info(f"Vulnerability chart successfully created at {output_path}")
            return True

        except PermissionError as e:
            logger.error(f"Permission denied saving chart to {output_path}: {str(e)}")
            return False
        except OSError as e:
            logger.error(f"OS error creating chart: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error creating vulnerability chart: {type(e).__name__}: {str(e)}")
            return False
        finally:
            # Ensure all matplotlib resources are cleaned up
            try:
                if fig is not None:
                    plt.close(fig)
                plt.clf()
                logger.debug("Matplotlib resources cleaned up")
            except Exception as cleanup_err:
                logger.debug(f"Note during matplotlib cleanup: {cleanup_err}")
