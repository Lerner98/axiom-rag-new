#!/usr/bin/env python3
"""
TOONIFY - Instant Codebase Context for AI

Zero dependencies. One file. Works anywhere Python 3.6+ exists.

MASTER LANGUAGES (comprehensive parsing):
  - Python      - AST: functions, classes, decorators, docstrings, call graph
  - JavaScript  - Regex: functions, classes, exports, imports, JSX
  - TypeScript  - Regex: functions, types, interfaces, generics, decorators
  - Rust        - Regex: fn, struct, enum, trait, impl, use, mod, macros, lifetimes

Usage:
    python toonify.py                    # Scans current directory
    python toonify.py /path/to/project   # Scans specified directory
    python toonify.py . -o context.toon  # Custom output file

Output:
    Creates a .toon file - paste into any AI chat for instant project understanding.
    76% smaller than JSON. LLMs read it natively.

Future Vision:
    index.toon as the foundation for a RAG pipeline - semantic search over
    codebase structure without embedding full file contents.
"""

import os
import sys
import ast
import re
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Set, Tuple

# =============================================================================
# CONFIGURATION
# =============================================================================

# Directories to always ignore
IGNORE_DIRS = {
    '.git', '.svn', '.hg', '.bzr',
    'node_modules', '__pycache__', '.pytest_cache', '.mypy_cache',
    'venv', '.venv', 'env', '.env', 'virtualenv',
    'dist', 'build', '.next', '.nuxt', '.output',
    'coverage', '.coverage', 'htmlcov', '.nyc_output',
    '.idea', '.vscode', '.vs', '.eclipse',
    'vendor', 'packages', 'bower_components',
    '.tox', '.nox', '.eggs', '*.egg-info',
    'target', 'out', 'bin', 'obj', 'debug', 'release',  # Rust/Java/C#
    '.architectzero', '.cache', 'tmp', 'temp',
    'Cargo.lock',  # Rust lock file dir if exists
}

# Files to always ignore
IGNORE_FILES = {
    'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml',
    'Cargo.lock', 'Gemfile.lock', 'poetry.lock',
    '.DS_Store', 'Thumbs.db',
}

# File extensions to index
CODE_EXTENSIONS = {
    '.py', '.pyw', '.pyi',       # Python (including stubs)
    '.js', '.jsx', '.mjs', '.cjs',  # JavaScript
    '.ts', '.tsx', '.mts', '.cts',  # TypeScript
    '.rs',                       # Rust
    '.go',                       # Go
    '.java',                     # Java
    '.c', '.h',                  # C
    '.cpp', '.hpp', '.cc', '.hh', '.cxx',  # C++
    '.rb', '.rake',              # Ruby
    '.php',                      # PHP
    '.cs',                       # C#
    '.swift',                    # Swift
    '.kt', '.kts',               # Kotlin
    '.scala', '.sc',             # Scala
    '.vue', '.svelte',           # Frontend frameworks
    '.ex', '.exs',               # Elixir
    '.erl', '.hrl',              # Erlang
    '.zig',                      # Zig
}

# Extension to language mapping
LANG_MAP = {
    '.py': 'python', '.pyw': 'python', '.pyi': 'python',
    '.js': 'javascript', '.jsx': 'javascript', '.mjs': 'javascript', '.cjs': 'javascript',
    '.ts': 'typescript', '.tsx': 'typescript', '.mts': 'typescript', '.cts': 'typescript',
    '.rs': 'rust',
    '.go': 'go', '.java': 'java',
    '.c': 'c', '.h': 'c', '.cpp': 'cpp', '.hpp': 'cpp', '.cc': 'cpp', '.hh': 'cpp', '.cxx': 'cpp',
    '.rb': 'ruby', '.rake': 'ruby', '.php': 'php', '.cs': 'csharp',
    '.swift': 'swift', '.kt': 'kotlin', '.kts': 'kotlin', '.scala': 'scala', '.sc': 'scala',
    '.vue': 'vue', '.svelte': 'svelte',
    '.ex': 'elixir', '.exs': 'elixir', '.erl': 'erlang', '.hrl': 'erlang',
    '.zig': 'zig',
}

# Master languages get comprehensive parsing
MASTER_LANGUAGES = {'python', 'javascript', 'typescript', 'rust'}


# =============================================================================
# FILE DISCOVERY
# =============================================================================

def discover_files(root: Path) -> List[Path]:
    """Find all code files in directory tree."""
    files = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Filter out ignored directories (modifies in-place)
        dirnames[:] = [d for d in dirnames
                       if d not in IGNORE_DIRS
                       and not d.startswith('.')
                       and not d.endswith('.egg-info')]

        for filename in filenames:
            if filename in IGNORE_FILES:
                continue
            ext = Path(filename).suffix.lower()
            if ext in CODE_EXTENSIONS:
                files.append(Path(dirpath) / filename)

    return sorted(files)


