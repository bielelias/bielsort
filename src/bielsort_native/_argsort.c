#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "_argsort.h"

#define ARGSORT_RADIX_BITS 11
#define ARGSORT_RADIX_BASE (1U << ARGSORT_RADIX_BITS)
#define ARGSORT_RADIX_MASK (ARGSORT_RADIX_BASE - 1U)
#define ARGSORT_NATIVE_MINIMUM 2048

typedef struct {
    PyObject_HEAD
    void *indices;
    Py_ssize_t length;
    Py_ssize_t source_length;
    Py_ssize_t shape;
    Py_ssize_t stride;
    int itemsize;
} BielSortPermutation;

static PyTypeObject bielsort_permutation_type;

static void
permutation_dealloc(BielSortPermutation *self)
{
    PyMem_Free(self->indices);
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static Py_ssize_t
permutation_length(PyObject *object)
{
    BielSortPermutation *self = (BielSortPermutation *)object;
    return self->length;
}

static PyObject *
permutation_item(PyObject *object, Py_ssize_t index)
{
    BielSortPermutation *self = (BielSortPermutation *)object;
    if (index < 0) {
        index += self->length;
    }
    if (index < 0 || index >= self->length) {
        PyErr_SetString(PyExc_IndexError, "permutation index out of range");
        return NULL;
    }
    if (self->itemsize == 4) {
        const uint32_t *indices = (const uint32_t *)self->indices;
        return PyLong_FromUnsignedLong((unsigned long)indices[index]);
    }
    const uint64_t *indices = (const uint64_t *)self->indices;
    return PyLong_FromUnsignedLongLong(
        (unsigned long long)indices[index]
    );
}

static PyObject *
permutation_repr(PyObject *object)
{
    BielSortPermutation *self = (BielSortPermutation *)object;
    return PyUnicode_FromFormat(
        "_Permutation(length=%zd, source_length=%zd, itemsize=%d)",
        self->length,
        self->source_length,
        self->itemsize
    );
}

static PyObject *
permutation_apply(BielSortPermutation *self, PyObject *sequence)
{
    if (!PySequence_Check(sequence)) {
        PyErr_SetString(
            PyExc_TypeError,
            "permutation.apply requires a reusable sequence"
        );
        return NULL;
    }
    PyObject *values = PySequence_Fast(
        sequence,
        "permutation.apply requires a reusable sequence"
    );
    if (values == NULL) {
        return NULL;
    }
    const Py_ssize_t length = PySequence_Fast_GET_SIZE(values);
    if (length != self->source_length) {
        Py_DECREF(values);
        PyErr_Format(
            PyExc_ValueError,
            "permutation source length %zd does not match sequence length %zd",
            self->source_length,
            length
        );
        return NULL;
    }

    PyObject *result = PyList_New(self->length);
    if (result == NULL) {
        Py_DECREF(values);
        return NULL;
    }
    for (Py_ssize_t position = 0; position < self->length; position++) {
        uint64_t index;
        if (self->itemsize == 4) {
            index = ((const uint32_t *)self->indices)[position];
        } else {
            index = ((const uint64_t *)self->indices)[position];
        }
        if (index >= (uint64_t)self->source_length) {
            Py_DECREF(result);
            Py_DECREF(values);
            PyErr_SetString(
                PyExc_SystemError,
                "permutation contains an invalid internal index"
            );
            return NULL;
        }
        PyObject *item = PySequence_Fast_GET_ITEM(
            values,
            (Py_ssize_t)index
        );
        Py_INCREF(item);
        PyList_SET_ITEM(result, position, item);
    }
    Py_DECREF(values);
    return result;
}

static int
permutation_getbuffer(PyObject *object, Py_buffer *view, int flags)
{
    BielSortPermutation *self = (BielSortPermutation *)object;
    if ((flags & PyBUF_WRITABLE) == PyBUF_WRITABLE) {
        PyErr_SetString(PyExc_BufferError, "permutation buffer is read-only");
        return -1;
    }
    if (self->length > PY_SSIZE_T_MAX / self->itemsize) {
        return PyErr_NoMemory(), -1;
    }
    if (
        PyBuffer_FillInfo(
            view,
            object,
            self->indices,
            self->length * self->itemsize,
            1,
            flags
        ) < 0
    ) {
        return -1;
    }
    view->itemsize = self->itemsize;
    view->format = (flags & PyBUF_FORMAT)
        ? (self->itemsize == 4 ? "I" : "Q")
        : NULL;
    view->shape = (flags & PyBUF_ND) ? &self->shape : NULL;
    view->strides = (flags & PyBUF_STRIDES) ? &self->stride : NULL;
    view->suboffsets = NULL;
    view->internal = NULL;
    return 0;
}

static PySequenceMethods permutation_sequence = {
    .sq_length = permutation_length,
    .sq_item = permutation_item,
};

static PyBufferProcs permutation_buffer = {
    .bf_getbuffer = permutation_getbuffer,
};

static PyMethodDef permutation_methods[] = {
    {
        "apply",
        (PyCFunction)permutation_apply,
        METH_O,
        "apply($self, sequence, /)\n--\n\n"
        "Return sequence values in this private permutation's order."
    },
    {NULL, NULL, 0, NULL}
};

static PyTypeObject bielsort_permutation_type = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "bielsort_native._bielsort._Permutation",
    .tp_basicsize = sizeof(BielSortPermutation),
    .tp_dealloc = (destructor)permutation_dealloc,
    .tp_repr = permutation_repr,
    .tp_as_sequence = &permutation_sequence,
    .tp_as_buffer = &permutation_buffer,
    .tp_methods = permutation_methods,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_doc = "Private immutable compact permutation prototype.",
};

