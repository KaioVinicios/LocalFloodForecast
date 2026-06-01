# Métodos

Detalhamento dos algoritmos usados no pipeline: intuição, hiperparâmetros,
como ler os resultados e quando re-tunar. Para a visão de alto nível,
veja [../README.md](../README.md). Para o código, veja
[../src/flood/model.py](../src/flood/model.py) e
[../src/flood/features.py](../src/flood/features.py).

## StandardScaler

Aplica `z = (x - μ) / σ` por coluna. **Obrigatório** para qualquer método
baseado em distância (KMeans, LOF) ou que combine features de escalas
diferentes — `tp` está em metros (~0,0001), `msl` em pascal (~101.000),
`t2m` em kelvin (~290). Sem padronizar, `msl` dominaria toda distância.

Aplicado em [scale_features](../src/flood/features.py) sobre as 11
colunas da lista `FEATURES`. O `scaler` ajustado é retornado, mas não é
serializado nem reusado em runs subsequentes.

## IsolationForest

### Intuição
Constrói N árvores binárias aleatórias. A cada nó, escolhe uma feature
e um valor de corte aleatórios. Pontos **anômalos são isolados em poucos
splits** (acabam em folhas próximas da raiz); pontos normais precisam
de muitos splits.

Score = profundidade média da folha em que o ponto cai, normalizada.
Quanto menor, mais anômalo.

### Hiperparâmetros (em [config.py](../src/flood/config.py))
- `ISO_N_ESTIMATORS = 200`. Default sklearn é 100; 200 estabiliza o
  score sem custo perceptível. Acima disso o ganho é marginal.
- `ISO_CONTAMINATION = 0.05`. Fração esperada de anomalias. Força o
  threshold no 5º percentil dos scores — exatamente 5% dos pontos são
  marcados como `is_anomaly_iso=True`. **Este é o principal botão a
  girar** se você quiser mais ou menos sensibilidade.
- `random_state=42` para reprodutibilidade entre execuções.

### Colunas produzidas
- `anomaly_label_iso`: -1 (anomalia) ou 1 (normal).
- `anomaly_raw_iso`: score contínuo do `decision_function`. **Menor =
  mais anômalo.** Range típico aqui: -0,17 a +0,16.
- `is_anomaly_iso`: bool, equivalente a `anomaly_label_iso == -1`.

### Quando re-tunar
- Mudou de região? O range natural de variabilidade muda — pode precisar
  ajustar `contamination` (ex.: clima muito estável → 1%; clima muito
  variável → 10%).
- Mudou de período? O mesmo.
- Quer comparar com outro método de threshold? Pode-se usar
  `decision_function` direto e cortar em outro quantil.

## Local Outlier Factor (LOF)

### Intuição
Para cada ponto, calcula sua densidade local (inverso da distância média
aos k vizinhos mais próximos) e compara com a densidade dos próprios
vizinhos. Pontos em regiões **muito menos densas que sua vizinhança**
são marcados como outliers.

Diferença para Iso: LOF é **local** (compara cada ponto com seu próprio
bairro), enquanto Iso é **global** (compara com o conjunto inteiro). Por
isso os dois métodos discordam bastante na prática — Jaccard de só ~9%
neste dataset (ver `[comparação Iso × LOF]` no log de execução e a fig
`method_comparison.png`).

### Hiperparâmetros
- `LOF_N_NEIGHBORS = 20`. Default sklearn. A varredura em
  [diagnostics.py](../src/flood/diagnostics.py) mostra que Jaccard com Iso
  varia só 8,99%→11,30% no range {10, 20, 30, 50} — pouco sensível.
- `LOF_CONTAMINATION` igual ao Iso para comparação justa (também 5%).

### Colunas produzidas
- `anomaly_label_lof`: -1 / 1.
- `anomaly_raw_lof`: `negative_outlier_factor_`. **Menor (mais negativo)
  = mais anômalo.** Range típico: -2,24 a -0,96 (sempre ≤ -1; quanto
  mais negativo, mais isolado densidade-localmente).
- `is_anomaly_lof`: bool.

### Quando re-tunar
- Dataset muito ruidoso → aumentar `n_neighbors` (suaviza estimativa
  de densidade).
- Dataset esparso ou pequeno → reduzir `n_neighbors`.
- LOF é **O(n²) na memória** se você desligar a árvore espacial; com
  default `algorithm="auto"` (BallTree/KDTree) escala em O(n log n).
  Para >100k pontos, monitore.