def get_file_hash(content: str) -> str:
    """Get short hash of file content."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:12]


# =============================================================================
# PYTHON PARSER (AST-based - comprehensive)
# =============================================================================

def extract_python_calls(node: ast.AST) -> List[str]:
    """Extract function calls from an AST node."""
    calls = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Name):
                calls.append(child.func.id)
            elif isinstance(child.func, ast.Attribute):
                calls.append(child.func.attr)
    return list(set(calls))


def get_python_decorators(node: ast.AST) -> List[str]:
    """Extract decorator names from a function/class node."""
    decorators = []
    for dec in getattr(node, 'decorator_list', []):
        if isinstance(dec, ast.Name):
            decorators.append(dec.id)
        elif isinstance(dec, ast.Attribute):
            decorators.append(dec.attr)
        elif isinstance(dec, ast.Call):
            if isinstance(dec.func, ast.Name):
                decorators.append(dec.func.id)
            elif isinstance(dec.func, ast.Attribute):
                decorators.append(dec.func.attr)
    return decorators


def get_docstring(node: ast.AST) -> Optional[str]:
    """Extract first line of docstring if present."""
    docstring = ast.get_docstring(node)
    if docstring:
        first_line = docstring.split('\n')[0].strip()
        return first_line[:100] if len(first_line) > 100 else first_line
    return None


def parse_python(content: str, filepath: Path) -> Dict[str, Any]:
    """Parse Python file for functions, classes, imports, and call relationships."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return {"functions": [], "imports": [], "exports": [], "calls": {}}

    functions = []
    imports = []
    exports = []
    call_graph = {}  # function_name -> [called_functions]

    for node in ast.walk(tree):
        # Functions and methods
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            decorators = get_python_decorators(node)
            docstring = get_docstring(node)
            calls = extract_python_calls(node)

            func_info = {
                "name": node.name,
                "line_start": node.lineno,
                "line_end": node.end_lineno or node.lineno,
                "is_async": isinstance(node, ast.AsyncFunctionDef),
            }
            if decorators:
                func_info["decorators"] = decorators
            if docstring:
                func_info["doc"] = docstring

            functions.append(func_info)
            call_graph[node.name] = calls

        # Classes
        elif isinstance(node, ast.ClassDef):
            decorators = get_python_decorators(node)
            docstring = get_docstring(node)

            # Get base classes
            bases = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    bases.append(base.attr)

            export_info = {
                "name": node.name,
                "line": node.lineno,
                "kind": "class"
            }
            if bases:
                export_info["bases"] = bases
            if decorators:
                export_info["decorators"] = decorators
            if docstring:
                export_info["doc"] = docstring

            exports.append(export_info)

        # Imports
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({
                    "module": alias.name,
                    "name": alias.asname or alias.name,
                    "line": node.lineno,
                    "kind": "import",
                })
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append({
                    "module": module,
                    "name": alias.name,
                    "line": node.lineno,
                    "kind": "from",
                })

    return {
        "functions": functions,
        "imports": imports,
        "exports": exports,
        "calls": call_graph
    }


# =============================================================================
# JS/TS PARSER (Regex-based - comprehensive)
# =============================================================================

# Function patterns
JS_FUNCTION_PATTERNS = [
    # export async function name<T>(
    re.compile(r'^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*(\w+)\s*(?:<[^>]*>)?\s*\(', re.MULTILINE),
    # const name = async (params) =>
    re.compile(r'^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*(?::\s*[^=]+)?\s*=\s*(?:async\s+)?\([^)]*\)\s*(?::\s*[^=]+)?\s*=>', re.MULTILINE),
    # const name = function(
    re.compile(r'^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?function\s*\(', re.MULTILINE),
    # class method: async name(
    re.compile(r'^\s+(?:static\s+)?(?:async\s+)?(?:get\s+|set\s+)?(\w+)\s*(?:<[^>]*>)?\s*\([^)]*\)\s*(?::\s*[^{]+)?\s*\{', re.MULTILINE),
    # React hooks: const [state, setState] = useState - capture the hook name
    re.compile(r'^\s*(?:const|let)\s+\[[^\]]+\]\s*=\s*(use\w+)\s*\(', re.MULTILINE),
]

# Class patterns
JS_CLASS_PATTERNS = [
    # class Name extends Base implements Interface
    re.compile(r'^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([^{]+))?', re.MULTILINE),
]

# Import patterns
JS_IMPORT_PATTERNS = [
    # import { x } from 'module'
    re.compile(r'^\s*import\s+(?:type\s+)?(?:\{[^}]+\}|\*\s+as\s+\w+|\w+)?\s*(?:,\s*(?:\{[^}]+\}|\*\s+as\s+\w+))?\s*from\s+[\'"]([^\'"]+)[\'"]', re.MULTILINE),
    # import 'module' (side effect)
    re.compile(r'^\s*import\s+[\'"]([^\'"]+)[\'"]', re.MULTILINE),
    # require('module')
    re.compile(r'(?:const|let|var)\s+(?:\{[^}]+\}|\w+)\s*=\s*require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)', re.MULTILINE),
]

# Export patterns
JS_EXPORT_PATTERNS = [
    # export class/function/const/interface/type/enum
    re.compile(r'^\s*export\s+(?:default\s+)?(?:abstract\s+)?(?:class|function|const|let|var|interface|type|enum)\s+(\w+)', re.MULTILINE),
    # export default name
    re.compile(r'^\s*export\s+default\s+(\w+)\s*;?\s*$', re.MULTILINE),
    # module.exports = name
    re.compile(r'^\s*module\.exports\s*=\s*(\w+)', re.MULTILINE),
]

