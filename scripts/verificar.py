"""Check source integrity, note metadata and local links without calling AI."""

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote

import yaml


ROOT = Path(__file__).resolve().parents[1]
STATUSES = {
    "extraido", "proposta", "em-pesquisa", "experimental",
    "aguardando-validacao", "aprovado", "arquivado",
}


def metadata(text):
    if not text.startswith("---\n"):
        return None
    _, header, _ = text.split("---", 2)
    value = yaml.safe_load(header)
    if not isinstance(value, dict):
        raise ValueError("Frontmatter deve ser um objeto YAML")
    return value


def check(root):
    errors, warnings, information = [], [], []
    manifest = json.loads((root / "fontes/manifesto.json").read_text(encoding="utf-8"))
    review_path = root / "fontes/revisao.json"
    reviews = json.loads(review_path.read_text(encoding="utf-8")) if review_path.exists() else {}
    blank_reviews = {
        (item["id"], item["sha256"], item["page"])
        for item in reviews.get("verified_blank_pages", [])
    }
    source_ids = set()
    for item in manifest:
        source_id = item["id"]
        if source_id in source_ids:
            errors.append(f"Fonte duplicada: {source_id}")
        source_ids.add(source_id)
        extracted = (root / item["extracted"].replace("\\", "/")).resolve()
        if not extracted.is_relative_to(root.resolve()):
            errors.append(f"Fonte fora da base: {source_id}")
            continue
        if not extracted.is_file():
            errors.append(f"Extracao ausente: {source_id}")
            continue
        text = extracted.read_text(encoding="utf-8")
        numbers = re.findall(r"^## Pagina (\d+)$", text, re.MULTILINE)
        expected = [str(n) for n in range(1, item["pages"] + 1)]
        if numbers != expected:
            errors.append(f"Paginas divergentes: {source_id}")
        raw = extracted.read_bytes()
        normalized = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        windows = normalized.replace(b"\n", b"\r\n")
        hashes = {
            hashlib.sha256(raw).hexdigest(),
            hashlib.sha256(normalized).hexdigest(),
            hashlib.sha256(windows).hexdigest(),
        }
        if item["extracted_sha256"] not in hashes:
            errors.append(f"Texto extraido alterado: {source_id}")
        pages = re.split(r"^## Pagina \d+$", text, flags=re.MULTILINE)[1:]
        for number, page in enumerate(pages, 1):
            if not page.strip():
                message = f"Pagina sem texto: {source_id} p. {number}"
                if (source_id, item["sha256"], number) in blank_reviews:
                    information.append(message + " (pagina branca conferida visualmente)")
                else:
                    warnings.append(message)
        bundled = root / "fontes" / "originais" / item["name"]
        original = bundled if bundled.is_file() else Path(item["original"])
        if not original.is_file():
            warnings.append(f"Original indisponivel: {source_id}")
        elif hashlib.sha256(original.read_bytes()).hexdigest() != item["sha256"]:
            errors.append(f"Original diverge do acervo importado: {source_id}")

    note_ids = set()
    notes = []
    for path in sorted(root.rglob("*.md")):
        parts = path.relative_to(root).parts
        if "fontes" in parts or parts[0] in {".agents", ".codex", ".obsidian", ".git"}:
            continue
        text = path.read_text(encoding="utf-8")
        relative = str(path.relative_to(root))
        if path.name not in {"README.md", "AGENTS.md"}:
            try:
                data = metadata(text)
            except (ValueError, yaml.YAMLError) as error:
                errors.append(f"Metadados invalidos: {relative}: {error}")
                continue
            if not data:
                errors.append(f"Metadados ausentes: {relative}")
                continue
            for field in ["id", "status", "versao", "atualizado"]:
                if field not in data or data[field] is None:
                    errors.append(f"Campo {field} ausente: {relative}")
            note_id = data.get("id")
            if note_id in note_ids:
                errors.append(f"ID duplicado: {note_id}")
            note_ids.add(note_id)
            if data.get("status") not in STATUSES:
                errors.append(f"Status desconhecido: {relative}")
            if data.get("status") == "aprovado":
                for field in ["aprovado_por", "aprovado_em", "origem_aprovacao"]:
                    if not data.get(field):
                        errors.append(f"Aprovacao sem {field}: {relative}")
            notes.append(relative)
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
            if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE) or target.startswith("#"):
                continue
            local = unquote(target.split("#", 1)[0].strip("<>"))
            if not (path.parent / local).is_file():
                errors.append(f"Link ausente: {relative} -> {target}")

    return {
        "ok": not errors and not warnings,
        "errors": errors,
        "warnings": warnings,
        "information": information,
        "sources": len(manifest),
        "pages": sum(item["pages"] for item in manifest),
        "notes": len(notes),
        "scope": "Integridade e estrutura; nao mede qualidade editorial ou eficacia",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="store_true", help="Salvar sessoes/verificacao.json")
    args = parser.parse_args()
    result = check(ROOT)
    if args.report:
        (ROOT / "sessoes/verificacao.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