static PyObject *
permutation_new_owned(
    Py_ssize_t length,
    Py_ssize_t source_length,
    int itemsize,
    void *indices
)
{
    BielSortPermutation *result = PyObject_New(
        BielSortPermutation,
        &bielsort_permutation_type
    );
    if (result == NULL) {
        PyMem_Free(indices);
        return NULL;
    }
    result->indices = indices;
    result->length = length;
    result->source_length = source_length;
    result->shape = length;
    result->stride = itemsize;
    result->itemsize = itemsize;
    return (PyObject *)result;
}

static int
permutation_itemsize(Py_ssize_t length)
{
    return (uint64_t)length <= UINT32_MAX ? 4 : 8;
}

static void *
allocate_indices(Py_ssize_t length, int itemsize)
{
    if (length == 0) {
        return NULL;
    }
    if ((size_t)length > SIZE_MAX / (size_t)itemsize) {
        PyErr_NoMemory();
        return NULL;
    }
    void *indices = PyMem_Malloc((size_t)length * (size_t)itemsize);
    if (indices == NULL) {
        PyErr_NoMemory();
    }
    return indices;
}

static PyObject *
identity_permutation(Py_ssize_t length)
{
    const int itemsize = permutation_itemsize(length);
    void *storage = allocate_indices(length, itemsize);
    if (length != 0 && storage == NULL) {
        return NULL;
    }
    if (itemsize == 4) {
        uint32_t *indices = (uint32_t *)storage;
        for (Py_ssize_t index = 0; index < length; index++) {
            indices[index] = (uint32_t)index;
        }
    } else {
        uint64_t *indices = (uint64_t *)storage;
        for (Py_ssize_t index = 0; index < length; index++) {
            indices[index] = (uint64_t)index;
        }
    }
    return permutation_new_owned(length, length, itemsize, storage);
}

static PyObject *
finalize_argsort(PyObject *permutation, const char *strategy, int diagnostic)
{
    if (!diagnostic || permutation == NULL) {
        return permutation;
    }
    PyObject *name = PyUnicode_FromString(strategy);
    if (name == NULL) {
        Py_DECREF(permutation);
        return NULL;
    }
    PyObject *result = PyTuple_New(2);
    if (result == NULL) {
        Py_DECREF(name);
        Py_DECREF(permutation);
        return NULL;
    }
    PyTuple_SET_ITEM(result, 0, permutation);
    PyTuple_SET_ITEM(result, 1, name);
    return result;
}

static PyObject *
pack_python_indices(PyObject *indices)
{
    const Py_ssize_t length = PyList_GET_SIZE(indices);
    const int itemsize = permutation_itemsize(length);
    void *storage = allocate_indices(length, itemsize);
    if (length != 0 && storage == NULL) {
        return NULL;
    }
    for (Py_ssize_t position = 0; position < length; position++) {
        Py_ssize_t index = PyLong_AsSsize_t(
            PyList_GET_ITEM(indices, position)
        );
        if (index == -1 && PyErr_Occurred()) {
            PyMem_Free(storage);
            return NULL;
        }
        if (itemsize == 4) {
            ((uint32_t *)storage)[position] = (uint32_t)index;
        } else {
            ((uint64_t *)storage)[position] = (uint64_t)index;
        }
    }
    return permutation_new_owned(length, length, itemsize, storage);
}

