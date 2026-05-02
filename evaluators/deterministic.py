from __future__ import annotations

import re
from typing import List, Optional, Tuple

from core.models import FailureCategory, TestCase, ValidatorSpec
from evaluators.base import BaseEvaluator


class DeterministicEvaluator(BaseEvaluator):
    """Rule-based validators — runs on every test before the LLM judge.

    All methods return (score 0.0–1.0, reason_or_None). Score in [0.3, 0.7]
    triggers the judge; outside that band the judge is skipped to save cost.
    """

    def evaluate(self, test_case: TestCase, response: str) -> Tuple[float, Optional[str]]:
        if test_case.validators:
            return self._run_custom_validators(test_case.validators, response)

        fn = {
            FailureCategory.INSTRUCTION_LOSS: self._check_instruction_loss,
            FailureCategory.RETRIEVAL_OVERSHADOWING: self._check_retrieval_overshadowing,
            FailureCategory.POSITION_BIAS: self._check_position_bias,
            FailureCategory.ANSWER_TRUNCATION: self._check_answer_truncation,
            FailureCategory.MULTI_TURN_MEMORY_DECAY: self._check_memory_decay,
            FailureCategory.CONTRADICTION_LONG_CONTEXT: self._check_contradiction,
            FailureCategory.CITATION_DRIFT: self._check_citation_drift,
            FailureCategory.HALLUCINATION_OVERLOAD: self._check_hallucination,
        }.get(test_case.failure_category)

        return fn(test_case, response) if fn else (0.5, "No validator for category")

    # ── custom YAML validators ─────────────────────────────────────────────────

    def _run_custom_validators(
        self, validators: List[ValidatorSpec], response: str
    ) -> Tuple[float, Optional[str]]:
        total_weight = sum(v.weight for v in validators)
        earned = 0.0
        failures: List[str] = []

        for v in validators:
            passed, reason = self._run_one_validator(v, response)
            if passed:
                earned += v.weight
            else:
                failures.append(reason or v.description or v.type)

        score = earned / total_weight if total_weight > 0 else 0.5
        return score, "; ".join(failures) if failures else None

    def _run_one_validator(self, v: ValidatorSpec, response: str) -> Tuple[bool, Optional[str]]:
        r = response.lower()
        if v.type == "contains_pattern":
            ok = bool(re.search(v.pattern or "", response, re.IGNORECASE))
            return ok, (f"Missing pattern: {v.pattern}" if not ok else None)
        if v.type == "not_contains":
            ok = not bool(re.search(v.pattern or "", response, re.IGNORECASE))
            return ok, (f"Forbidden pattern found: {v.pattern}" if not ok else None)
        if v.type == "min_length":
            ok = len(response.strip()) >= int(v.value or 0)
            return ok, (f"Response too short ({len(response)} < {v.value})" if not ok else None)
        if v.type == "max_length":
            ok = len(response.strip()) <= int(v.value or 99999)
            return ok, (f"Response too long ({len(response)} > {v.value})" if not ok else None)
        if v.type == "ends_with_punctuation":
            ok = bool(re.search(r"[.!?]\s*$", response.strip()))
            return ok, ("Response does not end with proper punctuation" if not ok else None)
        if v.type == "contains_all":
            required = v.value if isinstance(v.value, list) else [v.value]
            missing = [s for s in required if s.lower() not in r]
            return (not missing), (f"Missing required terms: {missing}" if missing else None)
        return True, None

    # ── category 1: instruction_loss ──────────────────────────────────────────

    def _check_instruction_loss(
        self, tc: TestCase, response: str
    ) -> Tuple[float, Optional[str]]:
        """Check whether the model violated explicit constraints in the system prompt."""
        score = 1.0
        reasons: List[str] = []
        sys = tc.system_prompt
        sys_lower = sys.lower()
        resp_lower = response.lower()

        # Citation requirement
        if any(kw in sys_lower for kw in ["cite", "citation", "[1]", "(source", "reference"]):
            if not re.search(r"\[\d+\]|\(source:|\(ref:", response, re.IGNORECASE):
                score -= 0.4
                reasons.append("Missing required citations")

        # Word / length limit: "maximum N words" / "no more than N words"
        limit_match = re.search(
            r"(?:maximum|no more than|at most|limit of?)\s+(\d+)\s+words", sys_lower
        )
        if limit_match:
            limit = int(limit_match.group(1))
            word_count = len(response.split())
            if word_count > limit * 1.1:
                score -= 0.35
                reasons.append(f"Exceeds word limit ({word_count} > {limit})")

        # Language restriction: "respond only in X" / "answer in X only"
        lang_match = re.search(
            r"(?:respond|answer|reply)\s+(?:only\s+)?in\s+(\w+)(?:\s+only)?", sys_lower
        )
        if lang_match:
            lang = lang_match.group(1)
            if lang == "english":
                non_ascii_ratio = len([c for c in response if ord(c) > 127]) / max(len(response), 1)
                if non_ascii_ratio > 0.1:
                    score -= 0.3
                    reasons.append("Response contains non-English characters despite language constraint")

        # Forbidden topic: "never mention X" / "do not include X"
        forbidden = re.findall(
            r"(?:never|do not|don't|avoid)\s+(?:mention|include|say|use|refer to)\s+([^\.,\n]{3,40})",
            sys_lower,
        )
        for phrase in forbidden[:2]:
            phrase_words = [w for w in phrase.split() if len(w) > 3]
            if phrase_words and any(w in resp_lower for w in phrase_words):
                score -= 0.2
                reasons.append(f"Violated 'do not mention' constraint: {phrase[:40]}")
                break

        # Required prefix: 'always start with "X"'
        start_match = re.search(r'always (?:start|begin) with ["\']([^"\']{2,40})["\']', sys_lower)
        if start_match:
            required_start = start_match.group(1).lower()
            if not resp_lower.startswith(required_start):
                score -= 0.3
                reasons.append("Response doesn't start with required prefix")

        # Bullet / list format — covers "use bullets", "bullet list", "respond with a list", etc.
        if re.search(r"\bbullet(?:\s+list)?|\bnumbered list|respond with (?:a\s+)?(?:bullet|list)", sys_lower):
            if not re.search(r"^\s*[-*•]|\n\s*[-*•]|\n\s*\d+[.)]\s", response, re.MULTILINE):
                score -= 0.25
                reasons.append("Expected list/bullet format not used")

        return max(0.0, score), "; ".join(reasons) if reasons else None

    # ── category 2: retrieval_overshadowing ───────────────────────────────────

    def _check_retrieval_overshadowing(
        self, tc: TestCase, response: str
    ) -> Tuple[float, Optional[str]]:
        """Detect when response parrots chunks verbatim while ignoring the actual query."""
        query_words = set(re.findall(r"\b\w{4,}\b", tc.user_query.lower()))
        resp_lower = response.lower()
        chunk_text = " ".join(tc.chunks).lower()

        # Query keyword coverage
        if not query_words:
            return 0.5, None
        coverage = sum(1 for w in query_words if w in resp_lower) / len(query_words)

        # Verbatim overlap: fraction of response's long words that appear in chunks
        resp_words = re.findall(r"\b\w{6,}\b", resp_lower)
        if resp_words:
            chunk_word_set = set(re.findall(r"\b\w{6,}\b", chunk_text))
            verbatim_ratio = sum(1 for w in resp_words if w in chunk_word_set) / len(resp_words)
        else:
            verbatim_ratio = 0.0

        # High verbatim overlap + low query coverage = model just copy-pasted context
        if verbatim_ratio > 0.65 and coverage < 0.3:
            return 0.2, (
                f"Response appears to parrot context verbatim ({verbatim_ratio:.0%} overlap) "
                f"without answering the query (coverage: {coverage:.0%})"
            )

        # Check for telltale "according to the provided context" phrases — classic overshadowing
        if re.search(
            r"(?:according to|based on|as (?:stated|mentioned)) (?:the )?(?:provided |above )?context",
            response,
            re.IGNORECASE,
        ) and coverage < 0.35:
            return 0.35, "Response anchored to context dump, not to the query"

        if coverage < 0.3:
            return 0.25, f"Response doesn't address the query (keyword coverage: {coverage:.0%})"

        return min(1.0, 0.45 + coverage * 0.55), None

    # ── category 3: position_bias ─────────────────────────────────────────────

    def _check_position_bias(
        self, tc: TestCase, response: str
    ) -> Tuple[float, Optional[str]]:
        """Position bias requires comparing scores across different chunk orderings.

        A single run can't conclusively prove bias — we need the same test with
        shuffled vs sequential chunks and delta comparison. Flag as needs cross-run.
        """
        # We can still check a necessary (not sufficient) condition:
        # if middle chunks carry unique keywords that never appear in the response,
        # that's a weak signal.
        if len(tc.chunks) < 3:
            return 0.5, "Requires cross-run comparison to detect position bias"

        resp_lower = response.lower()
        middle_chunks = tc.chunks[1:-1]
        covered = 0
        for chunk in middle_chunks:
            words = re.findall(r"\b\w{6,}\b", chunk.lower())
            if any(w in resp_lower for w in words[:5]):
                covered += 1

        if covered == 0 and middle_chunks:
            return 0.4, "Middle chunks not referenced — possible position bias (verify with cross-run)"

        return 0.5, "Requires cross-run comparison to detect position bias conclusively"

    # ── category 4: answer_truncation ─────────────────────────────────────────

    def _check_answer_truncation(
        self, tc: TestCase, response: str
    ) -> Tuple[float, Optional[str]]:
        """Check whether the response is complete or cut off."""
        stripped = response.strip()

        if not stripped:
            return 0.0, "Empty response"

        # Only enforce minimum length for multi-chunk summarisation questions.
        # Targeted lookups (2 chunks, specific question) legitimately have short answers.
        if len(tc.chunks) >= 3:
            min_expected = len(tc.chunks) * 30
            if len(stripped) < min_expected:
                return 0.3, (
                    f"Response too short ({len(stripped)} chars) given {len(tc.chunks)} chunks "
                    f"(expected ≥{min_expected})"
                )

        if len(stripped) < 20:
            return 0.2, f"Suspiciously short ({len(stripped)} chars)"

        # Ellipsis ending = explicit truncation signal
        if stripped.endswith("...") or stripped.endswith("…"):
            return 0.35, "Response ends with ellipsis — likely truncated"

        # Mid-word cut (no space, no punctuation after long token)
        if re.search(r"\b\w{20,}$", stripped):
            return 0.3, "Possible mid-word truncation"

        # Ends with a dangling clause (substantial text, no terminal punctuation)
        last_line = stripped.split("\n")[-1].strip()
        if len(last_line) > 20 and not re.search(r"[.!?)\]\"'`]\s*$", last_line):
            return 0.45, "Response ends without terminal punctuation (possible truncation)"

        return 1.0, None

    # ── category 5: multi_turn_memory_decay ───────────────────────────────────

    def _check_memory_decay(
        self, tc: TestCase, response: str
    ) -> Tuple[float, Optional[str]]:
        """Check if response contradicts or ignores facts established in conversation history."""
        if not tc.conversation_history:
            return 1.0, None

        resp_lower = response.lower()
        assistant_turns = [
            t["content"] for t in tc.conversation_history if t.get("role") == "assistant"
        ]
        if not assistant_turns:
            return 1.0, None

        history_text = " ".join(assistant_turns).lower()
        chunk_text = " ".join(tc.chunks).lower()

        # Numbers established in history that the model should honour
        history_numbers = set(
            re.findall(r"\b\d+(?:\.\d+)?(?:%|million|billion|k|thousand)?\b", history_text)
        )
        response_numbers = set(
            re.findall(r"\b\d+(?:\.\d+)?(?:%|million|billion|k|thousand)?\b", resp_lower)
        )
        chunk_numbers = set(
            re.findall(r"\b\d+(?:\.\d+)?(?:%|million|billion|k|thousand)?\b", chunk_text)
        )

        # Numbers present in response but absent from both history and context = contradiction risk
        alien = response_numbers - history_numbers - chunk_numbers - {"0", "1", "2", "3"}
        if len(alien) > 2:
            return 0.4, f"Response introduces numbers not in history or context: {sorted(alien)[:3]}"

        # Check if model ignores named entities from earlier assistant turns
        history_entities = set(re.findall(r"\b[A-Z][a-z]{2,}\b", " ".join(assistant_turns)))
        if len(history_entities) > 2:
            referenced = sum(1 for e in history_entities if e.lower() in resp_lower)
            if referenced == 0 and len(tc.conversation_history) >= 4:
                return 0.45, "Response ignores entities established in conversation history"

        # Check for direct contradiction keywords
        if re.search(
            r"\b(?:actually|in fact|no,|incorrect|wrong|that's not)\b",
            resp_lower,
        ) and len(assistant_turns) > 0:
            # Model may be contradicting its own prior statement
            return 0.5, "Response contains contradiction signals vs prior assistant turns"

        return 1.0, None

    # ── category 6: contradiction_long_context ────────────────────────────────

    def _check_contradiction(
        self, tc: TestCase, response: str
    ) -> Tuple[float, Optional[str]]:
        """Check if response silently asserts conflicting facts from different chunks."""
        # 1. Planted conflict marker from ConflictingEvidencePerturbation
        chunks_with_conflict = [c for c in tc.chunks if "[CONFLICTING DATA]" in c]
        if chunks_with_conflict:
            if re.search(
                r"\bconflict|contradic|inconsist|disagree|discrepan|however.{0,30}differ",
                response,
                re.IGNORECASE,
            ):
                return 0.85, None  # model correctly flagged the conflict
            return 0.3, "Model did not acknowledge conflicting evidence in context"

        # 2. Directional contradiction: response claims both increase and decrease for same metric
        increases = re.findall(
            r"\b(?:increase[ds]?|grew?|rose?|gained?|up\s+\d)\b.{0,60}\b(\d+(?:\.\d+)?%?)\b",
            response,
            re.IGNORECASE,
        )
        decreases = re.findall(
            r"\b(?:decrease[ds]?|fell?|dropped?|down\s+\d)\b.{0,60}\b(\d+(?:\.\d+)?%?)\b",
            response,
            re.IGNORECASE,
        )
        if increases and decreases:
            inc_vals = {re.sub(r"%$", "", v) for v in increases}
            dec_vals = {re.sub(r"%$", "", v) for v in decreases}
            if inc_vals & dec_vals:
                return 0.2, "Response makes contradictory directional claims about the same value"

        # 3. Explicit contradiction patterns within the response
        if re.search(
            r"\bon one hand\b.{10,200}\bon the other hand\b",
            response,
            re.IGNORECASE | re.DOTALL,
        ):
            return 0.8, None  # model surfaced the tension

        return 1.0, None

    # ── category 7: citation_drift ────────────────────────────────────────────

    def _check_citation_drift(
        self, tc: TestCase, response: str
    ) -> Tuple[float, Optional[str]]:
        """Verify citations exist, are in range, and loosely support the claim they annotate."""
        citations = re.findall(r"\[(\d+)\]", response)

        if not citations:
            if any(kw in tc.system_prompt.lower() for kw in ["cite", "citation", "[1]", "(source"]):
                return 0.3, "No citations found despite citation requirement"
            return 0.7, None  # ambiguous — send to judge

        max_valid = len(tc.chunks)
        out_of_range = [int(c) for c in citations if int(c) < 1 or int(c) > max_valid]
        if out_of_range:
            return 0.15, f"Citations reference non-existent chunks: {out_of_range}"

        # Semantic drift: sentence citing [N] should share at least one key word with chunk N
        sentences = re.split(r"(?<=[.!?])\s+", response)
        drift_count = 0
        for sent in sentences:
            cited_indices = re.findall(r"\[(\d+)\]", sent)
            if not cited_indices:
                continue
            clean = re.sub(r"\[\d+\]", "", sent).lower()
            sent_words = set(re.findall(r"\b\w{5,}\b", clean))
            for cidx in cited_indices:
                idx = int(cidx) - 1
                if 0 <= idx < len(tc.chunks):
                    chunk_words = set(re.findall(r"\b\w{5,}\b", tc.chunks[idx].lower()))
                    if sent_words and len(sent_words & chunk_words) == 0:
                        drift_count += 1

        if drift_count >= 2:
            return 0.35, f"{drift_count} citations don't semantically match the chunks they reference"

        return 1.0, None

    # ── category 8: hallucination_overload ────────────────────────────────────

    def _check_hallucination(
        self, tc: TestCase, response: str
    ) -> Tuple[float, Optional[str]]:
        """Check whether numeric claims in response are within 10% of any chunk number."""
        if not tc.chunks:
            return 0.5, None

        chunk_text = " ".join(tc.chunks).lower()

        def extract_numbers(text: str):
            result = []
            for m in re.finditer(
                r"\b(\d+(?:\.\d+)?)\s*(million|billion|thousand|k|b|m|%)?(?!\w)", text
            ):
                base = float(m.group(1))
                mult = {
                    "million": 1e6, "billion": 1e9, "thousand": 1e3,
                    "k": 1e3, "m": 1e6, "b": 1e9, "%": 1,
                }.get(m.group(2) or "", 1)
                result.append(base * mult)
            return result

        response_nums = extract_numbers(response.lower())
        chunk_nums = extract_numbers(chunk_text)

        unsupported: List[float] = []
        for r_num in response_nums:
            if r_num < 2:  # skip trivial counts (1, 2, 3…)
                continue
            if not chunk_nums:
                unsupported.append(r_num)
                continue
            # passes if any chunk number is within 10% tolerance
            if not any(
                abs(r_num - c_num) / max(abs(c_num), 1e-9) <= 0.10
                for c_num in chunk_nums
                if c_num > 0
            ):
                unsupported.append(r_num)

        if len(unsupported) >= 2:
            sample = [f"{n:.4g}" for n in unsupported[:3]]
            return 0.3, f"{len(unsupported)} numeric claims not supported by context (±10%): {sample}"

        # Named entity check — capitalized bi-grams absent from context
        entities = re.findall(r"\b([A-Z][a-z]{2,} [A-Z][a-z]{2,})\b", response)
        alien = [e for e in entities if e.lower() not in chunk_text]
        if len(alien) > 2:
            return 0.4, f"Response mentions entities not in context: {alien[:3]}"

        return 1.0, None
