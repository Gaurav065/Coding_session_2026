from pathlib import Path

logic_source = Path("competitor_main.py").read_text(encoding="utf-8")
tape_source = Path("fieldbook_tapes.py").read_text(encoding="utf-8")

TAPE_BEGIN = "# === BEGIN FIELD BOOK PLAN SCRIPTS ==="
TAPE_END = "# === END FIELD BOOK PLAN SCRIPTS ==="

tape_begin = tape_source.index(TAPE_BEGIN) + len(TAPE_BEGIN) + 1
tape_end = tape_source.index("\n" + TAPE_END, tape_begin)
tape_block = tape_source[tape_begin:tape_end]

PLACEHOLDER = "from fieldbook_tapes import PLAN_SCRIPTS\n\n# <FIELD_BOOK_PLAN_SCRIPTS>"
assembled = logic_source.replace(PLACEHOLDER, tape_block)

Path("their_agent.py").write_text(assembled, encoding="utf-8")
print("Successfully assembled their_agent.py!")