### Iso vs LOF aqui
| | IsolationForest | LOF |
|---|---|---|
| Visão | Global | Local |
| Hiperparâmetro principal | `n_estimators` | `n_neighbors` |
| Score | profundidade da folha | `negative_outlier_factor_` |
| Range típico | [-0,17, +0,16] | [-2,24, -0,96] |
| Anomalias flagged | 1.915 (forçado pelo contamination) | 1.915 (idem) |
| Após ∩ cluster de risco | ~293 | ~25 |
| Conclusão prática | Cobertura ampla, mais falsos positivos | Conservador, alta confiança |

## KMeans

### Intuição
Particiona N pontos em k clusters minimizando a soma de distâncias ao
quadrado entre cada ponto e o centróide do seu cluster. Inicialização
via k-means++ (espalha sementes iniciais).

Aqui o KMeans NÃO detecta anomalias — ele **agrupa instantes em regimes
meteorológicos** (tempo seco, tempo úmido moderado, tempestade…). O
detector de "qual regime é o de risco" é feito *depois*, ranqueando os
centróides.

### Hiperparâmetros
- `N_CLUSTERS = 4`. **Validado empiricamente**: silhouette score máximo
  em k=4 (0,215) na varredura k=2..8 (ver
  [diagnostics.py](../src/flood/diagnostics.py)).
- `KMEANS_N_INIT = 20`. Acima do default sklearn (10) para reduzir
  variância entre execuções.
- `random_state=42`.

### Como o cluster de risco é eleito
A constante `RISK_RANK_SPEC` em [config.py](../src/flood/config.py) define:

```python
RISK_RANK_SPEC = {
    "tp":   False,   # ascending=False → mais chuva = maior risco
    "msl":  True,    # ascending=True  → menor pressão = maior risco
    "fg10": False,   # ascending=False → rajada mais forte = maior risco
}
```

Para cada cluster e cada uma dessas 3 colunas, calcula-se a **média** e
depois o **posto (rank)** entre clusters. Somam-se os 3 postos com peso
igual; o cluster com a **menor soma** é o de risco.

Ver [cluster_regimes](../src/flood/model.py).

### Como ler os resultados
- `df["cluster"]`: inteiro 0..3.
- `df["in_flood_cluster"]`: bool.
- `stats` (DataFrame retornado): médias por cluster + a coluna
  `flood_risk_score`.
- Os tamanhos dos clusters aparecem no log (`tamanhos por cluster: {0:
  363, 1: 11991, ...}`). Cluster pequeno + score baixo = regime raro de
  tempo severo (típico do cluster de risco).

### Quando re-tunar
- Mudou de região? Rode `diagnostics.svg` e veja se k=4 ainda tem o
  silhouette máximo. Costa com regime monomodal pode preferir k=3;
  região com regimes muito heterogêneos pode preferir k=5–6.
- O `RISK_RANK_SPEC` está fixo nas 3 features clássicas de tempestade.
  Se você acrescentar uma feature relevante (ex.: altura significativa
  de onda), considere incluí-la no ranking.

## PCA

### Intuição
Projeção linear em componentes ortogonais que maximizam a variância
retida. Aqui usado **exclusivamente para visualização** em 2D — não
entra na modelagem.

### Hiperparâmetros
- `PCA_N_COMPONENTS = 2`. Suficiente para os scatters de
  [fig_pca](../src/flood/viz.py) e
  [fig_method_comparison](../src/flood/viz.py).

### Resultado
PC1+PC2 retêm **54,9%** da variância do dataset padronizado.
Razoável para inspeção visual; **insuficiente** se você quisesse usar
PCs como input de modelagem (precisaria de mais componentes — ver o
painel "PCA — variância explicada" em `diagnostics.svg`).

## Como esses métodos se combinam

```
StandardScaler             → X_scaled
       │
       ├─► IsolationForest → is_anomaly_iso (5% global)
       ├─► LOF             → is_anomaly_lof (5% densidade-local)
       └─► KMeans + rank   → in_flood_cluster (cluster meteorológico de risco)

flood_risk_flag_iso = is_anomaly_iso & in_flood_cluster
flood_risk_flag_lof = is_anomaly_lof & in_flood_cluster
                          │
                          ▼
                  PCA (visualização)
```

A interseção com `in_flood_cluster` é o que dá significado meteorológico
ao flag — anomalias *isoladas* podem ser qualquer coisa (sensor bagunçando,
dia anômalo de calor, etc.); cruzar com o cluster sinóptico de risco
filtra para "anomalia E condições típicas de tempestade".
