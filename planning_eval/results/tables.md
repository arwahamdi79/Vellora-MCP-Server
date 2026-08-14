
### Table A — Top-level decomposition (same request type, both methods)

| Method | Task success | Mean grounded score | Avg LLM calls | Avg tokens | Avg latency (s) | Est. cost/run |
|---|---|---|---|---|---|---|
| dynamic | 3/8  (4 errored, excluded) | 0.703 | 13 | 32942 | 774.7 | $0.00829 |
| static | 4/9  (3 errored, excluded) | 0.736 | 18.7 | 54268 | 81.8 | $0.01448 |

Cases covered (8): DEC-DYNAMIC-01, DEC-DYNAMIC-02, DEC-DYNAMIC-03, DEC-DYNAMIC-04, DEC-STATIC-01, DEC-STATIC-02, DEC-STATIC-03, DEC-STATIC-04
Model(s): mistral-small-latest

**7 run(s) aborted on provider errors and are excluded from the averages above.** Re-run with `--retry-errors` before citing this table:
  - DEC-DYNAMIC-01 [dynamic]: HTTPStatusError: Error response 503 while fetching https://api.mistral.ai/v1/chat/completi
  - DEC-DYNAMIC-01 [static]: HTTPStatusError: Error response 503 while fetching https://api.mistral.ai/v1/chat/completi
  - DEC-DYNAMIC-02 [dynamic]: HTTPStatusError: Error response 503 while fetching https://api.mistral.ai/v1/chat/completi
  - DEC-DYNAMIC-03 [dynamic]: HTTPStatusError: Error response 503 while fetching https://api.mistral.ai/v1/chat/completi
  - DEC-DYNAMIC-03 [static]: HTTPStatusError: Error response 503 while fetching https://api.mistral.ai/v1/chat/completi
  - DEC-DYNAMIC-04 [dynamic]: HTTPStatusError: Error response 503 while fetching https://api.mistral.ai/v1/chat/completi
  - DEC-DYNAMIC-04 [static]: HTTPStatusError: Error response 503 while fetching https://api.mistral.ai/v1/chat/completi


### Table B — Planning algorithms on the t5_plan sub-task

| Method | Task success | Mean grounded score | Avg LLM calls | Avg tokens | Avg latency (s) | Est. cost/run |
|---|---|---|---|---|---|---|
| lats_grounded | 2/14 | 0.393 | 9.4 | 15504 | 25.8 | $0.00445 |
| lats_ungrounded | 0/14 | 0.232 | 2.4 | 3627 | 6.7 | $0.00108 |
| plan_and_solve | 0/14 | 0.589 | 1 | 1741 | 4.9 | $0.00063 |
| tree_of_thoughts | 1/14 | 0.866 | 8.9 | 13595 | 28.5 | $0.00379 |

Cases covered (10): GRD-01, GRD-02, GRD-03, GRD-04, PLN-LOOKAHEAD-02, PLN-LOOKAHEAD-03, PLN-LOOKAHEAD-04, RFX-01, RFX-02, RFX-03
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

Grounded  : 2/14 success, mean score 0.393, 9.4 calls
Ungrounded: 0/14 success, mean score 0.232, 2.4 calls

Both rows are scored by the SAME grounded environment; only the signal guiding the search differs.