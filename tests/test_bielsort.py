import random
import struct
import unittest
from dataclasses import FrozenInstanceError
from importlib.metadata import version

from bielsort import (
    SortInfo,
    __version__,
    biel_sort,
    biel_sort_diagnostico,
    biel_sort_in_place,
    biel_sort_in_place_diagnostico,
    sort,
    sort_in_place,
    sort_in_place_with_strategy,
    sort_with_info,
    sort_with_strategy,
)
import bielsort_native


class InteiroComNome(int):
    pass


class BielSortTests(unittest.TestCase):
    """Correctness and API-compatibility tests for both sorting modes."""

    def test_package_version_matches_metadata(self):
        self.assertEqual(__version__, version("bielsort"))

    def test_legacy_import_remains_compatible(self):
        self.assertIs(bielsort_native.biel_sort, biel_sort)
        self.assertIs(bielsort_native.SortInfo, SortInfo)
        self.assertIs(bielsort_native.sort_with_info, sort_with_info)

    def test_canonical_api_and_compatibility_aliases(self):
        self.assertIs(sort, biel_sort)
        self.assertIs(sort_with_strategy, biel_sort_diagnostico)
        self.assertIs(sort_in_place, biel_sort_in_place)
        self.assertIs(
            sort_in_place_with_strategy,
            biel_sort_in_place_diagnostico,
        )
        self.assertEqual(sort((3, 1, 2)), [1, 2, 3])

        values = [3, 1, 2]
        self.assertIsNone(sort_in_place(values))
        self.assertEqual(values, [1, 2, 3])

    def conferir(self, valores):
        original = list(valores)
        resultado = biel_sort(valores)
        self.assertEqual(resultado, sorted(original))
        self.assertEqual(list(valores), original)
        self.assertIsNot(resultado, valores)

    def conferir_in_place(self, valores):
        esperado = sorted(valores)
        identidade = id(valores)
        retorno = biel_sort_in_place(valores)
        self.assertIsNone(retorno)
        self.assertEqual(id(valores), identidade)
        self.assertEqual(valores, esperado)

    def test_casos_basicos(self):
        casos = [
            [],
            [1],
            [2, 1],
            [3, -1, 3, 0, -10, 8, -1],
            [5] * 10_000,
            list(range(10_000)),
            list(range(10_000, -1, -1)),
        ]
        for caso in casos:
            with self.subTest(tamanho=len(caso)):
                self.conferir(caso)

    def test_limites_de_int64(self):
        minimo = -(1 << 63)
        maximo = (1 << 63) - 1
        rng = random.Random(2026)
        valores = [
            minimo,
            maximo,
            0,
            -1,
            1,
            *[rng.randint(minimo, maximo) for _ in range(100_000)],
        ]
        self.conferir(valores)
        self.conferir_in_place(valores.copy())

    def test_distribuicoes_aleatorias(self):
        rng = random.Random(2027)
        for tamanho in (2_048, 10_000, 100_000):
            casos = [
                [rng.randint(-100, 100) for _ in range(tamanho)],
                [rng.randint(-(1 << 31), (1 << 31) - 1) for _ in range(tamanho)],
                [rng.randint(-(1 << 63), (1 << 63) - 1) for _ in range(tamanho)],
            ]
            for caso in casos:
                with self.subTest(tamanho=tamanho):
                    self.conferir(caso)

    def test_estabilidade_para_inteiros_iguais(self):
        valores = []
        grupos_originais = {}
        for indice in range(10_000):
            valor = int(str(10_000 + indice % 7))
            valores.append(valor)
            grupos_originais.setdefault(valor, []).append(id(valor))

        resultado = biel_sort(valores)
        grupos_resultado = {}
        for valor in resultado:
            grupos_resultado.setdefault(valor, []).append(id(valor))

        self.assertEqual(grupos_resultado, grupos_originais)

        copia = valores.copy()
        self.conferir_in_place(copia)
        grupos_in_place = {}
        for valor in copia:
            grupos_in_place.setdefault(valor, []).append(id(valor))
        self.assertEqual(grupos_in_place, grupos_originais)

    def test_fallback_para_inteiros_gigantes(self):
        rng = random.Random(2028)
        valores = [
            rng.getrandbits(2048) * rng.choice((-1, 1))
            for _ in range(10_000)
        ]
        resultado, estrategia = biel_sort_diagnostico(valores)
        self.assertEqual(resultado, sorted(valores))
        self.assertTrue(estrategia.startswith("timsort:"))

    def test_fallback_preserva_objetos_e_estabilidade(self):
        valores = [
            InteiroComNome(3),
            InteiroComNome(1),
            InteiroComNome(3),
            InteiroComNome(1),
        ] * 1_000
        resultado, estrategia = biel_sort_diagnostico(valores)
        self.assertEqual(resultado, sorted(valores))
        self.assertTrue(estrategia.startswith("timsort:"))

        esperado_ids = {}
        resultado_ids = {}
        for valor in valores:
            esperado_ids.setdefault(int(valor), []).append(id(valor))
        for valor in resultado:
            resultado_ids.setdefault(int(valor), []).append(id(valor))
        self.assertEqual(resultado_ids, esperado_ids)

    def test_iteraveis_que_nao_sao_listas(self):
        self.assertEqual(biel_sort((3, 1, 2)), [1, 2, 3])
        self.assertEqual(biel_sort(x for x in (3, 1, 2)), [1, 2, 3])
        with self.assertRaises(TypeError):
            biel_sort_in_place((3, 1, 2))

    def test_key_e_reverse_compativeis_com_sorted(self):
        valores = ["bbb", "a", "cc", "dddd"]
        self.assertEqual(
            biel_sort(valores, key=len),
            sorted(valores, key=len),
        )
        self.assertEqual(
            biel_sort(valores, key=len, reverse=True),
            sorted(valores, key=len, reverse=True),
        )
        self.assertEqual(
            biel_sort([3, 1, 3, 2], reverse=True),
            sorted([3, 1, 3, 2], reverse=True),
        )
        copia = valores.copy()
        self.assertIsNone(biel_sort_in_place(copia, key=len, reverse=True))
        self.assertEqual(copia, sorted(valores, key=len, reverse=True))

    def test_key_int64_publica_seleciona_counting_estavel(self):
        rng = random.Random(2030)
        valores = [
            {"key": indice % 128, "position": indice}
            for indice in range(10_000)
        ]
        rng.shuffle(valores)
        original = valores.copy()
        esperado = sorted(valores, key=lambda registro: registro["key"])
        chamadas = []

        def key(registro):
            chamadas.append(registro["position"])
            return registro["key"]

        resultado, estrategia = sort_with_strategy(valores, key=key)

        self.assertEqual(resultado, esperado)
        self.assertEqual(valores, original)
        self.assertEqual(
            chamadas,
            [registro["position"] for registro in valores],
        )
        self.assertEqual(estrategia, "counting nativo estável por key")
        for chave in range(128):
            self.assertEqual(
                [
                    registro["position"]
                    for registro in resultado
                    if registro["key"] == chave
                ],
                [
                    registro["position"]
                    for registro in valores
                    if registro["key"] == chave
                ],
            )

    def test_key_int64_publica_reverse_seleciona_counting_estavel(self):
        valores = [
            {"key": indice % 128, "position": indice}
            for indice in range(10_000)
        ]
        resultado, estrategia = sort_with_strategy(
            valores,
            key=lambda registro: registro["key"],
            reverse=True,
        )

        self.assertEqual(
            resultado,
            sorted(
                valores,
                key=lambda registro: registro["key"],
                reverse=True,
            ),
        )
        self.assertEqual(estrategia, "counting nativo estável por key")
        for chave in range(127, -1, -1):
            self.assertEqual(
                [
                    registro["position"]
                    for registro in resultado
                    if registro["key"] == chave
                ],
                [
                    registro["position"]
                    for registro in valores
                    if registro["key"] == chave
                ],
            )

    def test_sort_with_info_publico_descreve_counting_e_memoria(self):
        rng = random.Random(2032)
        valores = [
            {"key": indice % 128, "position": indice}
            for indice in range(10_000)
        ]
        rng.shuffle(valores)
        original = valores.copy()

        resultado, info = sort_with_info(
            valores,
            key=lambda registro: registro["key"],
        )

        self.assertEqual(
            resultado,
            sorted(valores, key=lambda registro: registro["key"]),
        )
        self.assertEqual(valores, original)
        self.assertIsInstance(info, SortInfo)
        self.assertEqual(info.algorithm, "counting")
        self.assertEqual(info.key_domain, "signed-int64")
        self.assertEqual(info.size, len(valores))
        self.assertEqual((info.key_min, info.key_max), (0, 127))
        self.assertEqual(info.key_span, 127)
        self.assertIsNone(info.radix_passes)
        self.assertFalse(info.reverse)
        self.assertTrue(info.used_native)
        self.assertGreater(info.estimated_native_auxiliary_bytes, 0)
        self.assertGreater(info.worst_case_native_auxiliary_bytes, 0)
        self.assertGreaterEqual(
            info.worst_case_native_auxiliary_bytes,
            info.estimated_native_auxiliary_bytes,
        )
        self.assertIsNone(info.max_native_auxiliary_bytes)
        self.assertFalse(info.native_memory_limit_exceeded)
        with self.assertRaises(FrozenInstanceError):
            info.size = 0

    def test_sort_info_publico_tem_superficie_compacta(self):
        self.assertEqual(
            tuple(SortInfo.__dataclass_fields__),
            (
                "algorithm",
                "reason",
                "size",
                "reverse",
                "key_domain",
                "key_min",
                "key_max",
                "key_span",
                "radix_passes",
                "estimated_native_auxiliary_bytes",
                "worst_case_native_auxiliary_bytes",
                "max_native_auxiliary_bytes",
                "native_memory_limit_exceeded",
            ),
        )

    def test_sort_with_info_limite_cobre_pior_counting_e_radix(self):
        rng = random.Random(2034)
        valores = [
            {"key": indice * 4, "position": indice}
            for indice in range(8_192)
        ]
        rng.shuffle(valores)

        resultado, info = sort_with_info(
            valores,
            key=lambda registro: registro["key"],
        )

        self.assertEqual(
            resultado,
            sorted(valores, key=lambda registro: registro["key"]),
        )
        self.assertEqual(info.algorithm, "counting")
        radix_bound = len(valores) * (2 * struct.calcsize("P") + 2 * 8)
        self.assertGreater(
            info.worst_case_native_auxiliary_bytes,
            radix_bound,
        )
        self.assertGreaterEqual(
            info.worst_case_native_auxiliary_bytes,
            info.estimated_native_auxiliary_bytes,
        )

        chamadas = []

        def key(registro):
            chamadas.append(registro["position"])
            return registro["key"]

        resultado_limitado, info_limitado = sort_with_info(
            valores,
            key=key,
            max_native_auxiliary_bytes=radix_bound,
        )

        self.assertEqual(resultado_limitado, resultado)
        self.assertEqual(
            chamadas,
            [registro["position"] for registro in valores],
        )
        self.assertEqual(info_limitado.algorithm, "timsort")
        self.assertTrue(info_limitado.native_memory_limit_exceeded)

    def test_sort_with_info_limite_de_memoria_decide_antes_da_key(self):
        valores = [
            {"key": indice % 128, "position": indice}
            for indice in range(10_000)
        ]
        chamadas = []

        def key(registro):
            chamadas.append(registro["position"])
            return registro["key"]

        resultado, info = sort_with_info(
            valores,
            key=key,
            reverse=1,
            max_native_auxiliary_bytes=0,
        )

        self.assertEqual(
            resultado,
            sorted(
                valores,
                key=lambda registro: registro["key"],
                reverse=True,
            ),
        )
        self.assertEqual(chamadas, list(range(len(valores))))
        self.assertEqual(info.algorithm, "timsort")
        self.assertEqual(info.key_domain, "python")
        self.assertFalse(info.used_native)
        self.assertTrue(info.reverse)
        self.assertEqual(info.max_native_auxiliary_bytes, 0)
        self.assertTrue(info.native_memory_limit_exceeded)
        self.assertIsNone(info.estimated_native_auxiliary_bytes)
        self.assertIn("memory limit exceeded", info.reason)

    def test_sort_with_info_normaliza_radix_publico(self):
        rng = random.Random(2033)
        valores = [
            {
                "key": rng.randint(-(1 << 63), (1 << 63) - 1),
                "position": indice,
            }
            for indice in range(10_000)
        ]

        resultado, info = sort_with_info(
            valores,
            key=lambda registro: registro["key"],
            reverse=True,
        )

        self.assertEqual(
            resultado,
            sorted(
                valores,
                key=lambda registro: registro["key"],
                reverse=True,
            ),
        )
        self.assertEqual(info.algorithm, "radix")
        self.assertEqual(info.key_domain, "signed-int64")
        self.assertTrue(info.used_native)
        self.assertTrue(info.reverse)
        self.assertGreaterEqual(info.radix_passes, 1)
        self.assertLessEqual(info.radix_passes, 6)

    def test_sort_with_info_normaliza_fallback_generico(self):
        valores = ["bbb", "a", "cc", "dddd"] * 1_000
        chamadas = []

        def key(valor):
            chamadas.append(valor)
            return f"{len(valor):02d}:{valor}"

        resultado, info = sort_with_info(valores, key=key)

        self.assertEqual(
            resultado,
            sorted(
                valores,
                key=lambda valor: f"{len(valor):02d}:{valor}",
            ),
        )
        self.assertEqual(chamadas, valores)
        self.assertEqual(info.algorithm, "timsort")
        self.assertEqual(info.key_domain, "python")
        self.assertFalse(info.used_native)
        self.assertIsNone(info.key_min)
        self.assertIsNone(info.radix_passes)
        self.assertFalse(info.native_memory_limit_exceeded)

    def test_sort_with_info_limite_raise_nao_executa_key(self):
        valores = [{"key": 2}, {"key": 1}]
        chamadas = []

        def key(registro):
            chamadas.append(registro)
            return registro["key"]

        with self.assertRaises(MemoryError):
            sort_with_info(
                valores,
                key=key,
                max_native_auxiliary_bytes=0,
                on_memory_limit="raise",
            )

        self.assertEqual(chamadas, [])
        self.assertEqual(valores, [{"key": 2}, {"key": 1}])

    def test_sort_with_info_valida_contrato_publico(self):
        with self.assertRaisesRegex(TypeError, "key must be callable"):
            sort_with_info([3, 1, 2], key=None)
        with self.assertRaisesRegex(ValueError, "on_memory_limit"):
            sort_with_info(
                [3, 1, 2],
                key=lambda valor: valor,
                on_memory_limit="ignorar",
            )
        with self.assertRaisesRegex(TypeError, "exact list or tuple"):
            sort_with_info(
                (valor for valor in [3, 1, 2]),
                key=lambda valor: valor,
                max_native_auxiliary_bytes=1_000,
            )

    def test_key_int64_in_place_preserva_timsort_e_contrato(self):
        rng = random.Random(2031)
        valores = [
            {"key": indice % 128, "position": indice}
            for indice in range(10_000)
        ]
        rng.shuffle(valores)
        esperado = sorted(
            valores,
            key=lambda registro: registro["key"],
            reverse=True,
        )
        ordem_original = [registro["position"] for registro in valores]
        tamanhos_observados = []
        chamadas = []
        identidade = id(valores)

        def key(registro):
            tamanhos_observados.append(len(valores))
            chamadas.append(registro["position"])
            return registro["key"]

        estrategia = sort_in_place_with_strategy(
            valores,
            key=key,
            reverse=True,
        )

        self.assertEqual(id(valores), identidade)
        self.assertEqual(valores, esperado)
        self.assertEqual(chamadas, ordem_original)
        self.assertEqual(tamanhos_observados, [0] * len(valores))
        self.assertEqual(estrategia, "timsort: key ou reverse")

    def test_key_generica_publica_usa_fallback_uma_vez(self):
        valores = ["bbb", "a", "cc", "dddd"] * 1_000
        chamadas = []

        def key(valor):
            chamadas.append(valor)
            return f"{len(valor):02d}:{valor}"

        resultado, estrategia = sort_with_strategy(
            valores,
            key=key,
            reverse=1,
        )

        self.assertEqual(
            resultado,
            sorted(
                valores,
                key=lambda valor: f"{len(valor):02d}:{valor}",
                reverse=True,
            ),
        )
        self.assertEqual(chamadas, valores)
        self.assertEqual(estrategia, "timsort: fallback compatível por key")

    def test_key_in_place_detecta_mutacao_como_list_sort(self):
        valores = [3, 1, 2]
        tamanhos_observados = []

        def key(valor):
            tamanhos_observados.append(len(valores))
            if valor == 3:
                valores.append(99)
            return valor

        with self.assertRaisesRegex(ValueError, "list modified during sort"):
            sort_in_place(valores, key=key)

        self.assertEqual(valores, [1, 2, 3])
        self.assertEqual(tamanhos_observados, [0, 1, 1])

    def test_key_in_place_restaura_lista_apos_excecao(self):
        valores = [3, 1, 2]
        original = valores.copy()

        def key(valor):
            if valor == 1:
                raise RuntimeError("falha da key pública")
            return valor

        with self.assertRaisesRegex(RuntimeError, "falha da key pública"):
            sort_in_place(valores, key=key)

        self.assertEqual(valores, original)

    def test_diagnostico_in_place(self):
        rng = random.Random(2029)
        valores = [
            rng.randint(-(1 << 63), (1 << 63) - 1)
            for _ in range(100_000)
        ]
        estrategia = biel_sort_in_place_diagnostico(valores)
        self.assertEqual(valores, sorted(valores))
        self.assertIn("radix nativo", estrategia)

    def test_ordem_decrescente_usa_fallback_adaptativo(self):
        valores = list(range(100_000, 0, -1))
        resultado, estrategia = biel_sort_diagnostico(valores)
        self.assertEqual(resultado, sorted(valores))
        self.assertIn("monotônica", estrategia)


if __name__ == "__main__":
    unittest.main(verbosity=2)
