# Casos de uso e adoção

A promessa do BielSort é propositalmente específica: acelerar algumas
ordenações de grandes `list[int]` e listas novas de objetos com `key`
signed-int64, sem obrigar a aplicação a migrar os dados para outro contêiner.
A única forma confiável de saber se ele ajuda é medir a operação completa
dentro da aplicação que possui os dados.

!!! success "Um candidato promissor"

    Os dados já estão em uma lista Python grande, contêm inteiros exatos no
    intervalo signed 64-bit, precisam de ordem crescente natural e não chegam
    quase ordenados. Na versão 0.2, registros com chave signed-int64 exata
    também são elegíveis para a operação new-list. A ordenação representa uma
    parte relevante do tempo total do pipeline.

!!! warning "Geralmente não é um bom candidato"

    Prefira a ordenação do Python para entradas pequenas ou quase ordenadas,
    objetos mistos, chaves genéricas, `key=` in-place ou `reverse=` sem chave. Se
    o pipeline já utiliza NumPy, Polars, Pandas ou um banco de dados, normalmente
    é melhor manter os dados nesse sistema.

## Checklist de decisão

<div class="biel-grid" markdown>

<div class="biel-card" markdown>
### É uma `list[int]` exata?
Os caminhos nativos exigem inteiros Python exatos; conversões alteram a
comparação.
</div>

<div class="biel-card" markdown>
### Cabe em signed 64-bit?
Inteiros maiores usam o fallback para Timsort.
</div>

<div class="biel-card" markdown>
### A lista é grande?
Buffers nativos fazem mais sentido com dezenas ou centenas de milhares de
valores.
</div>

<div class="biel-card" markdown>
### Ordem crescente natural?
Inteiros naturais são o alvo original. A versão 0.2 também aceita uma `key`
new-list que retorne inteiros signed 64-bit exatos.
</div>

<div class="biel-card" markdown>
### É um gargalo medido?
Acelerar uma pequena fração do pipeline causa pouco impacto total.
</div>

<div class="biel-card" markdown>
### Há margem de memória?
Os caminhos nativos trocam memória adicional por velocidade.
</div>

</div>

## Workloads sintéticos transparentes

O repositório oferece três proxies determinísticos. Eles não fingem ser dados
de produção: servem como exemplos que podem ser substituídos por um gerador
anônimo semelhante ao workload real.

<div class="biel-grid" markdown>

<div class="biel-card" markdown>
### Timestamps de eventos
Horários desordenados de um dia, com duplicatas. Esse intervalo denso pode
favorecer Counting Sort em escala.
</div>

<div class="biel-card" markdown>
### IDs signed 64-bit
Identificadores desordenados em um intervalo amplo exercitam o Radix Sort.
</div>

<div class="biel-card" markdown>
### Offsets quase ordenados
Uma sequência crescente com poucos itens deslocados deve acionar Timsort e
demonstrar compatibilidade, não aceleração nativa.
</div>

</div>

Depois de clonar o repositório, execute:

```bash
python -m pip install -e ".[benchmark]"
python benchmarks/workload_validation.py \
  -n 10000 100000 1000000 \
  -r 7 \
  --json bielsort-workload-report.json
```

A comparação mede operações que retornam uma nova lista:

- `sorted(values)`;
- `bielsort.sort(values)`;
- NumPy completo: `list[int]` para `ndarray`, ordenação estável e conversão de
  volta para `list[int]`.

A geração da entrada e do resultado esperado fica fora da região cronometrada.
A ordem dos algoritmos é intercalada deterministicamente. O JSON registra o
ambiente, configurações, medianas, estratégia escolhida, se um caminho nativo
foi utilizado, vencedor e speedups. Use `--without-numpy` se essa comparação
não for necessária.

## Meça o pipeline, não apenas o sort

Um grande ganho isolado pode ter pouco impacto. Se a ordenação representa 10%
de um pipeline e fica quatro vezes mais rápida, o pipeline completo melhora
somente cerca de 1,08 vez:

```text
ganho total = 1 / (0,90 + 0,10 / 4) = 1,08x
```

Registre pelo menos:

1. tempo total do pipeline antes e depois;
2. tempo isolado da ordenação com tipos equivalentes;
3. pico de memória e limites do processo;
4. tamanho, intervalo, duplicatas e ordenação prévia da entrada;
5. CPU, sistema, versão do Python e número de repetições.

## Compartilhe um resultado real

Use o [BielSort Workload Evaluator](evaluator-pt.md) para comparar as APIs com
uma lista que permanece na sua máquina. A ferramenta gera JSON e Markdown sem
valores brutos ou envio automático; revise ambos antes de compartilhar.

Use o
[formulário de caso de uso](https://github.com/bielelias/bielsort/issues/new?template=use_case.yml)
para relatar ganho, perda ou incompatibilidade. Resultados negativos ajudam a
melhorar o seletor e a delimitar o nicho real do projeto.

Não envie bases proprietárias ou identificadores confidenciais. Prefira um
gerador pequeno e anônimo que reproduza a distribuição dos dados.

## Critérios antes de adotar em produção

- o resultado está correto em entradas representativas;
- a melhora do pipeline completo é relevante;
- o pico de memória permanece dentro de uma margem segura;
- existe uma wheel compatível para cada ambiente de implantação;
- o fallback para Timsort é aceitável;
- a aplicação fixa uma versão testada e possui um caminho de retorno.

Concluir que `sorted()`, NumPy ou o banco continua sendo a melhor opção também
é um resultado de validação bem-sucedido.

Para evidência de instalação e portabilidade, continue com a
[validação em runners independentes](external-validation-pt.md). Ela testa a
wheel pública, mas não substitui um workload de aplicação.