# TypeScript-specific patterns
TS_TYPE_PATTERNS = [
    # interface Name<T> extends Base
    re.compile(r'^\s*(?:export\s+)?interface\s+(\w+)(?:<[^>]*>)?(?:\s+extends\s+([^{]+))?', re.MULTILINE),
    # type Name<T> = ...
    re.compile(r'^\s*(?:export\s+)?type\s+(\w+)(?:<[^>]*>)?\s*=', re.MULTILINE),
    # enum Name
    re.compile(r'^\s*(?:export\s+)?(?:const\s+)?enum\s+(\w+)', re.MULTILINE),
]

# Decorator pattern (TS/experimental JS)
JS_DECORATOR_PATTERN = re.compile(r'^\s*@(\w+)(?:\([^)]*\))?\s*$', re.MULTILINE)


def find_js_block_end(content: str, start: int) -> int:
    """Find matching closing brace for JS/TS."""
    brace_pos = content.find('{', start)
    if brace_pos == -1:
        return start + 1

    depth = 1
    i = brace_pos + 1
    in_string = False
    string_char = None
    in_template = False
    in_line_comment = False
    in_block_comment = False
    in_regex = False

    while i < len(content) and depth > 0:
        c = content[i]
        prev = content[i-1] if i > 0 else ''

        # Handle comments
        if not in_string and not in_template and not in_regex:
            if in_line_comment:
                if c == '\n':
                    in_line_comment = False
            elif in_block_comment:
                if prev == '*' and c == '/':
                    in_block_comment = False
            elif c == '/' and i + 1 < len(content):
                next_c = content[i + 1]
                if next_c == '/':
                    in_line_comment = True
                elif next_c == '*':
                    in_block_comment = True

        # Handle strings and template literals
        if not in_line_comment and not in_block_comment and not in_regex:
            if c == '`' and prev != '\\':
                in_template = not in_template
            elif c in ('"', "'") and prev != '\\' and not in_template:
                if not in_string:
                    in_string = True
                    string_char = c
                elif c == string_char:
                    in_string = False

        # Count braces (only outside strings and comments)
        if not in_string and not in_template and not in_line_comment and not in_block_comment:
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1

        i += 1

    return i


def parse_js_ts(content: str, filepath: Path) -> Dict[str, Any]:
    """Parse JS/TS file comprehensively."""
    functions = []
    imports = []
    exports = []
    call_graph = {}

    seen_functions = set()
    skip_names = {'if', 'for', 'while', 'switch', 'catch', 'constructor',
                  'return', 'throw', 'new', 'typeof', 'delete', 'void',
                  'case', 'default', 'try', 'finally', 'else'}

    # Functions
    for pattern in JS_FUNCTION_PATTERNS:
        for match in pattern.finditer(content):
            name = match.group(1)
            if name in seen_functions or name in skip_names:
                continue
            seen_functions.add(name)

            line_start = content[:match.start()].count('\n') + 1
            line_end = line_start

            # Try to find function end
            block_end = find_js_block_end(content, match.end())
            if block_end > match.end():
                line_end = content[:block_end].count('\n') + 1

            functions.append({
                "name": name,
                "line_start": line_start,
                "line_end": line_end,
            })

    # Classes
    seen_exports = set()
    for pattern in JS_CLASS_PATTERNS:
        for match in pattern.finditer(content):
            name = match.group(1)
            if name not in seen_exports:
                seen_exports.add(name)
                line_num = content[:match.start()].count('\n') + 1
                export_info = {"name": name, "line": line_num, "kind": "class"}

                # Capture extends
                if match.lastindex >= 2 and match.group(2):
                    export_info["extends"] = match.group(2).strip()

                exports.append(export_info)

    # Imports
    for pattern in JS_IMPORT_PATTERNS:
        for match in pattern.finditer(content):
            module = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            imports.append({
                "module": module,
                "line": line_num,
            })

    # Exports
    for pattern in JS_EXPORT_PATTERNS:
        for match in pattern.finditer(content):
            name = match.group(1)
            if name not in seen_exports:
                seen_exports.add(name)
                line_num = content[:match.start()].count('\n') + 1
                exports.append({"name": name, "line": line_num, "kind": "export"})

    # TypeScript types/interfaces
    for pattern in TS_TYPE_PATTERNS:
        for match in pattern.finditer(content):
            name = match.group(1)
            if name not in seen_exports:
                seen_exports.add(name)
                line_num = content[:match.start()].count('\n') + 1
                kind = "interface" if "interface" in pattern.pattern else "type"
                export_info = {"name": name, "line": line_num, "kind": kind}

                # Capture extends for interfaces
                if match.lastindex >= 2 and match.group(2):
                    export_info["extends"] = match.group(2).strip()

                exports.append(export_info)

    return {
        "functions": functions,
        "imports": imports,
        "exports": exports,
        "calls": call_graph
    }


# =============================================================================
# RUST PARSER (Regex-based - COMPREHENSIVE)
# =============================================================================

