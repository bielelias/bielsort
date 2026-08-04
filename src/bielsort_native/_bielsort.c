#define PY_SSIZE_T_CLEAN
/* Native core for the bielsort_native CPython package. */
#include <Python.h>
#include <limits.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#define RADIX_BITS 11
#define RADIX_BASE (1U << RADIX_BITS)
#define RADIX_MASCARA (RADIX_BASE - 1U)
#define CONTAGEM_MINIMO_ELEMENTOS 250000
#define KEYED_CONTAGEM_MINIMO_ELEMENTOS 8192
#define CONTAGEM_LIMITE UINT64_C(4000000)
#define CONTAGEM_FATOR UINT64_C(4)
#define KEYED_ADAPTIVE_TIMSORT_MAX 262144
#define KEYED_ADAPTIVE_SAMPLE_MIN 64
#define KEYED_ADAPTIVE_SAMPLE_MAX 512
#define KEYED_ADAPTIVE_SAMPLE_LONG 2048
#define KEYED_ADAPTIVE_DESCENT_DIVISOR 32

typedef struct {
    PyObject *objeto;
    uint64_t chave;
} Entrada;

typedef enum {
    RETORNO_LISTA,
    RETORNO_DIAGNOSTICO,
    RETORNO_NONE,
    RETORNO_ESTRATEGIA,
    RETORNO_DIAGNOSTICO_ESTRUTURADO
} TipoRetorno;

static PyObject *
finalizar_resultado(PyObject *lista, const char *estrategia, TipoRetorno tipo)
{
    if (tipo == RETORNO_LISTA) {
        return lista;
    }

    if (tipo == RETORNO_NONE) {
        Py_DECREF(lista);
        Py_RETURN_NONE;
    }

    if (tipo == RETORNO_DIAGNOSTICO_ESTRUTURADO) {
        Py_DECREF(lista);
        PyErr_SetString(
            PyExc_SystemError,
            "diagnóstico estruturado requer o finalizador keyed-int64"
        );
        return NULL;
    }

    PyObject *nome = PyUnicode_FromString(estrategia);
    if (nome == NULL) {
        Py_DECREF(lista);
        return NULL;
    }

    if (tipo == RETORNO_ESTRATEGIA) {
        Py_DECREF(lista);
        return nome;
    }

    PyObject *resultado = PyTuple_New(2);
    if (resultado == NULL) {
        Py_DECREF(nome);
        Py_DECREF(lista);
        return NULL;
    }

    PyTuple_SET_ITEM(resultado, 0, lista);
    PyTuple_SET_ITEM(resultado, 1, nome);
    return resultado;
}

static PyObject *
usar_timsort(PyObject *lista, const char *motivo, TipoRetorno tipo)
{
    if (PyList_Sort(lista) < 0) {
        Py_DECREF(lista);
        return NULL;
    }
    return finalizar_resultado(lista, motivo, tipo);
}

typedef enum {
    KEYED_TRIVIAL,
    KEYED_JA_ORDENADO,
    KEYED_COUNTING,
    KEYED_RADIX
} AlgoritmoKeyed;

static int
multiplicar_tamanho(size_t a, size_t b, size_t *resultado)
{
    if (a != 0 && b > SIZE_MAX / a) {
        return 0;
    }
    *resultado = a * b;
    return 1;
}

static int
somar_tamanho(size_t a, size_t b, size_t *resultado)
{
    if (b > SIZE_MAX - a) {
        return 0;
    }
    *resultado = a + b;
    return 1;
}

static int
estimar_memoria_keyed(
    Py_ssize_t n,
    AlgoritmoKeyed algoritmo,
    uint64_t amplitude,
    size_t *estimativa,
    size_t *pior_caso
)
{
    const size_t quantidade = (size_t)n;
    const size_t bytes_por_radix =
        2 * sizeof(PyObject *) + 2 * sizeof(uint64_t);
    if (!multiplicar_tamanho(quantidade, bytes_por_radix, pior_caso)) {
        return 0;
    }

    if (algoritmo == KEYED_RADIX) {
        *estimativa = *pior_caso;
        return 1;
    }

    if (algoritmo == KEYED_COUNTING) {
        size_t fase_conversao;
        size_t fase_ordenacao;
        size_t tabela;
        if (
            !multiplicar_tamanho(
                quantidade,
                sizeof(PyObject *) + sizeof(uint64_t) + sizeof(uint32_t),
                &fase_conversao
            )
            || !multiplicar_tamanho(
                quantidade,
                2 * sizeof(PyObject *) + sizeof(uint32_t),
                &fase_ordenacao
            )
            || amplitude == UINT64_MAX
            || !multiplicar_tamanho(
                (size_t)(amplitude + 1),
                sizeof(Py_ssize_t),
                &tabela
            )
            || !somar_tamanho(fase_ordenacao, tabela, &fase_ordenacao)
        ) {
            return 0;
        }
        *estimativa = fase_conversao > fase_ordenacao
            ? fase_conversao
            : fase_ordenacao;
        return 1;
    }

    return multiplicar_tamanho(
        quantidade,
        sizeof(PyObject *) + sizeof(uint64_t),
        estimativa
    );
}

static int
adicionar_item_diagnostico(
    PyObject *diagnostico,
    const char *nome,
    PyObject *valor
)
{
    if (valor == NULL) {
        return -1;
    }
    const int resultado = PyDict_SetItemString(diagnostico, nome, valor);
    Py_DECREF(valor);
    return resultado;
}

