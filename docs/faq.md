# FAQ

Perguntas comuns sobre as escolhas de design e como adaptar o pipeline.

## Design

### Por que o pipeline é não supervisionado?
Não há ground truth disponível na origem do projeto — o dataset ERA5
traz só variáveis meteorológicas, não rótulos de "houve cheia / não
houve". Tentar treinar um classificador exigiria curar um dataset de
eventos reais à mão, o que é trabalhoso e foi adiado. A detecção
não supervisionada (Iso + LOF + KMeans) extrai estrutura sem precisar
de rótulos.

A validação contra cheias reais (curadoria manual) está no roadmap —
ver [TODO_evolucoes_analiticas.md](TODO_evolucoes_analiticas.md), item 3.

### Por que a costa líbia / Mediterrâneo central?
Foi o ponto inicial usado para experimentação (longitude 19.25,
latitude 31). É uma região com eventos documentados de cheia costeira
(p.ex. ciclone Daniel set/2023, Qendresa nov/2014). O pipeline é
agnóstico ao local — basta editar [era5_api.py](../src/hooks/era5_api.py)
e re-baixar os dados (ver "Posso mudar o local?" abaixo).

### Por que rodar IsolationForest E LOF em paralelo?
Os dois métodos têm visões complementares: Iso é **global** (procura
pontos atípicos no conjunto inteiro), LOF é **local** (procura pontos
em regiões menos densas que sua vizinhança imediata). Eles **discordam
muito** — Jaccard de ~9% na camada bruta nesse dataset. Ter os dois
permite:
- Ver onde concordam (alta confiança).
- Ver onde discordam (zona cinzenta para investigação).
- Não depender de um método só.

A comparação visual fica em `method_comparison.png` e as métricas no
bloco `[comparação Iso × LOF]` do log.

### Por que 4 clusters?
Foi **validado empiricamente**: o silhouette score atinge o máximo em
k=4 (0,215) na varredura k=2..8 — ver o painel "Silhouette por k" em
`diagnostics.svg` ou rode `python src/main.py` e leia o log
`[diagnóstico] k ótimo por silhouette: 4 (configurado = 4)`.

### Por que 5% de contamination?
É o teto razoável para "tempo incomum" nesse dataset. Chuva detectável
(>0,1 mm/h) ocorre em ~3,7% dos timesteps; 5% engloba isso + outros
sinais (rajada forte, pressão muito baixa). A varredura {1%, 2%, 5%,
10%} no `diagnostics.svg` mostra a sensibilidade. **É o principal
botão** se você quiser mais ou menos eventos sinalizados.

### Por que resample de 6h?
Suaviza ruído sub-horário sem perder a escala sinótica (00/06/12/18 UTC
são os tempos canônicos de evolução de sistemas meteorológicos). De
229.752 linhas horárias o pipeline passa para 38.292 linhas em 6h —
~6× mais leve, com qualidade analítica preservada.

Ressalva: `tp` (precipitação) hoje é agregada por **média**, virando
taxa em vez de acumulado. Correção está no
[TODO](TODO_evolucoes_analiticas.md), item 2.

### Por que PCA só com 2 componentes?
Só para **visualização** em scatter 2D (`pca.png`, `method_comparison.png`).
PC1+PC2 retêm 54,9% da variância — adequado para inspeção visual,
insuficiente para usar PCs como input de modelagem. O painel "PCA —
variância explicada" em `diagnostics.svg` confirma.

### Por que matplotlib estático em vez de HTML interativo?
A versão anterior usava Plotly + dashboard HTML standalone (~15 MB por
execução). Foi pivotada para PNG/SVG estáticos por:
- Arquivos ~5× menores (~3 MB vs 15 MB).
- Sem dependência de browser para visualizar.
- Comprimem melhor no Git (se algum dia forem versionados).
- Mais fáceis de embutir em relatório/PDF.

Como compensação: facetar/anotar com mais cuidado para extrair insight
sem hover/zoom. Ver
[viz.py:fig_timeline](../src/flood/viz.py) para o padrão.

### Por que o `flood_risk_flag_lof` é tão pequeno (~25 vs ~293 do Iso)?
LOF e Iso concordam em só ~9% das anomalias brutas. Quando você
intersecta com `in_flood_cluster` (cluster 0, que tem só 363 pontos), o
LOF mantém só uma fração — porque pontos "raros densidade-localmente"
nem sempre caem no cluster sinótico do tempo severo. Iso, sendo global,
acerta mais o cluster de risco.

Leitura prática: LOF é o **gatilho conservador** (poucos falsos
positivos esperados), Iso é a **rede de cobertura ampla**.

## Como adaptar

