#ifndef TRANSPILER_RUNTIME_H
#define TRANSPILER_RUNTIME_H

#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <string.h>

static inline void print_int(int x) { printf("%d\\n", x); }
static inline void print_float(double x) { printf("%f\\n", x); }
static inline void print_bool(bool x) { printf("%s\\n", x ? "true" : "false"); }
static inline void print_str(const char* x) { printf("%s\\n", x); }

#endif // TRANSPILER_RUNTIME_H