static PyObject *
argsort_timsort(PyObject *values, int reverse)
{
    const Py_ssize_t length = PyList_GET_SIZE(values);
    PyObject *indices = PyList_New(length);
    if (indices == NULL) {
        return NULL;
    }
    for (Py_ssize_t index = 0; index < length; index++) {
        PyObject *python_index = PyLong_FromSsize_t(index);
        if (python_index == NULL) {
            Py_DECREF(indices);
            return NULL;
        }
        PyList_SET_ITEM(indices, index, python_index);
    }

    PyObject *sort_method = PyObject_GetAttrString(indices, "sort");
    PyObject *key_method = PyObject_GetAttrString(values, "__getitem__");
    PyObject *arguments = NULL;
    PyObject *options = NULL;
    PyObject *call_result = NULL;
    if (sort_method != NULL && key_method != NULL) {
        arguments = PyTuple_New(0);
    }
    if (arguments != NULL) {
        options = Py_BuildValue(
            "{s:O,s:O}",
            "key",
            key_method,
            "reverse",
            reverse ? Py_True : Py_False
        );
    }
    if (options != NULL) {
        call_result = PyObject_Call(sort_method, arguments, options);
    }
    Py_XDECREF(options);
    Py_XDECREF(arguments);
    Py_XDECREF(key_method);
    Py_XDECREF(sort_method);
    if (call_result == NULL) {
        Py_DECREF(indices);
        return NULL;
    }
    Py_DECREF(call_result);

    PyObject *result = pack_python_indices(indices);
    Py_DECREF(indices);
    return result;
}

static int
radix_indices_u32(
    uint64_t **keys_result,
    uint64_t *keys_temporary,
    uint32_t **indices_result,
    uint32_t *indices_temporary,
    Py_ssize_t length,
    uint64_t variation
)
{
    uint64_t *input_keys = *keys_result;
    uint64_t *output_keys = keys_temporary;
    uint32_t *input_indices = *indices_result;
    uint32_t *output_indices = indices_temporary;
    int passes = 0;

    for (int shift = 0; shift < 64; shift += ARGSORT_RADIX_BITS) {
        if (((variation >> shift) & ARGSORT_RADIX_MASK) == 0) {
            continue;
        }
        Py_ssize_t counts[ARGSORT_RADIX_BASE];
        memset(counts, 0, sizeof(counts));
        for (Py_ssize_t index = 0; index < length; index++) {
            const unsigned digit = (unsigned)(
                (input_keys[index] >> shift) & ARGSORT_RADIX_MASK
            );
            counts[digit]++;
        }
        Py_ssize_t total = 0;
        for (unsigned digit = 0; digit < ARGSORT_RADIX_BASE; digit++) {
            const Py_ssize_t count = counts[digit];
            counts[digit] = total;
            total += count;
        }
        for (Py_ssize_t index = 0; index < length; index++) {
            const uint64_t key = input_keys[index];
            const unsigned digit = (unsigned)(
                (key >> shift) & ARGSORT_RADIX_MASK
            );
            const Py_ssize_t destination = counts[digit]++;
            output_keys[destination] = key;
            output_indices[destination] = input_indices[index];
        }
        uint64_t *key_swap = input_keys;
        input_keys = output_keys;
        output_keys = key_swap;
        uint32_t *index_swap = input_indices;
        input_indices = output_indices;
        output_indices = index_swap;
        passes++;
    }
    *keys_result = input_keys;
    *indices_result = input_indices;
    return passes;
}

