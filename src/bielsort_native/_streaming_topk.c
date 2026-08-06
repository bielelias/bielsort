#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <limits.h>
#include <stdint.h>

#include "_streaming_topk.h"

typedef union {
    uint64_t normalized;
    PyObject *object;
} StreamingTopKKey;

typedef struct {
    StreamingTopKKey key;
    uint64_t encounter_index;
} StreamingTopKEntry;

static void
stream_topk_clear_generic_keys(
    StreamingTopKEntry *entries,
    Py_ssize_t length
)
{
    for (Py_ssize_t position = 0; position < length; position++) {
        Py_XDECREF(entries[position].key.object);
        entries[position].key.object = NULL;
    }
}

static void
stream_topk_swap(
    StreamingTopKEntry *entries,
    PyObject *records,
    Py_ssize_t left,
    Py_ssize_t right
)
{
    const StreamingTopKEntry entry = entries[left];
    entries[left] = entries[right];
    entries[right] = entry;

    PyObject *record = PyList_GET_ITEM(records, left);
    PyList_SET_ITEM(records, left, PyList_GET_ITEM(records, right));
    PyList_SET_ITEM(records, right, record);
}

static int
stream_topk_try_normalize(
    PyObject *key_object,
    int largest,
    uint64_t *normalized_key
)
{
    if (!PyLong_CheckExact(key_object)) {
        return 0;
    }
    const long long signed_value = PyLong_AsLongLong(key_object);
    if (signed_value == -1 && PyErr_Occurred()) {
        if (PyErr_ExceptionMatches(PyExc_OverflowError)) {
            PyErr_Clear();
            return 0;
        }
        return -1;
    }
    uint64_t key = (
        (uint64_t)(int64_t)signed_value
    ) ^ (UINT64_C(1) << 63);
    *normalized_key = largest ? ~key : key;
    return 1;
}

static PyObject *
stream_topk_denormalize(uint64_t normalized, int largest)
{
    const uint64_t biased = largest ? ~normalized : normalized;
    const uint64_t bits = biased ^ (UINT64_C(1) << 63);
    long long signed_value;
    if (bits <= (uint64_t)LLONG_MAX) {
        signed_value = (long long)bits;
    } else {
        signed_value = -1 - (long long)(UINT64_MAX - bits);
    }
    return PyLong_FromLongLong(signed_value);
}

static int
stream_topk_promote_generic_keys(
    StreamingTopKEntry *entries,
    Py_ssize_t length,
    int largest
)
{
    if (length == 0) {
        return 0;
    }
    if ((size_t)length > SIZE_MAX / sizeof(PyObject *)) {
        return PyErr_NoMemory(), -1;
    }
    PyObject **keys = PyMem_Malloc(
        (size_t)length * sizeof(*keys)
    );
    if (keys == NULL) {
        return PyErr_NoMemory(), -1;
    }
    Py_ssize_t created = 0;
    for (; created < length; created++) {
        keys[created] = stream_topk_denormalize(
            entries[created].key.normalized,
            largest
        );
        if (keys[created] == NULL) {
            break;
        }
    }
    if (created != length) {
        for (Py_ssize_t position = 0; position < created; position++) {
            Py_DECREF(keys[position]);
        }
        PyMem_Free(keys);
        return -1;
    }
    for (Py_ssize_t position = 0; position < length; position++) {
        entries[position].key.object = keys[position];
    }
    PyMem_Free(keys);
    return 0;
}

static int
stream_topk_exact_is_better(
    StreamingTopKEntry left,
    StreamingTopKEntry right
)
{
    return left.key.normalized < right.key.normalized
        || (
            left.key.normalized == right.key.normalized
            && left.encounter_index < right.encounter_index
        );
}

static int
stream_topk_exact_is_worse(
    StreamingTopKEntry left,
    StreamingTopKEntry right
)
{
    return left.key.normalized > right.key.normalized
        || (
            left.key.normalized == right.key.normalized
            && left.encounter_index > right.encounter_index
        );
}

static void
stream_topk_exact_sift_down(
    StreamingTopKEntry *heap,
    PyObject *records,
    Py_ssize_t length,
    Py_ssize_t root
)
{
    while (length >= 2 && root <= (length - 2) / 2) {
        Py_ssize_t child = root * 2 + 1;
        if (
            child + 1 < length
            && stream_topk_exact_is_worse(heap[child + 1], heap[child])
        ) {
            child++;
        }
        if (!stream_topk_exact_is_worse(heap[child], heap[root])) {
            return;
        }
        stream_topk_swap(heap, records, root, child);
        root = child;
    }
}

