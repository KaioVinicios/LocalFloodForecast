# TODO — 3 evoluções analíticas

## Contexto

O pipeline atual (IsolationForest + LOF + KMeans, com saída estática em
matplotlib) produz **293 timesteps Iso / 25 LOF** sinalizados, mas tem três
limitações que comprometem a interpretação:

1. **Cada cheia real aparece como vários timesteps consecutivos** — a leitura
   de `flagged_events_*.csv` é cansativa e exagera o nº de "eventos".
2. **`tp` é agregado por média no resample 6h** (vira taxa, não acumulado).
   Pra um pipeline de cheia isso é semanticamente errado e o
   `flood_risk_score` que usa `tp` herda o erro. Já documentado como
   ressalva em [../src/flood/config.py](../src/flood/config.py) (linhas 18-20).
3. **Não há ground truth** — todo o pipeline é não supervisionado e não há
   prova de que as datas sinalizadas correspondam a inundações reais.

Esse TODO ataca os três, **na ordem (1)→(2)→(3)** para que a validação rode
sobre a versão final/corrigida. README fica fora do escopo (TODO separado).

---

## (1) Agrupar timesteps em eventos atômicos

**Objetivo**: colapsar runs consecutivos do `flood_risk_flag_*` em eventos
únicos, com início/fim/duração/pico.

**Arquivos**:
- [../src/flood/config.py](../src/flood/config.py): nova constante
  `EVENT_GAP_HOURS = 24` com justificativa (tempestades sinóticas típicas
  duram 6h–48h; 24h é o ponto onde o LOF passa de ~25→~15 eventos
  agrupados — validar empiricamente).
- [../src/flood/model.py](../src/flood/model.py): nova função
  `group_events(df, method, gap_hours=EVENT_GAP_HOURS)` que retorna um
  DataFrame com uma linha por evento e colunas:
  `event_id, start, end, duration_h, n_timesteps, peak_score,
   peak_score_at, sum_tp_mm, max_fg10, min_msl_hpa, cluster_id`.
  Algoritmo: ordenar por `valid_time`, marcar runs onde o gap entre
  flagged consecutivos > `gap_hours`, agregar.
- [../src/flood/viz.py](../src/flood/viz.py): nova
  `save_grouped_events_csv(df, out_path, method)` que substitui (não
  duplica) `save_flagged_csv` na saída padrão. CSV passa a ter uma linha
  por evento, não por timestep.
- [../src/main.py](../src/main.py): chamar `group_events` para `iso` e `lof`,
  logar `[grouping] iso: 293 timesteps → N eventos | lof: 25 → M eventos`,
  substituir as duas linhas de `save_flagged_csv` pelas novas grouped.

**Reutilização**: a estrutura `df[df[flag_col]]` já existe em `save_flagged_csv`
e em `fig_timeline` — extrair o predicado de "flagged" via `flag_col` parametrizado
(já feito na fase LOF).

---

## (2) Corrigir agregação do `tp`

**Objetivo**: `tp` deve ser **soma** (acumulado em 6h, em metros → mm) e não
média, para refletir precipitação real.

**Arquivos**:
- [../src/flood/data.py](../src/flood/data.py) (linhas 7-10): substituir
  `df.resample(resample_freq, on="valid_time").mean()` por
  `df.resample(resample_freq, on="valid_time").agg({**{c: "mean" for c in
   numeric_cols}, "tp": "sum"})`. Implementar com lista explícita de colunas
  derivadas do schema (todas numéricas exceto `valid_time`), com `tp`
  override para `sum`.
- [../src/flood/config.py](../src/flood/config.py) (linhas 18-20): atualizar
  o comentário da ressalva — agora `tp` é acumulado correto, não taxa.
- [../src/flood/viz.py](../src/flood/viz.py): em `fig_timeline`, o painel
  inferior ainda mostra `tp.rolling("30D").mean() * 1000` — manter o cálculo,
  só **mudar o label** do eixo Y de "Precip (média rolada 30d, mm)" para
  "Precip (acumulado 6h, média rolada 30d, mm)". Os números mudam de escala.
- [../src/flood/model.py](../src/flood/model.py): nada — `RISK_RANK_SPEC` em
  `cluster_regimes` continua usando `tp` (agora com semântica correta).

**Impacto esperado**: o `flood_cluster` pode mudar de índice (era 0).
Logar no main: `cluster antes do fix: 0 | depois: N`. **Não** ajustar
hardcodes — qualquer lugar que assuma `flood_cluster == 0` é bug.