static PyObject *
novo_none(void)
{
    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject *
finalizar_resultado_keyed(
    PyObject *lista,
    const char *estrategia,
    const char *algoritmo,
    const char *motivo,
    TipoRetorno tipo,
    Py_ssize_t n,
    int possui_dominio,
    long long menor_valor,
    long long maior_valor,
    uint64_t amplitude,
    int passagens,
    int normalizado,
    AlgoritmoKeyed codigo_algoritmo
)
{
    if (tipo != RETORNO_DIAGNOSTICO_ESTRUTURADO) {
        return finalizar_resultado(lista, estrategia, tipo);
    }

    size_t estimativa = 0;
    size_t pior_caso = 0;
    const int estimativa_valida = estimar_memoria_keyed(
        n,
        codigo_algoritmo,
        amplitude,
        &estimativa,
        &pior_caso
    );

    PyObject *diagnostico = PyDict_New();
    if (diagnostico == NULL) {
        Py_DECREF(lista);
        return NULL;
    }

    if (
        adicionar_item_diagnostico(
            diagnostico,
            "strategy",
            PyUnicode_FromString(estrategia)
        ) < 0
        || adicionar_item_diagnostico(
            diagnostico,
            "algorithm",
            PyUnicode_FromString(algoritmo)
        ) < 0
        || adicionar_item_diagnostico(
            diagnostico,
            "reason",
            PyUnicode_FromString(motivo)
        ) < 0
        || adicionar_item_diagnostico(
            diagnostico,
            "n",
            PyLong_FromSsize_t(n)
        ) < 0
        || adicionar_item_diagnostico(
            diagnostico,
            "key_domain",
            PyUnicode_FromString("signed-int64")
        ) < 0
        || adicionar_item_diagnostico(
            diagnostico,
            "key_min",
            possui_dominio
                ? PyLong_FromLongLong(menor_valor)
                : novo_none()
        ) < 0
        || adicionar_item_diagnostico(
            diagnostico,
            "key_max",
            possui_dominio
                ? PyLong_FromLongLong(maior_valor)
                : novo_none()
        ) < 0
        || adicionar_item_diagnostico(
            diagnostico,
            "key_span",
            possui_dominio
                ? PyLong_FromUnsignedLongLong(amplitude)
                : novo_none()
        ) < 0
        || adicionar_item_diagnostico(
            diagnostico,
            "radix_passes",
            codigo_algoritmo == KEYED_RADIX
                ? PyLong_FromLong(passagens)
                : novo_none()
        ) < 0
        || adicionar_item_diagnostico(
            diagnostico,
            "normalized",
            PyBool_FromLong(normalizado)
        ) < 0
        || adicionar_item_diagnostico(
            diagnostico,
            "stable",
            PyBool_FromLong(1)
        ) < 0
        || adicionar_item_diagnostico(
            diagnostico,
            "key_calls",
            PyLong_FromSsize_t(n)
        ) < 0
        || adicionar_item_diagnostico(
            diagnostico,
            "estimated_variable_auxiliary_bytes",
            estimativa_valida
                ? PyLong_FromSize_t(estimativa)
                : novo_none()
        ) < 0
        || adicionar_item_diagnostico(
            diagnostico,
            "worst_case_variable_auxiliary_bytes",
            estimativa_valida
                ? PyLong_FromSize_t(pior_caso)
                : novo_none()
        ) < 0
        || adicionar_item_diagnostico(
            diagnostico,
            "memory_estimate_scope",
            PyUnicode_FromString(
                "result-list items and native variable buffers; "
                "excludes input objects, allocator overhead, and fixed stack"
            )
        ) < 0
        || adicionar_item_diagnostico(
            diagnostico,
            "prototype",
            PyBool_FromLong(1)
        ) < 0
    ) {
        Py_DECREF(diagnostico);
        Py_DECREF(lista);
        return NULL;
    }

    PyObject *resultado = PyTuple_New(2);
    if (resultado == NULL) {
        Py_DECREF(diagnostico);
        Py_DECREF(lista);
        return NULL;
    }
    PyTuple_SET_ITEM(resultado, 0, lista);
    PyTuple_SET_ITEM(resultado, 1, diagnostico);
    return resultado;
}

static int
contar_digitos_variaveis(uint64_t variacao)
{
    int passagens = 0;
    for (
        int deslocamento = 0;
        deslocamento < 64;
        deslocamento += RADIX_BITS
    ) {
        if (((variacao >> deslocamento) & RADIX_MASCARA) != 0) {
            passagens++;
        }
    }
    return passagens;
}

static PyObject *
biel_sort_impl(PyObject *iteravel, TipoRetorno tipo, int copiar)
{
    PyObject *lista;
    if (!copiar) {
        if (!PyList_CheckExact(iteravel)) {
            PyErr_SetString(
                PyExc_TypeError,
                "biel_sort_in_place requer uma list exata"
            );
            return NULL;
        }
        lista = iteravel;
        Py_INCREF(lista);
    } else if (PyList_CheckExact(iteravel)) {
        lista = PyList_GetSlice(
            iteravel,
            0,
            PyList_GET_SIZE(iteravel)
        );
    } else {
        lista = PySequence_List(iteravel);
    }
    if (lista == NULL) {
        return NULL;
    }

    const Py_ssize_t n = PyList_GET_SIZE(lista);
    if (n < 2) {
        return finalizar_resultado(lista, "trivial", tipo);
    }

    /*
     * Entradas com poucos elementos favorecem o Timsort altamente otimizado
     * do CPython. Evitamos até mesmo alocar os buffers do radix nesse caso.
     */
    if (n < 2048) {
        return usar_timsort(lista, "timsort: entrada pequena", tipo);
    }

    /*
     * Uma amostra uniforme evita uma varredura e uma alocação completas nos
     * casos em que o Timsort provavelmente vencerá. Mesmo que a heurística
     * classifique uma distribuição incomum de forma conservadora, o resultado
     * continua correto: apenas usamos o fallback.
     */
    const Py_ssize_t total_amostras = n < 256 ? n : 256;
    Py_ssize_t descidas_amostra = 0;
    Py_ssize_t subidas_amostra = 0;
    int64_t anterior_amostra = 0;
    for (Py_ssize_t amostra = 0; amostra < total_amostras; amostra++) {
        const Py_ssize_t intervalo = n - 1;
        const Py_ssize_t divisor = total_amostras - 1;
        const Py_ssize_t indice =
            (intervalo / divisor) * amostra
            + ((intervalo % divisor) * amostra) / divisor;
        PyObject *objeto = PyList_GET_ITEM(lista, indice);

        if (!PyLong_CheckExact(objeto)) {
            return usar_timsort(
                lista,
                "timsort: amostra incompatível com int64",
                tipo
            );
        }

        long long valor = PyLong_AsLongLong(objeto);
        if (valor == -1 && PyErr_Occurred()) {
            if (PyErr_ExceptionMatches(PyExc_OverflowError)) {
                PyErr_Clear();
                return usar_timsort(
                    lista,
                    "timsort: magnitude detectada na amostra",
                    tipo
                );
            }
            Py_DECREF(lista);
            return NULL;
        }

        if (amostra > 0 && (int64_t)valor < anterior_amostra) {
            descidas_amostra++;
        }
        if (amostra > 0 && (int64_t)valor > anterior_amostra) {
            subidas_amostra++;
        }
        anterior_amostra = (int64_t)valor;
    }

    if (
        descidas_amostra <= total_amostras / 128
        || subidas_amostra <= total_amostras / 128
    ) {
        return usar_timsort(
            lista,
            "timsort: amostra quase monotônica",
            tipo
        );
    }

    if ((size_t)n > SIZE_MAX / sizeof(Entrada)) {
        Py_DECREF(lista);
        return PyErr_NoMemory();
    }

    Entrada *origem = PyMem_Malloc((size_t)n * sizeof(*origem));
    if (origem == NULL) {
        Py_DECREF(lista);
        return PyErr_NoMemory();
    }

    uint64_t primeira_chave = 0;
    uint64_t menor_chave = UINT64_MAX;
    uint64_t maior_chave = 0;
    uint64_t variacao = 0;
    int64_t anterior = 0;
    Py_ssize_t descidas = 0;
    Py_ssize_t subidas = 0;
    int somente_inteiros_64 = 1;

    for (Py_ssize_t i = 0; i < n; i++) {
        PyObject *objeto = PyList_GET_ITEM(lista, i);
        if (!PyLong_CheckExact(objeto)) {
            somente_inteiros_64 = 0;
            break;
        }

        long long valor = PyLong_AsLongLong(objeto);
        if (valor == -1 && PyErr_Occurred()) {
            if (PyErr_ExceptionMatches(PyExc_OverflowError)) {
                PyErr_Clear();
                somente_inteiros_64 = 0;
                break;
            }
            PyMem_Free(origem);
            Py_DECREF(lista);
            return NULL;
        }

        /*
         * O XOR com o bit de sinal converte a ordem signed em ordem unsigned:
         * INT64_MIN vira 0 e INT64_MAX vira UINT64_MAX.
         */
        uint64_t chave = ((uint64_t)(int64_t)valor) ^ (UINT64_C(1) << 63);
        origem[i].objeto = objeto;
        origem[i].chave = chave;
        if (chave < menor_chave) {
            menor_chave = chave;
        }
        if (chave > maior_chave) {
            maior_chave = chave;
        }

        if (i == 0) {
            primeira_chave = chave;
        } else {
            variacao |= chave ^ primeira_chave;
            if ((int64_t)valor < anterior) {
                descidas++;
            }
            if ((int64_t)valor > anterior) {
                subidas++;
            }
        }
        anterior = (int64_t)valor;
    }

    if (!somente_inteiros_64) {
        PyMem_Free(origem);
        return usar_timsort(
            lista,
            "timsort: tipo ou magnitude fora de int64",
            tipo
        );
    }

    if (descidas == 0) {
        PyMem_Free(origem);
        return finalizar_resultado(lista, "já ordenado", tipo);
    }

    /*
     * Poucas descidas indicam runs longas. Essa é exatamente a situação em
     * que o Timsort é difícil de superar.
     */
    if (descidas <= n / 128 || subidas <= n / 128) {
        PyMem_Free(origem);
        return usar_timsort(lista, "timsort: entrada quase monotônica", tipo);
    }

    int passagens = contar_digitos_variaveis(variacao);
    if (passagens == 0) {
        PyMem_Free(origem);
        return finalizar_resultado(lista, "todos iguais", tipo);
    }

    /*
     * Números pequenos dos dois lados do zero diferem em todos os dígitos depois
     * da transformação do sinal. Subtrair a menor chave compacta o intervalo:
     * por exemplo, [-1000, 1000] passa a [0, 2000] e usa somente um dígito.
     * A passagem adicional só é feita quando ela realmente reduz o radix.
     */
    const uint64_t amplitude = maior_chave - menor_chave;
    int digitos_amplitude = 0;
    uint64_t restante = amplitude;
    while (restante != 0) {
        digitos_amplitude++;
        restante >>= RADIX_BITS;
    }

    const int usar_contagem =
        n >= CONTAGEM_MINIMO_ELEMENTOS
        && amplitude < CONTAGEM_LIMITE
        && (
            (uint64_t)n >= CONTAGEM_LIMITE / CONTAGEM_FATOR
            || amplitude <= CONTAGEM_FATOR * (uint64_t)n
        );

    if (digitos_amplitude < passagens || usar_contagem) {
        variacao = 0;
        for (Py_ssize_t i = 0; i < n; i++) {
            origem[i].chave -= menor_chave;
            variacao |= origem[i].chave;
        }
        passagens = contar_digitos_variaveis(variacao);
    }

    if (usar_contagem) {
        const size_t tamanho_contagem = (size_t)amplitude + 1;
        uint32_t *chaves = PyMem_Malloc((size_t)n * sizeof(*chaves));

        /*
         * A amplitude deste caminho cabe em 32 bits. Compactar as chaves
         * antes de criar a saída evita manter simultaneamente dois buffers
         * Entrada de 16 bytes por elemento.
         */
        if (chaves != NULL) {
            for (Py_ssize_t i = 0; i < n; i++) {
                chaves[i] = (uint32_t)origem[i].chave;
            }
            PyMem_Free(origem);
            origem = NULL;

            PyObject **saida = PyMem_Malloc((size_t)n * sizeof(*saida));
            Py_ssize_t *contagem = PyMem_Calloc(
                tamanho_contagem,
                sizeof(*contagem)
            );

            if (saida != NULL && contagem != NULL) {
                PyObject **itens = PySequence_Fast_ITEMS(lista);
                PyThreadState *estado_gil = NULL;
                if (copiar) {
                    estado_gil = PyEval_SaveThread();
                }

                for (Py_ssize_t i = 0; i < n; i++) {
                    contagem[chaves[i]]++;
                }

                Py_ssize_t total = 0;
                for (size_t chave = 0; chave < tamanho_contagem; chave++) {
                    const Py_ssize_t quantidade = contagem[chave];
                    contagem[chave] = total;
                    total += quantidade;
                }

                for (Py_ssize_t i = 0; i < n; i++) {
                    const uint32_t chave = chaves[i];
                    saida[contagem[chave]++] = itens[i];
                }

                if (estado_gil != NULL) {
                    PyEval_RestoreThread(estado_gil);
                }

                for (Py_ssize_t i = 0; i < n; i++) {
                    PyList_SET_ITEM(lista, i, saida[i]);
                }

                PyMem_Free(contagem);
                PyMem_Free(saida);
                PyMem_Free(chaves);
                return finalizar_resultado(
                    lista,
                    "counting nativo estável",
                    tipo
                );
            }

            /*
             * O counting é opcional. Em caso de pressão de memória,
             * reconstruímos a representação completa e tentamos o radix.
             */
            PyMem_Free(contagem);
            PyMem_Free(saida);
            origem = PyMem_Malloc((size_t)n * sizeof(*origem));
            if (origem == NULL) {
                PyMem_Free(chaves);
                Py_DECREF(lista);
                return PyErr_NoMemory();
            }
            for (Py_ssize_t i = 0; i < n; i++) {
                origem[i].objeto = PyList_GET_ITEM(lista, i);
                origem[i].chave = chaves[i];
            }
            PyMem_Free(chaves);
        }
    }

    Entrada *destino = PyMem_Malloc((size_t)n * sizeof(*destino));
    if (destino == NULL) {
        PyMem_Free(origem);
        Py_DECREF(lista);
        return PyErr_NoMemory();
    }

    Entrada *buffer_a = origem;
    Entrada *buffer_b = destino;

    PyThreadState *estado_gil = NULL;
    if (copiar) {
        estado_gil = PyEval_SaveThread();
    }

    for (
        int deslocamento = 0;
        deslocamento < 64;
        deslocamento += RADIX_BITS
    ) {
        if (((variacao >> deslocamento) & RADIX_MASCARA) == 0) {
            continue;
        }

        Py_ssize_t contagem[RADIX_BASE] = {0};
        for (Py_ssize_t i = 0; i < n; i++) {
            const uint16_t digito = (uint16_t)(
                (buffer_a[i].chave >> deslocamento) & RADIX_MASCARA
            );
            contagem[digito]++;
        }

        Py_ssize_t total = 0;
        for (unsigned int digito = 0; digito < RADIX_BASE; digito++) {
            const Py_ssize_t quantidade = contagem[digito];
            contagem[digito] = total;
            total += quantidade;
        }

        for (Py_ssize_t i = 0; i < n; i++) {
            const uint16_t digito = (uint16_t)(
                (buffer_a[i].chave >> deslocamento) & RADIX_MASCARA
            );
            buffer_b[contagem[digito]++] = buffer_a[i];
        }

        Entrada *temporario = buffer_a;
        buffer_a = buffer_b;
        buffer_b = temporario;
    }

    if (estado_gil != NULL) {
        PyEval_RestoreThread(estado_gil);
    }

    /*
     * A lista já possui exatamente uma referência para cada item. Como apenas
     * permutamos o mesmo multiconjunto de ponteiros, não alteramos refcounts.
     */
    for (Py_ssize_t i = 0; i < n; i++) {
        PyList_SET_ITEM(lista, i, buffer_a[i].objeto);
    }

    PyMem_Free(destino);
    PyMem_Free(origem);

    char estrategia[48];
    if (passagens == 1) {
        PyOS_snprintf(
            estrategia,
            sizeof(estrategia),
            "radix nativo: 1 passagem"
        );
    } else {
        PyOS_snprintf(
            estrategia,
            sizeof(estrategia),
            "radix nativo: %d passagens",
            passagens
        );
    }
    return finalizar_resultado(lista, estrategia, tipo);
}

/*
 * Research-only path for evaluating the next BielSort direction.  It sorts
 * arbitrary Python objects by an exact signed-64-bit integer key while
 * preserving object identity and the encounter order of equal keys.
 *
 * The strict entry point deliberately has no Timsort fallback: calling the
 * user's key function again would violate the one-call-per-object contract.
 * A second private entry point accepts a complete cache list.  A third fuses
 * key evaluation with int64 extraction.  If that progressive path encounters
 * a generic key, it reconstructs the preceding exact integer values in a
 * replay prefix and returns None so CPython Timsort evaluates only the
 * remaining user keys.
 */
typedef enum {
    KEYED_CHAVE_DIRETA,
    KEYED_CACHE_COMPLETO,
    KEYED_CACHE_PREFIXO
} ModoChaveKeyed;

static int
preservar_cache_prefixado(
    PyObject *destino,
    const uint64_t *chaves_normalizadas,
    Py_ssize_t inicio,
    Py_ssize_t fim
)
{
    for (Py_ssize_t i = inicio; i < fim; i++) {
        const uint64_t bits =
            chaves_normalizadas[i] ^ (UINT64_C(1) << 63);
        PyObject *chave;
        if ((bits & (UINT64_C(1) << 63)) == 0) {
            chave = PyLong_FromUnsignedLongLong(bits);
        } else {
            const uint64_t magnitude = (~bits) + 1;
            PyObject *positivo = PyLong_FromUnsignedLongLong(magnitude);
            if (positivo == NULL) {
                return -1;
            }
            chave = PyNumber_Negative(positivo);
            Py_DECREF(positivo);
        }
        if (chave == NULL) {
            return -1;
        }
        const int resultado = PyList_Append(destino, chave);
        Py_DECREF(chave);
        if (resultado < 0) {
            return -1;
        }
    }
    return 0;
}

static PyObject *
sort_by_int64_key_prototype_impl(
    PyObject *iteravel,
    PyObject *funcao_chave,
    PyObject *chaves_cacheadas,
    TipoRetorno tipo,
    ModoChaveKeyed modo_chave
)
{
    if (
        modo_chave != KEYED_CACHE_COMPLETO
        && !PyCallable_Check(funcao_chave)
    ) {
        PyErr_SetString(PyExc_TypeError, "key deve ser chamável");
        return NULL;
    }

    PyObject *lista;
    if (modo_chave != KEYED_CHAVE_DIRETA) {
        if (
            !PyList_CheckExact(iteravel)
            || !PyList_CheckExact(chaves_cacheadas)
            || iteravel == chaves_cacheadas
        ) {
            PyErr_SetString(
                PyExc_TypeError,
                "o caminho cacheado requer duas lists exatas e distintas"
            );
            return NULL;
        }
        lista = iteravel;
        Py_INCREF(lista);
    } else if (PyList_CheckExact(iteravel)) {
        lista = PyList_GetSlice(iteravel, 0, PyList_GET_SIZE(iteravel));
    } else {
        lista = PySequence_List(iteravel);
    }
    if (lista == NULL) {
        return NULL;
    }

    const Py_ssize_t n = PyList_GET_SIZE(lista);
    if (
        modo_chave == KEYED_CACHE_COMPLETO
        && PyList_GET_SIZE(chaves_cacheadas) != n
    ) {
        Py_DECREF(lista);
        PyErr_SetString(
            PyExc_ValueError,
            "items e cached_keys devem ter o mesmo tamanho"
        );
        return NULL;
    }
    if (
        modo_chave == KEYED_CACHE_PREFIXO
        && PyList_GET_SIZE(chaves_cacheadas) > n
    ) {
        Py_DECREF(lista);
        PyErr_SetString(
            PyExc_ValueError,
            "cached_keys não pode ser maior que items"
        );
        return NULL;
    }

    const Py_ssize_t tamanho_cache_inicial =
        modo_chave == KEYED_CACHE_PREFIXO
            ? PyList_GET_SIZE(chaves_cacheadas)
            : 0;

    if (n == 0) {
        return finalizar_resultado_keyed(
            lista,
            "protótipo keyed-int64: trivial",
            "trivial",
            "entrada vazia",
            tipo,
            n,
            0,
            0,
            0,
            0,
            0,
            0,
            KEYED_TRIVIAL
        );
    }

    if (
        (size_t)n > SIZE_MAX / sizeof(uint64_t)
        || (size_t)n > SIZE_MAX / sizeof(PyObject *)
    ) {
        Py_DECREF(lista);
        return PyErr_NoMemory();
    }

    uint64_t *chaves_origem = PyMem_Malloc(
        (size_t)n * sizeof(*chaves_origem)
    );
    if (chaves_origem == NULL) {
        Py_DECREF(lista);
        return PyErr_NoMemory();
    }

    uint64_t primeira_chave = 0;
    uint64_t menor_chave = UINT64_MAX;
    uint64_t maior_chave = 0;
    uint64_t variacao = 0;
    uint64_t chave_anterior = 0;
    long long menor_valor = LLONG_MAX;
    long long maior_valor = LLONG_MIN;
    Py_ssize_t descidas = 0;

    for (Py_ssize_t i = 0; i < n; i++) {
        PyObject *resultado_chave;
        int resultado_novo = 0;
        if (
            modo_chave == KEYED_CACHE_COMPLETO
        ) {
            resultado_chave = PyList_GET_ITEM(chaves_cacheadas, i);
        } else if (
            modo_chave == KEYED_CACHE_PREFIXO
            && i < tamanho_cache_inicial
        ) {
            resultado_chave = PyList_GET_ITEM(chaves_cacheadas, i);
        } else {
            PyObject *objeto = PyList_GET_ITEM(lista, i);
            resultado_chave = PyObject_CallOneArg(funcao_chave, objeto);
            if (resultado_chave == NULL) {
                PyMem_Free(chaves_origem);
                Py_DECREF(lista);
                return NULL;
            }
            resultado_novo = 1;
        }

        if (!PyLong_CheckExact(resultado_chave)) {
            if (modo_chave != KEYED_CHAVE_DIRETA) {
                if (
                    modo_chave == KEYED_CACHE_PREFIXO
                    && preservar_cache_prefixado(
                        chaves_cacheadas,
                        chaves_origem,
                        tamanho_cache_inicial,
                        i
                    ) < 0
                ) {
                    if (resultado_novo) {
                        Py_DECREF(resultado_chave);
                    }
                    PyMem_Free(chaves_origem);
                    Py_DECREF(lista);
                    return NULL;
                }
                if (
                    modo_chave == KEYED_CACHE_PREFIXO
                    && resultado_novo
                    && PyList_Append(
                        chaves_cacheadas,
                        resultado_chave
                    ) < 0
                ) {
                    Py_DECREF(resultado_chave);
                    PyMem_Free(chaves_origem);
                    Py_DECREF(lista);
                    return NULL;
                }
                if (resultado_novo) {
                    Py_DECREF(resultado_chave);
                }
                PyMem_Free(chaves_origem);
                Py_DECREF(lista);
                Py_RETURN_NONE;
            }
            PyErr_Format(
                PyExc_TypeError,
                "key deve retornar int exato em int64; item %zd retornou %.200s",
                i,
                Py_TYPE(resultado_chave)->tp_name
            );
            if (resultado_novo) {
                Py_DECREF(resultado_chave);
            }
            PyMem_Free(chaves_origem);
            Py_DECREF(lista);
            return NULL;
        }

        long long valor = PyLong_AsLongLong(resultado_chave);
        if (valor == -1 && PyErr_Occurred()) {
            if (
                modo_chave != KEYED_CHAVE_DIRETA
                && PyErr_ExceptionMatches(PyExc_OverflowError)
            ) {
                PyErr_Clear();
                if (
                    modo_chave == KEYED_CACHE_PREFIXO
                    && preservar_cache_prefixado(
                        chaves_cacheadas,
                        chaves_origem,
                        tamanho_cache_inicial,
                        i
                    ) < 0
                ) {
                    if (resultado_novo) {
                        Py_DECREF(resultado_chave);
                    }
                    PyMem_Free(chaves_origem);
                    Py_DECREF(lista);
                    return NULL;
                }
                if (
                    modo_chave == KEYED_CACHE_PREFIXO
                    && resultado_novo
                    && PyList_Append(
                        chaves_cacheadas,
                        resultado_chave
                    ) < 0
                ) {
                    Py_DECREF(resultado_chave);
                    PyMem_Free(chaves_origem);
                    Py_DECREF(lista);
                    return NULL;
                }
                if (resultado_novo) {
                    Py_DECREF(resultado_chave);
                }
                PyMem_Free(chaves_origem);
                Py_DECREF(lista);
                Py_RETURN_NONE;
            }
            if (PyErr_ExceptionMatches(PyExc_OverflowError)) {
                PyErr_Clear();
                PyErr_Format(
                    PyExc_OverflowError,
                    "key do item %zd está fora do intervalo int64",
                    i
                );
            }
            if (resultado_novo) {
                Py_DECREF(resultado_chave);
            }
            PyMem_Free(chaves_origem);
            Py_DECREF(lista);
            return NULL;
        }
        if (resultado_novo) {
            Py_DECREF(resultado_chave);
        }

        const uint64_t chave =
            ((uint64_t)(int64_t)valor) ^ (UINT64_C(1) << 63);
        chaves_origem[i] = chave;

        if (valor < menor_valor) {
            menor_valor = valor;
        }
        if (valor > maior_valor) {
            maior_valor = valor;
        }

        if (chave < menor_chave) {
            menor_chave = chave;
        }
        if (chave > maior_chave) {
            maior_chave = chave;
        }

        if (i == 0) {
            primeira_chave = chave;
        } else {
            variacao |= chave ^ primeira_chave;
            if (chave < chave_anterior) {
                descidas++;
            }
        }
        chave_anterior = chave;

        const Py_ssize_t quantidade_amostrada = i + 1;
        const int checkpoint_adaptativo =
            (
                quantidade_amostrada >= KEYED_ADAPTIVE_SAMPLE_MIN
                && quantidade_amostrada <= KEYED_ADAPTIVE_SAMPLE_MAX
                && (
                    quantidade_amostrada
                    & (quantidade_amostrada - 1)
                ) == 0
            )
            || quantidade_amostrada == KEYED_ADAPTIVE_SAMPLE_LONG;
        if (
            modo_chave == KEYED_CACHE_PREFIXO
            && tamanho_cache_inicial == 0
            && n <= KEYED_ADAPTIVE_TIMSORT_MAX
            && checkpoint_adaptativo
            && descidas > 0
            && descidas
                <= quantidade_amostrada
                    / KEYED_ADAPTIVE_DESCENT_DIVISOR
            && (uint64_t)n <= UINT64_MAX / CONTAGEM_FATOR
            && maior_chave - menor_chave
                > CONTAGEM_FATOR * (uint64_t)n
        ) {
            if (preservar_cache_prefixado(
                chaves_cacheadas,
                chaves_origem,
                0,
                quantidade_amostrada
            ) < 0) {
                PyMem_Free(chaves_origem);
                Py_DECREF(lista);
                return NULL;
            }
            PyMem_Free(chaves_origem);
            Py_DECREF(lista);
            Py_RETURN_FALSE;
        }
    }

    if (
        modo_chave != KEYED_CHAVE_DIRETA
        && PyList_SetSlice(chaves_cacheadas, 0, n, NULL) < 0
    ) {
        PyMem_Free(chaves_origem);
        Py_DECREF(lista);
        return NULL;
    }

    if (n == 1 || descidas == 0) {
        PyMem_Free(chaves_origem);
        return finalizar_resultado_keyed(
            lista,
            n == 1
                ? "protótipo keyed-int64: trivial"
                : "protótipo keyed-int64: já ordenado",
            n == 1 ? "trivial" : "already-sorted",
            n == 1
                ? "um único elemento"
                : "chaves já estão em ordem não decrescente",
            tipo,
            n,
            1,
            menor_valor,
            maior_valor,
            maior_chave - menor_chave,
            0,
            0,
            n == 1 ? KEYED_TRIVIAL : KEYED_JA_ORDENADO
        );
    }

    int passagens = contar_digitos_variaveis(variacao);
    if (passagens == 0) {
        PyMem_Free(chaves_origem);
        return finalizar_resultado_keyed(
            lista,
            "protótipo keyed-int64: todos iguais",
            "already-sorted",
            "todas as chaves são iguais",
            tipo,
            n,
            1,
            menor_valor,
            maior_valor,
            0,
            0,
            0,
            KEYED_JA_ORDENADO
        );
    }

    const uint64_t amplitude = maior_chave - menor_chave;
    int digitos_amplitude = 0;
    uint64_t restante = amplitude;
    while (restante != 0) {
        digitos_amplitude++;
        restante >>= RADIX_BITS;
    }

    const int usar_contagem =
        n >= KEYED_CONTAGEM_MINIMO_ELEMENTOS
        && amplitude < CONTAGEM_LIMITE
        && (
            (uint64_t)n >= CONTAGEM_LIMITE / CONTAGEM_FATOR
            || amplitude <= CONTAGEM_FATOR * (uint64_t)n
        );

    int normalizado = 0;
    if (digitos_amplitude < passagens || usar_contagem) {
        normalizado = 1;
        variacao = 0;
        for (Py_ssize_t i = 0; i < n; i++) {
            chaves_origem[i] -= menor_chave;
            variacao |= chaves_origem[i];
        }
        passagens = contar_digitos_variaveis(variacao);
    }

    if (usar_contagem) {
        const size_t tamanho_contagem = (size_t)amplitude + 1;
        uint32_t *chaves = PyMem_Malloc((size_t)n * sizeof(*chaves));

        if (chaves != NULL) {
            for (Py_ssize_t i = 0; i < n; i++) {
                chaves[i] = (uint32_t)chaves_origem[i];
            }
            PyMem_Free(chaves_origem);
            chaves_origem = NULL;

            PyObject **saida = PyMem_Malloc((size_t)n * sizeof(*saida));
            Py_ssize_t *contagem = PyMem_Calloc(
                tamanho_contagem,
                sizeof(*contagem)
            );

            if (saida != NULL && contagem != NULL) {
                PyObject **itens = PySequence_Fast_ITEMS(lista);
                PyThreadState *estado_gil = PyEval_SaveThread();

                for (Py_ssize_t i = 0; i < n; i++) {
                    contagem[chaves[i]]++;
                }

                Py_ssize_t total = 0;
                for (size_t chave = 0; chave < tamanho_contagem; chave++) {
                    const Py_ssize_t quantidade = contagem[chave];
                    contagem[chave] = total;
                    total += quantidade;
                }

                for (Py_ssize_t i = 0; i < n; i++) {
                    const uint32_t chave = chaves[i];
                    saida[contagem[chave]++] = itens[i];
                }

                PyEval_RestoreThread(estado_gil);

                for (Py_ssize_t i = 0; i < n; i++) {
                    PyList_SET_ITEM(lista, i, saida[i]);
                }

                PyMem_Free(contagem);
                PyMem_Free(saida);
                PyMem_Free(chaves);
                return finalizar_resultado_keyed(
                    lista,
                    "protótipo keyed-int64: counting nativo estável",
                    "counting",
                    "intervalo denso elegível para Counting Sort",
                    tipo,
                    n,
                    1,
                    menor_valor,
                    maior_valor,
                    amplitude,
                    0,
                    normalizado,
                    KEYED_COUNTING
                );
            }

            PyMem_Free(contagem);
            PyMem_Free(saida);
            chaves_origem = PyMem_Malloc(
                (size_t)n * sizeof(*chaves_origem)
            );
            if (chaves_origem == NULL) {
                PyMem_Free(chaves);
                Py_DECREF(lista);
                return PyErr_NoMemory();
            }
            for (Py_ssize_t i = 0; i < n; i++) {
                chaves_origem[i] = chaves[i];
            }
            PyMem_Free(chaves);
        }
    }

    uint64_t *chaves_destino = PyMem_Malloc(
        (size_t)n * sizeof(*chaves_destino)
    );
    PyObject **objetos_destino = PyMem_Malloc(
        (size_t)n * sizeof(*objetos_destino)
    );
    if (chaves_destino == NULL || objetos_destino == NULL) {
        PyMem_Free(objetos_destino);
        PyMem_Free(chaves_destino);
        PyMem_Free(chaves_origem);
        Py_DECREF(lista);
        return PyErr_NoMemory();
    }

    uint64_t *buffer_chaves_a = chaves_origem;
    uint64_t *buffer_chaves_b = chaves_destino;
    PyObject **itens = PySequence_Fast_ITEMS(lista);
    PyThreadState *estado_gil = PyEval_SaveThread();

    for (
        int deslocamento = 0;
        deslocamento < 64;
        deslocamento += RADIX_BITS
    ) {
        if (((variacao >> deslocamento) & RADIX_MASCARA) == 0) {
            continue;
        }

        Py_ssize_t contagem[RADIX_BASE] = {0};
        for (Py_ssize_t i = 0; i < n; i++) {
            const uint16_t digito = (uint16_t)(
                (buffer_chaves_a[i] >> deslocamento) & RADIX_MASCARA
            );
            contagem[digito]++;
        }

        Py_ssize_t total = 0;
        for (unsigned int digito = 0; digito < RADIX_BASE; digito++) {
            const Py_ssize_t quantidade = contagem[digito];
            contagem[digito] = total;
            total += quantidade;
        }

        for (Py_ssize_t i = 0; i < n; i++) {
            const uint16_t digito = (uint16_t)(
                (buffer_chaves_a[i] >> deslocamento) & RADIX_MASCARA
            );
            const Py_ssize_t destino = contagem[digito]++;
            buffer_chaves_b[destino] = buffer_chaves_a[i];
            objetos_destino[destino] = itens[i];
        }

        /*
         * The result list is private to this call, so its item array can be
         * reused as the object side of the next radix pass.  Pointer copies do
         * not alter reference counts because every pass is only a permutation
         * of the same list-owned references.
         */
        memcpy(
            itens,
            objetos_destino,
            (size_t)n * sizeof(*itens)
        );

        uint64_t *chaves_temporarias = buffer_chaves_a;
        buffer_chaves_a = buffer_chaves_b;
        buffer_chaves_b = chaves_temporarias;
    }

    PyEval_RestoreThread(estado_gil);

    PyMem_Free(objetos_destino);
    PyMem_Free(chaves_destino);
    PyMem_Free(chaves_origem);

    char estrategia[80];
    PyOS_snprintf(
        estrategia,
        sizeof(estrategia),
        passagens == 1
            ? "protótipo keyed-int64: radix nativo compacto, 1 passagem"
            : "protótipo keyed-int64: radix nativo compacto, %d passagens",
        passagens
    );
    return finalizar_resultado_keyed(
        lista,
        estrategia,
        "radix",
        "intervalo amplo ou esparso; Counting Sort inelegível",
        tipo,
        n,
        1,
        menor_valor,
        maior_valor,
        amplitude,
        passagens,
        normalizado,
        KEYED_RADIX
    );
}

static int
parse_keyed_prototype_args(
    PyObject *args,
    PyObject **iteravel,
    PyObject **funcao_chave
)
{
    return PyArg_ParseTuple(
        args,
        "OO:_sort_by_int64_key_prototype",
        iteravel,
        funcao_chave
    );
}

typedef struct {
    PyObject_HEAD
    vectorcallfunc vectorcall;
    PyObject *chaves;
    PyObject *funcao_chave;
    Py_ssize_t quantidade;
    Py_ssize_t proximo;
} EstadoReplayChaves;

static int
visitar_replay_chaves(PyObject *objeto, visitproc visit, void *arg)
{
    EstadoReplayChaves *estado = (EstadoReplayChaves *)objeto;
    Py_VISIT(estado->chaves);
    Py_VISIT(estado->funcao_chave);
    return 0;
}

static int
limpar_replay_chaves(PyObject *objeto)
{
    EstadoReplayChaves *estado = (EstadoReplayChaves *)objeto;
    Py_CLEAR(estado->funcao_chave);
    Py_CLEAR(estado->chaves);
    return 0;
}

static void
destruir_replay_chaves(PyObject *objeto)
{
    PyObject_GC_UnTrack(objeto);
    limpar_replay_chaves(objeto);
    Py_TYPE(objeto)->tp_free(objeto);
}

static PyObject *
reproduzir_chave_cacheada(
    PyObject *objeto,
    PyObject *const *argumentos,
    size_t nargsf,
    PyObject *nomes_argumentos
)
{
    if (
        PyVectorcall_NARGS(nargsf) != 1
        || (
            nomes_argumentos != NULL
            && PyTuple_GET_SIZE(nomes_argumentos) != 0
        )
    ) {
        PyErr_SetString(
            PyExc_TypeError,
            "o replay de chaves recebe exatamente um argumento posicional"
        );
        return NULL;
    }

    EstadoReplayChaves *estado = (EstadoReplayChaves *)objeto;
    const Py_ssize_t indice = estado->proximo;
    if (indice >= estado->quantidade) {
        PyErr_SetString(
            PyExc_RuntimeError,
            "o replay de chaves é de uso único"
        );
        return NULL;
    }

    estado->proximo++;
    if (indice < PyList_GET_SIZE(estado->chaves)) {
        PyObject *chave = PyList_GET_ITEM(estado->chaves, indice);
        Py_INCREF(chave);
        return chave;
    }
    if (estado->funcao_chave == NULL) {
        PyErr_SetString(
            PyExc_RuntimeError,
            "o replay não possui uma chave cacheada para este item"
        );
        return NULL;
    }
    return PyObject_Vectorcall(
        estado->funcao_chave,
        argumentos,
        1,
        NULL
    );
}

static PyTypeObject tipo_replay_chaves = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "bielsort_native._CachedKeyReplay",
    .tp_basicsize = sizeof(EstadoReplayChaves),
    .tp_dealloc = destruir_replay_chaves,
    .tp_call = PyVectorcall_Call,
    .tp_flags = (
        Py_TPFLAGS_DEFAULT
        | Py_TPFLAGS_HAVE_VECTORCALL
        | Py_TPFLAGS_HAVE_GC
    ),
    .tp_doc = "Callable interno de uso único para replay de chaves.",
    .tp_traverse = visitar_replay_chaves,
    .tp_clear = limpar_replay_chaves,
    .tp_vectorcall_offset = offsetof(EstadoReplayChaves, vectorcall),
};