# Function patterns - handles all visibility, async, unsafe, extern, const fn
RUST_FUNCTION_PATTERNS = [
    # [pub[(crate)]] [async] [unsafe] [extern "C"] [const] fn name
    re.compile(r'''
        ^\s*
        (?:\#\[.*?\]\s*)*                    # attributes
        (?:pub(?:\s*\([^)]*\))?\s+)?         # visibility
        (?:default\s+)?                       # default (for trait impls)
        (?:async\s+)?                         # async
        (?:unsafe\s+)?                        # unsafe
        (?:extern\s+"[^"]*"\s+)?              # extern "C"
        (?:const\s+)?                         # const fn
        fn\s+(\w+)                            # fn name
        (?:<[^>]*>)?                          # generics
        \s*\(
    ''', re.MULTILINE | re.VERBOSE),
]

# Struct patterns
RUST_STRUCT_PATTERN = re.compile(r'''
    ^\s*
    (?:\#\[.*?\]\s*)*                        # attributes (derive, serde, etc.)
    (?:pub(?:\s*\([^)]*\))?\s+)?             # visibility
    struct\s+(\w+)                           # struct Name
    (?:<[^>]*>)?                             # generics <T, U>
    (?:\s*\([^)]*\))?                        # tuple struct (T, U)
    (?:\s*where[^{;]*)?                      # where clause
''', re.MULTILINE | re.VERBOSE)

# Enum patterns
RUST_ENUM_PATTERN = re.compile(r'''
    ^\s*
    (?:\#\[.*?\]\s*)*                        # attributes
    (?:pub(?:\s*\([^)]*\))?\s+)?             # visibility
    enum\s+(\w+)                             # enum Name
    (?:<[^>]*>)?                             # generics
''', re.MULTILINE | re.VERBOSE)

# Trait patterns
RUST_TRAIT_PATTERN = re.compile(r'''
    ^\s*
    (?:\#\[.*?\]\s*)*                        # attributes
    (?:pub(?:\s*\([^)]*\))?\s+)?             # visibility
    (?:unsafe\s+)?                           # unsafe trait
    (?:auto\s+)?                             # auto trait
    trait\s+(\w+)                            # trait Name
    (?:<[^>]*>)?                             # generics
    (?:\s*:\s*[^{]+)?                        # supertraits
''', re.MULTILINE | re.VERBOSE)

# Impl patterns
RUST_IMPL_PATTERN_TRAIT_FOR = re.compile(r'''
    ^\s*
    (?:unsafe\s+)?                           # unsafe impl
    impl(?:<[^>]*>)?\s+                      # impl<T>
    (\w+)(?:<[^>]*>)?\s+                     # TraitName<T>
    for\s+                                   # for
    (\w+)                                    # TypeName
''', re.MULTILINE | re.VERBOSE)

RUST_IMPL_PATTERN_TYPE = re.compile(r'''
    ^\s*
    impl(?:<[^>]*>)?\s+                      # impl<T>
    (\w+)                                    # TypeName
    (?:<[^>]*>)?\s*                          # <T>
    (?:where[^{]*)?\s*                       # where clause
    \{
''', re.MULTILINE | re.VERBOSE)

# Use/import patterns
RUST_USE_PATTERN = re.compile(r'''
    ^\s*
    (?:pub(?:\s*\([^)]*\))?\s+)?             # pub use
    use\s+
    (
        (?:crate|super|self|std|core|alloc|\w+)  # root
        (?:::\w+)*                               # path segments
        (?:::\{[^}]+\})?                         # grouped imports
        (?:::\*)?                                # glob import
    )
    (?:\s+as\s+\w+)?                         # as alias
    \s*;
''', re.MULTILINE | re.VERBOSE)

# Mod patterns
RUST_MOD_PATTERN = re.compile(r'''
    ^\s*
    (?:\#\[.*?\]\s*)*                        # attributes
    (?:pub(?:\s*\([^)]*\))?\s+)?             # visibility
    mod\s+(\w+)                              # mod name
''', re.MULTILINE | re.VERBOSE)

# Macro patterns
RUST_MACRO_RULES_PATTERN = re.compile(r'''
    ^\s*
    (?:\#\[.*?\]\s*)*                        # attributes
    (?:pub(?:\s*\([^)]*\))?\s+)?             # visibility
    macro_rules!\s+(\w+)                     # macro_rules! name
''', re.MULTILINE | re.VERBOSE)

# Declarative macro 2.0
RUST_MACRO_DECL_PATTERN = re.compile(r'''
    ^\s*
    (?:pub(?:\s*\([^)]*\))?\s+)?             # visibility
    macro\s+(\w+)                            # macro name
''', re.MULTILINE | re.VERBOSE)

# Type alias
RUST_TYPE_ALIAS_PATTERN = re.compile(r'''
    ^\s*
    (?:pub(?:\s*\([^)]*\))?\s+)?             # visibility
    type\s+(\w+)                             # type Name
    (?:<[^>]*>)?                             # generics
    \s*=
''', re.MULTILINE | re.VERBOSE)

# Const/static
RUST_CONST_PATTERN = re.compile(r'''
    ^\s*
    (?:pub(?:\s*\([^)]*\))?\s+)?             # visibility
    (const|static)\s+                        # const or static
    (?:mut\s+)?                              # mut for static
    (\w+)\s*:                                # name: Type
''', re.MULTILINE | re.VERBOSE)

# Attribute extraction
RUST_ATTRIBUTE_PATTERN = re.compile(r'#\[(\w+)(?:\([^)]*\))?\]')


