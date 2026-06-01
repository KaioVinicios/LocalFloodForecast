# Documentação — LocalFloodForecast

Índice dos materiais de apoio. Para a visão geral do projeto, comece pelo
[../README.md](../README.md) na raiz.

## Índice

| Documento | Para quê serve |
|---|---|
| [architecture.md](architecture.md) | Mapa do código: módulos do pacote `src/flood/`, dependências entre eles, padrões adotados e fluxo do pipeline em `main.py` passo a passo. |
| [methods.md](methods.md) | Métodos de ML/stats em detalhe: intuição, hiperparâmetros e leitura de resultados de IsolationForest, LOF, KMeans, PCA e StandardScaler. |
| [directories.md](directories.md) | Pasta-por-pasta: o que vai (e o que não vai) em cada diretório, o que é versionado, e o que cada artefato em `src/graphics/<timestamp>/` significa. |
| [faq.md](faq.md) | Perguntas comuns sobre decisões de design (não supervisionado, região, dois detectores, k=4, contamination=5%) e como adaptar o pipeline (mudar local, período, adicionar features/detectores). |
| [TODO_evolucoes_analiticas.md](TODO_evolucoes_analiticas.md) | Roadmap das próximas 3 evoluções: agrupamento de eventos, fix da agregação de `tp`, e validação contra cheias reais. |
| [artigo_v1.pdf](artigo_v1.pdf) | Artigo de referência (material original do projeto). |

## Por onde começar

- **Primeira vez no repo?** Leia [../README.md](../README.md) → execute
  `python src/main.py` → leia [directories.md](directories.md) para
  entender as saídas.
- **Vai mexer no código?** Comece por [architecture.md](architecture.md)
  para entender as fronteiras entre módulos.
- **Vai re-tunar hiperparâmetros ou mudar de método?** Vá direto pra
  [methods.md](methods.md) e depois a seção *Diagnóstico* em
  [architecture.md](architecture.md).
- **Vai trabalhar numa das 3 evoluções pendentes?** Veja
  [TODO_evolucoes_analiticas.md](TODO_evolucoes_analiticas.md).
- **Tem dúvida sobre uma escolha de design?** Procure em
  [faq.md](faq.md) antes de perguntar.
