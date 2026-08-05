# Avalie seu workload com privacidade

O BielSort Workload Evaluator compara a wheel pública com `sorted()` e
`list.sort()` usando uma lista que permanece na sua máquina. Ele produz JSON e
Markdown revisáveis, sem valores brutos, caminho do provedor ou envio
automático.

!!! warning "Execute somente seu próprio provedor"

    O arquivo provedor é código Python executado localmente. Não use arquivos
    recebidos de pessoas desconhecidas. Revise também os relatórios antes de
    compartilhá-los: eles contêm ambiente, tamanho, tempos e, por padrão,
    estatísticas agregadas da amostra.

## 1. Prepare o ambiente

O evaluator está no repositório e testa a versão estável instalada do PyPI:

```bash
git clone https://github.com/bielelias/bielsort.git
cd bielsort
python3 -m venv .venv
source .venv/bin/activate
python -m pip install bielsort==0.2.0
```

No Windows PowerShell, ative com:

```powershell
.venv\Scripts\Activate.ps1
```

## 2. Crie seu provedor

Copie o exemplo para um arquivo local ignorado pelo Git:

```bash
cp benchmarks/workload_provider_example.py my_workload.py
```

Altere apenas `load_values()` para retornar a `list` real que sua aplicação já
precisa ordenar:

```python
def load_values():
    numeros = carregar_ids_ou_timestamps()
    return numeros
```

O retorno deve ser uma `list` exata. Não imprima os elementos e não converta
outro contêiner apenas para fabricar um resultado favorável.

## 3. Execute

```bash
python benchmarks/workload_evaluator.py \
  my_workload.py:load_values \
  --label "descricao-anonima" \
  --json bielsort-workload-report.json \
  --markdown bielsort-workload-report.md
```

O evaluator realiza um aquecimento e sete medições intercaladas de:

- `sorted(values)` e `bielsort.sort(values)` para uma nova lista;
- `list.sort()` e `bielsort.sort_in_place()` para operações in-place.

As cópias necessárias para operações in-place, validação de correção e
destruição dos resultados ficam fora do cronômetro. A lista original não é
modificada.

!!! warning "Reserve memória"

    Durante o teste, a ferramenta mantém a lista original e uma referência
    ordenada, além de criar um resultado candidato por vez. Comece com uma
    amostra menor se a aplicação estiver próxima do limite de memória. O
    evaluator ainda não mede pico de memória nem o pipeline completo.

## 4. Revise a privacidade

O relatório normal contém:

- tamanho e tipo do contêiner;
- ambiente Python, BielSort, sistema e arquitetura;
- estratégia escolhida;
- amostras de tempo, medianas e razões;
- estatísticas agregadas de até 2.048 posições, como duplicatas aproximadas,
  monotonicidade, sinais e comprimentos de bits.

Ele não contém os números originais nem o caminho de `my_workload.py`. Para
omitir também as estatísticas de distribuição, use:

```bash
python benchmarks/workload_evaluator.py \
  my_workload.py:load_values \
  --minimal-metadata
```

Os nomes padrão `bielsort-workload-report*.json` e `.md` são ignorados pelo
Git para reduzir o risco de commit acidental. Ainda assim, abra os dois
arquivos e faça sua própria revisão antes de compartilhar.

## 5. Compartilhe ganhos e perdas

Cole o Markdown revisado no
[formulário de caso de uso](https://github.com/bielelias/bielsort/issues/new?template=use_case.yml)
e explique anonimamente o que produz a lista e por que ela é ordenada. Um
resultado em que `sorted()` vence é tão útil quanto uma aceleração.

O evaluator mede a ordenação isolada. Antes de adotar em produção, meça também
o tempo completo do pipeline e o pico de memória.
