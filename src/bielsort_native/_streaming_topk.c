#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "_streaming_topk.h"

typedef struct {
    uint64_t normalized_key;
    uint64_t encounter_index;
    PyObject *key_object;
    PyObject *record_object;
} StreamingTopKEntry;

static void
stream_topk_clear_entry(StreamingTopKEntry *entry)
{
    Py_XDECREF(entry->key_object);
    Py_XDECREF(entry->record_object);
    entry->key_object = NULL;
    entry->record_object = NULL;
}

static void
stream_topk_clear_entries(StreamingTopKEntry *entries, Py_ssize_t length)
{
    if (entries == NULL) {
        return;
    }
    for (Py_ssize_t position = 0; position < length; position++) {
        stream_topk_clear_entry(&entries[position]);
    }
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

static int
stream_topk_exact_is_better(
    StreamingTopKEntry left,
    StreamingTopKEntry right
)
{
    return left.normalized_key < right.normalized_key
        || (
            left.normalized_key == right.normalized_key
            && left.encounter_index < right.encounter_index
        );
}

static int
stream_topk_exact_is_worse(
    StreamingTopKEntry left,
    StreamingTopKEntry right
)
{
    return left.normalized_key > right.normalized_key
        || (
            left.normalized_key == right.normalized_key
            && left.encounter_index > right.encounter_index
        );
}

static void
stream_topk_exact_sift_down(
    StreamingTopKEntry *heap,
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
        const StreamingTopKEntry swap = heap[root];
        heap[root] = heap[child];
        heap[child] = swap;
        root = child;
    }
}

static int
stream_topk_exact_compare_best_first(
    const void *left_pointer,
    const void *right_pointer
)
{
    const StreamingTopKEntry left = (
        *(const StreamingTopKEntry *)left_pointer
    );
    const StreamingTopKEntry right = (
        *(const StreamingTopKEntry *)right_pointer
    );
    if (stream_topk_exact_is_better(left, right)) {
        return -1;
    }
    if (stream_topk_exact_is_better(right, left)) {
        return 1;
    }
    return 0;
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
            right->key_object,
            left->key_object,
            Py_LT
        );
    } else {
        left_is_better = PyObject_RichCompareBool(
            left->key_object,
            right->key_object,
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
            left->key_object,
            right->key_object,
            Py_LT
        );
    } else {
        right_is_better = PyObject_RichCompareBool(
            right->key_object,
            left->key_object,
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
        const StreamingTopKEntry swap = heap[root];
        heap[root] = heap[child];
        heap[child] = swap;
        root = child;
    }
    return 0;
}

static int
stream_topk_generic_merge_range(
    StreamingTopKEntry *entries,
    StreamingTopKEntry *temporary,
    Py_ssize_t left,
    Py_ssize_t right,
    int largest
)
{
    if (right - left < 2) {
        return 0;
    }
    const Py_ssize_t middle = left + (right - left) / 2;
    if (
        stream_topk_generic_merge_range(
            entries,
            temporary,
            left,
            middle,
            largest
        ) < 0
        || stream_topk_generic_merge_range(
            entries,
            temporary,
            middle,
            right,
            largest
        ) < 0
    ) {
        return -1;
    }

    memcpy(
        &temporary[left],
        &entries[left],
        (size_t)(right - left) * sizeof(*entries)
    );
    Py_ssize_t first = left;
    Py_ssize_t second = middle;
    Py_ssize_t output = left;
    while (first < middle && second < right) {
        int comparison;
        if (
            stream_topk_generic_compare_best(
                &temporary[first],
                &temporary[second],
                largest,
                &comparison
            ) < 0
        ) {
            memcpy(
                &entries[left],
                &temporary[left],
                (size_t)(right - left) * sizeof(*entries)
            );
            return -1;
        }
        if (comparison <= 0) {
            entries[output++] = temporary[first++];
        } else {
            entries[output++] = temporary[second++];
        }
    }
    while (first < middle) {
        entries[output++] = temporary[first++];
    }
    while (second < right) {
        entries[output++] = temporary[second++];
    }
    return 0;
}

static int
stream_topk_generic_sort(
    StreamingTopKEntry *entries,
    Py_ssize_t length,
    int largest
)
{
    if (length < 2) {
        return 0;
    }
    if ((size_t)length > SIZE_MAX / sizeof(*entries)) {
        return PyErr_NoMemory(), -1;
    }
    StreamingTopKEntry *temporary = PyMem_Malloc(
        (size_t)length * sizeof(*temporary)
    );
    if (temporary == NULL) {
        return PyErr_NoMemory(), -1;
    }
    const int result = stream_topk_generic_merge_range(
        entries,
        temporary,
        0,
        length,
        largest
    );
    PyMem_Free(temporary);
    return result;
}