static PyObject *
criar_replay_chaves_cacheadas(
    PyObject *itens,
    PyObject *chaves,
    PyObject *funcao_chave
)
{
    if (
        !PyList_CheckExact(itens)
        || !PyList_CheckExact(chaves)
        || itens == chaves
    ) {
        PyErr_SetString(
            PyExc_TypeError,
            "o replay requer duas lists exatas e distintas"
        );
        return NULL;
    }
    if (
        funcao_chave == NULL
        && PyList_GET_SIZE(itens) != PyList_GET_SIZE(chaves)
    ) {
        PyErr_SetString(
            PyExc_ValueError,
            "items e cached_keys devem ter o mesmo tamanho"
        );
        return NULL;
    }
    if (
        funcao_chave != NULL
        && (
            !PyCallable_Check(funcao_chave)
            || PyList_GET_SIZE(chaves) > PyList_GET_SIZE(itens)
        )
    ) {
        PyErr_SetString(
            PyExc_TypeError,
            "o replay de prefixo requer key chamável e prefixo válido"
        );
        return NULL;
    }

    EstadoReplayChaves *estado = (EstadoReplayChaves *)PyType_GenericAlloc(
        &tipo_replay_chaves,
        0
    );
    if (estado == NULL) {
        return NULL;
    }
    estado->vectorcall = reproduzir_chave_cacheada;
    estado->chaves = chaves;
    estado->funcao_chave = funcao_chave;
    estado->quantidade = PyList_GET_SIZE(itens);
    estado->proximo = 0;
    Py_INCREF(chaves);
    Py_XINCREF(funcao_chave);
    return (PyObject *)estado;
}

