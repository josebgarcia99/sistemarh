"""Manifiesto de archivos para respaldos y verificación de una copia.

El manifiesto se genera desde SQL Server (lista de archivos confirmados con
clave, tamaño y SHA-256). La verificación compara un manifiesto contra un
árbol de archivos —el almacenamiento o una copia restaurada— sin necesitar
la base de datos.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

MANIFEST_VERSION = 1


@dataclass(frozen=True)
class ManifestEntry:
    key: str
    size: int
    sha256: str


@dataclass
class VerificationReport:
    checked: int = 0
    hashes_checked: int = 0
    missing: list[str] = field(default_factory=list)
    size_mismatch: list[str] = field(default_factory=list)
    hash_mismatch: list[str] = field(default_factory=list)
    unexpected: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.missing or self.size_mismatch or self.hash_mismatch)


def write_manifest(
    path: Path, entries: Iterable[ManifestEntry], *, generated_at: str, schema_version: str
) -> int:
    """Escribe el manifiesto (JSON por líneas). Devuelve cuántos archivos lista."""
    count = 0
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        header = {
            "manifest_version": MANIFEST_VERSION,
            "generated_at": generated_at,
            "schema_version": schema_version,
        }
        handle.write(json.dumps(header) + "\n")
        for entry in entries:
            handle.write(
                json.dumps({"key": entry.key, "size": entry.size, "sha256": entry.sha256}) + "\n"
            )
            count += 1
    return count


def read_manifest(path: Path) -> Iterator[ManifestEntry]:
    with open(path, encoding="utf-8") as handle:
        header = json.loads(handle.readline())
        if header.get("manifest_version") != MANIFEST_VERSION:
            raise ValueError("Versión de manifiesto no reconocida.")
        for line in handle:
            if line.strip():
                item = json.loads(line)
                yield ManifestEntry(item["key"], int(item["size"]), item["sha256"])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def verify_tree(
    root: Path, entries: Iterable[ManifestEntry], *, full: bool = False
) -> VerificationReport:
    """Comprueba que cada archivo del manifiesto existe, mide lo mismo y, con
    ``full``, tiene el mismo SHA-256. También lista archivos no esperados."""
    root = root.resolve()
    report = VerificationReport()
    expected: set[str] = set()
    for entry in entries:
        expected.add(entry.key)
        path = (root / entry.key).resolve()
        report.checked += 1
        if not path.is_relative_to(root) or not path.is_file():
            report.missing.append(entry.key)
            continue
        if path.stat().st_size != entry.size:
            report.size_mismatch.append(entry.key)
            continue
        if full:
            report.hashes_checked += 1
            if _sha256(path) != entry.sha256:
                report.hash_mismatch.append(entry.key)
    for area in ("private", "generated"):
        base = root / area
        if base.is_dir():
            for path in sorted(base.rglob("*")):
                key = path.relative_to(root).as_posix()
                if path.is_file() and key not in expected:
                    report.unexpected.append(key)
    return report
