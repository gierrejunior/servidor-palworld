# Imagem que sabe ler o Level.sav do Palworld v1.0.
#
# A v1.0 comprime os saves com Oodle (magic PlM) em vez de zlib (PlZ), e o
# palworld-save-tools so entende PlZ. Aqui compilamos o ooz, uma reimplementacao
# aberta do decodificador Oodle, e ligamos os dois por ctypes.
FROM python:3.12-slim AS build

RUN apt-get update -qq \
 && apt-get install -y -qq --no-install-recommends git build-essential ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /build
RUN git clone --depth 1 https://github.com/powzix/ooz.git .

# O repositorio e Windows-only; trocamos o cabecalho e cortamos o trecho final
# do kraken.cpp, que carrega a DLL oficial da Oodle e contem o main() do CLI.
COPY stdafx_posix.h stdafx.h
COPY wrapper.cpp wrapper.cpp
RUN head -n 4287 kraken.cpp > kraken_lib.cpp \
 && g++ -O2 -fPIC -shared -msse4.1 -fpermissive -w \
      -o /libooz.so kraken_lib.cpp bitknit.cpp lzna.cpp wrapper.cpp \
 && test -f /libooz.so

FROM python:3.12-slim
RUN pip install --quiet --no-cache-dir palworld-save-tools==0.24.0
COPY --from=build /libooz.so /usr/local/lib/libooz.so
COPY report.py /report.py
ENTRYPOINT ["python", "/report.py"]