static PyObject *
py_sort(PyObject *Py_UNUSED(modulo), PyObject *iteravel)
{
    return biel_sort_impl(iteravel, RETORNO_LISTA, 1);
}

static PyObject *
py_sort_with_strategy(PyObject *Py_UNUSED(modulo), PyObject *iteravel)
{
    return biel_sort_impl(iteravel, RETORNO_DIAGNOSTICO, 1);
}

static PyObject *
py_sort_in_place(PyObject *Py_UNUSED(modulo), PyObject *lista)
{
    return biel_sort_impl(lista, RETORNO_NONE, 0);
}

static PyObject *
py_sort_in_place_with_strategy(PyObject *Py_UNUSED(modulo), PyObject *lista)
{
    return biel_sort_impl(lista, RETORNO_ESTRATEGIA, 0);
}

static PyObject *
py_sort_by_int64_key_prototype(PyObject *Py_UNUSED(modulo), PyObject *args)
{
    PyObject *iteravel;
    PyObject *funcao_chave;
    if (!parse_keyed_prototype_args(args, &iteravel, &funcao_chave)) {
        return NULL;
    }
    return sort_by_int64_key_prototype_impl(
        iteravel,
        funcao_chave,
        NULL,
        RETORNO_LISTA,
        KEYED_CHAVE_DIRETA
    );
}

