# ama-factory
공장 VM 앱(`factory/`), 중앙 수신(`ingest/`), 시험(`tests/`). 모든 자료는 합성(mode=SIMULATED).
- 로컬 시험: `ingest_app.py`(PORT·FACTORY_KEYS) 와 `factory_app.py`(AMAFACTORY_INGEST·AMAFACTORY_DATA·AMAFACTORY_KEY)를 띄우고 `tests/test_ingest.py <url> <key_id> <key> <site>` 실행.
- 배포: `operations/krdeploy3/deploy_ingest.sh vX.Y`, `deploy_factory_vm.py <rg> <vm> <site> <이름> <key_id> <ingest_url>`. 키는 `/srv/ama/hermes/secrets/factory-keys.json`(저장소 밖).
- 결정·한계: `knowledge/decisions/factory-backend-20261030/DECISION.md`
