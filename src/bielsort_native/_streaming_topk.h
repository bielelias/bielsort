#ifndef BIELSORT_STREAMING_TOPK_H
#define BIELSORT_STREAMING_TOPK_H

#include <Python.h>

PyObject *bielsort_py_stream_topk_prototype(
    PyObject *module,
    PyObject *args
);

PyObject *bielsort_py_stream_topk_prototype_with_info(
    PyObject *module,
    PyObject *args
);

PyObject *bielsort_py_stream_topk_worst_auxiliary_bytes(
    PyObject *module,
    PyObject *argument
);

#endif