static PyObject *
py_sort_by_int64_key_prototype_with_strategy(
    PyObject *Py_UNUSED(modulo),
    PyObject *args
)
{
    PyObject *iteravel;
    PyObject *funcao_chave;
    if (!parse_keyed_prototype_args(args, &iteravel, &funcao_chave)) {
        return NULL;
    }
    return sort_by_int64_key_prototype_impl(
        iteravel,
        funcao_chave,
        NULL,
        RETORNO_DIAGNOSTICO,
        KEYED_CHAVE_DIRETA
    );
}

static PyObject *
py_sort_by_int64_key_prototype_with_info(
    PyObject *Py_UNUSED(modulo),
    PyObject *args
)
{
    PyObject *iteravel;
    PyObject *funcao_chave;
    if (!parse_keyed_prototype_args(args, &iteravel, &funcao_chave)) {
        return NULL;
    }
    return sort_by_int64_key_prototype_impl(
        iteravel,
        funcao_chave,
        NULL,
        RETORNO_DIAGNOSTICO_ESTRUTURADO,
        KEYED_CHAVE_DIRETA
    );
}

static PyObject *
py_try_sort_by_cached_int64_keys_prototype(
    PyObject *Py_UNUSED(modulo),
    PyObject *args
)
{
    PyObject *itens;
    PyObject *chaves;
    if (!PyArg_ParseTuple(
        args,
        "OO:_try_sort_by_cached_int64_keys_prototype",
        &itens,
        &chaves
    )) {
        return NULL;
    }
    return sort_by_int64_key_prototype_impl(
        itens,
        NULL,
        chaves,
        RETORNO_LISTA,
        KEYED_CACHE_COMPLETO
    );
}

