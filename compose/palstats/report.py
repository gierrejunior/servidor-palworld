"""Relatorio do mundo Palworld a partir do Level.sav.

Le uma copia do save montada em /work/Level.sav. Nunca escreve nada.
"""
import collections
import ctypes
import datetime
import struct
import sys

B, R, D = "\033[1m", "\033[0m", "\033[2m"
SAV = "/work/Level.sav"


def titulo(t):
    print(f"\n{B}{t}{R}")


# ----------------------------------------------------------- descompressao --

raw = open(SAV, "rb").read()
uncompressed_len, _ = struct.unpack("<II", raw[:8])
magic = raw[8:11]

if magic == b"PlZ":
    import zlib

    data = zlib.decompress(raw[12:])
elif magic == b"PlM":
    ooz = ctypes.CDLL("/usr/local/lib/libooz.so")
    ooz.ooz_decompress.argtypes = [
        ctypes.c_char_p,
        ctypes.c_size_t,
        ctypes.c_char_p,
        ctypes.c_size_t,
    ]
    ooz.ooz_decompress.restype = ctypes.c_int
    buf = ctypes.create_string_buffer(uncompressed_len + 64)
    n = ooz.ooz_decompress(raw[12:], len(raw) - 12, buf, uncompressed_len)
    if n != uncompressed_len:
        sys.exit(f"descompressao Oodle falhou: {n} != {uncompressed_len}")
    data = buf.raw[:n]
else:
    sys.exit(f"magic desconhecido: {magic!r}")

if data[:4] != b"GVAS":
    sys.exit("conteudo nao e GVAS")

# ------------------------------------------------------------------ parsing --

from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS
from palworld_save_tools.rawdata import character


def decode_bytes_lenient(parent_reader, char_bytes):
    """A v1.0 acrescentou bytes ao fim de cada personagem; o decodificador
    original aborta por nao chegar ao EOF. O que interessa vem antes."""
    reader = parent_reader.internal_copy(bytes(char_bytes), debug=False)
    return {"object": reader.properties_until_end()}


character.decode_bytes = decode_bytes_lenient

# A v1.0 introduziu SetProperty, que a biblioteca de 2024 nao conhece e faz
# abortar a leitura inteira. Nao precisamos do conteudo desses campos, mas
# precisamos consumir os bytes para nao dessincronizar o fluxo: `size` cobre o
# corpo da propriedade depois do cabecalho de tipo, igual ao ArrayProperty.
from palworld_save_tools.archive import FArchiveReader

_property_original = FArchiveReader.property


def property_com_set(self, type_name, size, path, nested_caller_path=""):
    if type_name == "SetProperty":
        set_type = self.fstring()
        _id = self.optional_guid()
        self.byte_list(size)
        return {"set_type": set_type, "id": _id, "value": None, "type": type_name}
    return _property_original(self, type_name, size, path, nested_caller_path)


FArchiveReader.property = property_com_set

# Registrar so o decodificador de personagens: sem entrada em custom_properties,
# construcoes e vegetacao ficam como bytes crus, o que evita as incompatibilidades
# da v1.0 e deixa a leitura bem mais rapida.
CHAVE = ".worldSaveData.CharacterSaveParameterMap.Value.RawData"

# A biblioteca escreve avisos de "struct type not found" direto no stdout; sao
# esperados aqui, ja que deliberadamente nao decodificamos tudo.
import contextlib
import io

with contextlib.redirect_stdout(io.StringIO()):
    gvas = GvasFile.read(data, PALWORLD_TYPE_HINTS, {CHAVE: PALWORLD_CUSTOM_PROPERTIES[CHAVE]})
wsd = gvas.properties["worldSaveData"]["value"]
entries = wsd["CharacterSaveParameterMap"]["value"]


def val(p, campo, padrao=None):
    """Extrai o escalar de uma propriedade, que pode vir aninhada em value.value."""
    v = p.get(campo)
    if v is None:
        return padrao
    v = v.get("value", padrao)
    if isinstance(v, dict):
        v = v.get("value", padrao)
    return v


TICKS = datetime.datetime(1, 1, 1)


def quando(ticks):
    """Pals nunca capturados tem OwnedTime zerado, que cairia no ano 1."""
    try:
        d = TICKS + datetime.timedelta(microseconds=ticks / 10)
        return d if d.year >= 2020 else None
    except Exception:
        return None


