import asyncio
import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from dotenv import load_dotenv
import sys

# Import core components
from src.database.manager import DatabaseManager
from src.loaders.attack_loader import AttackLoader
from src.adapters.factory import get_adapter
from src.pipeline.benchmark import BenchmarkPipeline
from src.results.aggregator import ResultsAggregator
from src.utils.logger import Logger


class LLMGuardBenchOrchestrator:
    """Production-grade orchestrator for LLM Guard Bench evaluation."""

    def __init__(
        self,
        target: str,
        judge: str,
        concurrency: int,
        categories: Optional[List[str]] = None,
    ):
        """Initialize the orchestrator with CLI arguments."""
        self.target = target
        self.judge = judge
        self.concurrency = concurrency
        self.categories = categories or []
        self.session_id = self._generate_session_id()
        self.logger = Logger(self.session_id)
        
        self.db_manager: Optional[DatabaseManager] = None
        self.target_adapter = None
        self.judge_adapter = None
        self.benchmark_pipeline: Optional[BenchmarkPipeline] = None
        self.results_aggregator: Optional[ResultsAggregator] = None

    def _generate_session_id(self) -> str:
        """Generate a unique, structured session ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        return f"SESS_{timestamp}"

    def _log_section(self, title: str) -> None:
        """Print a formatted section header."""
        print(f"\n{'='*80}")
        print(f"  {title}")
        print(f"{'='*80}\n")

    async def load_environment(self) -> None:
        """Load environment variables using python-dotenv."""
        self._log_section("Loading Environment Variables")
        load_dotenv()
        print(f"✓ Environment variables loaded")
        print(f"  Session ID: {self.session_id}")

    async def initialize_database(self) -> None:
        """Initialize DatabaseManager and run migrations."""
        self._log_section("Initializing Database")
        self.db_manager = DatabaseManager()
        await self.db_manager.connect()
        await self.db_manager.run_migrations()
        print(f"✓ Database initialized and migrations completed")

    async def load_attack_prompts(self) -> List[dict]:
        """Load target prompts from config/prompts.json using AttackLoader."""
        self._log_section("Loading Attack Prompts")
        
        prompts_path = Path("config/prompts.json")
        if not prompts_path.exists():
            self.logger.error(f"Prompts file not found: {prompts_path}")
            raise FileNotFoundError(f"Prompts file not found: {prompts_path}")
        
        with open(prompts_path, "r") as f:
            prompts_data = json.load(f)
        
        loader = AttackLoader(prompts_data)
        prompts = loader.load()
        
        # Filter by categories if specified
        if self.categories:
            prompts = [p for p in prompts if p.get("category") in self.categories]
            print(f"✓ Loaded {len(prompts)} prompts (filtered by {len(self.categories)} categories)")
        else:
            print(f"✓ Loaded {len(prompts)} prompts")
        
        # Print summary table
        self._print_prompts_summary(prompts)
        return prompts

    def _print_prompts_summary(self, prompts: List[dict]) -> None:
        """Print a summary table of loaded prompts."""
        if not prompts:
            return
        
        categories = {}
        for prompt in prompts:
            category = prompt.get("category", "unknown")
            categories[category] = categories.get(category, 0) + 1
        
        print("\n  Attack Category Breakdown:")
        for category, count in sorted(categories.items()):
            print(f"    • {category}: {count} prompts")

    async def initialize_adapters(self) -> None:
        """Instantiate target and judge adapters using factory method."""
        self._log_section("Initializing Adapters")
        
        print(f"  Target Model: {self.target}")
        print(f"  Judge Model:  {self.judge}")
        
        self.target_adapter = get_adapter(self.target)
        self.judge_adapter = get_adapter(self.judge)
        
        print(f"✓ Target adapter initialized: {self.target_adapter.__class__.__name__}")
        print(f"✓ Judge adapter initialized: {self.judge_adapter.__class__.__name__}")

    async def run_benchmark(self, prompts: List[dict]) -> dict:
        """Initialize BenchmarkPipeline and trigger evaluation."""
        self._log_section("Running Benchmark Evaluation")
        
        self.benchmark_pipeline = BenchmarkPipeline(
            target_adapter=self.target_adapter,
            judge_adapter=self.judge_adapter,
            db_manager=self.db_manager,
            concurrency=self.concurrency,
            session_id=self.session_id,
            logger=self.logger,
        )
        
        print(f"  Concurrency Level: {self.concurrency}")
        print(f"  Total Prompts to Evaluate: {len(prompts)}\n")
        
        results = await self.benchmark_pipeline.run_benchmark(prompts)
        
        print(f"\n✓ Benchmark evaluation completed")
        print(f"  Total Evaluations: {len(results)}")
        
        return results

    async def aggregate_and_export_results(self, results: dict) -> None:
        """Trigger ResultsAggregator to calculate metrics and export chart."""
        self._log_section("Aggregating Results & Exporting Metrics")
        
        self.results_aggregator = ResultsAggregator(
            session_id=self.session_id,
            db_manager=self.db_manager,
            logger=self.logger,
        )
        
        metrics = await self.results_aggregator.aggregate(results)
        
        # Print metrics summary
        self._print_metrics_summary(metrics)
        
        # Export chart to results/ folder
        results_dir = Path("results")
        results_dir.mkdir(exist_ok=True)
        
        chart_path = await self.results_aggregator.export_chart(
            metrics=metrics,
            output_dir=results_dir,
        )
        
        print(f"\n✓ Results exported")
        print(f"  Chart: {chart_path}")

    def _print_metrics_summary(self, metrics: dict) -> None:
        """Print a summary table of evaluation metrics."""
        print("\n  Security Evaluation Metrics:")
        
        security_score = metrics.get("overall_security_score", 0)
        vulnerabilities = metrics.get("total_vulnerabilities", 0)
        successful_attacks = metrics.get("successful_attacks", 0)
        
        print(f"    • Overall Security Score: {security_score:.2f}%")
        print(f"    • Total Vulnerabilities: {vulnerabilities}")
        print(f"    • Successful Attacks: {successful_attacks}")
        
        if "category_breakdown" in metrics:
            print("\n  Category Breakdown:")
            for category, data in metrics["category_breakdown"].items():
                score = data.get("security_score", 0)
                print(f"    • {category}: {score:.2f}%")

    async def cleanup(self) -> None:
        """Cleanup resources."""
        if self.db_manager:
            await self.db_manager.disconnect()

    async def orchestrate(self) -> None:
        """Main orchestration flow."""
        try:
            # 1. Load environment
            await self.load_environment()
            
            # 2. Initialize database
            await self.initialize_database()
            
            # 3. Load attack prompts
            prompts = await self.load_attack_prompts()
            
            if not prompts:
                print("⚠ No prompts loaded. Exiting.")
                return
            
            # 4. Initialize adapters
            await self.initialize_adapters()
            
            # 5. Run benchmark
            results = await self.run_benchmark(prompts)
            
            # 6. Aggregate and export results
            await self.aggregate_and_export_results(results)
            
            # Print completion summary
            self._log_section("Benchmark Execution Complete")
            print(f"✓ Session {self.session_id} completed successfully\n")
            
        except Exception as e:
            self.logger.error(f"Orchestration failed: {str(e)}")
            print(f"\n✗ Error: {str(e)}\n")
            sys.exit(1)
        finally:
            await self.cleanup()


def parse_arguments() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="LLM Guard Bench - Comprehensive LLM Security Evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--target",
        type=str,
        required=True,
        help="Target LLM model (e.g., llama3, mistral, gpt-4)",
    )
    
    parser.add_argument(
        "--judge",
        type=str,
        default="llama-3.1-8b-instant",
        help="Judge model for evaluation (default: llama-3.1-8b-instant)",
    )
    
    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        help="Number of concurrent evaluations (default: 3)",
    )
    
    parser.add_argument(
        "--categories",
        type=str,
        nargs="+",
        help="Filter by specific attack categories (optional)",
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
