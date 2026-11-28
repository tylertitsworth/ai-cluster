# Halogen metrics in PromQL

The ServiceMonitor in `charts/halogen/values.yaml` scrapes `halogen.ollama:8731/metrics` every 5s into kube-prometheus-stack. Every metric below is exposed by Halogen 0.21.0 on that endpoint. These queries reproduce the fields computed by the `halogen-dashboard` Collector without running the Collector.

The dashboard uses 30s rolling windows; the examples here use one-minute windows to match a 5s scrape. Change the range to `$__interval` or `$__range` in Grafana if you want panels to follow the dashboard time picker.

Prometheus is the only reader of Halogen `/metrics`. Do not run the dashboard Collector or curl that endpoint while scraping it: `llamacpp:prompt_tokens_seconds` and `llamacpp:predicted_tokens_seconds` are measured over the time since the last read and reset on every read.

## Sample fields

| Dashboard field | PromQL | Notes |
| --- | --- | --- |
| `busy_slots` | `llamacpp:requests_processing` | Requests currently decoding. |
| `queued` | `llamacpp:requests_deferred` | Requests waiting for a slot. |
| `kv_used` | `llamacpp:kv_cache_tokens` | Engine-reported occupied positions. |
| `kv_reserved` | `halogen:kv_pool_reserved_tokens` | Front-end reservation, may exceed `kv_used`. |
| `kv_use` | `llamacpp:kv_cache_usage_ratio` | Occupancy of the engine pool, 0..1. |
| `gen_speed` | `llamacpp:predicted_tokens_seconds` | Decode tokens/s since the last scrape; the dashboard's `d(tokens)/d(seconds)` reduces to this gauge. Counter-derived alternative: `rate(llamacpp:tokens_predicted_total[1m]) / rate(llamacpp:tokens_predicted_seconds_total[1m])`. |
| `throughput` | `rate(llamacpp:tokens_predicted_total[1m])` | Wall-clock decode tokens/s, includes idle time. |
| `prefill_speed` | `llamacpp:prompt_tokens_seconds` | Prefill tokens/s since the last scrape. |
| `prefill_throughput` | `rate(llamacpp:prompt_tokens_total[1m])` | Wall-clock prompt tokens/s. |
| `requests_per_min` | `rate(halogen:requests_total[1m]) * 60` | Completed requests/min. |
| `mean_service_time` | `(rate(llamacpp:prompt_seconds_total[1m]) + rate(llamacpp:tokens_predicted_seconds_total[1m])) / rate(halogen:requests_total[1m])` | Seconds of engine work per request. The seconds counters carry only 6 significant digits; the dashboard recovers precision from the two windowed gauges. Steady-load approximation (not equivalent when idle or bursty): `(rate(llamacpp:prompt_tokens_total[1m]) / clamp_min(llamacpp:prompt_tokens_seconds, 0.001) + rate(llamacpp:tokens_predicted_total[1m]) / clamp_min(llamacpp:predicted_tokens_seconds, 0.001)) / rate(halogen:requests_total[1m])`. |
| `prompt_cache_hit_rate` | `rate(halogen:prompt_tokens_cached_total[1m]) / (rate(halogen:prompt_tokens_cached_total[1m]) + rate(llamacpp:prompt_tokens_total[1m]))` | Cached prompt tokens over all prompt tokens. |
| `draft_acceptance` | `rate(halogen:draft_tokens_accepted_total[1m]) / rate(halogen:draft_tokens_total[1m])` | MTP head plus prompt lookup; Halogen does not split them. |
| `busy_for` | `halogen:busy_for_seconds` | Age of the oldest running request. |
| `kv_waiting` | `halogen:kv_pool_waiting_for_room` | Requests waiting for pool room. |
| `cache_entries` | `halogen:cache_entries` | Conversations currently cached. |
| `cache_bytes` | `halogen:cache_bytes` | Cache size on disk/in memory as reported by the engine. |
| `cache_stats_age` | `halogen:cache_stats_age_seconds` | Age of the last engine cache report; large values mean the gauges are stale. |
| `cache_disk_enabled` | `halogen:cache_disk_enabled` | 1 when the disk tier is on. |
| `cache_disk_bytes` | `halogen:cache_disk_bytes` | Disk cache bytes used. |
| `cache_disk_budget` | `halogen:cache_disk_budget_bytes` | Disk cache budget. |
| `cache_lookup_hit_rate` | `rate(halogen:cache_hits_total[1m]) / (rate(halogen:cache_hits_total[1m]) + rate(halogen:cache_misses_total[1m]))` | Request-level cache hits over lookups. |
| `cache_evictions_per_min` | `rate(halogen:cache_evicted_total[1m]) * 60` | Entries evicted/min. |
| `cache_rewrites_per_min` | `rate(halogen:cache_last_message_rewrites_total[1m]) * 60` | Follow-ups that resumed in a previous last message. |
| `cache_disk_hits_per_min` | `rate(halogen:cache_disk_hits_total[1m]) * 60` | Disk-tier hits/min. |
| `cache_disk_cut_backs_per_min` | `rate(halogen:cache_disk_cut_back_total[1m]) * 60` | Times a conversation was trimmed to its resume point. |

## Totals fields

