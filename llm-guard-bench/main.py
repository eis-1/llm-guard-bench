"""
LLM Guard Bench: Adversarial Attack Benchmark Framework
Main orchestrator for executing security evaluations against LLMs.
"""

import asyncio
import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

# Core module imports - absolute paths per architectural constraints
from db.db import DatabaseManager
from core.loader import AttackLoader
from core.adapters import get_adapter
from core.models import AttackDefinition
from core.pipeline import BenchmarkPipeline
from analysis.aggregator import ResultsAggregator

# Standard production logger configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)


class LLMGuardBenchOrchestrator:
    """Production-grade orchestrator aligned with actual directory structure."""

    def __init__(
        self,
        target: str,
        judge: str,
        concurrency: int,
        categories: Optional[List[str]] = None,
    ):
        self.target = target
        self.judge = judge
        self.concurrency = concurrency
        self.categories = categories or []
        self.session_id = self._generate_session_id()
        self.logger = logging.getLogger(f"LLMGuardBench_{self.session_id}")

        self.db_manager: Optional[DatabaseManager] = None
        self.target_adapter = None
        self.judge_adapter = None
        self.benchmark_pipeline: Optional[BenchmarkPipeline] = None
        self.results_aggregator: Optional[ResultsAggregator] = None

    def _generate_session_id(self) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"SESS_{timestamp}"

    def _log_section(self, title: str) -> None:
        print(f"\n{'='*80}\n  {title}\n{'='*80}\n")

    async def load_environment(self) -> None:
        """Load environment variables from .env file."""
        self._log_section("Loading Environment Variables")
        load_dotenv()
        self.logger.info("Environment variables loaded successfully.")
        print(f"  Session ID: {self.session_id}")

    async def initialize_database(self) -> None:
        """Initialize database connection and run migrations."""
        self._log_section("Initializing Database")
        self.db_manager = DatabaseManager()
        await self.db_manager.connect()
        await self.db_manager.run_migrations()
        self.logger.info("Database initialized and migrations completed.")

    async def load_attack_definitions(self) -> List[AttackDefinition]:
        """Load attack definitions from config/prompts.json."""
        self._log_section("Loading Attack Definitions")
        prompts_path = Path("config/prompts.json")

        if not prompts_path.exists():
            self.logger.error(f"Attacks file not found at: {prompts_path}")
            raise FileNotFoundError(f"Attacks file not found: {prompts_path}")

        # Load attacks using the AttackLoader
        attacks = AttackLoader.load_prompts(
            str(prompts_path), 
            self.categories if self.categories else None
        )
        print(f"✓ Loaded {len(attacks)} attack definitions successfully.")
        return attacks

    async def initialize_adapters(self) -> None:
        """Initialize target and judge model adapters."""
        self._log_section("Initializing Network Adapters")
        print(f"  Target Model: {self.target}")
        print(f"  Judge Model:  {self.judge}")

        # Initialize target adapter
        self.target_adapter = get_adapter(
            os.getenv("TARGET_PROVIDER", "ollama"), 
            self.target
        )
        
        # Initialize judge adapter with API key
        self.judge_adapter = get_adapter(
            os.getenv("JUDGE_PROVIDER", "groq"), 
            self.judge, 
            os.getenv("GROQ_API_KEY")
        )

        print(f"✓ Target adapter initialized: {self.target_adapter.__class__.__name__}")
        print(f"✓ Judge adapter initialized: {self.judge_adapter.__class__.__name__}")

    async def run_benchmark(self, attacks: List[AttackDefinition]) -> list:
        """Execute the benchmark pipeline with comprehensive logging."""
        self._log_section("Running Concurrent Benchmark Evaluation")

        self.benchmark_pipeline = BenchmarkPipeline(
            target_adapter=self.target_adapter,
            judge_adapter=self.judge_adapter,
            db_manager=self.db_manager,
        )

        print(f"  Target Model: {self.target}")
        print(f"  Judge Model: {self.judge}")
        print(f"  Concurrency Level: {self.concurrency}")
        print(f"  Total Attack Vectors: {len(attacks)}\n")

        try:
            results = await self.benchmark_pipeline.run_benchmark(
                attacks=attacks,
                model_name=self.target,
                concurrency_limit=self.concurrency,
                session_id=self.session_id,
            )

            print(f"✓ Benchmark execution completed: {len(results)} results generated")
            print(f"  - Results: {len([r for r in results if r])} non-null")
            
            # Log result breakdown
            status_breakdown = {}
            for result in results:
                if result:
                    status = result.evaluation_status
                    status_breakdown[status] = status_breakdown.get(status, 0) + 1
            
            print("\n  Result Breakdown:")
            for status, count in sorted(status_breakdown.items()):
                print(f"    - {status}: {count}")
            
            self.logger.info(f"Benchmark completed with {len(results)} results")
            return results

        except Exception as e:
            self.logger.error(f"Benchmark pipeline execution failed: {str(e)}")
            print(f"\n✗ Benchmark failed: {str(e)}")
            return []

    async def aggregate_and_export_results(self) -> None:
        """Aggregate results and generate metrics/charts with robust error handling."""
        self._log_section("Aggregating Results & Exporting Metrics")
        self.logger.debug(f"Starting aggregation for session {self.session_id}")

        try:
            # CRITICAL: Database must be open and usable for aggregator
            if self.db_manager is None:
                self.logger.error("Database manager is None - cannot aggregate results")
                print("✗ Critical: Database manager not available")
                return

            self.logger.debug(f"Creating ResultsAggregator with db_manager: {type(self.db_manager)}")
            self.results_aggregator = ResultsAggregator(self.db_manager)
            
            self.logger.debug("Generating metrics summary...")
            metrics = await self.results_aggregator.generate_metrics_summary(
                self.session_id
            )
            self.logger.info(f"Metrics generated: total_runs={metrics.get('total_runs')}, vulnerable={metrics.get('total_vulnerable')}")

            # Display metrics with defensive formatting
            print("\n  Security Evaluation Metrics:")
            total_tests = metrics.get('total_runs', 0)
            successful = metrics.get('successful_runs', 0)
            vulnerable = metrics.get('total_vulnerable', 0)
            avg_time = metrics.get('average_execution_time', 0.0)
            
            print(f"    • Total Tests: {total_tests}")
            print(f"    • Successful Runs (Passed): {successful}")
            print(f"    • Total Vulnerable: {vulnerable}")
            print(f"    • Average Execution Time: {avg_time}s")
            self.logger.debug(f"Metrics display complete")

            if metrics.get("vulnerability_rates"):
                print("\n  Vulnerability Rates by Category:")
                for category, rates in sorted(metrics["vulnerability_rates"].items()):
                    rate = rates.get("rate", 0)
                    vulnerable_count = rates.get("vulnerable", 0)
                    passed_count = rates.get("passed", 0)
                    print(
                        f"    • {category}: {rate}% vulnerable ({vulnerable_count} vulnerable, {passed_count} passed)"
                    )
                self.logger.debug(f"Displayed {len(metrics['vulnerability_rates'])} categories")
            else:
                print("\n  No category breakdown available")
                self.logger.debug("No vulnerability rates to display")

            # Ensure results directory exists
            results_dir = Path("results")
            results_dir.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Results directory ready: {results_dir.resolve()}")

            # Generate chart with explicit error handling and timeout
            chart_path = "results/vulnerability_report.png"
            self.logger.info(f"Starting chart generation at {chart_path}")
            
            try:
                # Use timeout to prevent chart generation from hanging
                chart_success = await asyncio.wait_for(
                    self.results_aggregator.plot_vulnerability_chart(
                        self.session_id, chart_path
                    ),
                    timeout=180.0
                )
                
                chart_exists = Path(chart_path).exists()
                if chart_success and chart_exists:
                    chart_size = Path(chart_path).stat().st_size
                    print(f"\n✓ Analytical charts generated and saved to: {chart_path}")
                    self.logger.info(f"Chart successfully created at {chart_path} ({chart_size} bytes)")
                else:
                    print(f"\n⚠ Chart generation incomplete: success={chart_success}, exists={chart_exists}")
                    self.logger.warning(f"Chart generation returned success={chart_success}, file exists={chart_exists}")
                    
            except asyncio.TimeoutError:
                self.logger.error("Chart generation timed out after 60 seconds")
                print(f"\n⚠ Chart generation timed out (60s limit)")
                print(f"  Results data saved, but chart generation was cancelled")
            except Exception as chart_err:
                self.logger.error(f"Chart generation error: {type(chart_err).__name__}: {str(chart_err)}", exc_info=True)
                print(f"\n⚠ Chart generation encountered an error: {type(chart_err).__name__}")
                print(f"  Error: {str(chart_err)[:100]}")
                print(f"  Continuing - metrics have been computed successfully")

            self.logger.info("Aggregation phase completed successfully")

        except Exception as e:
            self.logger.error(f"Aggregation phase error: {type(e).__name__}: {str(e)}", exc_info=True)
            print(f"\n✗ Aggregation phase failed: {type(e).__name__}")
            print(f"  {str(e)[:150]}")
            print("  Note: Benchmark data has been saved to database and JSON files")

    async def cleanup(self) -> None:
        """Clean up resources (database connections, etc)."""
        self.logger.debug("Starting cleanup phase")
        try:
            if self.db_manager:
                self.logger.debug("Closing database connection")
                await self.db_manager.disconnect()
                self.logger.info("Database connection closed successfully")
            else:
                self.logger.debug("No database manager to disconnect")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {type(e).__name__}: {str(e)}", exc_info=True)
            print(f"\n⚠ Cleanup error (non-fatal): {str(e)[:100]}")

    async def orchestrate(self) -> None:
        """Main orchestration method with comprehensive logging and error recovery."""
        exit_code = 0
        try:
            self.logger.info(f"="*80)
            self.logger.info(f"Starting orchestration session: {self.session_id}")
            self.logger.info(f"="*80)
            
            # Stage 1: Environment
            try:
                self.logger.debug("Stage 1: Loading environment variables...")
                await self.load_environment()
                self.logger.info("✓ Stage 1 Complete: Environment variables loaded")
            except Exception as e:
                self.logger.error(f"Stage 1 FAILED: {type(e).__name__}: {str(e)}", exc_info=True)
                print(f"\n✗ Environment loading failed: {str(e)}")
                return
            
            # Stage 2: Database
            try:
                self.logger.debug("Stage 2: Initializing database...")
                await self.initialize_database()
                self.logger.info("✓ Stage 2 Complete: Database initialized")
            except Exception as e:
                self.logger.error(f"Stage 2 FAILED: {type(e).__name__}: {str(e)}", exc_info=True)
                print(f"\n✗ Database initialization failed: {str(e)}")
                return
            
            # Stage 3: Load Attacks
            try:
                self.logger.debug("Stage 3: Loading attack definitions...")
                attacks = await self.load_attack_definitions()
                self.logger.info(f"✓ Stage 3 Complete: Loaded {len(attacks)} attack definitions")

                if not attacks:
                    self.logger.warning("No attack vectors loaded. Exiting pipeline.")
                    print("\n✗ No attack vectors available")
                    return
            except Exception as e:
                self.logger.error(f"Stage 3 FAILED: {type(e).__name__}: {str(e)}", exc_info=True)
                print(f"\n✗ Attack loading failed: {str(e)}")
                return

            # Stage 4: Initialize Adapters
            try:
                self.logger.debug("Stage 4: Initializing network adapters...")
                await self.initialize_adapters()
                self.logger.info("✓ Stage 4 Complete: Adapters initialized")
            except Exception as e:
                self.logger.error(f"Stage 4 FAILED: {type(e).__name__}: {str(e)}", exc_info=True)
                print(f"\n✗ Adapter initialization failed: {str(e)}")
                return
            
            # Stage 5: Run Benchmark (may have partial failures - continue anyway)
            try:
                self.logger.debug("Stage 5: Running benchmark pipeline...")
                await self.run_benchmark(attacks)
                self.logger.info("✓ Stage 5 Complete: Benchmark execution finished")
            except Exception as e:
                self.logger.error(f"Stage 5 WARNING: {type(e).__name__}: {str(e)}", exc_info=True)
                print(f"\n⚠ Benchmark execution encountered errors: {str(e)[:100]}")
                print("  Attempting to aggregate available results...")
            
            # Stage 6: Aggregation (CRITICAL - keep database open)
            try:
                self.logger.debug("Stage 6: Aggregating results...")
                self.logger.info(f"Database manager state before aggregation: {type(self.db_manager)}")
                await self.aggregate_and_export_results()
                self.logger.info("✓ Stage 6 Complete: Results aggregated and exported")
            except Exception as e:
                self.logger.error(f"Stage 6 CRITICAL: {type(e).__name__}: {str(e)}", exc_info=True)
                print(f"\n✗ Aggregation failed: {type(e).__name__}")
                print(f"  {str(e)[:150]}")
                exit_code = 1

            # Final summary
            self._log_section("Benchmark Execution Complete")
            print(f"✓ Session {self.session_id} finalized successfully.\n")
            self.logger.info(f"Session {self.session_id} completed with exit_code={exit_code}")
            self.logger.info(f"="*80)

        except Exception as e:
            # This should never happen due to individual stage try-except blocks
            self.logger.critical(f"UNEXPECTED ERROR in orchestrate(): {type(e).__name__}: {str(e)}", exc_info=True)
            print(f"\n✗ FATAL: Unexpected pipeline error: {str(e)}")
            exit_code = 1
        
        finally:
            # Always cleanup, but don't let cleanup errors hide the real issue
            try:
                self.logger.debug("Finally block: Starting cleanup...")
                await self.cleanup()
                self.logger.info("Cleanup completed successfully")
            except Exception as cleanup_err:
                self.logger.error(f"Cleanup error (ignored): {type(cleanup_err).__name__}: {str(cleanup_err)}", exc_info=True)
                print(f"\n⚠ Note: Cleanup encountered a non-fatal error")
            
            if exit_code != 0:
                self.logger.error(f"Exiting with code {exit_code}")
                sys.exit(exit_code)


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="LLM Guard Bench: Adversarial Attack Benchmark Suite"
    )
    parser.add_argument(
        "--target", 
        type=str, 
        required=True, 
        help="Target LLM model name (e.g., 'llama3:8b', 'gpt-4')"
    )
    parser.add_argument(
        "--judge",
        type=str,
        default="llama-3.1-8b-instant",
        help="Judge LLM model name for evaluation",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Maximum concurrent benchmark executions",
    )
    parser.add_argument(
        "--categories",
        type=str,
        nargs="+",
        help="Filter attack vectors by category (DAN, ROLEPLAY_EXPLOIT, PROMPT_INJECTION, etc)",
    )
    return parser.parse_args()


async def main() -> None:
    """Main entry point."""
    args = parse_arguments()
    orchestrator = LLMGuardBenchOrchestrator(
        target=args.target,
        judge=args.judge,
        concurrency=args.concurrency,
        categories=args.categories,
    )
    await orchestrator.orchestrate()


if __name__ == "__main__":
    asyncio.run(main())