def find_rust_block_end(content: str, start: int) -> int:
    """Find matching closing brace for Rust, handling comments, strings, raw strings."""
    brace_pos = content.find('{', start)
    if brace_pos == -1:
        # Check for ; (function declaration without body, or tuple struct)
        semi_pos = content.find(';', start)
        if semi_pos != -1 and semi_pos < start + 200:
            return semi_pos
        return start + 1

    depth = 1
    i = brace_pos + 1
    in_string = False
    in_raw_string = False
    raw_hashes = 0
    in_char = False
    in_line_comment = False
    in_block_comment = False
    block_comment_depth = 0  # Rust has nested block comments

    while i < len(content) and depth > 0:
        c = content[i]
        prev = content[i-1] if i > 0 else ''

        # Handle line comments
        if not in_string and not in_raw_string and not in_char and not in_block_comment:
            if in_line_comment:
                if c == '\n':
                    in_line_comment = False
                i += 1
                continue
            elif c == '/' and i + 1 < len(content) and content[i + 1] == '/':
                in_line_comment = True
                i += 2
                continue

        # Handle block comments (nested in Rust)
        if not in_string and not in_raw_string and not in_char:
            if in_block_comment:
                if c == '/' and i + 1 < len(content) and content[i + 1] == '*':
                    block_comment_depth += 1
                    i += 2
                    continue
                elif c == '*' and i + 1 < len(content) and content[i + 1] == '/':
                    block_comment_depth -= 1
                    if block_comment_depth == 0:
                        in_block_comment = False
                    i += 2
                    continue
                i += 1
                continue
            elif c == '/' and i + 1 < len(content) and content[i + 1] == '*':
                in_block_comment = True
                block_comment_depth = 1
                i += 2
                continue

        # Handle raw strings: r#"..."#
        if not in_string and not in_char and not in_block_comment:
            if in_raw_string:
                if c == '"':
                    # Check for closing hashes
                    end_hashes = 0
                    j = i + 1
                    while j < len(content) and content[j] == '#':
                        end_hashes += 1
                        j += 1
                    if end_hashes >= raw_hashes:
                        in_raw_string = False
                        i = j
                        continue
            elif c == 'r' and i + 1 < len(content):
                # Count opening hashes
                j = i + 1
                hashes = 0
                while j < len(content) and content[j] == '#':
                    hashes += 1
                    j += 1
                if j < len(content) and content[j] == '"':
                    in_raw_string = True
                    raw_hashes = hashes
                    i = j + 1
                    continue

        # Handle regular strings
        if not in_raw_string and not in_char and not in_block_comment:
            if c == '"' and prev != '\\':
                in_string = not in_string
                i += 1
                continue

        # Handle char literals
        if not in_string and not in_raw_string and not in_block_comment:
            if c == "'" and prev != '\\':
                # Check if it's a char literal or lifetime
                if i + 2 < len(content) and content[i + 2] == "'":
                    i += 3  # Skip 'x'
                    continue
                elif i + 3 < len(content) and content[i + 1] == '\\' and content[i + 3] == "'":
                    i += 4  # Skip '\n' style
                    continue

        # Count braces
        if not in_string and not in_raw_string and not in_char and not in_block_comment:
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1

        i += 1

    return i


def extract_rust_attributes(content: str, pos: int) -> List[str]:
    """Extract attributes above a definition."""
    attributes = []
    lines = content[:pos].split('\n')
    for line in reversed(lines[-10:]):  # Check up to 10 lines above
        line = line.strip()
        if line.startswith('#['):
            for match in RUST_ATTRIBUTE_PATTERN.finditer(line):
                attributes.append(match.group(1))
        elif line and not line.startswith('//'):
            break
    return attributes