static int
radix_indices_u64(
    uint64_t **keys_result,
    uint64_t *keys_temporary,
    uint64_t **indices_result,
    uint64_t *indices_temporary,
    Py_ssize_t length,
    uint64_t variation
)
{
    uint64_t *input_keys = *keys_result;
    uint64_t *output_keys = keys_temporary;
    uint64_t *input_indices = *indices_result;
    uint64_t *output_indices = indices_temporary;
    int passes = 0;

    for (int shift = 0; shift < 64; shift += ARGSORT_RADIX_BITS) {
        if (((variation >> shift) & ARGSORT_RADIX_MASK) == 0) {
            continue;
        }
        Py_ssize_t counts[ARGSORT_RADIX_BASE];
        memset(counts, 0, sizeof(counts));
        for (Py_ssize_t index = 0; index < length; index++) {
            const unsigned digit = (unsigned)(
                (input_keys[index] >> shift) & ARGSORT_RADIX_MASK
            );
            counts[digit]++;
        }
        Py_ssize_t total = 0;
        for (unsigned digit = 0; digit < ARGSORT_RADIX_BASE; digit++) {
            const Py_ssize_t count = counts[digit];
            counts[digit] = total;
            total += count;
        }
        for (Py_ssize_t index = 0; index < length; index++) {
            const uint64_t key = input_keys[index];
            const unsigned digit = (unsigned)(
                (key >> shift) & ARGSORT_RADIX_MASK
            );
            const Py_ssize_t destination = counts[digit]++;
            output_keys[destination] = key;
            output_indices[destination] = input_indices[index];
        }
        uint64_t *key_swap = input_keys;
        input_keys = output_keys;
        output_keys = key_swap;
        uint64_t *index_swap = input_indices;
        input_indices = output_indices;
        output_indices = index_swap;
        passes++;
    }
    *keys_result = input_keys;
    *indices_result = input_indices;
    return passes;
}

static PyObject *
argsort_int64_impl(PyObject *sequence, int reverse, int diagnostic)
{
    if (!PySequence_Check(sequence)) {
        PyErr_SetString(
            PyExc_TypeError,
            "_argsort_int64_prototype requires a reusable sequence"
        );
        return NULL;
    }
    PyObject *values = PySequence_List(sequence);
    if (values == NULL) {
        return NULL;
    }
    const Py_ssize_t length = PyList_GET_SIZE(values);
    if (length < 2) {
        PyObject *result = identity_permutation(length);
        Py_DECREF(values);
        return finalize_argsort(result, "trivial", diagnostic);
    }
    if (length < ARGSORT_NATIVE_MINIMUM) {
        PyObject *result = argsort_timsort(values, reverse);
        Py_DECREF(values);
        return finalize_argsort(
            result,
            "timsort: entrada pequena",
            diagnostic
        );
    }
    if ((size_t)length > SIZE_MAX / sizeof(uint64_t)) {
        Py_DECREF(values);
        return PyErr_NoMemory();
    }
    uint64_t *keys = PyMem_Malloc((size_t)length * sizeof(*keys));
    if (keys == NULL) {
        Py_DECREF(values);
        return PyErr_NoMemory();
    }

    uint64_t minimum = UINT64_MAX;
    uint64_t maximum = 0;
    uint64_t previous = 0;
    Py_ssize_t descents = 0;
    Py_ssize_t ascents = 0;
    int exact_int64 = 1;
    for (Py_ssize_t index = 0; index < length; index++) {
        PyObject *value = PyList_GET_ITEM(values, index);
        if (!PyLong_CheckExact(value)) {
            exact_int64 = 0;
            break;
        }
        long long signed_value = PyLong_AsLongLong(value);
        if (signed_value == -1 && PyErr_Occurred()) {
            if (PyErr_ExceptionMatches(PyExc_OverflowError)) {
                PyErr_Clear();
                exact_int64 = 0;
                break;
            }
            PyMem_Free(keys);
            Py_DECREF(values);
            return NULL;
        }
        uint64_t key = ((uint64_t)(int64_t)signed_value) ^ (UINT64_C(1) << 63);
        if (reverse) {
            key = ~key;
        }
        keys[index] = key;
        if (key < minimum) {
            minimum = key;
        }
        if (key > maximum) {
            maximum = key;
        }
        if (index != 0) {
            if (key < previous) {
                descents++;
            } else if (key > previous) {
                ascents++;
            }
        }
        previous = key;
    }

    if (!exact_int64) {
        PyMem_Free(keys);
        PyObject *result = argsort_timsort(values, reverse);
        Py_DECREF(values);
        return finalize_argsort(
            result,
            "timsort: tipo ou magnitude fora de int64",
            diagnostic
        );
    }
    if (descents == 0) {
        PyMem_Free(keys);
        PyObject *result = identity_permutation(length);
        Py_DECREF(values);
        return finalize_argsort(result, "já ordenado", diagnostic);
    }
    if (descents <= length / 128 || ascents <= length / 128) {
        PyMem_Free(keys);
        PyObject *result = argsort_timsort(values, reverse);
        Py_DECREF(values);
        return finalize_argsort(
            result,
            "timsort: entrada quase monotônica",
            diagnostic
        );
    }

    uint64_t variation = 0;
    for (Py_ssize_t index = 0; index < length; index++) {
        keys[index] -= minimum;
        variation |= keys[index];
    }
    if (variation == 0 || maximum == minimum) {
        PyMem_Free(keys);
        PyObject *result = identity_permutation(length);
        Py_DECREF(values);
        return finalize_argsort(result, "todos iguais", diagnostic);
    }

    uint64_t *temporary_keys = PyMem_Malloc(
        (size_t)length * sizeof(*temporary_keys)
    );
    const int itemsize = permutation_itemsize(length);
    void *indices = allocate_indices(length, itemsize);
    void *temporary_indices = allocate_indices(length, itemsize);
    if (
        temporary_keys == NULL
        || indices == NULL
        || temporary_indices == NULL
    ) {
        PyMem_Free(temporary_indices);
        PyMem_Free(indices);
        PyMem_Free(temporary_keys);
        PyMem_Free(keys);
        Py_DECREF(values);
        return PyErr_NoMemory();
    }

    uint64_t *final_keys = keys;
    void *final_indices = indices;
    int passes;
    if (itemsize == 4) {
        uint32_t *input = (uint32_t *)indices;
        for (Py_ssize_t index = 0; index < length; index++) {
            input[index] = (uint32_t)index;
        }
        uint32_t *output = (uint32_t *)temporary_indices;
        passes = radix_indices_u32(
            &final_keys,
            temporary_keys,
            &input,
            output,
            length,
            variation
        );
        final_indices = input;
    } else {
        uint64_t *input = (uint64_t *)indices;
        for (Py_ssize_t index = 0; index < length; index++) {
            input[index] = (uint64_t)index;
        }
        uint64_t *output = (uint64_t *)temporary_indices;
        passes = radix_indices_u64(
            &final_keys,
            temporary_keys,
            &input,
            output,
            length,
            variation
        );
        final_indices = input;
    }

    PyMem_Free(final_keys == keys ? temporary_keys : keys);
    PyMem_Free(final_keys);
    PyMem_Free(final_indices == indices ? temporary_indices : indices);
    Py_DECREF(values);

    PyObject *permutation = permutation_new_owned(
        length,
        length,
        itemsize,
        final_indices
    );
    if (permutation == NULL) {
        return NULL;
    }
    char strategy[80];
    PyOS_snprintf(
        strategy,
        sizeof(strategy),
        "radix nativo estável de índices: %d %s",
        passes,
        passes == 1 ? "passagem" : "passagens"
    );
    return finalize_argsort(permutation, strategy, diagnostic);
}

