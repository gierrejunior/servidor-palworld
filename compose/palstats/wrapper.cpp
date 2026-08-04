// Expoe o Kraken_Decompress do ooz com ligacao C, para o ctypes do Python
// conseguir chamar sem lidar com name mangling do C++.
#include "stdafx.h"

int Kraken_Decompress(const byte *src, size_t src_len, byte *dst, size_t dst_len);

extern "C" int ooz_decompress(const unsigned char *src, size_t src_len,
                              unsigned char *dst, size_t dst_len) {
  return Kraken_Decompress((const byte *)src, src_len, (byte *)dst, dst_len);
}
