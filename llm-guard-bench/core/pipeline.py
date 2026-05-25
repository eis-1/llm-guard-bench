import asyncio
import time
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from llm_guard_bench.core.adapters.base import BaseAdapter
from llm_guard_bench.core.evaluation import EvaluationEngine
from llm_guard_bench.core.models import TestResult


class BenchmarkPipeline:
    """
    Production-ready async benchmark pipeline for executing prompts against target and judge adapters.
    Implements rate limiting, resilience, and database persistence.
    """

    def __init__(
        self,
        target_adapter: BaseAdapter,
        judge_adapter: BaseAdapter,
        db_manager
    ) -> None:
        """
        Initialize the benchmark pipeline.

        Args:
            target_adapter: BaseAdapter for target model inference
            judge_adapter: BaseAdapter for evaluation model inference
            db_manager: Database manager for persisting results
        """
        self.target_adapter = target_adapter
        self.judge_adapter = judge_adapter
        self.db_manager = db_manager
        self.evaluation_engine = EvaluationEngine(judge_adapter=judge_adapter)

    async def run_benchmark(
        self,
        prompts: List[str],
        concurrency_limit: int,
        session_id: str
    ) -> List[TestResult]:
        """
        Execute benchmark across multiple prompts with concurrency control and rate limiting.

        Args:
            prompts: List of input prompts to benchmark
            concurrency_limit: Maximum number of concurrent executions
            session_id: Unique session identifier for batch tracking

        Returns:
            List of TestResult objects containing execution and evaluation metrics
        """
        semaphore = asyncio.Semaphore(concurrency_limit)
        results: List[TestResult] = []
        tasks = []

        async def _bounded_execute(prompt: str, index: int) -> Optional[TestResult]:
            """Execute single test within semaphore bounds."""
            async with semaphore:
                return await self._execute_single_test(
                    prompt=prompt,
                    prompt_index=index,
                    session_id=session_id
                )

        # Create all tasks with concurrency control
        for idx, prompt in enumerate(prompts):
            task = _bounded_execute(prompt, idx)
            tasks.append(task)

        # Execute all tasks and collect results
        batch_results = await asyncio.gather(*tasks, return_exceptions=False)

        # Filter out None results and collect valid TestResult objects
        for result in batch_results:
            if isinstance(result, TestResult):
                results.append(result)

        return results

    async def _execute_single_test(
        self,
        prompt: str,
        prompt_index: int,
        session_id: str
    ) -> Optional[TestResult]:
        """
        Execute a single benchmark test with full instrumentation and error handling.

        Captures timing metrics, executes target model, evaluates output, and persists to database.

        Args:
            prompt: Input prompt for the target model
            prompt_index: Index of prompt in batch
            session_id: Session identifier for batch tracking

        Returns:
            TestResult object with complete execution and evaluation data, or None on fatal error
        """
        start_time = time.time()
        execution_status = "COMPLETED"
        target_output = None
        evaluation_result = None
        error_message = None

        try:
            # ===== Target Model Execution =====
            target_start = time.time()
            target_output = await self.target_adapter.generate(prompt)
            target_end = time.time()
            target_execution_time = target_end - target_start

        except asyncio.TimeoutError as e:
            execution_status = "FAILED"
            error_message = f"Target model timeout: {str(e)}"
            target_execution_time = time.time() - start_time
        except ValueError as e:
            # Context length exceeded or other constraint violation
            execution_status = "FAILED"
            error_message = f"Target model constraint violation: {str(e)}"
            target_execution_time = time.time() - start_time
        except Exception as e:
            # Network drops, connection errors, or unexpected failures
            execution_status = "FAILED"
            error_message = f"Target model execution error: {str(e)}"
            target_execution_time = time.time() - start_time

        # ===== Evaluation Engine Execution =====
        if target_output is not None:
            try:
                eval_start = time.time()

                # Send payload to EvaluationEngine with both prompt and target output
                evaluation_result = await self.evaluation_engine.evaluate(
                    prompt=prompt,
                    response=target_output
                )

                eval_end = time.time()
                evaluation_time = eval_end - eval_start

            except asyncio.TimeoutError as e:
                execution_status = "EVAL_ERROR"
                error_message = f"Evaluation timeout: {str(e)}"
                evaluation_time = time.time() - eval_start
            except Exception as e:
                execution_status = "EVAL_ERROR"
                error_message = f"Evaluation error: {str(e)}"
                evaluation_time = time.time() - eval_start
        else:
            evaluation_time = 0.0

        # ===== Construct Unified TestResult =====
        end_time = time.time()
        total_execution_time = end_time - start_time

        test_result = TestResult(
            session_id=session_id,
            prompt_index=prompt_index,
            prompt=prompt,
            target_output=target_output or "",
            execution_status=execution_status,
            target_execution_time=target_execution_time,
            evaluation_result=evaluation_result,
            evaluation_time=evaluation_time,
            total_execution_time=total_execution_time,
            error_message=error_message,
            timestamp=datetime.utcnow()
        )

        # ===== Persist to Database =====
        try:
            await self.db_manager.insert_result(test_result)
        except Exception as e:
            # Log persistence error but don't fail the pipeline
            print(f"Warning: Failed to persist result for prompt {prompt_index}: {str(e)}")

        return test_result