typedef struct {
    uint64_t key;
    uint64_t index;
} TopKEntry;

static int
topk_entry_is_better(TopKEntry left, TopKEntry right)
{
    return left.key < right.key
        || (left.key == right.key && left.index < right.index);
}

static int
topk_entry_is_worse(TopKEntry left, TopKEntry right)
{
    return left.key > right.key
        || (left.key == right.key && left.index > right.index);
}

static void
topk_sift_down(
    TopKEntry *heap,
    Py_ssize_t length,
    Py_ssize_t root
)
{
    while (length >= 2 && root <= (length - 2) / 2) {
        Py_ssize_t child = root * 2 + 1;
        if (
            child + 1 < length
            && topk_entry_is_worse(heap[child + 1], heap[child])
        ) {
            child++;
        }
        if (!topk_entry_is_worse(heap[child], heap[root])) {
            return;
        }
        const TopKEntry swap = heap[root];
        heap[root] = heap[child];
        heap[child] = swap;
        root = child;
    }
}

static int
topk_compare_best_first(const void *left_pointer, const void *right_pointer)
{
    const TopKEntry left = *(const TopKEntry *)left_pointer;
    const TopKEntry right = *(const TopKEntry *)right_pointer;
    if (topk_entry_is_better(left, right)) {
        return -1;
    }
    if (topk_entry_is_better(right, left)) {
        return 1;
    }
    return 0;
}

