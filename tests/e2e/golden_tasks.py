"""Golden tasks for evaluation harness."""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

import structlog

logger = structlog.get_logger()


class TaskType(Enum):
    """Task types for evaluation."""
    CITATION = "citation"
    HEDGING = "hedging"
    UNITS = "units"
    EVIDENCE = "evidence"
    RAG = "rag"
    MCP = "mcp"


class TaskDifficulty(Enum):
    """Task difficulty levels."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass
class GoldenTask:
    """Golden task for evaluation."""
    
    id: str
    name: str
    description: str
    task_type: TaskType
    difficulty: TaskDifficulty
    prompt: str
    expected_output: str
    expected_citations: int = 0
    expected_sources: List[str] = None
    expected_units: List[str] = None
    max_hedging_ratio: float = 0.1
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.expected_sources is None:
            self.expected_sources = []
        if self.expected_units is None:
            self.expected_units = []
        if self.metadata is None:
            self.metadata = {}


class GoldenTaskRegistry:
    """Registry of golden tasks for evaluation."""
    
    def __init__(self):
        """Initialize golden task registry."""
        self.tasks: Dict[str, GoldenTask] = {}
        self._load_default_tasks()
    
    def _load_default_tasks(self):
        """Load default golden tasks."""
        # Citation tasks
        self.add_task(GoldenTask(
            id="citation-001",
            name="Quantum Computing Basics",
            description="Explain quantum computing with proper citations",
            task_type=TaskType.CITATION,
            difficulty=TaskDifficulty.MEDIUM,
            prompt="Explain the basic principles of quantum computing, including superposition and entanglement. Provide specific examples and cite relevant research.",
            expected_output="Quantum computing leverages quantum mechanical phenomena...",
            expected_citations=3,
            expected_sources=["arxiv.org", "nature.com", "science.org"],
        ))
        
        # Hedging tasks
        self.add_task(GoldenTask(
            id="hedging-001",
            name="Climate Change Facts",
            description="State climate change facts without hedging",
            task_type=TaskType.HEDGING,
            difficulty=TaskDifficulty.EASY,
            prompt="Describe the current state of climate change and its impacts. Be direct and factual.",
            expected_output="Climate change is causing global temperatures to rise...",
            max_hedging_ratio=0.05,
        ))
        
        # Units tasks
        self.add_task(GoldenTask(
            id="units-001",
            name="Physics Measurements",
            description="Convert and normalize physics measurements to SI units",
            task_type=TaskType.UNITS,
            difficulty=TaskDifficulty.MEDIUM,
            prompt="A car is traveling at 60 mph. What is its speed in m/s? A building is 100 feet tall. What is its height in meters?",
            expected_output="The car is traveling at 26.8 m/s. The building is 30.5 meters tall.",
            expected_units=["m/s", "m"],
        ))
        
        # Evidence tasks
        self.add_task(GoldenTask(
            id="evidence-001",
            name="Medical Research",
            description="Present medical research findings with evidence",
            task_type=TaskType.EVIDENCE,
            difficulty=TaskDifficulty.HARD,
            prompt="Summarize recent findings on the effectiveness of a new cancer treatment. Include specific data and study details.",
            expected_output="Recent studies show that the new treatment...",
            expected_citations=5,
            expected_sources=["pubmed.ncbi.nlm.nih.gov", "nejm.org", "thelancet.com"],
        ))
        
        # RAG tasks
        self.add_task(GoldenTask(
            id="rag-001",
            name="Technical Documentation",
            description="Answer technical questions using retrieved documents",
            task_type=TaskType.RAG,
            difficulty=TaskDifficulty.MEDIUM,
            prompt="How do I configure a Kubernetes cluster for high availability?",
            expected_output="To configure a Kubernetes cluster for high availability...",
            expected_citations=2,
        ))
        
        # MCP tasks
        self.add_task(GoldenTask(
            id="mcp-001",
            name="GitHub Operations",
            description="Perform GitHub operations using MCP tools",
            task_type=TaskType.MCP,
            difficulty=TaskDifficulty.MEDIUM,
            prompt="Create a new issue in the repository with the title 'Bug: Memory leak in API' and assign it to the 'bugs' label.",
            expected_output="I'll create a new issue in the repository...",
        ))
    
    def add_task(self, task: GoldenTask):
        """Add a task to the registry.
        
        Args:
            task: Golden task to add
        """
        self.tasks[task.id] = task
        logger.info("Golden task added", task_id=task.id, name=task.name)
    
    def get_task(self, task_id: str) -> Optional[GoldenTask]:
        """Get a task by ID.
        
        Args:
            task_id: Task ID
            
        Returns:
            Golden task or None
        """
        return self.tasks.get(task_id)
    
    def get_tasks_by_type(self, task_type: TaskType) -> List[GoldenTask]:
        """Get tasks by type.
        
        Args:
            task_type: Task type
            
        Returns:
            List of tasks
        """
        return [task for task in self.tasks.values() if task.task_type == task_type]
    
    def get_tasks_by_difficulty(self, difficulty: TaskDifficulty) -> List[GoldenTask]:
        """Get tasks by difficulty.
        
        Args:
            difficulty: Task difficulty
            
        Returns:
            List of tasks
        """
        return [task for task in self.tasks.values() if task.difficulty == difficulty]
    
    def get_all_tasks(self) -> List[GoldenTask]:
        """Get all tasks.
        
        Returns:
            List of all tasks
        """
        return list(self.tasks.values())
    
    def get_task_count(self) -> int:
        """Get total task count.
        
        Returns:
            Number of tasks
        """
        return len(self.tasks)


# Global registry instance
golden_task_registry = GoldenTaskRegistry()
