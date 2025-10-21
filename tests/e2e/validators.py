"""Validators for evaluation harness."""

import re
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

import structlog

logger = structlog.get_logger()


@dataclass
class ValidationResult:
    """Result of a validation check."""
    
    passed: bool
    score: float
    violations: List[str]
    suggestions: List[str]
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class CitationValidator:
    """Validates citation requirements."""
    
    def __init__(self, min_citations: int = 3):
        """Initialize citation validator.
        
        Args:
            min_citations: Minimum number of citations required
        """
        self.min_citations = min_citations
    
    def validate(self, output: str, expected_citations: int = 0) -> ValidationResult:
        """Validate citations in output.
        
        Args:
            output: Generated output
            expected_citations: Expected number of citations
            
        Returns:
            Validation result
        """
        violations = []
        suggestions = []
        
        # Count citations
        citation_count = self._count_citations(output)
        
        # Check minimum citations
        min_required = max(self.min_citations, expected_citations)
        if citation_count < min_required:
            violations.append(f"Insufficient citations: {citation_count}/{min_required}")
            suggestions.append(f"Add at least {min_required - citation_count} more citations")
        
        # Check citation quality
        quality_issues = self._check_citation_quality(output)
        violations.extend(quality_issues)
        
        # Calculate score
        score = min(citation_count / min_required, 1.0) if min_required > 0 else 1.0
        
        return ValidationResult(
            passed=len(violations) == 0,
            score=score,
            violations=violations,
            suggestions=suggestions,
            metadata={"citation_count": citation_count},
        )
    
    def _count_citations(self, text: str) -> int:
        """Count citations in text."""
        patterns = [
            r'\[\d+\]',  # [1], [2], etc.
            r'\([^)]*\d{4}[^)]*\)',  # (Author, 2023)
            r'\[[^\]]+\]',  # [Author, 2023]
        ]
        
        total = 0
        for pattern in patterns:
            matches = re.findall(pattern, text)
            total += len(matches)
        
        return total
    
    def _check_citation_quality(self, text: str) -> List[str]:
        """Check citation quality."""
        issues = []
        
        # Check for incomplete citations
        incomplete_patterns = [
            r'\[[^\]]*$',  # Unclosed brackets
            r'\([^)]*$',   # Unclosed parentheses
        ]
        
        for pattern in incomplete_patterns:
            if re.search(pattern, text):
                issues.append("Incomplete citations found")
        
        return issues


class HedgingValidator:
    """Validates hedging language."""
    
    def __init__(self, max_hedging_ratio: float = 0.1):
        """Initialize hedging validator.
        
        Args:
            max_hedging_ratio: Maximum allowed hedging ratio
        """
        self.max_hedging_ratio = max_hedging_ratio
        self.hedging_phrases = self._get_hedging_phrases()
    
    def validate(self, output: str, max_hedging_ratio: float = None) -> ValidationResult:
        """Validate hedging in output.
        
        Args:
            output: Generated output
            max_hedging_ratio: Maximum allowed hedging ratio
            
        Returns:
            Validation result
        """
        if max_hedging_ratio is None:
            max_hedging_ratio = self.max_hedging_ratio
        
        violations = []
        suggestions = []
        
        # Detect hedging
        hedging_instances = self._detect_hedging(output)
        total_words = len(output.split())
        hedging_ratio = len(hedging_instances) / total_words if total_words > 0 else 0
        
        if hedging_ratio > max_hedging_ratio:
            violations.append(f"Excessive hedging: {hedging_ratio:.2f} > {max_hedging_ratio}")
            suggestions.append("Reduce hedging language and be more direct")
        
        # Calculate score
        score = max(0.0, 1.0 - (hedging_ratio / max_hedging_ratio))
        
        return ValidationResult(
            passed=len(violations) == 0,
            score=score,
            violations=violations,
            suggestions=suggestions,
            metadata={"hedging_ratio": hedging_ratio, "hedging_instances": len(hedging_instances)},
        )
    
    def _get_hedging_phrases(self) -> List[str]:
        """Get hedging phrases to detect."""
        return [
            "might", "may", "could", "possibly", "perhaps", "maybe",
            "seems", "appears", "suggests", "indicates",
            "I think", "I believe", "I feel", "I suspect",
            "somewhat", "rather", "quite", "fairly",
            "about", "approximately", "roughly", "around",
        ]
    
    def _detect_hedging(self, text: str) -> List[str]:
        """Detect hedging language."""
        detected = []
        text_lower = text.lower()
        
        for phrase in self.hedging_phrases:
            pattern = r'\b' + re.escape(phrase.lower()) + r'\b'
            matches = re.findall(pattern, text_lower)
            detected.extend(matches)
        
        return detected