static void
stream_topk_exact_sort(
    StreamingTopKEntry *heap,
    PyObject *records,
    Py_ssize_t length
)
{
    for (Py_ssize_t end = length - 1; end > 0; end--) {
        stream_topk_swap(heap, records, 0, end);
        stream_topk_exact_sift_down(heap, records, end, 0);
    }
}

static int
stream_topk_generic_compare_best(
    const StreamingTopKEntry *left,
    const StreamingTopKEntry *right,
    int largest,
    int *comparison
)
{
    int left_is_better;
    int right_is_better;
    if (largest) {
        left_is_better = PyObject_RichCompareBool(
            right->key.object,
            left->key.object,
            Py_LT
        );
    } else {
        left_is_better = PyObject_RichCompareBool(
            left->key.object,
            right->key.object,
            Py_LT
        );
    }
    if (left_is_better < 0) {
        return -1;
    }
    if (left_is_better) {
        *comparison = -1;
        return 0;
    }

    if (largest) {
        right_is_better = PyObject_RichCompareBool(
            left->key.object,
            right->key.object,
            Py_LT
        );
    } else {
        right_is_better = PyObject_RichCompareBool(
            right->key.object,
            left->key.object,
            Py_LT
        );
    }
    if (right_is_better < 0) {
        return -1;
    }
    if (right_is_better) {
        *comparison = 1;
        return 0;
    }

    if (left->encounter_index < right->encounter_index) {
        *comparison = -1;
    } else if (left->encounter_index > right->encounter_index) {
        *comparison = 1;
    } else {
        *comparison = 0;
    }
    return 0;
}

static int
stream_topk_generic_sift_down(
    StreamingTopKEntry *heap,
    PyObject *records,
    Py_ssize_t length,
    Py_ssize_t root,
    int largest
)
{
    while (length >= 2 && root <= (length - 2) / 2) {
        Py_ssize_t child = root * 2 + 1;
        int comparison;
        if (child + 1 < length) {
            if (
                stream_topk_generic_compare_best(
                    &heap[child + 1],
                    &heap[child],
                    largest,
                    &comparison
                ) < 0
            ) {
                return -1;
            }
            if (comparison > 0) {
                child++;
            }
        }
        if (
            stream_topk_generic_compare_best(
                &heap[child],
                &heap[root],
                largest,
                &comparison
            ) < 0
        ) {
            return -1;
        }
        if (comparison <= 0) {
            return 0;
        }
        stream_topk_swap(heap, records, root, child);
        root = child;
    }
    return 0;
}

static int
stream_topk_generic_sort(
    StreamingTopKEntry *entries,
    PyObject *records,
    Py_ssize_t length,
    int largest,
    int heap_ready
)
{
    if (length < 2) {
        return 0;
    }
    if (!heap_ready) {
        for (Py_ssize_t parent = length / 2; parent > 0; parent--) {
            if (
                stream_topk_generic_sift_down(
                    entries,
                    records,
                    length,
                    parent - 1,
                    largest
                ) < 0
            ) {
                return -1;
            }
        }
    }
    for (Py_ssize_t end = length - 1; end > 0; end--) {
        stream_topk_swap(entries, records, 0, end);
        if (
            stream_topk_generic_sift_down(
                entries,
                records,
                end,
                0,
                largest
            ) < 0
        ) {
            return -1;
        }
    }
    return 0;
}

static PyObject *
stream_topk_finish(
    PyObject *result,
    Py_ssize_t processed,
    int exact_int64,
    int diagnostic,
    Py_ssize_t k
)
{
    if (!diagnostic || result == NULL) {
        return result;
    }
    PyObject *processed_object = PyLong_FromSsize_t(processed);
    PyObject *exact_object = PyBool_FromLong(exact_int64);
    const size_t bytes_per_item = exact_int64
        ? sizeof(StreamingTopKEntry)
        : sizeof(StreamingTopKEntry) + sizeof(PyObject *);
    PyObject *estimated_object = NULL;
    if ((size_t)k <= SIZE_MAX / bytes_per_item) {
        estimated_object = PyLong_FromSize_t(
            (size_t)k * bytes_per_item
        );
    } else {
        PyErr_NoMemory();
    }
    if (
        processed_object == NULL
        || exact_object == NULL
        || estimated_object == NULL
    ) {
        Py_XDECREF(processed_object);
        Py_XDECREF(exact_object);
        Py_XDECREF(estimated_object);
        Py_DECREF(result);
        return NULL;
    }
    PyObject *output = PyTuple_New(4);
    if (output == NULL) {
        Py_DECREF(processed_object);
        Py_DECREF(exact_object);
        Py_DECREF(estimated_object);
        Py_DECREF(result);
        return NULL;
    }
    PyTuple_SET_ITEM(output, 0, result);
    PyTuple_SET_ITEM(output, 1, processed_object);
    PyTuple_SET_ITEM(output, 2, exact_object);
    PyTuple_SET_ITEM(output, 3, estimated_object);
    return output;
}

