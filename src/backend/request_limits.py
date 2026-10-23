"""Fixed public JSON request limits, shared by models and the receive boundary."""

MAX_TEXT_CHARACTERS = 8_000
MAX_HISTORY_MESSAGES = 50
MAX_HISTORY_CHARACTERS = 64_000
MAX_MODEL_CHARACTERS = 256
MAX_API_KEY_CHARACTERS = 4_096
MAX_BASE_URL_CHARACTERS = 2_048
MAX_JSON_BODY_BYTES = 1_048_576

# Python str.isspace()'s Unicode whitespace set, expressed explicitly so Rust
# regex (Pydantic), Python regex (JSON Schema), and JavaScript (Ajv) agree.
# A match requires at least one character outside this set; text is never stripped.
NONBLANK_PATTERN = (
    r"[^\u0009-\u000D\u001C-\u0020\u0085\u00A0\u1680\u2000-\u200A"
    r"\u2028\u2029\u202F\u205F\u3000]"
)
