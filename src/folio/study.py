"""Escaped study-markup adapter for retrieval and tutorial reading blocks.

This small dialect accepts plain paragraphs, ``sk:`` learner paragraphs,
``> [!tutor]`` quoted callouts, fenced ``quiz`` blocks, and fenced ``mermaid``
diagrams. A quiz has a question and an answer separated by a line containing
``---``. It does not accept raw HTML or attempt to replace a general Markdown
renderer.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StudyBlock:
    """Plain text block passed to autoescaped Django templates."""

    kind: str
    text: str
    answer: str = ""


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
            index += 1
            content: list[str] = []
            while index < len(lines) and lines[index].strip() != "```":
                content.append(lines[index])
                index += 1
            if index == len(lines):
                raise ValueError("quiz requires a closing fence")
            separators = [i for i, value in enumerate(content) if value.strip() == "---"]
            if len(separators) != 1:
                raise ValueError("quiz requires one --- question/answer separator")
            split = separators[0]
            question = "\n".join(content[:split]).strip()
            answer = "\n".join(content[split + 1 :]).strip()
            if not question or not answer:
                raise ValueError("quiz requires a question and an answer")
            blocks.append(StudyBlock("quiz", question, answer))
            index += 1
        elif line == "```mermaid":
            index += 1
            content = []
            while index < len(lines) and lines[index].strip() != "```":
                content.append(lines[index])
                index += 1
            if index == len(lines):
                raise ValueError("mermaid requires a closing fence")
            diagram = "\n".join(content).strip()
            if not diagram:
                raise ValueError("mermaid requires diagram source")
            blocks.append(StudyBlock("mermaid", diagram))
            index += 1
        elif line == "> [!tutor]":
            index += 1
            content = []
            while index < len(lines) and lines[index].lstrip().startswith(">"):
                content.append(lines[index].lstrip()[1:].lstrip())
                index += 1
            text = "\n".join(content).strip()
            if not text:
                raise ValueError("tutor callout requires text")
            blocks.append(StudyBlock("tutor", text))
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
