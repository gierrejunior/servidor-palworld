#!/usr/bin/env python3
"""Monta o site do dashboard em docs/.

Nao gera HTML: copia os arquivos de web/ como estao e grava o dados.json que o
app.js consome. HTML, CSS e JS ficam em arquivos de verdade, editaveis com
realce de sintaxe - a versao anterior montava tudo dentro de f-strings, onde
cada chave precisava ser escapada e um erro de aspas passava despercebido.

  gerar-dashboard.py <dados.json de entrada> <diretorio de saida> [gist_id]
"""
import json
import shutil
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
WEB = AQUI / "web"

entrada = Path(sys.argv[1])
saida = Path(sys.argv[2])
gist_id = sys.argv[3] if len(sys.argv) > 3 else ""

saida.mkdir(parents=True, exist_ok=True)

for arquivo in ("index.html", "estilo.css", "app.js", "favicon.svg"):
    shutil.copy2(WEB / arquivo, saida / arquivo)

dados = json.loads(entrada.read_text(encoding="utf-8"))
# O id do Gist entra nos dados em vez de no HTML: assim o app.js nao precisa de
# nenhuma substituicao de template.
dados["gist"] = gist_id

destino = saida / "dados.json"
destino.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

print(f"site montado em {saida} ({destino.stat().st_size:,} bytes de dados)")