static PyObject *
stream_topk_finish(
    PyObject *result,
    Py_ssize_t processed,
    int exact_int64,
    int diagnostic
)
{
    if (!diagnostic || result == NULL) {
        return result;
    }
    PyObject *processed_object = PyLong_FromSsize_t(processed);
    PyObject *exact_object = PyBool_FromLong(exact_int64);
    if (processed_object == NULL || exact_object == NULL) {
        Py_XDECREF(processed_object);
        Py_XDECREF(exact_object);
        Py_DECREF(result);
        return NULL;
    }
    PyObject *output = PyTuple_New(3);
    if (output == NULL) {
        Py_DECREF(processed_object);
        Py_DECREF(exact_object);
        Py_DECREF(result);
        return NULL;
    }
    PyTuple_SET_ITEM(output, 0, result);
    PyTuple_SET_ITEM(output, 1, processed_object);
    PyTuple_SET_ITEM(output, 2, exact_object);
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
        return stream_topk_finish(PyList_New(0), 0, 1, diagnostic);
    }
    const int natural_order = key_function == Py_None;
    if (!natural_order && !PyCallable_Check(key_function)) {
        PyErr_SetString(PyExc_TypeError, "key must be callable or None");
        return NULL;
    }
    if ((size_t)k > SIZE_MAX / sizeof(StreamingTopKEntry)) {
        return PyErr_NoMemory();
    }
    StreamingTopKEntry *heap = PyMem_Calloc(
        (size_t)k,
        sizeof(*heap)
    );
    if (heap == NULL) {
        return PyErr_NoMemory();
    }
    PyObject *iterator = PyObject_GetIter(iterable);
    if (iterator == NULL) {
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
            Py_INCREF(key_object);
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
                Py_DECREF(key_object);
                Py_DECREF(record);
                goto error;
            }
            if (normalization == 0) {
                exact_int64 = 0;
            }
        }

        const StreamingTopKEntry candidate = {
            normalized_key,
            (uint64_t)processed,
            key_object,
            record,
        };
        processed++;
        if (retained < k) {
            heap[retained++] = candidate;
            if (retained == k) {
                for (Py_ssize_t parent = k / 2; parent > 0; parent--) {
                    if (exact_int64) {
                        stream_topk_exact_sift_down(
                            heap,
                            k,
                            parent - 1
                        );
                    } else if (
                        stream_topk_generic_sift_down(
                            heap,
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
                    heap[0].key_object,
                    candidate.key_object,
                    Py_LT
                );
            } else {
                candidate_is_better = PyObject_RichCompareBool(
                    candidate.key_object,
                    heap[0].key_object,
                    Py_LT
                );
            }
            if (candidate_is_better < 0) {
                StreamingTopKEntry owned_candidate = candidate;
                stream_topk_clear_entry(&owned_candidate);
                goto error;
            }
        }
        if (!candidate_is_better) {
            StreamingTopKEntry rejected = candidate;
            stream_topk_clear_entry(&rejected);
            continue;
        }

        StreamingTopKEntry replaced = heap[0];
        heap[0] = candidate;
        if (exact_int64) {
            stream_topk_exact_sift_down(heap, k, 0);
        } else if (
            stream_topk_generic_sift_down(heap, k, 0, largest) < 0
        ) {
            stream_topk_clear_entry(&replaced);
            goto error;
        }
        stream_topk_clear_entry(&replaced);
    }
    if (PyErr_Occurred()) {
        goto error;
    }
    Py_DECREF(iterator);
    iterator = NULL;

    if (exact_int64) {
        qsort(
            heap,
            (size_t)retained,
            sizeof(*heap),
            stream_topk_exact_compare_best_first
        );
    } else if (stream_topk_generic_sort(heap, retained, largest) < 0) {
        goto error;
    }

    PyObject *result = PyList_New(retained);
    if (result == NULL) {
        goto error;
    }
    for (Py_ssize_t position = 0; position < retained; position++) {
        PyObject *selected_record = heap[position].record_object;
        Py_INCREF(selected_record);
        PyList_SET_ITEM(result, position, selected_record);
    }
    stream_topk_clear_entries(heap, retained);
    PyMem_Free(heap);
    return stream_topk_finish(
        result,
        processed,
        exact_int64,
        diagnostic
    );

error:
    Py_XDECREF(iterator);
    stream_topk_clear_entries(heap, retained);
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
    if (
        (size_t)k > SIZE_MAX / sizeof(StreamingTopKEntry)
        || (size_t)k * sizeof(StreamingTopKEntry) > SIZE_MAX / 2
    ) {
        return PyErr_NoMemory();
    }
    const size_t worst_case = (
        (size_t)k * sizeof(StreamingTopKEntry) * 2
    );
    return PyLong_FromSize_t(worst_case);
}
