# Guia em português

O BielSort é uma biblioteca de ordenação estável e adaptativa para CPython. Ela
tenta acelerar listas grandes de inteiros com implementações nativas em C e
usa o Timsort do próprio Python quando ele é mais adequado.

<div class="biel-grid" markdown>

<div class="biel-card" markdown>
### Fácil de instalar

Está disponível no PyPI e não possui dependências obrigatórias em tempo de
execução.
</div>

<div class="biel-card" markdown>
### Compatível com Python

Mantém ordenação estável e aceita `key=` e `reverse=` por meio do fallback para
Timsort.
</div>

<div class="biel-card" markdown>
### Especializado

O caminho acelerado foi desenvolvido para listas grandes de inteiros exatos no
intervalo de 64 bits com sinal.
</div>

</div>

## Instalação

Para uma utilização normal:

```bash
python -m pip install bielsort
```

Para instalar exatamente a versão estável atual:

```bash
python -m pip install bielsort==0.1.0
```

Verifique a instalação:

```bash
python -c "import bielsort; print(bielsort.__version__)"
```

## Primeiro exemplo

```python
import bielsort

numeros = [8, -4, 10, 3, -4]
ordenados = bielsort.sort(numeros)

print(ordenados)  # [-4, -4, 3, 8, 10]
print(numeros)    # a lista original continua igual
```

Usar `import bielsort` deixa o código visualmente diferente das operações
nativas do Python:

```python
sorted(numeros)                 # cria uma lista usando o Python
numeros.sort()                  # modifica a lista usando o Python
bielsort.sort(numeros)          # cria uma lista usando o BielSort
bielsort.sort_in_place(numeros) # modifica a lista usando o BielSort
```

## As quatro funções principais

| Função | Modifica a entrada? | Retorno |
|---|---:|---|
| `bielsort.sort()` | não | nova lista ordenada |
| `bielsort.sort_in_place()` | sim | `None` |
| `bielsort.sort_with_strategy()` | não | lista e estratégia |
| `bielsort.sort_in_place_with_strategy()` | sim | estratégia |

### Ordenação in-place

```python
import bielsort

numeros = [3, 1, 2]
retorno = bielsort.sort_in_place(numeros)

print(numeros)  # [1, 2, 3]
print(retorno)  # None
```

### Descobrir a estratégia

```python
import random
import bielsort

rng = random.Random(42)
numeros = [rng.randint(-(1 << 31), (1 << 31) - 1) for _ in range(100_000)]

ordenados, estrategia = bielsort.sort_with_strategy(numeros)
print(estrategia)
```

O texto da estratégia serve para diagnóstico e benchmarks. Não use uma frase
exata como condição necessária para a lógica do seu programa, pois essa frase
pode evoluir antes da versão 1.0.

## Como o algoritmo é escolhido

<div class="biel-flow" markdown>

<div class="biel-flow-step" data-step="Counting Sort" markdown>
### Intervalo denso

Pode ser usado em listas muito grandes quando os valores ocupam um intervalo
numérico relativamente compacto.
</div>

<div class="biel-flow-step" data-step="Radix Sort" markdown>
### Inteiros variados

Pode ser usado para outros inteiros exatos dentro do intervalo de 64 bits com
sinal.
</div>

<div class="biel-flow-step" data-step="Timsort" markdown>
### Compatibilidade

É usado para entradas pequenas, quase ordenadas, objetos gerais, inteiros
gigantes, `key=` e `reverse=`.
</div>

</div>

O fallback para Timsort não representa erro. Ele faz parte do projeto e garante
que o BielSort preserve o comportamento esperado do Python nos casos em que a
especialização nativa não compensa.

## Quando o BielSort faz sentido?

=== "Bom candidato"

    - listas grandes de inteiros;
    - valores entre `-(2**63)` e `2**63 - 1`;
    - dados que normalmente não chegam quase ordenados;
    - velocidade importante e memória auxiliar aceitável;
    - ganho confirmado por benchmark com dados reais.

=== "Prefira o Python"

    - listas pequenas ou quase ordenadas;
    - strings, floats ou objetos gerais;
    - uso constante de `key=` ou `reverse=`;
    - necessidade de funcionar em implementações diferentes do CPython;
    - economia de memória acima de velocidade.

Antes de adotar, execute o benchmark de workloads, meça o pipeline completo e
registre também resultados negativos. O
[guia de casos de uso e adoção](use-cases-pt.md) explica os cenários sintéticos,
as comparações equivalentes e o formulário para compartilhar uma avaliação
real sem publicar dados confidenciais.

## O que significam `.` e `-e .`?

Estes comandos são para quem clonou o código-fonte:

```bash
python -m pip install .
```

O ponto significa **a pasta atual**. O `pip` encontra e instala o projeto que
está nessa pasta.

```bash
python -m pip install -e .
```

O `-e` significa **instalação editável**, utilizada durante o desenvolvimento.
Alterações em arquivos Python ficam disponíveis no ambiente; alterações no
código C precisam de uma nova compilação.

Usuários que instalaram pelo PyPI não precisam executar esses comandos.

## Desempenho

Nos benchmarks registrados na máquina original de desenvolvimento, o BielSort
foi mais rápido em distribuições favoráveis de um milhão de inteiros. Ele
empatou com o Timsort em inteiros de 1024 bits e dados quase ordenados, pois
esses casos usam o fallback. Os resultados são medições de uma máquina, não uma
promessa universal.

Consulte a [página de desempenho](performance.md) para ver tabelas separadas,
metodologia, consumo de memória e comparação com NumPy.

## Próximos links

- [Instalação detalhada e solução de problemas](getting-started.md)
- [Referência completa da API](api.md)
- [Como as estratégias são escolhidas](strategies.md)
- [Limitações e compatibilidade](limitations.md)
- [Casos de uso e adoção](use-cases-pt.md)
- [Código-fonte no GitHub](https://github.com/bielelias/bielsort)
- [Pacote no PyPI](https://pypi.org/project/bielsort/)
