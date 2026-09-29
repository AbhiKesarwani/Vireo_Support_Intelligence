"""
src/issue_extractor.py — LLM-assisted issue extraction with schema validation and caching.

Requirements:
- Strict JSON contract
- Validation via Pydantic
- Rejects / retries malformed JSON safely
- Never silently converts malformed responses into valid-looking data
- Evidence span verification against source text
- Persistent caching by (ticket_id, prompt_version, model)
- Never exposes API keys
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from pydantic import BaseModel, Field, field_validator

from src.config import (
    APPROVED_TAXONOMY,
    DATA_AI,
    DEFAULT_MODEL,
    EXTRACTION_CACHE_FILE,
    PROMPT_ISSUE_EXTRACTION,
)
from src.llm_client import LLMClient, LLMClientError


class IssueExtractionSchema(BaseModel):
    """Pydantic model enforcing strict extraction contract."""
    issue_code: str
    sub_issue: str
    repeat_claim: Optional[bool] = None
    evidence_span: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    ambiguous: bool
    reason: Optional[str] = None

    @field_validator("issue_code")
    @classmethod
    def validate_issue_code(cls, v: str) -> str:
        clean_v = v.strip().upper()
        if clean_v not in APPROVED_TAXONOMY:
            raise ValueError(
                f"issue_code '{v}' not in approved taxonomy: {APPROVED_TAXONOMY}"
            )
        return clean_v

    @field_validator("sub_issue")
    @classmethod
    def validate_sub_issue(cls, v: str) -> str:
        clean_v = v.strip().lower()
        if not clean_v:
            return "general"
        return clean_v

    @field_validator("confidence")
    @classmethod
    def validate_confidence_range(cls, v: float) -> float:
        if v < 0.0 or v > 1.0:
            raise ValueError(f"confidence {v} out of range [0.0, 1.0]")
        return round(float(v), 4)

    @field_validator("ambiguous")
    @classmethod
    def validate_ambiguous_bool(cls, v: Any) -> bool:
        if not isinstance(v, bool):
            raise ValueError(f"ambiguous must be a boolean, got {type(v).__name__}")
        return v


def parse_and_clean_json(raw_text: str) -> Dict[str, Any]:
    """Safely extract and parse JSON from LLM output, rejecting malformed text."""
    text = raw_text.strip()
    # Strip markdown codeblocks if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

    # Look for outer JSON object
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No valid JSON object found in response: {raw_text[:100]}...")

    json_str = match.group(0)
    return json.loads(json_str)


def compute_prompt_version(prompt_text: str) -> str:
    """Compute deterministic prompt version identifier combining header and content hash."""
    header_match = re.search(r"#\s*VERSION:\s*([^\r\n]+)", prompt_text, re.IGNORECASE)
    ver_tag = header_match.group(1).strip() if header_match else "v1.0"
    content_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:8]
    return f"{ver_tag}_{content_hash}"


def verify_evidence_grounding(
    evidence_span: str, customer_message: str, agent_notes: str
) -> bool:
    """Check if evidence_span is actually present in customer_message or agent_notes."""
    import difflib

    if not evidence_span or not str(evidence_span).strip():
        return True

    span_clean = str(evidence_span).strip().strip('"\'')
    if not span_clean:
        return True

    combined_source = f"{customer_message or ''} {agent_notes or ''}"

    # 1. Direct case-insensitive substring check
    if span_clean.lower() in combined_source.lower():
        return True

    # 2. Whitespace-normalized check (handles newlines and multiple spaces)
    span_norm = re.sub(r"\s+", " ", span_clean).lower()
    combined_norm = re.sub(r"\s+", " ", combined_source).lower()
    if span_norm in combined_norm:
        return True

    # 3. Punctuation-stripped check
    span_alpha = re.sub(r"[^\w\s]", "", span_norm)
    combined_alpha = re.sub(r"[^\w\s]", "", combined_norm)
    if span_alpha in combined_alpha:
        return True

    # 4. Fuzzy window match (accounts for customer typos like 'cahrge' vs 'charge')
    words_span = span_norm.split()
    words_combined = combined_norm.split()
    w_len = len(words_span)
    if w_len > 0 and len(words_combined) >= w_len:
        for i in range(len(words_combined) - w_len + 1):
            window = " ".join(words_combined[i : i + w_len])
            if difflib.SequenceMatcher(None, span_norm, window).ratio() >= 0.85:
                return True

    return False



class IssueExtractor:
    """Manages prompt execution, output validation, caching, and batch processing."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        prompt_path: Optional[Path] = None,
        cache_file: Optional[Path] = None,
        model: Optional[str] = None,
    ) -> None:
        self.llm_client = llm_client or LLMClient(model=model)
        self.model_name = self.llm_client.model
        self.prompt_path = prompt_path or PROMPT_ISSUE_EXTRACTION
        self.cache_file = cache_file or EXTRACTION_CACHE_FILE

        if not self.prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found at {self.prompt_path}")

        self.system_prompt = self.prompt_path.read_text(encoding="utf-8")
        self.prompt_version = compute_prompt_version(self.system_prompt)

        # In-memory and on-disk cache
        self.cache_df: pd.DataFrame = self._load_cache()

    def _load_cache(self) -> pd.DataFrame:
        if self.cache_file.exists():
            try:
                return pd.read_parquet(self.cache_file)
            except Exception:
                pass
        return pd.DataFrame()

    def _save_cache(self) -> None:
        if not self.cache_df.empty:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            self.cache_df.to_parquet(self.cache_file, index=False)

    def is_cached(self, ticket_id: str) -> bool:
        if self.cache_df.empty:
            return False
        matches = self.cache_df[
            (self.cache_df["ticket_id"] == ticket_id)
            & (self.cache_df["prompt_version"] == self.prompt_version)
            & (self.cache_df["model"] == self.model_name)
        ]
        return not matches.empty

    def get_from_cache(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        if self.cache_df.empty:
            return None
        matches = self.cache_df[
            (self.cache_df["ticket_id"] == ticket_id)
            & (self.cache_df["prompt_version"] == self.prompt_version)
            & (self.cache_df["model"] == self.model_name)
        ]
        if not matches.empty:
            return matches.iloc[0].to_dict()
        return None

    def format_user_prompt(self, ticket_row: Dict[str, Any]) -> str:
        """Create structured ticket context for LLM input."""
        channel = ticket_row.get("channel", "Unknown")
        product = ticket_row.get("prod_product_name") or ticket_row.get("product_sku", "Unknown")
        customer_msg = ticket_row.get("customer_message", "")
        agent_notes = ticket_row.get("agent_notes", "")

        return (
            f"Ticket ID: {ticket_row.get('ticket_id')}\n"
            f"Channel: {channel}\n"
            f"Product: {product}\n"
            f"Customer Message:\n{customer_msg}\n\n"
            f"Agent Notes:\n{agent_notes}"
        )

    def extract_ticket(
        self,
        ticket_row: Dict[str, Any],
        use_cache: bool = True,
        max_retries: int = 2,
    ) -> Dict[str, Any]:
        """
        Extract structured issue information for a single ticket.
        Never silently fakes valid data if LLM response is malformed.
        """
        ticket_id = str(ticket_row["ticket_id"])
        customer_msg = str(ticket_row.get("customer_message") or "")
        agent_notes = str(ticket_row.get("agent_notes") or "")

        # 1. Check Cache
        if use_cache and self.is_cached(ticket_id):
            cached = self.get_from_cache(ticket_id)
            if cached is not None:
                cached["from_cache"] = True
                return cached

        # 2. Call LLM with retry for schema / JSON validation
        user_prompt = self.format_user_prompt(ticket_row)
        attempts = 0
        last_error = None

        while attempts <= max_retries:
            attempts += 1
            try:
                llm_res = self.llm_client.generate(
                    system_prompt=self.system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.0,
                    max_tokens=400,
                )
                raw_text = llm_res["raw_text"]
                extracted_at = llm_res["extracted_at"]

                # Parse JSON
                parsed_data = parse_and_clean_json(raw_text)

                # Validate with Pydantic
                schema_obj = IssueExtractionSchema(**parsed_data)

                # Grounding check: verify evidence_span
                evidence_span = schema_obj.evidence_span.strip()
                is_grounded = verify_evidence_grounding(
                    evidence_span, customer_msg, agent_notes
                )
                if not is_grounded:
                    # If span was not verbatim, retry or flag
                    # Clean surrounding quotes
                    stripped_span = evidence_span.strip('"\'')
                    if verify_evidence_grounding(stripped_span, customer_msg, agent_notes):
                        evidence_span = stripped_span
                        is_grounded = True
                    else:
                        # Non-grounded evidence span is an issue
                        if attempts <= max_retries:
                            last_error = f"evidence_span '{evidence_span}' not found in source text"
                            continue

                # Clean validated output dict
                result: Dict[str, Any] = {
                    "ticket_id": ticket_id,
                    "issue_code": schema_obj.issue_code,
                    "sub_issue": schema_obj.sub_issue,
                    "repeat_claim": schema_obj.repeat_claim,
                    "evidence_span": evidence_span,
                    "confidence": schema_obj.confidence,
                    "ambiguous": schema_obj.ambiguous,
                    "reason": schema_obj.reason or "",
                    "model": self.model_name,
                    "prompt_version": self.prompt_version,
                    "extracted_at": extracted_at,
                    "raw_response": raw_text,
                    "from_cache": False,
                    "is_valid": True,
                    "is_grounded": is_grounded,
                    "error": None,
                }

                # Update in-memory and disk cache
                new_row_df = pd.DataFrame([result])
                if self.cache_df.empty:
                    self.cache_df = new_row_df
                else:
                    self.cache_df = pd.concat([self.cache_df, new_row_df], ignore_index=True)
                self._save_cache()

                return result

            except Exception as e:
                last_error = f"{type(e).__name__}: {str(e)}"

        # If all retries failed, raise or return explicit invalid record
        raise ValueError(
            f"Extraction failed for ticket {ticket_id} after {attempts} attempts. Last error: {last_error}"
        )

    def extract_batch(
        self,
        tickets_df: pd.DataFrame,
        use_cache: bool = True,
        on_progress: Optional[Any] = None,
    ) -> pd.DataFrame:
        """Process a dataframe of tickets, returning extractions dataframe."""
        results: List[Dict[str, Any]] = []
        for idx, row in tickets_df.iterrows():
            res = self.extract_ticket(row.to_dict(), use_cache=use_cache)
            results.append(res)
            if on_progress:
                on_progress(len(results), len(tickets_df))

        return pd.DataFrame(results)