static PyObject *
stream_topk_impl(
    PyObject *iterable,
    Py_ssize_t k,
    PyObject *key_function,
    int largest,
    int diagnostic
)
{
    if (k < 0) {
        PyErr_SetString(PyExc_ValueError, "k must be non-negative");
        return NULL;
    }
    if (k == 0) {
        return stream_topk_finish(
            PyList_New(0),
            0,
            1,
            diagnostic,
            0
        );
    }
    const int natural_order = key_function == Py_None;
    if (!natural_order && !PyCallable_Check(key_function)) {
        PyErr_SetString(PyExc_TypeError, "key must be callable or None");
        return NULL;
    }
    if ((size_t)k > SIZE_MAX / sizeof(StreamingTopKEntry)) {
        return PyErr_NoMemory();
    }
    StreamingTopKEntry *heap = PyMem_Malloc(
        (size_t)k * sizeof(*heap)
    );
    if (heap == NULL) {
        return PyErr_NoMemory();
    }
    PyObject *records = PyList_New(0);
    if (records == NULL) {
        PyMem_Free(heap);
        return NULL;
    }
    PyObject *iterator = PyObject_GetIter(iterable);
    if (iterator == NULL) {
        Py_DECREF(records);
        PyMem_Free(heap);
        return NULL;
    }

    int exact_int64 = 1;
    Py_ssize_t retained = 0;
    Py_ssize_t processed = 0;
    PyObject *record;
    while ((record = PyIter_Next(iterator)) != NULL) {
        if (processed == PY_SSIZE_T_MAX) {
            Py_DECREF(record);
            PyErr_SetString(
                PyExc_OverflowError,
                "stream contains more records than Py_ssize_t can count"
            );
            goto error;
        }
        PyObject *key_object;
        if (natural_order) {
            key_object = record;
        } else {
            key_object = PyObject_CallOneArg(key_function, record);
            if (key_object == NULL) {
                Py_DECREF(record);
                goto error;
            }
        }

        uint64_t normalized_key = 0;
        if (exact_int64) {
            const int normalization = stream_topk_try_normalize(
                key_object,
                largest,
                &normalized_key
            );
            if (normalization < 0) {
                if (!natural_order) {
                    Py_DECREF(key_object);
                }
                Py_DECREF(record);
                goto error;
            }
            if (normalization == 0) {
                if (
                    stream_topk_promote_generic_keys(
                        heap,
                        retained,
                        largest
                    ) < 0
                ) {
                    if (!natural_order) {
                        Py_DECREF(key_object);
                    }
                    Py_DECREF(record);
                    goto error;
                }
                exact_int64 = 0;
                if (natural_order) {
                    Py_INCREF(key_object);
                }
            } else if (!natural_order) {
                Py_DECREF(key_object);
            }
        } else if (natural_order) {
            Py_INCREF(key_object);
        }

        StreamingTopKEntry candidate;
        if (exact_int64) {
            candidate.key.normalized = normalized_key;
        } else {
            candidate.key.object = key_object;
        }
        candidate.encounter_index = (uint64_t)processed;
        processed++;
        if (retained < k) {
            heap[retained] = candidate;
            if (PyList_Append(records, record) < 0) {
                if (!exact_int64) {
                    Py_DECREF(candidate.key.object);
                }
                Py_DECREF(record);
                goto error;
            }
            Py_DECREF(record);
            retained++;
            if (retained == k) {
                for (Py_ssize_t parent = k / 2; parent > 0; parent--) {
                    if (exact_int64) {
                        stream_topk_exact_sift_down(
                            heap,
                            records,
                            k,
                            parent - 1
                        );
                    } else if (
                        stream_topk_generic_sift_down(
                            heap,
                            records,
                            k,
                            parent - 1,
                            largest
                        ) < 0
                    ) {
                        goto error;
                    }
                }
            }
            continue;
        }

        int candidate_is_better;
        if (exact_int64) {
            candidate_is_better = stream_topk_exact_is_better(
                candidate,
                heap[0]
            );
        } else {
            /*
             * A later equal-key record can never displace an earlier one.
             * The hot rejection path therefore needs only the strict
             * comparison that proves the candidate is better.  Heap repair
             * and final stable ordering still use the bidirectional helper
             * where distinguishing equality is necessary.
             */
            if (largest) {
                candidate_is_better = PyObject_RichCompareBool(
                    heap[0].key.object,
                    candidate.key.object,
                    Py_LT
                );
            } else {
                candidate_is_better = PyObject_RichCompareBool(
                    candidate.key.object,
                    heap[0].key.object,
                    Py_LT
                );
            }
            if (candidate_is_better < 0) {
                Py_DECREF(candidate.key.object);
                Py_DECREF(record);
                goto error;
            }
        }
        if (!candidate_is_better) {
            if (!exact_int64) {
                Py_DECREF(candidate.key.object);
            }
            Py_DECREF(record);
            continue;
        }

        StreamingTopKEntry replaced = heap[0];
        PyObject *replaced_record = PyList_GET_ITEM(records, 0);
        heap[0] = candidate;
        PyList_SET_ITEM(records, 0, record);
        if (exact_int64) {
            stream_topk_exact_sift_down(heap, records, k, 0);
        } else if (
            stream_topk_generic_sift_down(
                heap,
                records,
                k,
                0,
                largest
            ) < 0
        ) {
            Py_DECREF(replaced.key.object);
            Py_DECREF(replaced_record);
            goto error;
        }
        if (!exact_int64) {
            Py_DECREF(replaced.key.object);
        }
        Py_DECREF(replaced_record);
    }
    if (PyErr_Occurred()) {
        goto error;
    }
    Py_DECREF(iterator);
    iterator = NULL;

    if (exact_int64) {
        if (retained < k) {
            for (
                Py_ssize_t parent = retained / 2;
                parent > 0;
                parent--
            ) {
                stream_topk_exact_sift_down(
                    heap,
                    records,
                    retained,
                    parent - 1
                );
            }
        }
        stream_topk_exact_sort(heap, records, retained);
    } else if (
        stream_topk_generic_sort(
            heap,
            records,
            retained,
            largest,
            retained == k
        ) < 0
    ) {
        goto error;
    }

    if (!exact_int64) {
        stream_topk_clear_generic_keys(heap, retained);
    }
    PyMem_Free(heap);
    return stream_topk_finish(
        records,
        processed,
        exact_int64,
        diagnostic,
        k
    );

error:
    Py_XDECREF(iterator);
    if (!exact_int64) {
        stream_topk_clear_generic_keys(heap, retained);
    }
    Py_DECREF(records);
    PyMem_Free(heap);
    return NULL;
}

