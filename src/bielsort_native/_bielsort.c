#define PY_SSIZE_T_CLEAN
/* Native core for the bielsort_native CPython package. */
#include <Python.h>
#include <stdint.h>

#define RADIX_BITS 11
#define RADIX_BASE (1U << RADIX_BITS)
#define RADIX_MASCARA (RADIX_BASE - 1U)
#define CONTAGEM_MINIMO_ELEMENTOS 250000
#define CONTAGEM_LIMITE UINT64_C(4000000)
#define CONTAGEM_FATOR UINT64_C(4)

typedef struct {
    PyObject *objeto;
    uint64_t chave;
} Entrada;

typedef enum {
    RETORNO_LISTA,
    RETORNO_DIAGNOSTICO,
    RETORNO_NONE,
    RETORNO_ESTRATEGIA
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

    Entrada *destino = PyMem_Malloc((size_t)n * sizeof(*destino));
    if (destino == NULL) {
        PyMem_Free(origem);
        Py_DECREF(lista);
        return PyErr_NoMemory();
    }

    if (usar_contagem) {
        const size_t tamanho_contagem = (size_t)amplitude + 1;
        Py_ssize_t *contagem = PyMem_Calloc(
            tamanho_contagem,
            sizeof(*contagem)
        );

        /*
         * Se a tabela opcional não couber na memória, o radix continua sendo
         * uma alternativa correta e já possui os buffers necessários.
         */
        if (contagem != NULL) {
            PyThreadState *estado_gil = NULL;
            if (copiar) {
                estado_gil = PyEval_SaveThread();
            }

            for (Py_ssize_t i = 0; i < n; i++) {
                contagem[(size_t)origem[i].chave]++;
            }

            Py_ssize_t total = 0;
            for (size_t chave = 0; chave < tamanho_contagem; chave++) {
                const Py_ssize_t quantidade = contagem[chave];
                contagem[chave] = total;
                total += quantidade;
            }

            for (Py_ssize_t i = 0; i < n; i++) {
                const size_t chave = (size_t)origem[i].chave;
                destino[contagem[chave]++] = origem[i];
            }

            if (estado_gil != NULL) {
                PyEval_RestoreThread(estado_gil);
            }

            for (Py_ssize_t i = 0; i < n; i++) {
                PyList_SET_ITEM(lista, i, destino[i].objeto);
            }

            PyMem_Free(contagem);
            PyMem_Free(destino);
            PyMem_Free(origem);
            return finalizar_resultado(
                lista,
                "counting nativo estável",
                tipo
            );
        }
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
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef modulo = {
    PyModuleDef_HEAD_INIT,
    "_bielsort",
    "Núcleo nativo do BielSort.",
    -1,
    metodos
};

PyMODINIT_FUNC
PyInit__bielsort(void)
{
    return PyModule_Create(&modulo);
}