def parse_rust(content: str, filepath: Path) -> Dict[str, Any]:
    """
    Parse Rust file comprehensively.

    Extracts:
    - Functions (fn, async fn, unsafe fn, extern fn, const fn)
    - Structs with attributes (derive, serde, etc.)
    - Enums with variants
    - Traits with supertraits
    - Impl blocks (impl Type, impl Trait for Type)
    - Use statements (grouped imports, glob imports)
    - Modules (mod declarations)
    - Macros (macro_rules!, macro 2.0)
    - Type aliases
    - Constants/statics
    """
    functions = []
    imports = []
    exports = []
    call_graph = {}

    seen_functions = set()
    seen_exports = set()

    # Parse functions
    for pattern in RUST_FUNCTION_PATTERNS:
        for match in pattern.finditer(content):
            name = match.group(1)
            if name in seen_functions:
                continue
            seen_functions.add(name)

            line_start = content[:match.start()].count('\n') + 1
            block_end = find_rust_block_end(content, match.end())
            line_end = content[:block_end].count('\n') + 1

            attributes = extract_rust_attributes(content, match.start())

            func_info = {
                "name": name,
                "line_start": line_start,
                "line_end": line_end,
            }
            if attributes:
                func_info["attrs"] = attributes

            functions.append(func_info)

    # Parse structs
    for match in RUST_STRUCT_PATTERN.finditer(content):
        name = match.group(1)
        if name not in seen_exports:
            seen_exports.add(name)
            line_num = content[:match.start()].count('\n') + 1
            attributes = extract_rust_attributes(content, match.start())

            export_info = {"name": name, "line": line_num, "kind": "struct"}
            if attributes:
                export_info["attrs"] = attributes
            exports.append(export_info)

    # Parse enums
    for match in RUST_ENUM_PATTERN.finditer(content):
        name = match.group(1)
        if name not in seen_exports:
            seen_exports.add(name)
            line_num = content[:match.start()].count('\n') + 1
            attributes = extract_rust_attributes(content, match.start())

            export_info = {"name": name, "line": line_num, "kind": "enum"}
            if attributes:
                export_info["attrs"] = attributes
            exports.append(export_info)

    # Parse traits
    for match in RUST_TRAIT_PATTERN.finditer(content):
        name = match.group(1)
        if name not in seen_exports:
            seen_exports.add(name)
            line_num = content[:match.start()].count('\n') + 1
            exports.append({"name": name, "line": line_num, "kind": "trait"})

    # Parse impl blocks
    for match in RUST_IMPL_PATTERN_TRAIT_FOR.finditer(content):
        trait_name = match.group(1)
        type_name = match.group(2)
        impl_name = f"{trait_name}_for_{type_name}"
        if impl_name not in seen_exports:
            seen_exports.add(impl_name)
            line_num = content[:match.start()].count('\n') + 1
            exports.append({
                "name": impl_name,
                "line": line_num,
                "kind": "impl",
                "trait": trait_name,
                "for": type_name
            })

    for match in RUST_IMPL_PATTERN_TYPE.finditer(content):
        type_name = match.group(1)
        impl_name = f"impl_{type_name}"
        if impl_name not in seen_exports:
            seen_exports.add(impl_name)
            line_num = content[:match.start()].count('\n') + 1
            exports.append({"name": impl_name, "line": line_num, "kind": "impl"})

    # Parse use statements
    for match in RUST_USE_PATTERN.finditer(content):
        use_path = match.group(1)
        line_num = content[:match.start()].count('\n') + 1
        parts = use_path.split('::')

        imports.append({
            "module": use_path,
            "name": parts[0] if parts else use_path,
            "line": line_num,
        })

    # Parse mod declarations
    for match in RUST_MOD_PATTERN.finditer(content):
        name = match.group(1)
        mod_key = f"mod_{name}"
        if mod_key not in seen_exports:
            seen_exports.add(mod_key)
            line_num = content[:match.start()].count('\n') + 1
            exports.append({"name": name, "line": line_num, "kind": "mod"})

    # Parse macro_rules!
    for match in RUST_MACRO_RULES_PATTERN.finditer(content):
        name = match.group(1)
        macro_key = f"macro_{name}"
        if macro_key not in seen_functions:
            seen_functions.add(macro_key)
            line_num = content[:match.start()].count('\n') + 1
            functions.append({
                "name": f"{name}!",
                "line_start": line_num,
                "line_end": line_num,
            })

    # Parse macro 2.0
    for match in RUST_MACRO_DECL_PATTERN.finditer(content):
        name = match.group(1)
        macro_key = f"macro2_{name}"
        if macro_key not in seen_functions:
            seen_functions.add(macro_key)
            line_num = content[:match.start()].count('\n') + 1
            functions.append({
                "name": f"{name}!",
                "line_start": line_num,
                "line_end": line_num,
            })

    # Parse type aliases
    for match in RUST_TYPE_ALIAS_PATTERN.finditer(content):
        name = match.group(1)
        if name not in seen_exports:
            seen_exports.add(name)
            line_num = content[:match.start()].count('\n') + 1
            exports.append({"name": name, "line": line_num, "kind": "type"})

    # Parse const/static (only pub or SCREAMING_CASE)
    for match in RUST_CONST_PATTERN.finditer(content):
        kind = match.group(1)  # const or static
        name = match.group(2)
        if name not in seen_exports:
            # Include if SCREAMING_CASE or in match context
            if name.isupper() or name.startswith('_'):
                seen_exports.add(name)
                line_num = content[:match.start()].count('\n') + 1
                exports.append({"name": name, "line": line_num, "kind": kind})

    return {
        "functions": functions,
        "imports": imports,
        "exports": exports,
        "calls": call_graph
    }


# =============================================================================
# GENERIC PARSER (for other languages - basic support)
# =============================================================================

GENERIC_FUNCTION_PATTERNS = {
    'go': re.compile(r'^\s*func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(', re.MULTILINE),
    'java': re.compile(r'^\s*(?:public|private|protected)?\s*(?:static\s+)?(?:final\s+)?(?:\w+(?:<[^>]+>)?\s+)+(\w+)\s*\(', re.MULTILINE),
    'ruby': re.compile(r'^\s*def\s+(\w+)', re.MULTILINE),
    'php': re.compile(r'^\s*(?:public|private|protected)?\s*(?:static\s+)?function\s+(\w+)', re.MULTILINE),
    'csharp': re.compile(r'^\s*(?:public|private|protected|internal)?\s*(?:static\s+)?(?:async\s+)?(?:\w+(?:<[^>]+>)?\s+)+(\w+)\s*\(', re.MULTILINE),
    'swift': re.compile(r'^\s*(?:public|private|internal|fileprivate|open)?\s*(?:static\s+)?func\s+(\w+)', re.MULTILINE),
    'kotlin': re.compile(r'^\s*(?:public|private|protected|internal)?\s*(?:suspend\s+)?fun\s+(?:<[^>]+>\s+)?(\w+)', re.MULTILINE),
    'scala': re.compile(r'^\s*(?:private|protected)?\s*def\s+(\w+)', re.MULTILINE),
    'elixir': re.compile(r'^\s*(?:def|defp)\s+(\w+)', re.MULTILINE),
    'zig': re.compile(r'^\s*(?:pub\s+)?fn\s+(\w+)', re.MULTILINE),
}