---

## (3) Validação contra eventos reais (curadoria manual)

**Objetivo**: cruzar as datas sinalizadas com cheias documentadas na costa
líbia/Mediterrâneo central, calcular precision/recall por método.

**Arquivos**:
- **NOVO** `data/known_floods.csv` (curadoria manual): schema
  `date,location,source,notes,severity` — usuário popula com ~10-30 eventos
  pesquisados (ex.: ciclone Daniel set/2023, Qendresa nov/2014, eventos
  do EM-DAT, papers regionais). Plano cria o arquivo com header e 3-5
  exemplos como template + comentário inicial explicando o schema.
- **NOVO** `src/flood/validation.py`:
  - `load_known_floods(path)` → DataFrame com `date` como `datetime`.
  - `match_events(grouped_events, known, window_days=2)` → adiciona a
    cada evento agrupado a coluna `matched_known` (linha do known mais
    próxima dentro da janela, ou NaN). Janela ±2 dias por default —
    documentar como compromise entre tolerância e false matches.
  - `compute_metrics(grouped_events, known, window_days=2)` →
    `{tp, fp, fn, precision, recall, f1}` onde `tp` = known com pelo
    menos 1 evento sinalizado em ±window; `fp` = eventos sinalizados sem
    known em ±window; `fn` = known sem nenhum sinalizado.
- [../src/flood/viz.py](../src/flood/viz.py): nova
  `fig_validation(grouped_events_iso, grouped_events_lof, known, window_days)`
  com 2 linhas (Iso/LOF) × 1 coluna. Cada subplot: timeline horizontal
  com `known` como linhas verticais (cinza), eventos sinalizados como
  marcadores coloridos por status (TP=verde, FP=vermelho); título inclui
  precision/recall/F1.
- [../src/main.py](../src/main.py): após `group_events`, tentar
  `load_known_floods(KNOWN_FLOODS_PATH)`; se arquivo existir, rodar
  `compute_metrics` para Iso e LOF, logar bloco `[validação]` com tabela
  e gravar `validation_iso.csv` + `validation_lof.csv` (eventos agrupados
  com coluna `matched_known`), e a fig `validation.png`. Se o CSV não
  existir ou tiver header só, pular validação e logar aviso amigável.
- [../src/flood/config.py](../src/flood/config.py): novas constantes
  `KNOWN_FLOODS_PATH = PROJECT_ROOT / "data" / "known_floods.csv"` e
  `VALIDATION_WINDOW_DAYS = 2`.

**Reutilização**: a paleta de cores e tema em `viz.apply_theme()`, o helper
`_format_year_axis()`, e `save_figures()` continuam servindo sem mudança.

---

## Verificação ponta-a-ponta

```bash
source .venv/bin/activate
cd src && python main.py
```

Esperado no console:
1. Bloco `[grouping]` com timesteps→eventos para Iso e LOF.
2. Bloco com `cluster de risco antes/depois do fix tp` (uma vez na primeira
   execução pós-fix; depois só o valor estável).
3. Bloco `[validação]` com `precision/recall/F1` para Iso e LOF (após
   popular `known_floods.csv`).

Arquivos esperados em `src/graphics/<ts>/`:
- `flagged_events_iso.csv` e `flagged_events_lof.csv` (agrupados; muito
  menores que antes).
- `validation.png`, `validation_iso.csv`, `validation_lof.csv` (se houver
  known_floods).
- Demais artefatos inalterados (`timeline_*`, `pca`, `method_comparison`,
  `diagnostics`, etc.).

Checagens manuais:
- Inspecionar `flagged_events_iso.csv`: cada linha deve ter `duration_h ≥ 6`
  e `n_timesteps ≥ 1`; eventos com `duration_h` muito alto (>72h) sugerem
  que `EVENT_GAP_HOURS=24` está agrupando demais — revisitar parâmetro.
- Confirmar nos logs que `tp` médio do cluster de risco é maior agora
  (é soma, não taxa).
- Em `validation.png`: as linhas verticais cinzas (known floods) devem ter
  marcadores TP perto na maioria; falhas (FN) destacadas visualmente para
  inspeção.

Sem testes automatizados configurados no repo (CLAUDE.md confirma) —
verificação fica em rodada manual + inspeção dos CSVs/figuras.