The dashboard keeps adjusted, monotonic counters across restarts. Prometheus counters do the same and handle resets itself, so use `increase(...)` for a window total or the bare counter for a since-restart total.

| Dashboard field | Window total (one minute) |
| --- | --- |
| `totals.requests` | `increase(halogen:requests_total[1m])` |
| `totals.prompt_tokens` | `increase(llamacpp:prompt_tokens_total[1m])` |
| `totals.predicted_tokens` | `increase(llamacpp:tokens_predicted_total[1m])` |
| `totals.cached_tokens` | `increase(halogen:prompt_tokens_cached_total[1m])` |
| `totals.draft_tokens` | `increase(halogen:draft_tokens_total[1m])` |
| `totals.draft_accepted` | `increase(halogen:draft_tokens_accepted_total[1m])` |
| `totals.structured_requests` | `increase(halogen:structured_requests_total[1m])` |
| `totals.cache_hits` | `increase(halogen:cache_hits_total[1m])` |
| `totals.cache_misses` | `increase(halogen:cache_misses_total[1m])` |
| `totals.cache_evicted` | `increase(halogen:cache_evicted_total[1m])` |
| `totals.cache_rewrites` | `increase(halogen:cache_last_message_rewrites_total[1m])` |
| `totals.cache_disk_hits` | `increase(halogen:cache_disk_hits_total[1m])` |
| `totals.cache_disk_cut_backs` | `increase(halogen:cache_disk_cut_back_total[1m])` |

Related counters the dashboard does not tile but that are useful for the same panels: `increase(halogen:cache_prompt_tokens_saved_total[1m])`, `increase(halogen:queue_waited_total[1m])`, `increase(halogen:queue_wait_seconds_total[1m])`, `increase(halogen:queue_gave_up_total[1m])`, `increase(halogen:draft_list_tokens_total[1m])`, `increase(halogen:draft_list_misses_total[1m])`, `increase(halogen:strict_tool_requests_total[1m])`, `increase(halogen:strict_tools_unenforced_total[1m])`, and `increase(halogen:adapter_requests_total[1m])` (the last one has an `adapter` label).

## Status and restarts

The dashboard's Up / Degraded / Down status comes from scrape failures and `/health`. A close Prometheus equivalent:

```promql
min(halogen:engine_up) == 0 or absent(halogen:engine_up) or min(up{job=~".*halogen.*"}) == 0
```

Degraded, while the engine is still up, can be keyed off stale cache numbers, pool pressure, or long queue waits:

```promql
min(halogen:engine_up) == 1 and (max(halogen:cache_stats_age_seconds) > 30 or max(halogen:kv_pool_waiting_for_room) > 0 or max(halogen:queue_wait_longest_seconds) > 1)
```

Restart events and scrape-level health:

```promql
resets(halogen:requests_total[30d])
```

Use the scrape target's `up` series for transport-level failures; Halogen's own liveness is `halogen:engine_up`. `halogen:build_info` carries `version`, `engine_version`, and `model` labels, which cover the dashboard's version/model readout.

## Grafana panel queries

Throughput:

```promql
rate(llamacpp:tokens_predicted_total[1m])
rate(llamacpp:prompt_tokens_total[1m])
rate(halogen:requests_total[1m]) * 60
```

Speed:

```promql
llamacpp:predicted_tokens_seconds
llamacpp:prompt_tokens_seconds
halogen:busy_for_seconds
```

Cache:

```promql
rate(halogen:prompt_tokens_cached_total[1m]) / (rate(halogen:prompt_tokens_cached_total[1m]) + rate(llamacpp:prompt_tokens_total[1m]))
rate(halogen:cache_hits_total[1m]) / (rate(halogen:cache_hits_total[1m]) + rate(halogen:cache_misses_total[1m]))
rate(halogen:cache_evicted_total[1m]) * 60
halogen:cache_disk_bytes / halogen:cache_disk_budget_bytes
```

KV and queue:

```promql
llamacpp:kv_cache_usage_ratio
halogen:kv_pool_reserved_tokens / halogen:kv_pool_positions
llamacpp:requests_deferred
halogen:queue_wait_longest_seconds
rate(halogen:queue_gave_up_total[1m])
```

GPU stalls (host memory compaction/reclaim holding the engine's GPU queues):

```promql
rate(halogen:gpu_queues_evicted_seconds_total[1m])
```

## Not available from /metrics

These dashboard fields come from `/health`, `/cache`, the log, or its own event history and have no Prometheus equivalent:

- NPU status, loaded models, passes, and contexts.
- Uptime since last restart and the exact restart/outage marker times (approximated by `resets()` above).
- Recent requests list and per-request prompt/answer counts.
- Slot count, context window, chat template, and the `supported` fields from `/health`.
- Prompt-cache details only present in the full `/cache` JSON, such as region movement and cold resorts.

## Caveats

- Metric names contain colons. That is valid in Prometheus metric names and PromQL selectors; do not rewrite them to underscores.
- The two windowed speed gauges are only meaningful when Prometheus is the sole reader of `/metrics`.
- Cache counters reflect the engine's last background report; check `halogen:cache_stats_age_seconds` before trusting a sudden change in cache panels.
- When no request has completed inside the scrape window, the speed gauges fall to zero. Use the counter-derived rates for long-range averages.
