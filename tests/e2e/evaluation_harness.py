"""Evaluation harness for golden tasks."""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import structlog
import httpx

from .golden_tasks import GoldenTask, GoldenTaskRegistry, TaskType
from .validators import (
    CitationValidator, HedgingValidator, UnitsValidator,
    EvidenceValidator, RAGValidator, MCPValidator
)

logger = structlog.get_logger()


class EvaluationHarness:
    """Evaluation harness for testing AI system performance."""
    
    def __init__(
        self,
        api_url: str = "http://localhost:8080",
        mlflow_url: str = "http://localhost:5000",
        output_dir: str = "evaluation_results",
    ):
        """Initialize evaluation harness.
        
        Args:
            api_url: API endpoint URL
            mlflow_url: MLflow tracking URL
            output_dir: Output directory for results
        """
        self.api_url = api_url
        self.mlflow_url = mlflow_url
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize validators
        self.citation_validator = CitationValidator()
        self.hedging_validator = HedgingValidator()
        self.units_validator = UnitsValidator()
        self.evidence_validator = EvidenceValidator()
        self.rag_validator = RAGValidator()
        self.mcp_validator = MCPValidator()
        
        # Initialize task registry
        self.task_registry = GoldenTaskRegistry()
    
    async def run_evaluation(
        self,
        task_ids: Optional[List[str]] = None,
        task_types: Optional[List[TaskType]] = None,
        difficulty: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run evaluation on specified tasks.
        
        Args:
            task_ids: Specific task IDs to run
            task_types: Task types to run
            difficulty: Difficulty level to run
            
        Returns:
            Evaluation results
        """
        # Get tasks to evaluate
        tasks = self._get_tasks_to_evaluate(task_ids, task_types, difficulty)
        
        logger.info("Starting evaluation", task_count=len(tasks))
        
        results = []
        for task in tasks:
            try:
                result = await self._evaluate_task(task)
                results.append(result)
                logger.info("Task evaluated", task_id=task.id, passed=result["passed"])
            except Exception as e:
                logger.error("Task evaluation failed", task_id=task.id, error=str(e))
                results.append({
                    "task_id": task.id,
                    "passed": False,
                    "error": str(e),
                })
        
        # Generate report
        report = self._generate_report(results)
        
        # Save results
        await self._save_results(results, report)
        
        return report
    
    def _get_tasks_to_evaluate(
        self,
        task_ids: Optional[List[str]] = None,
        task_types: Optional[List[TaskType]] = None,
        difficulty: Optional[str] = None,
    ) -> List[GoldenTask]:
        """Get tasks to evaluate based on criteria."""
        if task_ids:
            tasks = [self.task_registry.get_task(task_id) for task_id in task_ids]
            return [task for task in tasks if task is not None]
        
        tasks = self.task_registry.get_all_tasks()
        
        if task_types:
            tasks = [task for task in tasks if task.task_type in task_types]
        
        if difficulty:
            tasks = [task for task in tasks if task.difficulty.value == difficulty]
        
        return tasks
    
    async def _evaluate_task(self, task: GoldenTask) -> Dict[str, Any]:
        """Evaluate a single task.
        
        Args:
            task: Golden task to evaluate
            
        Returns:
            Evaluation result
        """
        start_time = time.time()
        
        # Send request to API
        response = await self._send_request(task)
        
        # Extract output and metadata
        output = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        run_id = response.get("id")
        trace_id = response.get("trace_id")
        
        # Run validators
        validation_results = await self._run_validators(task, output, response)
        
        # Calculate overall score
        overall_score = self._calculate_overall_score(validation_results)
        overall_passed = overall_score >= 0.8
        
        duration = time.time() - start_time
        
        return {
            "task_id": task.id,
            "task_name": task.name,
            "task_type": task.task_type.value,
            "difficulty": task.difficulty.value,
            "passed": overall_passed,
            "overall_score": overall_score,
            "duration": duration,
            "run_id": run_id,
            "trace_id": trace_id,
            "validation_results": validation_results,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    async def _send_request(self, task: GoldenTask) -> Dict[str, Any]:
        """Send request to API.
        
        Args:
            task: Golden task
            
        Returns:
            API response
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.api_url}/v1/chat/completions",
                json={
                    "model": "mistralai/Mistral-7B-Instruct-v0.3",
                    "messages": [{"role": "user", "content": task.prompt}],
                    "temperature": 0.7,
                    "max_tokens": 1000,
                },
                headers={
                    "Content-Type": "application/json",
                    "x-trace-id": f"eval-{task.id}",
                    "x-run-id": f"eval-{task.id}-{int(time.time())}",
                    "x-policy-set": "evaluation",
                }
            )
            
            if response.status_code != 200:
                raise Exception(f"API request failed: {response.status_code} - {response.text}")
            
            return response.json()
    
    async def _run_validators(
        self,
        task: GoldenTask,
        output: str,
        response: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run validators on task output.
        
        Args:
            task: Golden task
            output: Generated output
            response: API response
            
        Returns:
            Validation results
        """
        results = {}
        
        # Citation validation
        if task.task_type == TaskType.CITATION:
            citation_result = self.citation_validator.validate(output, task.expected_citations)
            results["citation"] = {
                "passed": citation_result.passed,
                "score": citation_result.score,
                "violations": citation_result.violations,
                "suggestions": citation_result.suggestions,
            }
        
        # Hedging validation
        if task.task_type == TaskType.HEDGING:
            hedging_result = self.hedging_validator.validate(output, task.max_hedging_ratio)
            results["hedging"] = {
                "passed": hedging_result.passed,
                "score": hedging_result.score,
                "violations": hedging_result.violations,
                "suggestions": hedging_result.suggestions,
            }
        
        # Units validation
        if task.task_type == TaskType.UNITS:
            units_result = self.units_validator.validate(output, task.expected_units)
            results["units"] = {
                "passed": units_result.passed,
                "score": units_result.score,
                "violations": units_result.violations,
                "suggestions": units_result.suggestions,
            }
        
        # Evidence validation
        if task.task_type == TaskType.EVIDENCE:
            evidence_result = self.evidence_validator.validate(output, task.expected_sources)
            results["evidence"] = {
                "passed": evidence_result.passed,
                "score": evidence_result.score,
                "violations": evidence_result.violations,
                "suggestions": evidence_result.suggestions,
            }
        
        # RAG validation
        if task.task_type == TaskType.RAG:
            # Extract retrieval docs from response metadata
            retrieval_docs = response.get("metadata", {}).get("retrieval_docs", [])
            rag_result = self.rag_validator.validate(output, retrieval_docs)
            results["rag"] = {
                "passed": rag_result.passed,
                "score": rag_result.score,
                "violations": rag_result.violations,
                "suggestions": rag_result.suggestions,
            }
        
        # MCP validation
        if task.task_type == TaskType.MCP:
            # Extract tool calls from response metadata
            tool_calls = response.get("metadata", {}).get("tool_calls", [])
            mcp_result = self.mcp_validator.validate(output, tool_calls)
            results["mcp"] = {
                "passed": mcp_result.passed,
                "score": mcp_result.score,
                "violations": mcp_result.violations,
                "suggestions": mcp_result.suggestions,
            }
        
        return results
    
    def _calculate_overall_score(self, validation_results: Dict[str, Any]) -> float:
        """Calculate overall score from validation results.
        
        Args:
            validation_results: Validation results
            
        Returns:
            Overall score
        """
        if not validation_results:
            return 0.0
        
        scores = [result["score"] for result in validation_results.values()]
        return sum(scores) / len(scores)
    
    def _generate_report(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate evaluation report.
        
        Args:
            results: Evaluation results
            
        Returns:
            Report
        """
        total_tasks = len(results)
        passed_tasks = sum(1 for result in results if result.get("passed", False))
        avg_score = sum(result.get("overall_score", 0) for result in results) / total_tasks if total_tasks > 0 else 0
        
        # Group by task type
        by_type = {}
        for result in results:
            task_type = result.get("task_type", "unknown")
            if task_type not in by_type:
                by_type[task_type] = {"total": 0, "passed": 0, "scores": []}
            
            by_type[task_type]["total"] += 1
            if result.get("passed", False):
                by_type[task_type]["passed"] += 1
            by_type[task_type]["scores"].append(result.get("overall_score", 0))
        
        # Calculate type-specific metrics
        for task_type, data in by_type.items():
            data["pass_rate"] = data["passed"] / data["total"] if data["total"] > 0 else 0
            data["avg_score"] = sum(data["scores"]) / len(data["scores"]) if data["scores"] else 0
        
        return {
            "summary": {
                "total_tasks": total_tasks,
                "passed_tasks": passed_tasks,
                "pass_rate": passed_tasks / total_tasks if total_tasks > 0 else 0,
                "avg_score": avg_score,
            },
            "by_type": by_type,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    async def _save_results(self, results: List[Dict[str, Any]], report: Dict[str, Any]):
        """Save evaluation results.
        
        Args:
            results: Evaluation results
            report: Evaluation report
        """
        # Save detailed results
        results_file = self.output_dir / "evaluation_results.json"
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2)
        
        # Save report
        report_file = self.output_dir / "evaluation_report.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)
        
        # Generate markdown report
        markdown_report = self._generate_markdown_report(report)
        markdown_file = self.output_dir / "evaluation_report.md"
        with open(markdown_file, "w") as f:
            f.write(markdown_report)
        
        logger.info("Evaluation results saved", output_dir=str(self.output_dir))
    
    def _generate_markdown_report(self, report: Dict[str, Any]) -> str:
        """Generate markdown report.
        
        Args:
            report: Evaluation report
            
        Returns:
            Markdown report
        """
        summary = report["summary"]
        
        markdown = f"""# Evaluation Report

## Summary

- **Total Tasks**: {summary['total_tasks']}
- **Passed Tasks**: {summary['passed_tasks']}
- **Pass Rate**: {summary['pass_rate']:.2%}
- **Average Score**: {summary['avg_score']:.2f}

## Results by Task Type

"""
        
        for task_type, data in report["by_type"].items():
            markdown += f"""### {task_type.title()}

- **Total**: {data['total']}
- **Passed**: {data['passed']}
- **Pass Rate**: {data['pass_rate']:.2%}
- **Average Score**: {data['avg_score']:.2f}

"""
        
        markdown += f"""
## Timestamp

{report['timestamp']}
"""
        
        return markdown


# CLI interface
async def main():
    """Main CLI interface."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run evaluation harness")
    parser.add_argument("--task-ids", nargs="+", help="Specific task IDs to run")
    parser.add_argument("--task-types", nargs="+", help="Task types to run")
    parser.add_argument("--difficulty", help="Difficulty level to run")
    parser.add_argument("--api-url", default="http://localhost:8080", help="API URL")
    parser.add_argument("--output-dir", default="evaluation_results", help="Output directory")
    
    args = parser.parse_args()
    
    # Convert task types
    task_types = None
    if args.task_types:
        task_types = [TaskType(t) for t in args.task_types]
    
    # Run evaluation
    harness = EvaluationHarness(api_url=args.api_url, output_dir=args.output_dir)
    report = await harness.run_evaluation(
        task_ids=args.task_ids,
        task_types=task_types,
        difficulty=args.difficulty,
    )
    
    print(f"Evaluation complete. Results saved to {args.output_dir}")
    print(f"Pass rate: {report['summary']['pass_rate']:.2%}")
    print(f"Average score: {report['summary']['avg_score']:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