static PyObject *
permutation_prefix(PyObject *object, Py_ssize_t length)
{
    BielSortPermutation *permutation = (BielSortPermutation *)object;
    if (
        Py_TYPE(object) != &bielsort_permutation_type
        || length < 0
        || length > permutation->length
    ) {
        PyErr_SetString(
            PyExc_SystemError,
            "invalid private permutation prefix"
        );
        return NULL;
    }
    void *storage = allocate_indices(length, permutation->itemsize);
    if (length != 0 && storage == NULL) {
        return NULL;
    }
    if (length != 0) {
        memcpy(
            storage,
            permutation->indices,
            (size_t)length * (size_t)permutation->itemsize
        );
    }
    return permutation_new_owned(
        length,
        permutation->source_length,
        permutation->itemsize,
        storage
    );
}

static PyObject *
topk_full_argsort(
    PyObject *sequence,
    Py_ssize_t k,
    int largest,
    const char *strategy,
    int diagnostic
)
{
    PyObject *full = argsort_int64_impl(sequence, largest, 0);
    if (full == NULL) {
        return NULL;
    }
    PyObject *result = permutation_prefix(full, k);
    Py_DECREF(full);
    return finalize_argsort(result, strategy, diagnostic);
}

static PyObject *
topk_int64_impl(
    PyObject *sequence,
    Py_ssize_t k,
    int largest,
    int diagnostic
)
{
    if (!PySequence_Check(sequence)) {
        PyErr_SetString(
            PyExc_TypeError,
            "_topk_int64_prototype requires a reusable sequence"
        );
        return NULL;
    }
    if (k < 0) {
        PyErr_SetString(PyExc_ValueError, "k must be non-negative");
        return NULL;
    }
    PyObject *values = PySequence_Fast(
        sequence,
        "_topk_int64_prototype requires a reusable sequence"
    );
    if (values == NULL) {
        return NULL;
    }
    const Py_ssize_t source_length = PySequence_Fast_GET_SIZE(values);
    if (k > source_length) {
        k = source_length;
    }
    const int itemsize = permutation_itemsize(source_length);
    if (k == 0) {
        Py_DECREF(values);
        PyObject *result = permutation_new_owned(
            0,
            source_length,
            itemsize,
            NULL
        );
        return finalize_argsort(result, "seleção vazia", diagnostic);
    }
    if (k > source_length / 8) {
        Py_DECREF(values);
        return topk_full_argsort(
            sequence,
            k,
            largest,
            "argsort completo adaptativo: k grande",
            diagnostic
        );
    }
    if ((size_t)k > SIZE_MAX / sizeof(TopKEntry)) {
        Py_DECREF(values);
        return PyErr_NoMemory();
    }
    TopKEntry *heap = PyMem_Malloc((size_t)k * sizeof(*heap));
    if (heap == NULL) {
        Py_DECREF(values);
        return PyErr_NoMemory();
    }

    int exact_int64 = 1;
    for (Py_ssize_t index = 0; index < k; index++) {
        PyObject *value = PySequence_Fast_GET_ITEM(values, index);
        if (!PyLong_CheckExact(value)) {
            exact_int64 = 0;
            break;
        }
        const long long signed_value = PyLong_AsLongLong(value);
        if (signed_value == -1 && PyErr_Occurred()) {
            if (PyErr_ExceptionMatches(PyExc_OverflowError)) {
                PyErr_Clear();
                exact_int64 = 0;
                break;
            }
            PyMem_Free(heap);
            Py_DECREF(values);
            return NULL;
        }
        uint64_t key = (
            (uint64_t)(int64_t)signed_value
        ) ^ (UINT64_C(1) << 63);
        if (largest) {
            key = ~key;
        }
        heap[index].key = key;
        heap[index].index = (uint64_t)index;
    }
    if (!exact_int64) {
        PyMem_Free(heap);
        Py_DECREF(values);
        return topk_full_argsort(
            sequence,
            k,
            largest,
            "argsort completo: tipo ou magnitude fora de int64",
            diagnostic
        );
    }

    for (Py_ssize_t parent = k / 2; parent > 0; parent--) {
        topk_sift_down(heap, k, parent - 1);
    }
    for (Py_ssize_t index = k; index < source_length; index++) {
        PyObject *value = PySequence_Fast_GET_ITEM(values, index);
        if (!PyLong_CheckExact(value)) {
            exact_int64 = 0;
            break;
        }
        const long long signed_value = PyLong_AsLongLong(value);
        if (signed_value == -1 && PyErr_Occurred()) {
            if (PyErr_ExceptionMatches(PyExc_OverflowError)) {
                PyErr_Clear();
                exact_int64 = 0;
                break;
            }
            PyMem_Free(heap);
            Py_DECREF(values);
            return NULL;
        }
        uint64_t key = (
            (uint64_t)(int64_t)signed_value
        ) ^ (UINT64_C(1) << 63);
        if (largest) {
            key = ~key;
        }
        const TopKEntry candidate = {key, (uint64_t)index};
        if (topk_entry_is_better(candidate, heap[0])) {
            heap[0] = candidate;
            topk_sift_down(heap, k, 0);
        }
    }
    Py_DECREF(values);
    if (!exact_int64) {
        PyMem_Free(heap);
        return topk_full_argsort(
            sequence,
            k,
            largest,
            "argsort completo: tipo ou magnitude fora de int64",
            diagnostic
        );
    }

    qsort(heap, (size_t)k, sizeof(*heap), topk_compare_best_first);
    void *storage = allocate_indices(k, itemsize);
    if (storage == NULL) {
        PyMem_Free(heap);
        return NULL;
    }
    for (Py_ssize_t position = 0; position < k; position++) {
        if (itemsize == 4) {
            ((uint32_t *)storage)[position] = (uint32_t)heap[position].index;
        } else {
            ((uint64_t *)storage)[position] = heap[position].index;
        }
    }
    PyMem_Free(heap);

    PyObject *result = permutation_new_owned(
        k,
        source_length,
        itemsize,
        storage
    );
    if (result == NULL) {
        return NULL;
    }
    char strategy[96];
    PyOS_snprintf(
        strategy,
        sizeof(strategy),
        "heap nativo estável int64: k=%zd de n=%zd",
        k,
        source_length
    );
    return finalize_argsort(result, strategy, diagnostic);
}

