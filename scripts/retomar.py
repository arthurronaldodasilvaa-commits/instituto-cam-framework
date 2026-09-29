"""Read a project's saved state; no AI or inference is used."""

import argparse
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def snapshot(project):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", project):
        raise ValueError("Nome de projeto invalido")
    folder = ROOT / "projetos" / project
    if not folder.is_dir():
        raise ValueError("Projeto desconhecido")
    files = []
    for name in ["estado.md", "decisoes.md"]:
        path = folder / name
        files.append({
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "content": path.read_text(encoding="utf-8"),
        })
    return {"project": project, "method": "Leitura literal dos arquivos; sem IA", "files": files}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", help="Nome da pasta em projetos/")
    parser.add_argument("--report", action="store_true", help="Salvar snapshot em sessoes")
    args = parser.parse_args()
    result = snapshot(args.project)
    if args.report:
        (ROOT / f"sessoes/retomada-{args.project}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