class UnitsValidator:
    """Validates SI units."""
    
    def __init__(self, enforce_si: bool = True):
        """Initialize units validator.
        
        Args:
            enforce_si: Whether to enforce SI units
        """
        self.enforce_si = enforce_si
        self.si_units = self._get_si_units()
    
    def validate(self, output: str, expected_units: List[str] = None) -> ValidationResult:
        """Validate units in output.
        
        Args:
            output: Generated output
            expected_units: Expected units
            
        Returns:
            Validation result
        """
        violations = []
        suggestions = []
        
        # Detect measurements
        measurements = self._detect_measurements(output)
        
        if measurements:
            # Check for non-SI units
            non_si_units = self._find_non_si_units(measurements)
            if non_si_units and self.enforce_si:
                violations.append(f"Non-SI units detected: {', '.join(non_si_units)}")
                suggestions.append("Convert all measurements to SI units")
            
            # Check for expected units
            if expected_units:
                missing_units = set(expected_units) - set(m["unit"] for m in measurements)
                if missing_units:
                    violations.append(f"Missing expected units: {', '.join(missing_units)}")
                    suggestions.append("Include the expected units in your response")
        
        # Calculate score
        score = 1.0 if len(violations) == 0 else 0.5
        
        return ValidationResult(
            passed=len(violations) == 0,
            score=score,
            violations=violations,
            suggestions=suggestions,
            metadata={"measurements": measurements},
        )
    
    def _get_si_units(self) -> List[str]:
        """Get SI units."""
        return [
            "m", "cm", "mm", "km",  # Length
            "kg", "g", "mg",        # Mass
            "s", "min", "h",        # Time
            "K", "°C",              # Temperature
            "Pa", "kPa", "MPa",     # Pressure
            "N", "kN",              # Force
            "J", "kJ", "MJ",        # Energy
            "W", "kW", "MW",        # Power
        ]
    
    def _detect_measurements(self, text: str) -> List[Dict[str, Any]]:
        """Detect measurements in text."""
        measurements = []
        pattern = r'(\d+(?:\.\d+)?)\s*([a-zA-Z°]+(?:\^?[0-9]*)?)'
        matches = re.finditer(pattern, text)
        
        for match in matches:
            measurements.append({
                "value": float(match.group(1)),
                "unit": match.group(2),
                "text": match.group(0),
            })
        
        return measurements
    
    def _find_non_si_units(self, measurements: List[Dict[str, Any]]) -> List[str]:
        """Find non-SI units."""
        non_si = []
        for measurement in measurements:
            unit = measurement["unit"].lower()
            if unit not in self.si_units and unit not in [u.lower() for u in self.si_units]:
                non_si.append(measurement["unit"])
        
        return list(set(non_si))


