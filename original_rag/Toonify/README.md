# TOONIFY v2.0

**One file. Zero dependencies. Drop it anywhere. Run it.**

Master of: **Python, JavaScript, TypeScript, Rust**

## Usage

```bash
# Drop toonify.py in your project root, then:
python toonify.py
```

That's it. Outputs `<project_name>.toon`. Paste into any AI chat.

## What It Does

Recursively scans your entire project from root to deepest subfolder:
- All files, all directories (ignores `node_modules`, `target/`, `.git`, etc.)
- Extracts **functions, classes, types, imports, call graphs**
- Creates a `.toon` file with your entire codebase structure

**76% smaller than JSON.** LLMs read it natively.

## Master Languages

| Language | What It Extracts |
|----------|-----------------|
| **Python** | Functions (AST), classes, decorators, docstrings, **call graph**, imports |
| **JavaScript** | Functions, classes, exports, imports, React hooks, JSX |
| **TypeScript** | Functions, types, interfaces, enums, generics, decorators |
| **Rust** | `fn`, `struct`, `enum`, `trait`, `impl`, `use`, `mod`, `macro_rules!`, attributes |

### Rust Deep Support

```rust
// All of these are extracted:
#[derive(Debug, Serialize)]
pub struct Config { ... }

pub async fn fetch_data() -> Result<Data> { ... }

impl Display for Config { ... }

macro_rules! my_macro { ... }

use crate::utils::{helper, format};
```

### Python Deep Support

```python
# All of these are extracted:
@dataclass
class User:
    """User model with validation."""
    name: str

async def fetch_user(id: int) -> User:
    """Fetch user by ID."""
    result = db.query(id)  # Call graph captured!
    return validate(result)
```

## Other Languages (Basic Support)

Go, Java, Ruby, PHP, C#, Swift, Kotlin, Scala, Elixir, Zig

## Why?

```
Day 1: Working with AI on your project, full context
Day 5: New chat session, AI knows NOTHING

Solution:
  python toonify.py
  -> paste .toon into chat
  -> instant project context restored
```

## Future Vision: RAG Pipeline

The `.toon` format is designed as a foundation for **semantic code search**:
- Structured metadata without full file contents
- Function signatures and call relationships
- Type hierarchies and trait implementations
- Import graphs for dependency analysis

Use `index.toon` as the retrieval layer in a RAG pipeline - search over codebase structure without embedding millions of tokens.

## Requirements

- Python 3.6+
- Nothing else. Zero dependencies.

## Example Output

```bash
$ python toonify.py

Scanning: /home/user/my-rust-project

============================================================
TOONIFY COMPLETE
============================================================
Files indexed:            127
Functions found:          892
Exports found:            234
Import edges:            1456
Languages:         rust(89), python(23), typescript(15)
Master languages:  rust, python, typescript
------------------------------------------------------------
JSON size:            589,234 bytes
TOON size:            139,456 bytes
Savings:                 76.3%
============================================================
Output: /home/user/my-rust-project/my-rust-project.toon

Paste the .toon file into any AI chat for instant context!
```

## Custom Output

```bash
python toonify.py -o context.toon        # Custom filename
python toonify.py /other/project         # Different directory
```

## Version History

| Version | Changes |
|---------|---------|
| 2.0 | Enhanced Rust parser, Python call graphs, docstring extraction, attribute capture |
| 1.0 | Initial release with basic parsing |

## License

MIT
