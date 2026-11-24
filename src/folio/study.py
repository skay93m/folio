"""Escaped study-markup adapter for retrieval and tutorial reading blocks.

This small dialect accepts plain paragraphs, ``sk:`` learner paragraphs,
``> [!tutor]`` quoted callouts (with optional tutor label), fenced YAML-like
``quiz`` multiple-choice blocks (``id``, ``question``, ``options`` ``A:``-``D:``,
``answer``, ``explanation``), and fenced ``mermaid`` diagrams. It does not
accept raw HTML or attempt to replace a general Markdown renderer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_OPTION_KEY_RE = re.compile(r"^([A-D])\s*:\s*(.+)$")
_SCALAR_KEY_RE = re.compile(r"^(id|question|answer|explanation)\s*:\s*(.*)$")


@dataclass(frozen=True, slots=True)
class StudyBlock:
    """Plain text block passed to autoescaped Django templates."""

    kind: str
    text: str
    answer: str = ""
    label: str = ""
    quiz_id: str = ""
    options: tuple[tuple[str, str], ...] = ()
    explanation: str = ""


def _read_fenced_block(lines: list[str], start_index: int, block_name: str) -> tuple[list[str], int]:
    """Collect lines inside a fenced code block until closing ``` or raise ValueError."""
    index = start_index + 1
    content: list[str] = []
    while index < len(lines) and lines[index].strip() != "```":
        content.append(lines[index])
        index += 1
    if index == len(lines):
        raise ValueError(f"{block_name} requires a closing fence")
    return content, index + 1


def _unquote_yaml_scalar(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        quote = value[0]
        inner = value[1:-1]
        if quote == '"':
            inner = inner.replace('\\"', '"').replace("\\\\", "\\")
        else:
            inner = inner.replace("''", "'")
        return inner.strip()
    return value


def _parse_quiz_block(content: list[str]) -> StudyBlock:
    """Parse structured YAML-like TeachArtifact quiz fields with strict validation."""
    fields: dict[str, str] = {}
    options: list[tuple[str, str]] = []
    seen_option_keys: set[str] = set()
    in_options = False
    active_scalar_key: str | None = None

    for raw_line in content:
        stripped = raw_line.strip()
        if not stripped:
            continue
        is_indented = len(raw_line) > len(raw_line.lstrip(" \t"))
        if in_options and is_indented:
            opt_match = _OPTION_KEY_RE.match(stripped)
            if not opt_match:
                raise ValueError(f"quiz option must use A-D key format: {stripped!r}")
            opt_key, opt_raw = opt_match.group(1), opt_match.group(2)
            if opt_key in seen_option_keys:
                raise ValueError(f"quiz contains duplicate option {opt_key!r}")
            opt_text = _unquote_yaml_scalar(opt_raw)
            if not opt_text:
                raise ValueError(f"quiz option {opt_key!r} must not be empty")
            seen_option_keys.add(opt_key)
            options.append((opt_key, opt_text))
            continue

        if is_indented and active_scalar_key in {"question", "explanation"}:
            fields[active_scalar_key] = f"{fields[active_scalar_key]} {stripped}".strip()
            continue

        in_options = False
        active_scalar_key = None
        if stripped == "options:":
            in_options = True
            continue

        scalar_match = _SCALAR_KEY_RE.match(stripped)
        if not scalar_match:
            raise ValueError(f"quiz contains unsupported field or syntax: {stripped!r}")
        key, raw_val = scalar_match.group(1), scalar_match.group(2)
        fields[key] = _unquote_yaml_scalar(raw_val)
        active_scalar_key = key

    question = fields.get("question", "").strip()
    answer = fields.get("answer", "").strip().upper()
    explanation = fields.get("explanation", "").strip()
    quiz_id = fields.get("id", "").strip()

    if not question:
        raise ValueError("quiz requires a non-empty question")
    if len(options) < 2:
        raise ValueError("quiz requires at least two options (A-D)")
    if not answer or answer not in seen_option_keys:
        raise ValueError("quiz answer must match one of the declared option keys")
    if not explanation:
        raise ValueError("quiz requires a non-empty explanation")

    return StudyBlock(
        kind="quiz",
        text=question,
        answer=answer,
        quiz_id=quiz_id,
        options=tuple(options),
        explanation=explanation,
    )


def _is_tutor_header(line: str) -> bool:
    return line == "> [!tutor]" or line.startswith(("> [!tutor] ", "> [!tutor]\t"))


def _parse_tutor_callout(lines: list[str], start_index: int) -> tuple[StudyBlock, int]:
    header_tail = lines[start_index].strip()[len("> [!tutor]") :].strip()
    label = ""
    body_lines: list[str] = []
    if header_tail:
        if ":" in header_tail:
            prefix, rest = header_tail.split(":", 1)
            label = prefix.strip()
            if rest.strip():
                body_lines.append(rest.strip())
        else:
            label = header_tail

    index = start_index + 1
    while index < len(lines) and lines[index].lstrip().startswith(">"):
        body_lines.append(lines[index].lstrip()[1:].lstrip())
        index += 1

    text = "\n".join(body_lines).strip()
    if not text:
        raise ValueError("tutor callout requires text")
    return StudyBlock("tutor", text, label=label), index


def parse_study_markup(source: str) -> tuple[StudyBlock, ...]:
    """Validate and parse the documented study dialect without HTML execution."""
    lines = source.splitlines()
    blocks: list[StudyBlock] = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        if line == "```quiz":
            content, index = _read_fenced_block(lines, index, "quiz")
            blocks.append(_parse_quiz_block(content))
        elif line == "```mermaid":
            content, index = _read_fenced_block(lines, index, "mermaid")
            diagram = "\n".join(content).strip()
            if not diagram:
                raise ValueError("mermaid requires diagram source")
            blocks.append(StudyBlock("mermaid", diagram))
        elif _is_tutor_header(line):
            block, index = _parse_tutor_callout(lines, index)
            blocks.append(block)
        else:
            kind = "learner" if line.startswith("sk:") else "paragraph"
            content = [line[3:].lstrip() if kind == "learner" else line]
            index += 1
            while (
                index < len(lines)
                and lines[index].strip()
                and not lines[index].strip().startswith(("sk:", "> [!tutor]", "```quiz", "```mermaid"))
            ):
                content.append(lines[index].strip())
                index += 1
            text = "\n".join(content).strip()
            if not text:
                raise ValueError("learner turn requires text")
            blocks.append(StudyBlock(kind, text))
    return tuple(blocks)