class EvidenceValidator:
    """Validates evidence requirements."""
    
    def __init__(self, min_sources: int = 2):
        """Initialize evidence validator.
        
        Args:
            min_sources: Minimum number of sources required
        """
        self.min_sources = min_sources
    
    def validate(self, output: str, expected_sources: List[str] = None) -> ValidationResult:
        """Validate evidence in output.
        
        Args:
            output: Generated output
            expected_sources: Expected sources
            
        Returns:
            Validation result
        """
        violations = []
        suggestions = []
        
        # Check for evidence indicators
        evidence_indicators = self._find_evidence_indicators(output)
        
        if len(evidence_indicators) < self.min_sources:
            violations.append(f"Insufficient evidence: {len(evidence_indicators)}/{self.min_sources}")
            suggestions.append("Provide more evidence to support your claims")
        
        # Check for expected sources
        if expected_sources:
            found_sources = self._find_sources(output)
            missing_sources = set(expected_sources) - set(found_sources)
            if missing_sources:
                violations.append(f"Missing expected sources: {', '.join(missing_sources)}")
                suggestions.append("Include citations from the expected sources")
        
        # Calculate score
        score = min(len(evidence_indicators) / self.min_sources, 1.0) if self.min_sources > 0 else 1.0
        
        return ValidationResult(
            passed=len(violations) == 0,
            score=score,
            violations=violations,
            suggestions=suggestions,
            metadata={"evidence_indicators": evidence_indicators},
        )
    
    def _find_evidence_indicators(self, text: str) -> List[str]:
        """Find evidence indicators in text."""
        indicators = []
        
        # Look for evidence patterns
        patterns = [
            r'according to [^.]*',
            r'studies show [^.]*',
            r'research indicates [^.]*',
            r'data shows [^.]*',
            r'evidence suggests [^.]*',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            indicators.extend(matches)
        
        return indicators
    
    def _find_sources(self, text: str) -> List[str]:
        """Find sources in text."""
        sources = []
        
        # Look for domain patterns
        domain_pattern = r'https?://([^/\s]+)'
        matches = re.findall(domain_pattern, text)
        sources.extend(matches)
        
        return sources


class RAGValidator:
    """Validates RAG performance."""
    
    def __init__(self, min_retrieval_score: float = 0.7):
        """Initialize RAG validator.
        
        Args:
            min_retrieval_score: Minimum retrieval score
        """
        self.min_retrieval_score = min_retrieval_score
    
    def validate(self, output: str, retrieval_docs: List[Dict[str, Any]] = None) -> ValidationResult:
        """Validate RAG performance.
        
        Args:
            output: Generated output
            retrieval_docs: Retrieved documents
            
        Returns:
            Validation result
        """
        violations = []
        suggestions = []
        
        if not retrieval_docs:
            violations.append("No retrieval documents provided")
            return ValidationResult(
                passed=False,
                score=0.0,
                violations=violations,
                suggestions=["Ensure retrieval documents are available"],
            )
        
        # Check retrieval scores
        avg_score = sum(doc.get("score", 0) for doc in retrieval_docs) / len(retrieval_docs)
        if avg_score < self.min_retrieval_score:
            violations.append(f"Low retrieval score: {avg_score:.2f} < {self.min_retrieval_score}")
            suggestions.append("Improve retrieval quality or adjust search parameters")
        
        # Check source diversity
        unique_sources = len(set(doc.get("source_uri", "") for doc in retrieval_docs))
        if unique_sources < 2:
            violations.append(f"Low source diversity: {unique_sources} sources")
            suggestions.append("Retrieve from more diverse sources")
        
        # Calculate score
        score = min(avg_score / self.min_retrieval_score, 1.0)
        
        return ValidationResult(
            passed=len(violations) == 0,
            score=score,
            violations=violations,
            suggestions=suggestions,
            metadata={
                "avg_retrieval_score": avg_score,
                "unique_sources": unique_sources,
                "retrieval_count": len(retrieval_docs),
            },
        )


class MCPValidator:
    """Validates MCP tool usage."""
    
    def __init__(self):
        """Initialize MCP validator."""
        pass
    
    def validate(self, output: str, tool_calls: List[Dict[str, Any]] = None) -> ValidationResult:
        """Validate MCP tool usage.
        
        Args:
            output: Generated output
            tool_calls: Tool calls made
            
        Returns:
            Validation result
        """
        violations = []
        suggestions = []
        
        if not tool_calls:
            violations.append("No MCP tools were used")
            suggestions.append("Use appropriate MCP tools to complete the task")
            return ValidationResult(
                passed=False,
                score=0.0,
                violations=violations,
                suggestions=suggestions,
            )
        
        # Check tool success rate
        successful_tools = sum(1 for tool in tool_calls if tool.get("success", False))
        success_rate = successful_tools / len(tool_calls)
        
        if success_rate < 0.8:
            violations.append(f"Low tool success rate: {success_rate:.2f}")
            suggestions.append("Improve tool usage and error handling")
        
        # Check tool diversity
        unique_tools = len(set(tool.get("tool_name", "") for tool in tool_calls))
        if unique_tools < 2:
            violations.append(f"Low tool diversity: {unique_tools} tools")
            suggestions.append("Use a variety of MCP tools")
        
        # Calculate score
        score = success_rate * 0.7 + (unique_tools / 5) * 0.3  # Weighted score
        
        return ValidationResult(
            passed=len(violations) == 0,
            score=score,
            violations=violations,
            suggestions=suggestions,
            metadata={
                "tool_count": len(tool_calls),
                "successful_tools": successful_tools,
                "success_rate": success_rate,
                "unique_tools": unique_tools,
            },
        )
