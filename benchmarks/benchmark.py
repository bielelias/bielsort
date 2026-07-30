import argparse
import gc
import random
import statistics
import time

from bielsort import (
    biel_sort,
    biel_sort_diagnostico,
    biel_sort_in_place,
    biel_sort_in_place_diagnostico,
)


def medir(funcao, dados, esperado, repeticoes):
    tempos = []
    for _ in range(repeticoes):
        entrada = dados.copy()
        gc.collect()
        gc.disable()
        inicio = time.perf_counter()
        resultado = funcao(entrada)
        duracao = time.perf_counter() - inicio
        gc.enable()
        if resultado != esperado:
            raise AssertionError("Resultado incorreto")
        tempos.append(duracao)
    return statistics.median(tempos)


def medir_in_place(funcao, dados, esperado, repeticoes):
    tempos = []
    for _ in range(repeticoes):
        entrada = dados.copy()
        gc.collect()
        gc.disable()
        inicio = time.perf_counter()
        retorno = funcao(entrada)
        duracao = time.perf_counter() - inicio
        gc.enable()
        if retorno is not None:
            raise AssertionError("Ordenação in-place deve retornar None")
        if entrada != esperado:
            raise AssertionError("Resultado incorreto")
        tempos.append(duracao)
    return statistics.median(tempos)


def criar_casos(n, semente):
    rng = random.Random(semente)

    quase_ordenado = list(range(n))
    for _ in range(max(1, n // 500)):
        a = rng.randrange(n)
        b = rng.randrange(n)
        quase_ordenado[a], quase_ordenado[b] = (
            quase_ordenado[b],
            quase_ordenado[a],
        )

    return {
        "denso": [rng.randint(-n // 4, n // 4) for _ in range(n)],
        "int32": [rng.randint(-(1 << 31), (1 << 31) - 1) for _ in range(n)],
        "int64": [rng.randint(-(1 << 63), (1 << 63) - 1) for _ in range(n)],
        "1024 bits": [
            rng.getrandbits(1024) * rng.choice((-1, 1))
            for _ in range(n)
        ],
        "quase ordenado": quase_ordenado,
        "decrescente": list(range(n, 0, -1)),
    }


def executar(tamanhos, repeticoes):
    """Run reproducible comparisons against sorted() and list.sort()."""
    resultados = []
    print(
        f"{'n':>10}  {'caso':<16}  {'estratégia':<39}"
        f"  {'sorted':>9}  {'Biel-new':>9}  {'ganho':>7}"
        f"  {'.sort':>9}  {'Biel-ip':>9}  {'ganho':>7}"
    )
    print("-" * 139)

    for n in tamanhos:
        for nome, dados in criar_casos(n, 2026 + n).items():
            esperado = sorted(dados)
            _, estrategia = biel_sort_diagnostico(dados)
            tempo_sorted = medir(sorted, dados, esperado, repeticoes)
            tempo_biel = medir(biel_sort, dados, esperado, repeticoes)
            copia_diagnostico = dados.copy()
            estrategia_in_place = biel_sort_in_place_diagnostico(
                copia_diagnostico
            )
            if estrategia_in_place != estrategia:
                raise AssertionError("Estratégias divergentes")
            tempo_list_sort = medir_in_place(
                list.sort,
                dados,
                esperado,
                repeticoes,
            )
            tempo_biel_in_place = medir_in_place(
                biel_sort_in_place,
                dados,
                esperado,
                repeticoes,
            )
            ganho_nova_lista = tempo_sorted / tempo_biel
            ganho_in_place = tempo_list_sort / tempo_biel_in_place
            resultados.append(
                {
                    "n": n,
                    "caso": nome,
                    "estrategia": estrategia,
                    "sorted_s": tempo_sorted,
                    "bielsort_s": tempo_biel,
                    "ganho": ganho_nova_lista,
                    "list_sort_s": tempo_list_sort,
                    "bielsort_in_place_s": tempo_biel_in_place,
                    "ganho_in_place": ganho_in_place,
                }
            )
            print(
                f"{n:>10,}  {nome:<16}  {estrategia:<39}"
                f"  {tempo_sorted:>8.5f}  {tempo_biel:>8.5f}"
                f"  {ganho_nova_lista:>6.2f}x"
                f"  {tempo_list_sort:>8.5f}  {tempo_biel_in_place:>8.5f}"
                f"  {ganho_in_place:>6.2f}x"
            )
    return resultados


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-n",
        "--tamanhos",
        nargs="+",
        type=int,
        default=[10_000, 100_000, 1_000_000],
    )
    parser.add_argument("-r", "--repeticoes", type=int, default=5)
    argumentos = parser.parse_args()
    executar(argumentos.tamanhos, argumentos.repeticoes)


if __name__ == "__main__":
    main()