jogadores, pals = [], []
for e in entries:
    try:
        p = e["value"]["RawData"]["value"]["object"]["SaveParameter"]["value"]
    except Exception:
        continue

    if val(p, "IsPlayer"):
        jogadores.append(
            {
                "uid": str(e["key"].get("PlayerUId", {}).get("value", "")),
                "nome": val(p, "NickName", "?"),
                "nivel": val(p, "Level", 1) or 1,
                "exp": val(p, "Exp", 0) or 0,
                "pontos": val(p, "UnusedStatusPoint", 0) or 0,
            }
        )
    else:
        especie = val(p, "CharacterID", "?") or "?"
        pals.append(
            {
                "especie": especie,
                "boss": especie.upper().startswith("BOSS_"),
                "nivel": val(p, "Level", 1) or 1,
                "rank": val(p, "Rank", 1) or 1,
                "lucky": bool(val(p, "IsRarePal", False)),
                "dono": str(p.get("OwnerPlayerUId", {}).get("value", "")),
                "capturado": quando(val(p, "OwnedTime", 0) or 0),
                "amizade": val(p, "FriendshipPoint", 0) or 0,
                "doente": val(p, "WorkerSick") is not None,
                "ivs": [
                    val(p, "Talent_HP", 0) or 0,
                    val(p, "Talent_Shot", 0) or 0,
                    val(p, "Talent_Defense", 0) or 0,
                ],
                "passivas": (p.get("PassiveSkillList", {}).get("value", {}) or {}).get("values", []),
            }
        )

nomes = {j["uid"]: j["nome"] for j in jogadores}


def dono_de(p):
    for uid, nome in nomes.items():
        if uid and p["dono"].startswith(uid[:8]):
            return nome
    return None


# ------------------------------------------------------------------- json ----

if "--json" in sys.argv:
    import json

    def resumo_jogador(j):
        meus = [p for p in pals if dono_de(p) == j["nome"]]
        melhor = max(meus, key=lambda p: sum(p["ivs"]), default=None)
        return {
            # O identificador interno fica de fora de proposito: o dashboard e
            # publico e nao precisa expor UID de ninguem.
            "nome": j["nome"],
            "nivel": j["nivel"],
            "exp": j["exp"],
            "pals": len(meus),
            "alphas": sum(1 for p in meus if p["boss"]),
            "lucky": sum(1 for p in meus if p["lucky"]),
            "nivel_medio_pals": round(sum(p["nivel"] for p in meus) / len(meus), 1) if meus else 0,
            "melhor_pal": (
                {
                    "especie": melhor["especie"].replace("BOSS_", ""),
                    "ivs": melhor["ivs"],
                    "media_ivs": round(sum(melhor["ivs"]) / 3, 1),
                    "nivel": melhor["nivel"],
                }
                if melhor
                else None
            ),
        }

    capturas_validas = [p["capturado"] for p in pals if p["capturado"]]
    linha_tempo = collections.Counter(c.date().isoformat() for c in capturas_validas)

    saida = {
        "gerado_em": datetime.datetime.now().isoformat(timespec="seconds"),
        "mundo": {
            "jogadores": len(jogadores),
            "pals": len(pals),
            "especies": len(set(p["especie"] for p in pals)),
            "alphas": sum(1 for p in pals if p["boss"]),
            "lucky": sum(1 for p in pals if p["lucky"]),
            "rank4": sum(1 for p in pals if p["rank"] >= 4),
            "doentes": sum(1 for p in pals if p["doente"]),
        },
        "jogadores": [resumo_jogador(j) for j in sorted(jogadores, key=lambda x: (-x["nivel"], -x["exp"]))],
        "especies_comuns": collections.Counter(
            p["especie"].replace("BOSS_", "") for p in pals
        ).most_common(12),
        "hall_ivs": [
            {
                "especie": p["especie"].replace("BOSS_", ""),
                "media_ivs": round(sum(p["ivs"]) / 3, 1),
                "ivs": p["ivs"],
                "nivel": p["nivel"],
                "dono": dono_de(p) or "?",
                "lucky": p["lucky"],
                "alpha": p["boss"],
            }
            for p in sorted(pals, key=lambda p: -sum(p["ivs"]))[:10]
        ],
        "passivas": collections.Counter(s for p in pals for s in p["passivas"]).most_common(10),
        "linha_tempo": sorted(linha_tempo.items()),
        "lucky_especies": sorted(set(p["especie"].replace("BOSS_", "") for p in pals if p["lucky"])),
        # Lista completa para o dashboard filtrar/ordenar no navegador. Chaves
        # curtas porque sao ~900 registros embutidos na pagina.
        "pals": [
            {
                "e": p["especie"].replace("BOSS_", ""),
                "n": p["nivel"],
                "r": p["rank"],
                "l": 1 if p["lucky"] else 0,
                "a": 1 if p["boss"] else 0,
                "iv": p["ivs"],
                "d": dono_de(p) or "",
                "c": p["capturado"].date().isoformat() if p["capturado"] else "",
                "f": p["amizade"],
            }
            for p in sorted(pals, key=lambda p: -sum(p["ivs"]))
        ],
    }
    print(json.dumps(saida, ensure_ascii=False, indent=1))
    sys.exit(0)