static int
parse_argsort_arguments(PyObject *args, PyObject **sequence, int *reverse)
{
    return PyArg_ParseTuple(
        args,
        "O|p:_argsort_int64_prototype",
        sequence,
        reverse
    );
}

PyObject *
bielsort_py_argsort_int64_prototype(
    PyObject *Py_UNUSED(module),
    PyObject *args
)
{
    PyObject *sequence;
    int reverse = 0;
    if (!parse_argsort_arguments(args, &sequence, &reverse)) {
        return NULL;
    }
    return argsort_int64_impl(sequence, reverse, 0);
}

PyObject *
bielsort_py_argsort_int64_prototype_with_strategy(
    PyObject *Py_UNUSED(module),
    PyObject *args
)
{
    PyObject *sequence;
    int reverse = 0;
    if (!parse_argsort_arguments(args, &sequence, &reverse)) {
        return NULL;
    }
    return argsort_int64_impl(sequence, reverse, 1);
}

static int
parse_topk_arguments(
    PyObject *args,
    PyObject **sequence,
    Py_ssize_t *k,
    int *largest
)
{
    return PyArg_ParseTuple(
        args,
        "On|p:_topk_int64_prototype",
        sequence,
        k,
        largest
    );
}

PyObject *
bielsort_py_topk_int64_prototype(
    PyObject *Py_UNUSED(module),
    PyObject *args
)
{
    PyObject *sequence;
    Py_ssize_t k;
    int largest = 0;
    if (!parse_topk_arguments(args, &sequence, &k, &largest)) {
        return NULL;
    }
    return topk_int64_impl(sequence, k, largest, 0);
}

PyObject *
bielsort_py_topk_int64_prototype_with_strategy(
    PyObject *Py_UNUSED(module),
    PyObject *args
)
{
    PyObject *sequence;
    Py_ssize_t k;
    int largest = 0;
    if (!parse_topk_arguments(args, &sequence, &k, &largest)) {
        return NULL;
    }
    return topk_int64_impl(sequence, k, largest, 1);
}

int
bielsort_argsort_add_type(PyObject *module)
{
    if (PyType_Ready(&bielsort_permutation_type) < 0) {
        return -1;
    }
    Py_INCREF(&bielsort_permutation_type);
    if (
        PyModule_AddObject(
            module,
            "_Permutation",
            (PyObject *)&bielsort_permutation_type
        ) < 0
    ) {
        Py_DECREF(&bielsort_permutation_type);
        return -1;
    }
    return 0;
}