static PyObject *
py_try_sort_by_cached_int64_keys_prototype_with_info(
    PyObject *Py_UNUSED(modulo),
    PyObject *args
)
{
    PyObject *itens;
    PyObject *chaves;
    if (!PyArg_ParseTuple(
        args,
        "OO:_try_sort_by_cached_int64_keys_prototype_with_info",
        &itens,
        &chaves
    )) {
        return NULL;
    }
    return sort_by_int64_key_prototype_impl(
        itens,
        NULL,
        chaves,
        RETORNO_DIAGNOSTICO_ESTRUTURADO,
        KEYED_CACHE_COMPLETO
    );
}

static PyObject *
py_try_sort_by_prefix_cached_int64_keys_prototype(
    PyObject *Py_UNUSED(modulo),
    PyObject *args
)
{
    PyObject *itens;
    PyObject *chaves;
    PyObject *funcao_chave;
    if (!PyArg_ParseTuple(
        args,
        "OOO:_try_sort_by_prefix_cached_int64_keys_prototype",
        &itens,
        &chaves,
        &funcao_chave
    )) {
        return NULL;
    }
    return sort_by_int64_key_prototype_impl(
        itens,
        funcao_chave,
        chaves,
        RETORNO_LISTA,
        KEYED_CACHE_PREFIXO
    );
}

