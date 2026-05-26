"""
Core benchmark pipeline orchestrator.

Executes adversarial attacks against target LLM with concurrent rate limiting,
captures responses, evaluates them through a 2-stage cascading evaluator, and
persists results to both SQLite and JSONL.
"""

import asyncio
import logging
import time
from typing import List, Optional

from core.adapters import BaseAdapter
from core.evaluator import EvaluationEngine, EvaluationResult
from core.models import AttackDefinition, EvalResult, EvaluationStatus, TestResult

logger = logging.getLogger(__name__)


class BenchmarkPipeline:
    """
    Production-ready async benchmark pipeline for executing attacks against target and judge adapters.
    Implements rate limiting, resilience, database persistence, and comprehensive error handling.
    """

    def __init__(
        self,
        target_adapter: BaseAdapter,
        judge_adapter: BaseAdapter,
        db_manager,
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
        self.logger = logging.getLogger(self.__class__.__name__)

    async def run_benchmark(
        self,
        attacks: List[AttackDefinition],
        model_name: str,
        concurrency_limit: int,
        session_id: str,
    ) -> List[TestResult]:
        """
        Execute benchmark across multiple attack vectors with concurrency control.

        Args:
            attacks: List of AttackDefinition objects to execute
            model_name: Target model identifier
            concurrency_limit: Maximum number of concurrent executions
            session_id: Unique session identifier for batch tracking

        Returns:
            List of TestResult objects containing execution and evaluation metrics
        """
        semaphore = asyncio.Semaphore(concurrency_limit)
        results: List[TestResult] = []
        tasks = []

        async def _bounded_execute(
            attack: AttackDefinition, index: int
        ) -> Optional[TestResult]:
            """Execute single test within semaphore bounds with defensive error handling."""
            try:
                async with semaphore:
                    return await self._execute_single_test(
                        attack=attack,
                        model_name=model_name,
                        attack_index=index,
                        session_id=session_id,
                    )
            except Exception as e:
                # This should never happen due to try-except in _execute_single_test,
                # but we catch any unforeseen exceptions to prevent batch failure
                self.logger.error(
                    f"Attack {index} ({attack.attack_id}) unhandled exception in _bounded_execute: {type(e).__name__}: {str(e)}"
                )
                # Return None to signal fatal error (will be logged above)
                return None

        # Create all tasks with concurrency control
        for idx, attack in enumerate(attacks):
            task = _bounded_execute(attack, idx)
            tasks.append(task)

        # Execute all tasks with exception handling to prevent batch failure
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results: collect valid TestResult objects, log any exceptions
        for idx, result in enumerate(batch_results):
            if isinstance(result, Exception):
                self.logger.error(
                    f"Attack {idx} execution raised exception: {type(result).__name__}: {str(result)}"
                )
            elif isinstance(result, TestResult):
                results.append(result)
            elif result is None:
                self.logger.debug(f"Attack {idx} returned None (expected for fatal errors)")

        self.logger.info(
            f"Benchmark completed: {len(results)} results from {len(attacks)} attacks"
        )
        return results

    async def _execute_single_test(
        self,
        attack: AttackDefinition,
        model_name: str,
        attack_index: int,
        session_id: str,
        timeout_seconds: float = 30.0,
    ) -> Optional[TestResult]:
        """
        Execute a single benchmark test with full instrumentation and error handling.

        Captures timing metrics, executes target model, evaluates output, and persists to database.
        Uses asyncio.wait_for timeout to prevent indefinite hangs.

        Args:
            attack: AttackDefinition to execute
            model_name: Target model identifier
            attack_index: Index of attack in batch
            session_id: Session identifier for batch tracking
            timeout_seconds: Maximum seconds to wait for target model response

        Returns:
            TestResult object with complete execution and evaluation data, or None on fatal error
        """
        start_time = time.time()
        target_output = ""
        execution_time_ms = 0
        total_time_ms = 0
        eval_result: Optional[EvalResult] = None

        # ===== Stage 1: Target Model Execution =====
        try:
            target_start = time.time()
            try:
                target_output = await asyncio.wait_for(
                    self.target_adapter.generate(
                        system_prompt=attack.system_prompt or "",
                        user_prompt=attack.adversarial_prompt,
                    ),
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError:
                execution_time_ms = int((time.time() - target_start) * 1000)
                self.logger.warning(
                    f"Attack {attack.attack_id}: Target model timeout after {timeout_seconds}s"
                )
                eval_result = EvalResult(
                    status="TIMEOUT",
                    stage="PRE_FLIGHT",
                    error_message=f"Target model timeout after {timeout_seconds}s",
                )

            target_end = time.time()
            if eval_result is None:
                execution_time_ms = int((target_end - target_start) * 1000)
                if not target_output:
                    target_output = ""
                self.logger.debug(f"Attack {attack.attack_id}: Target model response ({execution_time_ms}ms)")

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            self.logger.error(
                f"Attack {attack.attack_id}: Target model error: {type(e).__name__}: {str(e)}"
            )
            eval_result = EvalResult(
                status="EVAL_ERROR",
                stage="PRE_FLIGHT",
                error_message=f"Target model error: {type(e).__name__}: {str(e)}",
            )

        # ===== Stage 2: Evaluation Engine (if target succeeded) =====
        if eval_result is None:
            try:
                eval_start = time.time()
                try:
                    evaluation_result: EvaluationResult = await asyncio.wait_for(
                        self.evaluation_engine.evaluate(target_output),
                        timeout=timeout_seconds,
                    )
                    eval_end = time.time()
                    self.logger.debug(
                        f"Attack {attack.attack_id}: Evaluation completed ({int((eval_end - eval_start) * 1000)}ms)"
                    )
                    eval_result = self._convert_evaluation_result(evaluation_result)

                except asyncio.TimeoutError:
                    self.logger.warning(
                        f"Attack {attack.attack_id}: Evaluation timeout after {timeout_seconds}s"
                    )
                    eval_result = EvalResult(
                        status="EVAL_ERROR",
                        stage="STAGE_2_JUDGE",
                        error_message=f"Evaluation timeout after {timeout_seconds}s",
                    )

            except Exception as e:
                self.logger.error(
                    f"Attack {attack.attack_id}: Evaluation error: {type(e).__name__}: {str(e)}"
                )
                eval_result = EvalResult(
                    status="EVAL_ERROR",
                    stage="STAGE_2_JUDGE",
                    error_message=f"Evaluation error: {type(e).__name__}: {str(e)}",
                )

        # Ensure eval_result is set (should never be None at this point)
        if eval_result is None:
            eval_result = EvalResult(
                status="EVAL_ERROR",
                stage="PRE_FLIGHT",
                error_message="Unknown evaluation error",
            )

        # ===== Construct Unified TestResult =====
        total_time_ms = int((time.time() - start_time) * 1000)

        test_result = TestResult.from_attack_and_eval(
            session_id=session_id,
            attack=attack,
            model_name=model_name,
            raw_response=target_output,
            eval_result=eval_result,
            execution_time_ms=execution_time_ms,
            total_time_ms=total_time_ms,
        )

        # ===== Persist to Database =====
        try:
            await self.db_manager.insert_result(test_result)
        except Exception as e:
            self.logger.warning(
                f"Failed to persist result for attack {attack.attack_id}: {str(e)}"
            )

        return test_result

    def _convert_evaluation_result(
        self, evaluation_result: EvaluationResult
    ) -> EvalResult:
        """
        Convert EvaluationEngine's EvaluationResult enum to EvalResult model.

        Args:
            evaluation_result: Result from EvaluationEngine.evaluate()

        Returns:
            EvalResult with appropriate status and stage
        """
        result_str = evaluation_result.value.upper()

        if result_str == "PASSED":
            return EvalResult(
                status="PASSED",
                stage="STAGE_1_KEYWORD",
            )
        elif result_str == "VULNERABLE":
            return EvalResult(
                status="VULNERABLE",
                stage="STAGE_2_JUDGE",
                judge_verdict="VULNERABLE",
            )
        elif result_str == "AMBIGUOUS":
            return EvalResult(
                status="EVAL_ERROR",
                stage="STAGE_2_JUDGE",
                error_message="Judge evaluation produced ambiguous result",
            )
        else:
            return EvalResult(
                status="EVAL_ERROR",
                stage="STAGE_2_JUDGE",
                error_message=f"Unknown evaluation result: {result_str}",
            )
