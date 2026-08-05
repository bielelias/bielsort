#ifndef BIELSORT_ARGSORT_H
#define BIELSORT_ARGSORT_H

#include <Python.h>

int bielsort_argsort_add_type(PyObject *module);

PyObject *bielsort_py_argsort_int64_prototype(
    PyObject *module,
    PyObject *args
);

PyObject *bielsort_py_argsort_int64_prototype_with_strategy(
    PyObject *module,
    PyObject *args
);

PyObject *bielsort_py_topk_int64_prototype(
    PyObject *module,
    PyObject *args
);

PyObject *bielsort_py_topk_int64_prototype_with_strategy(
    PyObject *module,
    PyObject *args
);

#endif