# ------------------------------------------------------------------ saida ----

print(f"{B}MUNDO{R}  {len(jogadores)} jogadores  ·  {len(pals)} pals  ·  "
      f"{len(set(p['especie'] for p in pals))} especies distintas")

titulo("JOGADORES")
print(f"  {'nome':<18}{'nivel':>6}{'exp':>14}{'pals':>7}{'alphas':>8}{'lucky':>7}")
for j in sorted(jogadores, key=lambda x: (-x["nivel"], -x["exp"])):
    meus = [p for p in pals if p["dono"].startswith(j["uid"][:8])]
    print(f"  {j['nome']:<18}{j['nivel']:>6}{j['exp']:>14,}{len(meus):>7}"
          f"{sum(1 for p in meus if p['boss']):>8}{sum(1 for p in meus if p['lucky']):>7}")

titulo("ESPECIES MAIS COMUNS")
comuns = collections.Counter(p["especie"].replace("BOSS_", "") for p in pals)
maior = comuns.most_common(1)[0][1] if comuns else 1
for especie, n in comuns.most_common(10):
    print(f"  {especie:<24}{'#' * max(1, round(n / maior * 26))} {n}")

titulo("HALL DA FAMA — IVs (media de HP/Ataque/Defesa)")
melhores = sorted(pals, key=lambda p: -sum(p["ivs"]) / 3)[:8]
for p in melhores:
    media = sum(p["ivs"]) / 3
    marca = " LUCKY" if p["lucky"] else (" ALPHA" if p["boss"] else "")
    dono = nomes.get(next((u for u in nomes if p["dono"].startswith(u[:8])), ""), "?")
    print(f"  {p['especie'].replace('BOSS_',''):<22}media {media:>5.1f}  "
          f"{str(p['ivs']):<16}nv{p['nivel']:<4}{dono}{marca}")

titulo("RARIDADES")
lucky = [p for p in pals if p["lucky"]]
bosses = [p for p in pals if p["boss"]]
quatro = [p for p in pals if p["rank"] >= 4]
print(f"  lucky pals ... {len(lucky)}")
print(f"  alphas ....... {len(bosses)}")
print(f"  rank 4+ ...... {len(quatro)}")
if lucky:
    print(f"  {D}lucky: {', '.join(sorted(set(p['especie'].replace('BOSS_','') for p in lucky))[:8])}{R}")

titulo("PASSIVAS MAIS COMUNS")
passivas = collections.Counter(s for p in pals for s in p["passivas"])
for skill, n in passivas.most_common(8):
    print(f"  {skill:<32}{n}")

capturas = [p["capturado"] for p in pals if p["capturado"]]
if capturas:
    titulo("LINHA DO TEMPO — capturas por dia")
    por_dia = collections.Counter(c.date() for c in capturas)
    pico = max(por_dia.values())
    for dia in sorted(por_dia)[-14:]:
        n = por_dia[dia]
        print(f"  {dia:%d/%m}  {'#' * max(1, round(n / pico * 30))} {n}")
    print(f"\n  {D}primeiro pal: {min(capturas):%d/%m/%Y}  ·  "
          f"ultimo: {max(capturas):%d/%m/%Y}  ·  {len(por_dia)} dias com capturas{R}")

doentes = [p for p in pals if p["doente"]]
if doentes:
    titulo("ATENCAO")
    print(f"  {len(doentes)} pals doentes nas bases")

grupos = wsd.get("GroupSaveDataMap", {}).get("value", [])
if grupos:
    titulo("GUILDAS")
    for g in grupos:
        try:
            gv = g["value"]["RawData"]["value"]
            if gv.get("group_type") != "EPalGroupType::Guild":
                continue
            membros = gv.get("individual_character_handle_ids", [])
            print(f"  {gv.get('guild_name', '?'):<28}{len(gv.get('players', []))} membros"
                  f"  ·  {len(membros)} personagens")
        except Exception:
            continue
