# Live validation

No real model, embedding or arXiv quality result is implied by a fixed demo or a green engineering suite. Configure `RF_LLM_BASE_URL`, `RF_LLM_API_KEY`, `RF_LLM_MODEL` and `RF_CONTEXT_WINDOW` in a private environment. Run development live evaluation first, inspect every false support and inconclusive result, freeze the verifier strategy, then run holdout. The reports preserve the dataset denominator, source hashes and verifier/source strategy versions. Missing prices or provider usage remain null.

Real model and embedding calls can incur provider charges. No credentials are bundled. The current environment has no configured live provider; quality and live smoke results are explicitly not_run.