static PyObject *
py_try_sort_by_prefix_cached_int64_keys_prototype_with_info(
    PyObject *Py_UNUSED(modulo),
    PyObject *args
)
{
    PyObject *itens;
    PyObject *chaves;
    PyObject *funcao_chave;
    if (!PyArg_ParseTuple(
        args,
        "OOO:_try_sort_by_prefix_cached_int64_keys_prototype_with_info",
        &itens,
        &chaves,
        &funcao_chave
    )) {
        return NULL;
    }
    return sort_by_int64_key_prototype_impl(
        itens,
        funcao_chave,
        chaves,
        RETORNO_DIAGNOSTICO_ESTRUTURADO,
        KEYED_CACHE_PREFIXO
    );
}

static PyObject *
py_make_cached_key_replay_prototype(
    PyObject *Py_UNUSED(modulo),
    PyObject *args
)
{
    PyObject *itens;
    PyObject *chaves;
    if (!PyArg_ParseTuple(
        args,
        "OO:_make_cached_key_replay_prototype",
        &itens,
        &chaves
    )) {
        return NULL;
    }
    return criar_replay_chaves_cacheadas(itens, chaves, NULL);
}

static PyObject *
py_make_prefix_cached_key_replay_prototype(
    PyObject *Py_UNUSED(modulo),
    PyObject *args
)
{
    PyObject *itens;
    PyObject *chaves;
    PyObject *funcao_chave;
    if (!PyArg_ParseTuple(
        args,
        "OOO:_make_prefix_cached_key_replay_prototype",
        &itens,
        &chaves,
        &funcao_chave
    )) {
        return NULL;
    }
    return criar_replay_chaves_cacheadas(
        itens,
        chaves,
        funcao_chave
    );
}

