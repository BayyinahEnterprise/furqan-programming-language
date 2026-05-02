"""Furqan parser — public surface.

The parser layer's stable surface is the :func:`parse` entry point and
the AST node set. The tokenizer is exported for tooling that needs to
work below parse level (syntax-highlighting, language-server token
streams). All names below are pinned by the additive-only invariant
declared in NAMING.md §6.
"""

from .ast_nodes import (
    # v0.1.x nodes
    BismillahBlock,
    CallRef,
    FunctionDef,
    Module,
    SourceSpan,
    # Phase 2.4 (Session 1.3) — zahir/batin nodes
    CompoundTypeDef,
    FieldDecl,
    LayerAccess,
    LayerBlock,
    ParamDecl,
    TypePath,
    # Phase 2.5 (Session 1.4) — additive-only module nodes
    AdditiveOnlyModuleDecl,
    ExportDecl,
    MajorVersionBump,
    RemovesEntry,
    RenamesEntry,
    VersionLiteral,
    # Phase 2.6 (Session 1.5) — scan-incomplete nodes
    CallStmt,
    IdentExpr,
    IdentList,
    IfStmt,
    IncompleteField,
    IncompleteLiteral,
    IntegrityLiteral,
    NotExpr,
    NumberLiteral,
    ReturnStmt,
    StringLiteral,
    UnionType,
    # Phase 2.7 (Session 1.6) — Mizan calibration nodes
    BinaryComparisonExpr,
    ComparisonOp,
    MizanDecl,
    MizanField,
    # Phase 2.8 (Session 1.7) — Tanzil build-ordering nodes
    DependencyEntry,
    TanzilDecl,
)
from .parser import MAX_NESTING_DEPTH, ParseError, parse
from .tokenizer import (
    KEYWORDS,
    Token,
    TokenizeError,
    TokenKind,
    tokenize,
)

__all__ = [
    # Tokenizer surface
    "KEYWORDS",
    "Token",
    "TokenKind",
    "TokenizeError",
    "tokenize",
    # AST nodes — v0.1.x
    "BismillahBlock",
    "CallRef",
    "FunctionDef",
    "Module",
    "SourceSpan",
    # AST nodes — Phase 2.4 additions
    "CompoundTypeDef",
    "FieldDecl",
    "LayerAccess",
    "LayerBlock",
    "ParamDecl",
    "TypePath",
    # AST nodes — Phase 2.5 additions
    "AdditiveOnlyModuleDecl",
    "ExportDecl",
    "MajorVersionBump",
    "RemovesEntry",
    "RenamesEntry",
    "VersionLiteral",
    # AST nodes — Phase 2.6 additions
    "CallStmt",
    "IdentExpr",
    "IdentList",
    "IfStmt",
    "IncompleteField",
    "IncompleteLiteral",
    "IntegrityLiteral",
    "NotExpr",
    "NumberLiteral",
    "ReturnStmt",
    "StringLiteral",
    "UnionType",
    # AST nodes — Phase 2.7 additions
    "BinaryComparisonExpr",
    "ComparisonOp",
    "MizanDecl",
    "MizanField",
    # AST nodes — Phase 2.8 additions
    "DependencyEntry",
    "TanzilDecl",
    # Parser surface
    "MAX_NESTING_DEPTH",
    "ParseError",
    "parse",
]