### Posso mudar o local?
Sim. Dois passos:
1. Edite `location` em [era5_api.py](../src/hooks/era5_api.py).
2. Rode `python src/hooks/era5_api.py` (precisa de credencial Copernicus).
3. Atualize o nome do arquivo em
   [config.py:DATA_PATH](../src/flood/config.py) se for diferente.

Pode ser necessário re-rodar `diagnostics.svg` e ajustar `N_CLUSTERS`
ou `ISO_CONTAMINATION` para o novo regime climático.

### Posso mudar o período?
Sim. Edite `date` em [era5_api.py](../src/hooks/era5_api.py)
(`["YYYY-MM-DD/YYYY-MM-DD"]`) e re-baixe. Os hiperparâmetros do KMeans
e a fração de anomalias se recalculam automaticamente.

### Posso adicionar uma feature nova?
Sim. Passos:
1. Em [features.py](../src/flood/features.py), adicione a derivação
   dentro de `engineer_features`.
2. Adicione o nome da coluna na lista `FEATURES` em
   [config.py](../src/flood/config.py).
3. Se a feature for relevante para risco de cheia (alta-quando-tempestade
   ou baixa-quando-tempestade), considere incluí-la em `RISK_RANK_SPEC`
   para que o KMeans considere no ranqueamento de cluster de risco.

### Posso adicionar um terceiro detector (ex.: DBSCAN)?
Sim, seguindo o padrão Iso/LOF. Resumo:
1. Em [model.py](../src/flood/model.py), adicione
   `detect_anomalies_dbscan(df, X_scaled)` retornando colunas com
   sufixo `_dbscan`.
2. Em `flag_flood_risk`, adicione `flood_risk_flag_dbscan`.
3. Em [config.py](../src/flood/config.py), adicione constantes
   `DBSCAN_EPS`, `DBSCAN_MIN_SAMPLES` etc.
4. Parametrize `fig_timeline`, `fig_pca`, `save_flagged_csv` para
   aceitar `method="dbscan"`.
5. Estenda `fig_method_comparison` ou crie `fig_method_comparison_3way`
   para mostrar overlaps de 3 conjuntos (Venn-style ficaria interessante).

### Posso desligar o LOF?
Sim. Em [main.py](../src/main.py), comente os blocos:
- `detect_anomalies_lof` (passo 5)
- Métricas de comparação (`_comparison_metrics`)
- Figuras `timeline_lof` e `method_comparison`
- `save_flagged_csv(..., method="lof")`

E em [model.py:flag_flood_risk](../src/flood/model.py) remova a linha
do `flood_risk_flag_lof`. Tempo total cai de ~40s para ~10s.

### Posso desligar o diagnostics?
Sim. É a etapa mais pesada (~28s das ~40s totais). Em
[main.py](../src/main.py), comente o bloco `run_diagnostics(...)` e a
entrada `"diagnostics"` em `figs`. Pipeline funcional principal não muda.

### Posso mudar o detector primário do `pca.png`?
Sim. `fig_pca` aceita `method="iso"|"lof"`. Em
[main.py](../src/main.py), troque
`viz.fig_pca(df, flood_cluster, pca_var, method="iso")` por
`method="lof"`. Ou gere os dois (`pca_iso.png`, `pca_lof.png`).

## Operacional

### O notebook ainda funciona?
[src/main.ipynb](../src/main.ipynb) é mantido como referência histórica,
**não como pipeline ativo**. Pode rodar parcialmente se você tiver
matplotlib instalado, mas algumas evoluções recentes (Iso + LOF
paralelo, fig_method_comparison, agrupamento futuro) não estão
refletidas lá. **Não edite o notebook** — qualquer evolução acontece
no script + pacote.

### Quanto tempo leva uma execução?
**~40 segundos** num laptop moderno (Apple Silicon ou equivalente).
Etapa mais cara: `run_diagnostics` (~28s, treina KMeans 7× +
IsolationForest 4× + LOF 4×). O pipeline principal sem diagnostics
roda em ~12s.

### Como reproduzir uma execução antiga?
Tudo é determinístico (`RANDOM_STATE=42`). Mesmo CSV de entrada + mesmo
código = mesma saída byte-a-byte (exceto timestamps na pasta). Para
reproduzir uma execução de outro commit, faça `git checkout <sha>` e
rode `python src/main.py`.

### Por que não há testes automatizados?
Pipeline pequeno + saída visual → custo de manter testes > valor. A
verificação acontece pela inspeção dos logs e das figuras. Se evoluir
muito, vale começar por testes de smoke (asserts em colunas e
contagens esperadas) em vez de testes de unidade pesados.