static int
parse_stream_topk_arguments(
    PyObject *args,
    const char *function_name,
    PyObject **iterable,
    Py_ssize_t *k,
    PyObject **key_function,
    int *largest
)
{
    char format[96];
    PyOS_snprintf(format, sizeof(format), "OnO|p:%s", function_name);
    return PyArg_ParseTuple(
        args,
        format,
        iterable,
        k,
        key_function,
        largest
    );
}

PyObject *
bielsort_py_stream_topk_prototype(
    PyObject *Py_UNUSED(module),
    PyObject *args
)
{
    PyObject *iterable;
    PyObject *key_function;
    Py_ssize_t k;
    int largest = 0;
    if (
        !parse_stream_topk_arguments(
            args,
            "_stream_topk_prototype",
            &iterable,
            &k,
            &key_function,
            &largest
        )
    ) {
        return NULL;
    }
    return stream_topk_impl(
        iterable,
        k,
        key_function,
        largest,
        0
    );
}

PyObject *
bielsort_py_stream_topk_prototype_with_info(
    PyObject *Py_UNUSED(module),
    PyObject *args
)
{
    PyObject *iterable;
    PyObject *key_function;
    Py_ssize_t k;
    int largest = 0;
    if (
        !parse_stream_topk_arguments(
            args,
            "_stream_topk_prototype_with_info",
            &iterable,
            &k,
            &key_function,
            &largest
        )
    ) {
        return NULL;
    }
    return stream_topk_impl(
        iterable,
        k,
        key_function,
        largest,
        1
    );
}

PyObject *
bielsort_py_stream_topk_worst_auxiliary_bytes(
    PyObject *Py_UNUSED(module),
    PyObject *argument
)
{
    const Py_ssize_t k = PyLong_AsSsize_t(argument);
    if (k == -1 && PyErr_Occurred()) {
        return NULL;
    }
    if (k < 0) {
        PyErr_SetString(PyExc_ValueError, "k must be non-negative");
        return NULL;
    }
    const size_t bytes_per_item = (
        sizeof(StreamingTopKEntry) + sizeof(PyObject *)
    );
    if ((size_t)k > SIZE_MAX / bytes_per_item) {
        return PyErr_NoMemory();
    }
    const size_t worst_case = (size_t)k * bytes_per_item;
    return PyLong_FromSize_t(worst_case);
}