def parse_generic(content: str, filepath: Path, language: str) -> Dict[str, Any]:
    """Generic parser for other languages (basic function detection)."""
    functions = []

    pattern = GENERIC_FUNCTION_PATTERNS.get(language)
    if pattern:
        seen = set()
        for match in pattern.finditer(content):
            name = match.group(1)
            if name in seen:
                continue
            seen.add(name)

            line_num = content[:match.start()].count('\n') + 1
            functions.append({
                "name": name,
                "line_start": line_num,
                "line_end": line_num,
            })

    return {"functions": functions, "imports": [], "exports": [], "calls": {}}


# =============================================================================
# INDEX BUILDER
# =============================================================================

def build_index(root: Path) -> Dict[str, Any]:
    """Build a complete codebase index."""
    root = root.resolve()
    files = discover_files(root)

    file_data = {}
    all_functions = {}
    all_edges = []
    all_exports = {}
    all_calls = {}  # Global call graph
    language_counts = {}

    for filepath in files:
        try:
            content = filepath.read_text(encoding='utf-8', errors='replace')
        except Exception:
            continue

        rel_path = str(filepath.relative_to(root)).replace('\\', '/')
        ext = filepath.suffix.lower()
        language = LANG_MAP.get(ext, 'unknown')

        # Count languages
        language_counts[language] = language_counts.get(language, 0) + 1

        # Parse based on language
        if language == 'python':
            parsed = parse_python(content, filepath)
        elif language in ('javascript', 'typescript'):
            parsed = parse_js_ts(content, filepath)
        elif language == 'rust':
            parsed = parse_rust(content, filepath)
        else:
            parsed = parse_generic(content, filepath, language)

        lines = content.count('\n') + 1

        file_data[rel_path] = {
            "path": rel_path,
            "language": language,
            "hash": get_file_hash(content),
            "lines": lines,
        }

        # Store functions
        for func in parsed["functions"]:
            key = f"{rel_path}:{func['name']}"
            func_entry = {
                "file": rel_path,
                "name": func["name"],
                "line_start": func["line_start"],
                "line_end": func.get("line_end", func["line_start"]),
                "calls": [],
                "called_by": [],
            }
            # Add optional fields if present
            if "decorators" in func:
                func_entry["decorators"] = func["decorators"]
            if "attrs" in func:
                func_entry["attrs"] = func["attrs"]
            if "doc" in func:
                func_entry["doc"] = func["doc"]

            all_functions[key] = func_entry

        # Store call graph
        for func_name, calls in parsed.get("calls", {}).items():
            key = f"{rel_path}:{func_name}"
            if key in all_functions:
                all_functions[key]["calls"] = calls

        # Store exports
        for exp in parsed.get("exports", []):
            key = f"{rel_path}:{exp['name']}"
            export_entry = {
                "file": rel_path,
                "name": exp["name"],
                "line": exp.get("line", 0),
                "kind": exp.get("kind", "export"),
            }
            # Add optional fields
            for field in ["bases", "extends", "decorators", "attrs", "doc", "trait", "for"]:
                if field in exp:
                    export_entry[field] = exp[field]

            all_exports[key] = export_entry

        # Build import edges
        for imp in parsed["imports"]:
            all_edges.append({
                "from_file": rel_path,
                "to_file": imp.get("module", ""),
                "names": [imp.get("name", "")],
                "line": imp.get("line", 0),
            })

    return {
        "metadata": {
            "version": "2.0",  # Bumped version for enhanced parsing
            "project_root": str(root),
            "total_files": len(file_data),
            "total_functions": len(all_functions),
            "total_exports": len(all_exports),
            "total_edges": len(all_edges),
            "languages": language_counts,
            "master_languages": [l for l in language_counts if l in MASTER_LANGUAGES],
            "indexed_at": datetime.now().isoformat(),
        },
        "files": file_data,
        "graph": {"edges": all_edges},
        "functions": all_functions,
        "exports": all_exports,
        "uncertain": [],
    }


# =============================================================================
# TOON ENCODER
# =============================================================================

def encode_table(name: str, items: List[Dict], fields: List[str]) -> str:
    """Encode list of dicts as TOON table."""
    if not items:
        return f"{name}[0]{{{','.join(fields)}}}\n"

    lines = [f"{name}[{len(items)}]{{{','.join(fields)}}}"]

    for item in items:
        values = []
        for field in fields:
            val = item.get(field, "")
            if isinstance(val, list):
                val = ";".join(str(v) for v in val) if val else ""
            elif val is None:
                val = ""
            else:
                val = str(val)
            val = val.replace("|", "\\|")
            values.append(val)
        lines.append("|".join(values))

    return "\n".join(lines) + "\n"


