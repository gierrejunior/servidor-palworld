// Substitui o stdafx.h do ooz, que e Windows-only, pelos equivalentes do GCC.
#pragma once

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <stdint.h>
#include <immintrin.h>

typedef unsigned char byte;
typedef unsigned char uint8;
typedef unsigned int uint32;
typedef uint64_t uint64;
typedef int64_t int64;
typedef int32_t int32;
typedef uint16_t uint16;
typedef int16_t int16;
typedef unsigned int uint;

#define __forceinline inline __attribute__((always_inline))
#define __debugbreak() __builtin_trap()

// MSVC devolve 0 quando a mascara e zero; caso contrario grava a posicao do bit.
static inline unsigned char _BitScanReverse(unsigned long *index, unsigned long mask) {
  if (!mask) return 0;
  *index = 31 - __builtin_clz(mask);
  return 1;
}

static inline unsigned char _BitScanForward(unsigned long *index, unsigned long mask) {
  if (!mask) return 0;
  *index = __builtin_ctz(mask);
  return 1;
}

static inline unsigned char _BitScanReverse64(unsigned long *index, uint64_t mask) {
  if (!mask) return 0;
  *index = 63 - __builtin_clzll(mask);
  return 1;
}

static inline unsigned char _BitScanForward64(unsigned long *index, uint64_t mask) {
  if (!mask) return 0;
  *index = __builtin_ctzll(mask);
  return 1;
}

// _rotl e _rotr ja vem do x86intrin.h do GCC; redefinir aqui colide.

#define _byteswap_ulong(x)  __builtin_bswap32(x)
#define _byteswap_uint64(x) __builtin_bswap64(x)
#define _byteswap_ushort(x) __builtin_bswap16(x)
#define __popcnt(x)         __builtin_popcount(x)
#define __popcnt64(x)       __builtin_popcountll(x)

static inline uint64_t _umul128(uint64_t a, uint64_t b, uint64_t *hi) {
  __uint128_t r = (__uint128_t)a * b;
  *hi = (uint64_t)(r >> 64);
  return (uint64_t)r;
}
