# Сопоставимые контроли: результаты, 2026-11-16

Источник: data/v2/analysis/informatica_revision/matched_controls_v1/.
Два портфеля × 203 конфигурации: real, conditional prior-only, EW,
100 full-shuffle и 100 eligible-shuffle. Новых LLM-запросов нет.

| Sharpe | Core | Holdout |
|---|---:|---:|
| Реальные views | 0.634879 | 0.546927 |
| Prior-only с тем же tilting | 0.600382 | 0.514789 |
| Equal Weight | 0.564748 | 0.495879 |
| Медиана полного перемешивания | 0.617410 | 0.485972 |
| Медиана перемешивания внутри выбранных компаний | 0.630515 | 0.540575 |
| Full-shuffle seeds не хуже real (из 100) | 34 | 7 |
| Eligible-shuffle seeds не хуже real (из 100) | 35 | 29 |

Парный блочный bootstrap, 21 день, 10 000 draws:
- real − prior-only: Core 0.0345 [−0.0470; 0.1132], Holdout 0.0321 [−0.0439; 0.1059].
- real − средний дневной ряд full-shuffle: Core 0.0107 [−0.0612; 0.0767], Holdout 0.0510 [−0.0139; 0.1149].
- real − средний дневной ряд eligible-shuffle: Core 0.0036 [−0.0190; 0.0269], Holdout 0.0051 [−0.0221; 0.0336].

Все указанные интервалы включают ноль. Средний дневной ряд ансамбля не равен
медианному seed и не является ранее определённой торгуемой стратегией.
Процентили по seeds — разброс контролей, не sampling confidence interval.
Rank exceedance — условная диагностика, не причинное/predictive p-value.

Интерпретация: значительная часть уровня Sharpe сохраняется при prior-only
и перестановке величин среди уже выбранных компаний. Данные не устанавливают
добавочную ценность точного соответствия числовых views акциям. Разница полного
и eligible-перемешивания совместима с ролью выбранного набора компаний, но не
доказывает её причинно: меняется также структура экспозиции и persistence.
Эти тесты не устраняют temporal leakage, survivorship или неизвестные vintages.

Проверки: реальные daily returns совпали с frozen сериями до 5.97e−16; EW до
1.04e−16; новая shuffled-конфигурация с shared engine до 4.17e−17. Сохранены
все seeds, дневные ряды, веса, turnover, source hashes и полный протокол.
Первый незавершённый прогон выявил ошибочное применение covariance fallback
к EW; исправленный прогон воспроизводит benchmark. История сохранена отдельно.
Turnover/HHI не включают target 2025-12-31, исполняемый в январе 2026.

Дополнительный этап завершён: 199 входов, четыре портфельных среза,
1 194 валидных Grok 4.3 ответа без повторных запросов, стоимость $2.5373412
при разрешённом лимите $10. Узкое удаление явных имён/тикеров не является
полной анонимизацией. Результаты и ограничения: PORTFOLIO_MASKING_RESULTS.md.

Additional check: on all 79 pre-terminal rebalance dates per group, at least one positive medium-confidence view is present (minimum 6 Core, 7 Holdout). The conditional prior-only no-view branch therefore does not drive the reported comparison.

Sensitivity: none of the real-minus-control intervals excludes zero at block lengths 5, 21 or 63 in either group. This does not establish equivalence or absence of useful effects.