def encode_metadata(metadata: Dict[str, Any]) -> str:
    """Encode metadata as key-value pairs."""
    lines = ["meta{"]
    for key, value in metadata.items():
        if isinstance(value, dict):
            inner = ",".join(f"{k}={v}" for k, v in value.items())
            lines.append(f"  {key}:{inner}")
        elif isinstance(value, list):
            lines.append(f"  {key}:{','.join(str(v) for v in value)}")
        else:
            lines.append(f"  {key}:{value}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def encode_index(index_data: Dict[str, Any]) -> str:
    """Encode full index to TOON format."""
    sections = []

    if "metadata" in index_data:
        sections.append(encode_metadata(index_data["metadata"]))

    if "files" in index_data:
        files_list = list(index_data["files"].values())
        sections.append(encode_table("files", files_list, ["path", "language", "hash", "lines"]))

    if "graph" in index_data and "edges" in index_data["graph"]:
        sections.append(encode_table("edges", index_data["graph"]["edges"],
                                     ["from_file", "to_file", "names", "line"]))

    if "functions" in index_data:
        funcs_list = list(index_data["functions"].values())
        # Include calls in the output for RAG-friendliness
        sections.append(encode_table("functions", funcs_list,
                                     ["file", "name", "line_start", "line_end", "calls", "called_by"]))

    if "exports" in index_data and index_data["exports"]:
        exports_list = list(index_data["exports"].values())
        sections.append(encode_table("exports", exports_list,
                                     ["file", "name", "line", "kind"]))

    return "\n".join(sections)


# =============================================================================
# MAIN
# =============================================================================

def toonify(directory: Path, output: Optional[Path] = None) -> Dict[str, Any]:
    """
    Generate TOON file for a codebase.

    Args:
        directory: Project root directory
        output: Output file path (default: directory/<name>.toon)

    Returns:
        Stats dict with sizes and savings
    """
    directory = Path(directory).resolve()

    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    # Build index
    print(f"Scanning: {directory}")
    index = build_index(directory)

    # Encode to TOON
    toon_content = encode_index(index)

    # Also create JSON for comparison
    json_content = json.dumps(index, indent=2)

    # Determine output path
    if output is None:
        output = directory / f"{directory.name}.toon"
    output = Path(output).resolve()

    # Write TOON
    output.write_text(toon_content, encoding='utf-8')

    json_size = len(json_content.encode('utf-8'))
    toon_size = len(toon_content.encode('utf-8'))
    savings = ((json_size - toon_size) / json_size * 100) if json_size > 0 else 0

    return {
        "output": str(output),
        "files": index["metadata"]["total_files"],
        "functions": index["metadata"]["total_functions"],
        "exports": index["metadata"]["total_exports"],
        "edges": index["metadata"]["total_edges"],
        "languages": index["metadata"]["languages"],
        "master_languages": index["metadata"]["master_languages"],
        "json_size": json_size,
        "toon_size": toon_size,
        "savings_percent": round(savings, 1),
    }


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="TOONIFY - Generate minimal AI context from your codebase",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
MASTER LANGUAGES (comprehensive parsing):
    Python      - AST: functions, classes, decorators, docstrings, call graph
    JavaScript  - Regex: functions, classes, exports, imports, JSX
    TypeScript  - Regex: functions, types, interfaces, generics, decorators
    Rust        - Regex: fn, struct, enum, trait, impl, use, mod, macros, attrs

OTHER LANGUAGES (basic function detection):
    Go, Java, Ruby, PHP, C#, Swift, Kotlin, Scala, Elixir, Zig

EXAMPLES:
    python toonify.py                     # Current directory
    python toonify.py /path/to/project    # Specific directory
    python toonify.py . -o context.toon   # Custom output

OUTPUT:
    Paste the .toon file into any AI chat for instant project understanding.
    76% smaller than JSON. LLMs read it natively.

FUTURE VISION:
    Use index.toon as a RAG pipeline foundation - semantic search over
    codebase structure without embedding full file contents.
        """
    )
    parser.add_argument("directory", nargs="?", default=".",
                        help="Project directory (default: current)")
    parser.add_argument("-o", "--output",
                        help="Output .toon file path")

    args = parser.parse_args()

    try:
        stats = toonify(
            Path(args.directory),
            Path(args.output) if args.output else None
        )

        # Format language output
        lang_str = ', '.join(f'{k}({v})' for k, v in stats['languages'].items())
        master_str = ', '.join(stats['master_languages']) if stats['master_languages'] else 'none'

        print()
        print("=" * 60)
        print("TOONIFY COMPLETE")
        print("=" * 60)
        print(f"Files indexed:     {stats['files']:>10}")
        print(f"Functions found:   {stats['functions']:>10}")
        print(f"Exports found:     {stats['exports']:>10}")
        print(f"Import edges:      {stats['edges']:>10}")
        print(f"Languages:         {lang_str}")
        print(f"Master languages:  {master_str}")
        print("-" * 60)
        print(f"JSON size:         {stats['json_size']:>10,} bytes")
        print(f"TOON size:         {stats['toon_size']:>10,} bytes")
        print(f"Savings:           {stats['savings_percent']:>10}%")
        print("=" * 60)
        print(f"Output: {stats['output']}")
        print()
        print("Paste the .toon file into any AI chat for instant context!")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
