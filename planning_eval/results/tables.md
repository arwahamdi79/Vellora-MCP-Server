
### Table A — Top-level decomposition (same request type, both methods)

| Method | Task success | Mean grounded score | Avg LLM calls | Avg tokens | Avg latency (s) | Est. cost/run |
|---|---|---|---|---|---|---|
| dynamic | 0/1  (3 errored, excluded) | 0.0 | 18 | 55523 | 42.2 | $0.01351 |
| static | 0/2  (2 errored, excluded) | 0.0 | 22 | 68820 | 114.1 | $0.01781 |

Cases covered (4): DEC-DYNAMIC-01, DEC-DYNAMIC-02, DEC-DYNAMIC-03, DEC-DYNAMIC-04
Model(s): mistral-small-latest

**5 run(s) aborted on provider errors and are excluded from the averages above.** Re-run with `--retry-errors` before citing this table:
  - DEC-DYNAMIC-02 [dynamic]: HTTPStatusError: Error response 503 while fetching https://api.mistral.ai/v1/chat/completi
  - DEC-DYNAMIC-03 [dynamic]: HTTPStatusError: Error response 503 while fetching https://api.mistral.ai/v1/chat/completi
  - DEC-DYNAMIC-03 [static]: HTTPStatusError: Error response 503 while fetching https://api.mistral.ai/v1/chat/completi
  - DEC-DYNAMIC-04 [dynamic]: HTTPStatusError: Error response 503 while fetching https://api.mistral.ai/v1/chat/completi
  - DEC-DYNAMIC-04 [static]: HTTPStatusError: Error response 503 while fetching https://api.mistral.ai/v1/chat/completi


### Table B — Planning algorithms on the t5_plan sub-task

| Method | Task success | Mean grounded score | Avg LLM calls | Avg tokens | Avg latency (s) | Est. cost/run |
|---|---|---|---|---|---|---|
| lats_grounded | 2/4 | 0.719 | 7.8 | 13447 | 21.2 | $0.00384 |
| lats_ungrounded | 0/4 | 0.406 | 3 | 4718 | 10.0 | $0.00143 |
| plan_and_solve | 0/4 | 0.75 | 1 | 1749 | 5.5 | $0.00063 |
| tree_of_thoughts | 0/4 | 0.875 | 8.8 | 13773 | 48.7 | $0.00387 |

Cases covered (4): GRD-01, PLN-LOOKAHEAD-02, PLN-LOOKAHEAD-03, PLN-LOOKAHEAD-04
Model(s): mistral-small-latest


### Table C — Self-correction

| Method | Task success | Mean grounded score | Avg LLM calls | Avg tokens | Avg latency (s) | Est. cost/run |
|---|---|---|---|---|---|---|
| reflexion_mem0 | 0/2 | 0.875 | 6 | 8928 | 13.4 | $0.00244 |
| reflexion_mem2 | 1/2 | 0.938 | 4.5 | 7231 | 11.1 | $0.00194 |
| self_refine | 0/2 | 0.875 | 3 | 6181 | 9.8 | $0.00177 |

Cases covered (2): RFX-01, RFX-02
Model(s): mistral-small-latest


### Grounded vs ungrounded LATS

Grounded  : 2/4 success, mean score 0.719, 7.8 calls
Ungrounded: 0/4 success, mean score 0.406, 3 calls

Both rows are scored by the SAME grounded environment; only the signal guiding the search differs.