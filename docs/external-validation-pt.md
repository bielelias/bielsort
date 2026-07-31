# Validação em runners independentes

A matriz instala exatamente a wheel pública do BielSort em ambientes
descartáveis do GitHub. Ela verifica se o pacote do PyPI instala corretamente,
escolhe estratégias consistentes, produz resultados corretos e apresenta o
mesmo comportamento geral em diferentes sistemas e arquiteturas.

!!! important "Evidência técnica, não demanda de usuários"

    Os runners do GitHub são máquinas compartilhadas e possuem carga variável.
    Os resultados sintéticos servem para portabilidade e consistência, não para
    ranking absoluto de hardware, planejamento de produção ou prova de que
    usuários reais precisam do BielSort.

## Matriz utilizada

| Ambiente | Python | Cobertura principal |
|---|---:|---|
| Ubuntu mais recente | 3.11 | Wheel Linux e runtime comum |
| Ubuntu mais recente | 3.14 | CPython mais novo suportado |
| Windows mais recente | 3.11 | Wheel e runtime do Windows |
| macOS Intel | 3.11 | Wheel para Macs Intel |
| macOS mais recente | 3.11 | Wheel para Apple Silicon |

Cada máquina:

1. instala uma versão exata do PyPI aceitando apenas wheels;
2. rejeita uma importação acidental do código-fonte local;
3. instala NumPy somente para comparação;
4. executa os proxies com 100 mil e um milhão de elementos;
5. compara cada resultado com `sorted()`;
6. envia um JSON com ambiente, estratégias e medições.

O último job valida os arquivos, calcula speedups dentro de cada máquina e
gera uma tabela Markdown consolidada no GitHub Actions.

## Como executar

Um mantenedor abre
[Hosted runner validation](https://github.com/bielelias/bielsort/actions/workflows/workload-validation.yml),
clica em **Run workflow**, informa a versão exata do PyPI e escolhe três, cinco
ou sete repetições. A execução é manual para não gastar runners com medições
ruidosas em toda alteração de código.

Os artefatos permanecem disponíveis por 30 dias. Um resultado revisado pode
ser preservado em `benchmarks/results/` junto com data, workflow, versão e
limitações.

## Leitura correta

- Compare BielSort, `sorted()` e NumPy dentro da mesma máquina.
- Não compare segundos absolutos entre runners diferentes.
- Procure consistência de estratégia e de razão de desempenho.
- Repita resultados contraditórios antes de alterar o seletor.
- Trate dados quase ordenados como controle de compatibilidade com Timsort.
- Exija uma medição da aplicação antes de recomendar uso em produção.

O [guia de casos de uso](use-cases-pt.md) continua sendo o critério de adoção.
Essa matriz reduz incertezas de instalação e portabilidade, mas não substitui
feedback de workloads externos.