PyDoc_STRVAR(
    sort_doc,
    "sort(iterable, /)\n"
    "--\n\n"
    "Retorna uma nova lista ordenada usando o BielSort híbrido nativo."
);

PyDoc_STRVAR(
    strategy_doc,
    "sort_with_strategy(iterable, /)\n"
    "--\n\n"
    "Retorna (lista_ordenada, estrategia_utilizada)."
);

PyDoc_STRVAR(
    in_place_doc,
    "sort_in_place(lista, /)\n"
    "--\n\n"
    "Ordena uma lista no lugar e retorna None, como list.sort()."
);

PyDoc_STRVAR(
    in_place_strategy_doc,
    "sort_in_place_with_strategy(lista, /)\n"
    "--\n\n"
    "Ordena no lugar e retorna o nome da estratégia utilizada."
);

PyDoc_STRVAR(
    keyed_prototype_doc,
    "_sort_by_int64_key_prototype(iterable, key, /)\n"
    "--\n\n"
    "Protótipo interno: ordena objetos por uma chave int64 estável."
);

PyDoc_STRVAR(
    keyed_prototype_strategy_doc,
    "_sort_by_int64_key_prototype_with_strategy(iterable, key, /)\n"
    "--\n\n"
    "Protótipo interno: retorna (lista_ordenada, estratégia)."
);

PyDoc_STRVAR(
    keyed_prototype_info_doc,
    "_sort_by_int64_key_prototype_with_info(iterable, key, /)\n"
    "--\n\n"
    "Protótipo interno: retorna (lista_ordenada, diagnóstico estruturado)."
);

PyDoc_STRVAR(
    cached_keyed_prototype_doc,
    "_try_sort_by_cached_int64_keys_prototype(items, cached_keys, /)\n"
    "--\n\n"
    "Protótipo interno: consome chaves int64 ou retorna None."
);

PyDoc_STRVAR(
    cached_keyed_prototype_info_doc,
    "_try_sort_by_cached_int64_keys_prototype_with_info(items, keys, /)\n"
    "--\n\n"
    "Protótipo interno cacheado com diagnóstico estruturado."
);

PyDoc_STRVAR(
    prefix_cached_keyed_prototype_doc,
    "_try_sort_by_prefix_cached_int64_keys_prototype(items, keys, key, /)\n"
    "--\n\n"
    "Protótipo interno: completa o cache enquanto extrai int64."
);

PyDoc_STRVAR(
    prefix_cached_keyed_prototype_info_doc,
    "_try_sort_by_prefix_cached_int64_keys_prototype_with_info(items, keys, "
    "key, /)\n"
    "--\n\n"
    "Protótipo prefixado com diagnóstico estruturado."
);

PyDoc_STRVAR(
    cached_key_replay_prototype_doc,
    "_make_cached_key_replay_prototype(items, cached_keys, /)\n"
    "--\n\n"
    "Protótipo interno: cria callable nativo de replay para Timsort."
);

PyDoc_STRVAR(
    prefix_cached_key_replay_prototype_doc,
    "_make_prefix_cached_key_replay_prototype(items, keys, key, /)\n"
    "--\n\n"
    "Protótipo interno: reproduz um prefixo e avalia as chaves restantes."
);

static PyMethodDef metodos[] = {
    {"sort", py_sort, METH_O, sort_doc},
    {"sort_with_strategy", py_sort_with_strategy, METH_O, strategy_doc},
    {"sort_in_place", py_sort_in_place, METH_O, in_place_doc},
    {
        "sort_in_place_with_strategy",
        py_sort_in_place_with_strategy,
        METH_O,
        in_place_strategy_doc
    },
    {
        "_sort_by_int64_key_prototype",
        py_sort_by_int64_key_prototype,
        METH_VARARGS,
        keyed_prototype_doc
    },
    {
        "_sort_by_int64_key_prototype_with_strategy",
        py_sort_by_int64_key_prototype_with_strategy,
        METH_VARARGS,
        keyed_prototype_strategy_doc
    },
    {
        "_sort_by_int64_key_prototype_with_info",
        py_sort_by_int64_key_prototype_with_info,
        METH_VARARGS,
        keyed_prototype_info_doc
    },
    {
        "_try_sort_by_cached_int64_keys_prototype",
        py_try_sort_by_cached_int64_keys_prototype,
        METH_VARARGS,
        cached_keyed_prototype_doc
    },
    {
        "_try_sort_by_cached_int64_keys_prototype_with_info",
        py_try_sort_by_cached_int64_keys_prototype_with_info,
        METH_VARARGS,
        cached_keyed_prototype_info_doc
    },
    {
        "_try_sort_by_prefix_cached_int64_keys_prototype",
        py_try_sort_by_prefix_cached_int64_keys_prototype,
        METH_VARARGS,
        prefix_cached_keyed_prototype_doc
    },
    {
        "_try_sort_by_prefix_cached_int64_keys_prototype_with_info",
        py_try_sort_by_prefix_cached_int64_keys_prototype_with_info,
        METH_VARARGS,
        prefix_cached_keyed_prototype_info_doc
    },
    {
        "_make_cached_key_replay_prototype",
        py_make_cached_key_replay_prototype,
        METH_VARARGS,
        cached_key_replay_prototype_doc
    },
    {
        "_make_prefix_cached_key_replay_prototype",
        py_make_prefix_cached_key_replay_prototype,
        METH_VARARGS,
        prefix_cached_key_replay_prototype_doc
    },
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef modulo = {
    PyModuleDef_HEAD_INIT,
    "_bielsort",
    "Núcleo nativo do BielSort.",
    -1,
    metodos,
    NULL,
    NULL,
    NULL,
    NULL
};

PyMODINIT_FUNC
PyInit__bielsort(void)
{
    if (PyType_Ready(&tipo_replay_chaves) < 0) {
        return NULL;
    }
    return PyModule_Create(&modulo);
}
