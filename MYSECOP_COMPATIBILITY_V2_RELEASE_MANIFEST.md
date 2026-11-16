# MySECOP Compatibility V2 — Manifiesto RC1

Fecha de preparación: 16 de noviembre de 2026. Estado: **snapshot local**, sin commit/tag/publicación.

Nombre propuesto: `mysecop-compatibility-v2-rc1`. Rama `develop`; base Git `cac56d02c9f07690bc0ed04a96350cb5e8fa3377`.

Identidad del payload SHA-256: `0475bffbe701d87abf352acacc1d7350671624b55c2578971568d2636ae9fce7`.

Archivo local: `/private/tmp/mysecop-rc-final-20261116/mysecop-compatibility-v2-rc1-source.tar.gz`. SHA-256 del archivo: `4ef4d23b71aa35703ce185d05e29614493839ceec36ad0faf44d8ed00f3dcd9c`.

Manifiesto JSON: `/private/tmp/mysecop-rc-final-20261116/manifest.json`. Backup previo independiente: `/private/tmp/mysecop-rc-preparation-20261116/source-backup.tar.gz`.

La identidad se calcula como SHA-256 de las líneas UTF-8 ordenadas `modo sha256 ruta\n` de la tabla siguiente. Incluye código completo, assets públicos comerciales, lockfiles, catálogo UNSPSC, fixtures explícitos y documentación. Excluye este manifiesto para evitar autorreferencia. El tar usa metadatos normalizados y gzip mtime=0; se verificaron todos los miembros sin extraerlos. Regenerar con `backend/.venv/bin/python backend/scripts/prepare_release_candidate.py --output /private/tmp/mysecop-rc-final-20261116` desde la raíz. No conecta a servicios ni crea referencias Git.

## Archivos incluidos

La clasificación es por contenido y función, no atribución histórica de autor. Los archivos compartidos contienen varias fases. `HEAD` designa base comercial intacta; `untracked` está capturado en este paquete y debe incorporarse explícitamente a un commit futuro autorizado.

| Archivo | Git | Fase / alcance | Modo | SHA-256 |
|---|---|---|---|---|
| `.env.example` | modified | Compartido 1.1/1.2/1.3/2/2.1 | 0644 | `21d22c2e6e90589ac49dc855b09e488298633e17657fccd7d244302b80282fa0` |
| `.github/workflows/ci.yml` | modified | Consolidación RC: seguridad, dependencias o entrega | 0644 | `3e667f9d34abe9b3071bc8ef81e0a0d9138b8a03b05cbd5ca1f46f9b517c293e` |
| `.github/workflows/deploy-development.yml` | HEAD | Base comercial preexistente, sin cambios | 0644 | `f76fb3f31e849cad401bd946eebfab453557deaf4c854b1177039893c2c9d633` |
| `.github/workflows/deploy-reusable.yml` | HEAD | Base comercial preexistente, sin cambios | 0644 | `3e1314831d9dde7360e88a33ef5c832d6f79da3a6334e34c2a99a9b1c6902134` |
| `.github/workflows/deploy-staging.yml` | HEAD | Base comercial preexistente, sin cambios | 0644 | `6ec24eca29497b29f6b34acc290c0bf76c69aacb754ca77da3bec8d94b7476cc` |
| `.github/workflows/deploy.yml` | HEAD | Base comercial preexistente, sin cambios | 0644 | `f9faca1d33bc4702627be8dd942ec7b2f951e281eac43022a43c145c4e614df2` |
| `.gitignore` | modified | Consolidación RC: seguridad, dependencias o entrega | 0644 | `df9ce408bc9ab4f4c82bb1b857a23897d6912d02849f3af5141a7197892b5343` |
| `AUDITORIA_MOTOR_COMPATIBILIDAD_MYSECOP.md` | untracked | Documentación histórica de fases 1–2.1 | 0644 | `d105bb0953f6ee6fbadb39e42bef79e1efde12419c3ff0cea0ba5f785e551ceb` |
| `IMPLEMENTACION_COMPATIBILITY_ENGINE_V2_FASE1.md` | untracked | Documentación histórica de fases 1–2.1 | 0644 | `0c22738389350f067509ccd2a6167a8c380e6f85f74275553801a68c1367d9d9` |
| `MYSECOP_COMPATIBILITY_ENGINE_V2_FASE1_2.md` | untracked | Documentación histórica de fases 1–2.1 | 0644 | `0a2f6f41204f9aef67837c32a239966bbdf9b2d7b0fbf549330386bb61d1ba4d` |
| `MYSECOP_COMPATIBILITY_ENGINE_V2_FASE1_3.md` | untracked | Documentación histórica de fases 1–2.1 | 0644 | `c299590872d4c2c85d6d87cf2c28e98c5769a177d8143c446f55dcb17dc9018e` |
| `MYSECOP_COMPATIBILITY_ENGINE_V2_FASE2.md` | untracked | Documentación histórica de fases 1–2.1 | 0644 | `7f25415822e2d9ba183cdecc391f4a838fd0460f4917a774b73f0dec53e9f013` |
| `MYSECOP_COMPATIBILITY_ENGINE_V2_FASE2_1.md` | untracked | Documentación histórica de fases 1–2.1 | 0644 | `695602d8708b967ed54986edde31054a7776956bfc9392245b37dec71b64d3ac` |
| `MYSECOP_COMPATIBILITY_V2_DEV_RUNBOOK.md` | untracked | Consolidación RC: seguridad, dependencias o entrega | 0644 | `16ffdd7b3613f3a36ce67314f9445d775440985a28133642b3fcf40ea5986e54` |
| `MYSECOP_COMPATIBILITY_V2_RELEASE_CANDIDATE.md` | untracked | Consolidación RC: seguridad, dependencias o entrega | 0644 | `4f03c54da995f5fa4b9cc44a470ba9db11ad8d4e550e507a9a06c0f58a3092b3` |
| `MYSECOP_COMPATIBILITY_V2_RELEASE_VALIDATION.json` | untracked | Consolidación RC: seguridad, dependencias o entrega | 0644 | `06fa6063a623cb64b912335b4edfe527b359cf520b15bf9049d7213a0c3fe8ba` |
| `MYSECOP_FASE1_1_CORRECCION_BLOQUEOS.md` | untracked | Documentación histórica de fases 1–2.1 | 0644 | `2f4b11079e158972fac05efe8ce61e66c5d23e24d114c2fbfbf622689ee6a469` |
| `MYSECOP_FASE1_1_SINCRONIZACION_INCREMENTAL.md` | untracked | Documentación histórica de fases 1–2.1 | 0644 | `e494f3ef39e34b133dd8f4d7681e97d5a28e72a3b99004e7b9cbf79065936546` |
| `README.md` | HEAD | Base comercial preexistente, sin cambios | 0644 | `f36281de92b2d5a1c38721d9ed2ffc62cc7453a9e263b925814eb1f38754cf0f` |
| `VALIDACION_MYSECOP_FASE1_1.md` | untracked | Documentación histórica de fases 1–2.1 | 0644 | `15c9407c2e0c32f24f78369ec323a7cea399d32f022beef794c8c01d39a3e8e7` |
| `backend/.dockerignore` | untracked | Consolidación RC: seguridad, dependencias o entrega | 0644 | `0d9138e8c756e70f9d089e1fcca6ed9f68962c3aeb92b93a1e7d7331b03b4eba` |
| `backend/Dockerfile` | modified | Consolidación RC: seguridad, dependencias o entrega | 0644 | `34dc37c414722e97397647bf157f0932d8ba36f673c0bfc2cec04fc2a4569969` |
| `backend/alembic.ini` | HEAD | Base comercial preexistente, sin cambios | 0644 | `62d89673d271d5f4eef089cfb8849b310ef34b58b9f036c225f7baed0f038608` |
| `backend/alembic/env.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `402d03caac3384c20b74ebb0ba9268debe207bc3782cf4c0c6abe7855b73ee82` |
| `backend/alembic/versions/0001_initial.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `8635404b89c02e310c99e762f429d1010c310ec367dc89a09d99798d70957d2a` |
| `backend/alembic/versions/0002_mercadopago_subscription.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `3bb680a57da70bfae7eeadb383fc15f215a2dac438b63fa7b33809ac7cf3420a` |
| `backend/alembic/versions/0003_password_reset.py` | modified | 1.1 compatibilidad histórica de migraciones | 0644 | `bc0462c920904cbbf64135939d222085ace320673f8d7625401b900d73281591` |
| `backend/alembic/versions/0004_sync_usage.py` | modified | 1.1 compatibilidad histórica de migraciones | 0644 | `6f3b802a1b8c0c81a13ab8af3b59d928817362c717313c5ca5c0b28d888453ae` |
| `backend/alembic/versions/0005_sync_run_user.py` | modified | 1.1 compatibilidad histórica de migraciones | 0644 | `32b9140243713ea9049f7dcbc28d9845c385f370a4f10a577df734488bc27623` |
| `backend/alembic/versions/0006_admin_presence.py` | modified | 1.1 compatibilidad histórica de migraciones | 0644 | `b1e5edf86849d33decae105e6e2a32c2ab2bc9a2b558e168fdcb0336489d7d3a` |
| `backend/alembic/versions/0007_alert_email_to.py` | modified | 1.1 compatibilidad histórica de migraciones | 0644 | `119d0e8c5f5f96942ea1a08b10099d1924470ad441106ba59114f027ebec407b` |
| `backend/alembic/versions/0008_last_opportunity_search.py` | modified | 1.1 compatibilidad histórica de migraciones | 0644 | `fda0b602dea3ba92d2e405f45deca986673cc66f46fadf45843887ce982188a5` |
| `backend/alembic/versions/0009_landing_visits.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `7fcb836a7d90262542d599189b56f0d86382e2faa4c0c7ce5fb180d5c93274f9` |
| `backend/alembic/versions/0010_sync_cursor.py` | untracked | 1.1 sincronización incremental y SECOP I | 0644 | `0cb156de85cdf6410e9d55e5e5e81f39f0c21a89510c876fb77a70899340ab66` |
| `backend/alembic/versions/0011_match_jobs.py` | untracked | 1.2 recálculo / 1.3 estabilización | 0644 | `14390aa148ea6f61ad833a0e386b14cfc7402145c5312c306c15b8c90fe3a8ef` |
| `backend/alembic/versions/0012_failed_match_inputs.py` | untracked | 1.2 recálculo / 1.3 estabilización | 0644 | `7a84502e490fed505c45606d763936ecec4bb038b117aaa1efdad16e248abe7f` |
| `backend/alembic/versions/0013_compatibility_shadow.py` | untracked | 2 modelo V2 / guardias 2.1 | 0644 | `f53797111e69c810f8a79dc655cb77055d13011d4a9e80ef68906b2710ce5261` |
| `backend/alembic/versions/0014_evaluation_platform.py` | untracked | 2.1 evaluación (plantillas ranking anteriores: 1/2) | 0644 | `de5e064344d29e1fbb0f71a147456708c2a0df2939693de1c84d5f2c18194101` |
| `backend/app/__init__.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `backend/app/agents/__init__.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `backend/app/agents/pliegos.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `a5857a45641937d0dfccfe278a7699ede2ce8b0a684cefe9b9ae2891efe923ab` |
| `backend/app/agents/viability.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `f7026e4f4abeac21a350055b7ccf7ac3d409bc8966b45926ac9a0c81a09cf726` |
| `backend/app/compatibility_schemas.py` | untracked | 2 modelo V2 / guardias 2.1 | 0644 | `1009db3e009d1acd98def9df0c8fcd1bf61e2056bf635ffeda30dacd914e48da` |
| `backend/app/core/__init__.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `backend/app/core/config.py` | modified | Compartido 1.1/1.2/1.3/2/2.1 | 0644 | `b879040a6057d4ccdd2a36149b03f7444be1c07d5daba4e6d01f668971406bcd` |
| `backend/app/core/runtime_errors.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `47c59a55a7fcce379d7a0510300ab069a9c031822dfce4726871fd68ff653057` |
| `backend/app/core/security.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `d5778883e50ee030c70f019460a6beff92bb0b8ab88acff087cdea6b131a7129` |
| `backend/app/data/unspsc_v14_codes.json` | untracked | 2 modelo V2 / guardias 2.1 | 0644 | `8289f93c4a474dc304b423830e1cfd906a35e02158a1ca6a977b73addcfeedca` |
| `backend/app/db/__init__.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `backend/app/db/base.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `bfc26d456bb169f0c6b72cd61574ab7cb701307485e7d2329ca1ccd273ecaa54` |
| `backend/app/db/models.py` | modified | Compartido 1.1/1.2/1.3/2/2.1 | 0644 | `dec79f44ef8f5efcc6a99abe356bd9a943d3ee0e7057ffb96c0e208a781eab1d` |
| `backend/app/db/session.py` | modified | Compartido 1.1/1.2/1.3/2/2.1 | 0644 | `71360d73e805239cf23a342954ea31a2ea5eb9b6df86495a182c39dc87e89895` |
| `backend/app/evaluation_schemas.py` | untracked | 2.1 evaluación (plantillas ranking anteriores: 1/2) | 0644 | `fbad6bab1a7f476f6fa11ce78900d32dfd6aa81614382a7a4597fdce43f46d46` |
| `backend/app/main.py` | modified | Compartido 1.1/1.2/1.3/2/2.1 | 0644 | `148b7675998cddcd9f2579ee5bef7891d7ace518e35ec8552a5c032f455bf6f6` |
| `backend/app/routers/admin.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `1365917782e3dd5a8b60969c8635ff8d3f56f660e0e0e68a66556fd4a3c894e2` |
| `backend/app/routers/agents.py` | modified | 1/1.2 integración comercial + corrección RC de análisis privados | 0644 | `5db6afc306ecf755fd8f352bbc50cd4ebb7891032861b5b7ded0a387403eae8a` |
| `backend/app/routers/alerts.py` | modified | 1 filtros, vigencia y alertas | 0644 | `72cf4f0b2e4e3b79d0d40984a3d55da5512a92f214f89ed8bb250d19951d2714` |
| `backend/app/routers/auth.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `0f7f151a5630b4140dd488ec4bae48e8791187d53597be9ad333a1d8520fe89f` |
| `backend/app/routers/billing.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `722c3b399444a165773fe9c407b4093ea6e86c9a0ba343df72abf6066c7e0d49` |
| `backend/app/routers/companies.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `ef365364a9c36f93f0d7537b8fe73204272c532f49795179f559a49ed7f0be04` |
| `backend/app/routers/compatibility.py` | untracked | 2 modelo V2 / guardias 2.1 | 0644 | `e20fee1c942291056003204b7da928fc3344199b2651ec3757f6fef70cfdbe3f` |
| `backend/app/routers/contact.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `349c8766c364357a287352c5cc3994d5110c4eb7354025255a928c52e1118761` |
| `backend/app/routers/debug.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `fb208a03ee1eeb2ef6bedc2a18a06ab0e1d6e8f79490f0c8068ccbe9e5db2cc8` |
| `backend/app/routers/documents.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `be4b7108502f136a0ef029c77df2a1c3a58ef672218ea36bf501b2e8fe2e33ee` |
| `backend/app/routers/evaluation.py` | untracked | 2.1 evaluación (plantillas ranking anteriores: 1/2) | 0644 | `c6a61036ba80bd0b539c798df323373293051d94f1d7c5aa4b7e0c61e59f4f57` |
| `backend/app/routers/matches.py` | untracked | 1.2 recálculo / 1.3 estabilización | 0644 | `24b0bed803bf051316b3fb4523b4da1c5e8db8ae530cc83d94b60cd4a0f86206` |
| `backend/app/routers/opportunities.py` | modified | 1/1.2 integración comercial + corrección RC de análisis privados | 0644 | `c0a19831131e6d3014b7d4c492cf67a17834ad4f90fd020ae3200a93a712d62c` |
| `backend/app/routers/profile.py` | modified | 1/1.2/1.3 integración y regresión | 0644 | `6bcc7e5439df674dd82a0bc33474650bba3a49173c2712537942c1cce7b3ddef` |
| `backend/app/routers/sync.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `5d308bd59070be5815320c1fcfac7caba0b26abd38efe7a29239576da89127c5` |
| `backend/app/schemas.py` | modified | Compartido 1.1/1.2/1.3/2/2.1 | 0644 | `0d080ecdb451669ededb90599d030a46e9f2d488feb3f5d1b028465a3122cba2` |
| `backend/app/services/__init__.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `backend/app/services/alerts.py` | modified | 1/1.2 integración comercial + corrección RC de análisis privados | 0644 | `9911b018e853bb6884d169b308d4366118cf9cc44f3286d352d2a51a8df7c4a4` |
| `backend/app/services/audit.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `c0b27bc3406a87a71adaa1b8100263fa8f4b7a7729ccf48ca5b2e8d3c9fcdd1d` |
| `backend/app/services/compatibility_documents.py` | untracked | 2 modelo V2 / guardias 2.1 | 0644 | `2ec28618b194179208cfb7660b47b5bc5f2268952b162313aea4c9506ae1091f` |
| `backend/app/services/compatibility_evaluation.py` | untracked | 2.1 evaluación (plantillas ranking anteriores: 1/2) | 0644 | `b601694734eaca7e66487a42f2e7681b5de96d001bf36febce88d255d6b34d35` |
| `backend/app/services/compatibility_shadow.py` | untracked | 2 modelo V2 / guardias 2.1 | 0644 | `fa85a65f80515d9f5ff489fc366b794d42c8d8e966eb4fed7b746d2f15ab02de` |
| `backend/app/services/compatibility_unspsc.py` | untracked | 2 modelo V2 / guardias 2.1 | 0644 | `93ceb12ddaffa4f6dc24a6c151059c9c62933beb0ce7cc7b7ddb48f83b25ab90` |
| `backend/app/services/compatibility_v2.py` | untracked | 2 modelo V2 / guardias 2.1 | 0644 | `c15c69be0d824e652001f3bc65c3c40d6bf976a3fc088d50b1bc73923f00ce04` |
| `backend/app/services/demo.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `0cd4aa9461c3b3fdd8f6bc04cbdc5bcdbdcab4b703504ffa3c00331ba555aa74` |
| `backend/app/services/eligibility.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `ab12f80c8bc9bc60c30fafecba0f8005386802daeb5cc109766b0105bf391892` |
| `backend/app/services/embeddings.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `a7bc584c539d14b35268c3f83b7313f6d49bb7dbe441df5927d7611bc50788b0` |
| `backend/app/services/evaluation_guard.py` | untracked | 2.1 evaluación (plantillas ranking anteriores: 1/2) | 0644 | `3250258322227c77e5187aac42227c7265f96754bd6be59ac9e337bc832cea86` |
| `backend/app/services/evaluation_platform.py` | untracked | 2.1 evaluación (plantillas ranking anteriores: 1/2) | 0644 | `0c5bb2f844a374f2cf8cf537bf41b8acb1d07838e7c58eae2400335d73a09a9e` |
| `backend/app/services/evaluation_reporting.py` | untracked | 2.1 evaluación (plantillas ranking anteriores: 1/2) | 0644 | `32fca4448c6c9b6a4843a17394fae20db60c2f02df489170c293507a226eee65` |
| `backend/app/services/evaluation_sampling.py` | untracked | 2.1 evaluación (plantillas ranking anteriores: 1/2) | 0644 | `86e5e236a46a2b6f297b2bd31fa77709c9adf22c24996e06bdecbe23067971f3` |
| `backend/app/services/evaluation_semantic.py` | untracked | 2.1 evaluación (plantillas ranking anteriores: 1/2) | 0644 | `4fcee64afb0222a55e9c8d6fdde85d207bb04448cba1805c881b091f854c5a4c` |
| `backend/app/services/exporter.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `9ec2b37b8fd30eabd5553e88526f216728f5e70391163550f0216cb309906dd3` |
| `backend/app/services/ingest.py` | modified | 1.1 sincronización incremental y SECOP I | 0644 | `a509e4697e7209f66351a8fc12599c769dfde01a6465456f06a5660ee8e1c22a` |
| `backend/app/services/match_execution.py` | untracked | 1.2 recálculo / 1.3 estabilización | 0644 | `31e93ce02650e98a264063ed17822ff26787269046ec5a034cd1fe54dcb28c03` |
| `backend/app/services/match_jobs.py` | untracked | 1.2 recálculo / 1.3 estabilización | 0644 | `82fb61cc5f00e413938bd727fbc14d37246e0ab2da4eb0f2a63ba8c2f4a7cbc1` |
| `backend/app/services/match_metrics.py` | untracked | 1.2 recálculo / 1.3 estabilización | 0644 | `d97d5846fc590c9e04cad4f1b50eb4232b256a328a500e3ea13eeac5454de540` |
| `backend/app/services/match_versions.py` | untracked | 1.2 recálculo / 1.3 estabilización | 0644 | `4bf9396276ece34a27c9dbc6d23cf589d95b84388aab6b243d7659dcaac37d4f` |
| `backend/app/services/matcher.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `6d9b87658b6bd23e049c7047d3f1a8238b88922f6ee4ccfb6274a38b78d715e6` |
| `backend/app/services/nlq.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `d06f8c7886b9bdf4869eea2ab1907c03b97599ede0662833bc90fa2ea1af336a` |
| `backend/app/services/notifier.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `e44721d2192cfd250d8b3a24d5ee96a9b967881747a31b3e6125e6c7ad622b9b` |
| `backend/app/services/opportunity_filters.py` | untracked | 1 filtros, vigencia y alertas | 0644 | `4514d63a3614037d2122313ce8156b294fd91ad6e915910f11dd965f47520a8a` |
| `backend/app/services/opportunity_status.py` | untracked | 1 filtros, vigencia y alertas | 0644 | `2a5f7fdbb4e66134e5b1b21d0219e410b61be334f0e3ef84f495dfae64371f78` |
| `backend/app/services/quota.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `a702178e5bd2a85448846c2f50e6db249456805cbd8d9f55607d74a7d537d6d1` |
| `backend/app/services/ranking_evaluation.py` | untracked | 2.1 evaluación (plantillas ranking anteriores: 1/2) | 0644 | `80f4fc2f2857d60c29000e2cab49ef1909f9e423f78d12e47d30c15a23b81583` |
| `backend/app/services/secop_client.py` | modified | 1.1 sincronización incremental y SECOP I | 0644 | `b416593c1226af286bd2ecc370509f9d1fc8b3e775369cdf142968019848655a` |
| `backend/app/workers/celery_app.py` | modified | Compartido 1.1/1.2/1.3/2/2.1 | 0644 | `bc8e0260ed0a20ae87ff40aedbc6214230d982c00cf2cbc83715a8f9e0a13176` |
| `backend/app/workers/tasks.py` | modified | Compartido 1.1/1.2/1.3/2/2.1 | 0644 | `23a9d742404d9725becb280cc9b668d25daa84301a7e23248e7fd1f319b62511` |
| `backend/constraints-release-candidate.txt` | untracked | Consolidación RC: seguridad, dependencias o entrega | 0644 | `e70c965c5024917d642f608ffab42b9e3b2045336a3b4c9823fc78eed11f5204` |
| `backend/evaluation/README.md` | untracked | 2.1 evaluación (plantillas ranking anteriores: 1/2) | 0644 | `cf834faa7d4e59baa46964ec987290d691f766a2df4991ff6a96116b8f4acfb5` |
| `backend/evaluation/baseline-status.json` | untracked | 2.1 evaluación (plantillas ranking anteriores: 1/2) | 0644 | `6c3042dc590a0d7452c80d937260e0a25a3c1de30119809cdb4499cd16ac8cdf` |
| `backend/evaluation/judgments.blind.template.jsonl` | untracked | 2.1 evaluación (plantillas ranking anteriores: 1/2) | 0644 | `3f8f2b2161e7fc793eebeeb65a470c2602ab11d80dba58212e72c381fceba0ef` |
| `backend/evaluation/phase2-labeling.md` | untracked | 2.1 evaluación (plantillas ranking anteriores: 1/2) | 0644 | `46103b946106f2068b0984a257b369f5cb765b7250a55dfef61c144654a8685f` |
| `backend/evaluation/phase2.human-labels.template.jsonl` | untracked | 2.1 evaluación (plantillas ranking anteriores: 1/2) | 0644 | `cce6b1b2b47f829c8b48d27788fe4eecebfba4bff1d6475831d44649f7cbf3f5` |
| `backend/evaluation/phase2.queries.template.jsonl` | untracked | 2.1 evaluación (plantillas ranking anteriores: 1/2) | 0644 | `88dbfcc6be9312d42366f82df1fc46f3e5b56cdbd674fb98467c4cfbe4787536` |
| `backend/evaluation/phase21/pilot-synthetic-100.json` | untracked | 2.1 evaluación (plantillas ranking anteriores: 1/2) | 0644 | `e5f235beb112235b03b3abc12686834bd34015ac9a85cb9807580f5fe417f6ca` |
| `backend/evaluation/predictions.template.jsonl` | untracked | 2.1 evaluación (plantillas ranking anteriores: 1/2) | 0644 | `8bad6f3b08887fe1d96a894ea94ae2b3a598cc8829c92713598f97ff96a4c7bb` |
| `backend/evaluation/queries.template.jsonl` | untracked | 2.1 evaluación (plantillas ranking anteriores: 1/2) | 0644 | `d41cac5e574db21e8b311c47954db82c8c524faa2c6d3689db89f38e46448436` |
| `backend/requirements-isolated-tests.txt` | untracked | 1/1.2/1.3 integración y regresión | 0644 | `030dc72fd400ef8d5925472f0f34a6bac5a8b9b05f52de36a1cb743129abe944` |
| `backend/requirements.txt` | HEAD | Base comercial preexistente, sin cambios | 0644 | `1f7377cc60b9833f77d9f875a11728713060eadc21798ec24574f5a28b84c6bf` |
| `backend/scripts/benchmark_compatibility_v2.py` | untracked | 2 modelo V2 / guardias 2.1 | 0644 | `4428ce5b57098125966c7a571c36db0a308734ccbdd2e8893741a118938fa58e` |
| `backend/scripts/benchmark_phase13.py` | untracked | 1.2 recálculo / 1.3 estabilización | 0644 | `7a81985ca078c99070f759de7e85d3f67b6a9a3cbae5aaa90da267c5ace87be0` |
| `backend/scripts/build_unspsc_catalog.py` | untracked | 2 modelo V2 / guardias 2.1 | 0644 | `9218367bb2626e79fd197170ea613ba0f455c338aabe19530c060805c200641f` |
| `backend/scripts/compare_compatibility.py` | untracked | 2 modelo V2 / guardias 2.1 | 0644 | `149b0b3ea391ff7ce515bc13bcc0b89c34d73fb91f1e3b19ad32c913b567db73` |
| `backend/scripts/e2e_evaluation_flow.py` | untracked | 2.1 evaluación (plantillas ranking anteriores: 1/2) | 0644 | `1ae2ebba2618e89dfaa24e098f432b7c32e9ab5b22ba01555dd47426597cafb8` |
| `backend/scripts/e2e_phase13.py` | untracked | 1.2 recálculo / 1.3 estabilización | 0644 | `a52ec6acbf72f2d29c1b31a5838357f2685eceffdda6849480347cc8be7647f8` |
| `backend/scripts/evaluate_ranking.py` | untracked | 1/2 evaluación de ranking y plantillas | 0644 | `a221ec2b855c768b90ab2bdaa119d00d366733ac7f4b7b5a45ef974762152f60` |
| `backend/scripts/evaluation_target.py` | untracked | 2.1 evaluación (plantillas ranking anteriores: 1/2) | 0644 | `8ace9327f8c1ad55d471d64312faf5c94a9502904f29d809cdcf0237e20c1863` |
| `backend/scripts/prepare_release_candidate.py` | untracked | Consolidación RC: seguridad, dependencias o entrega | 0644 | `10277ccc35bd64a0b36ec0834ff752f6dfc31a68a57623bfd8bd21d721a47561` |
| `backend/scripts/release_preflight.py` | untracked | Consolidación RC: seguridad, dependencias o entrega | 0644 | `f28a8018f0ff7442c9d8a85eb65b2321f70bf13ba2d035df009eb6721097e875` |
| `backend/scripts/seed_elite_dev.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `39874c5f3cacab60598bfcdf4bee76e2bfd1cab59d62345842e99593bd9622f9` |
| `backend/scripts/test_isolated_phase13.py` | untracked | 1.2 recálculo / 1.3 estabilización | 0644 | `ddbb4375f454fa68f771a64eb242d5d75b8f510758f40630626d0f2258371765` |
| `backend/scripts/test_isolated_postgresql.py` | untracked | 1/1.2/1.3 integración y regresión | 0644 | `9ec0ebd35d67e4dd987d47e79489f96dfedcd7e72c088c5fe4216cd494797c9a` |
| `backend/tests/conftest.py` | modified | Compartido 1.1/1.2/1.3/2/2.1 | 0644 | `2d5ee36ec55a3d81fda4c2b35e58650a53d4142da404b54632cbf3a0fb600f29` |
| `backend/tests/evaluation_test_support.py` | untracked | 2.1 evaluación (plantillas ranking anteriores: 1/2) | 0644 | `aa3e7f425b816be143e9ebef1db3a1e49b0f02a2fc0aa3095e09d87e8185ccfb` |
| `backend/tests/isolated_match_worker.py` | untracked | 1.2 recálculo / 1.3 estabilización | 0644 | `a4cccc7730f377c106857ea57ad1dc170e6edc56cff5ab19e1fac7efbda56276` |
| `backend/tests/match_test_support.py` | untracked | 1.2 recálculo / 1.3 estabilización | 0644 | `cf44db96ba355b61c3803adb724f81f2e69b0d0720629f1874c9423d8eaa103b` |
| `backend/tests/test_alerts.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `718a90e4334a479c579cf346523f5b3526ac88d583f51f84d47c6cdfd91f5f28` |
| `backend/tests/test_auth.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `496ad7eac48d9389ad8c09c8157c0289477d0b81543bbd6bf1cbe660b0b5c166` |
| `backend/tests/test_companies.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `fd5a00cd27ae081624593cf1104cb95562641f2ce76f8d16832f492991f985ac` |
| `backend/tests/test_compatibility_evaluation.py` | untracked | 2.1 evaluación (plantillas ranking anteriores: 1/2) | 0644 | `e9906660d7871648c77993c969d413df4c24553789198ef7ed7bf010f6b3f10e` |
| `backend/tests/test_compatibility_shadow.py` | untracked | 2 modelo V2 / guardias 2.1 | 0644 | `2d0eca50bb53f6ffbcc236b3a33858f669591b8abae06434fe75846e1c5f3405` |
| `backend/tests/test_compatibility_v2.py` | untracked | 2 modelo V2 / guardias 2.1 | 0644 | `003a0b2f1adf6ddabd39de751a03dd8dd992e85851dfd2fc6bc6b1568c3514a3` |
| `backend/tests/test_contacto.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `bbcff0f372646ede8bb9fe9d7368ed34ea9dde9004824a881778fbf364a6f91f` |
| `backend/tests/test_dashboard_ranking.py` | modified | 1/2 evaluación de ranking y plantillas | 0644 | `6a1d90048fe2d9b0c94707c06f929195842186851cfbd0be792e2c65efd51bc2` |
| `backend/tests/test_eligibility.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `c88c6bba8e750c57dec9f744ea97fcd77cd5ca265ffcd725e947a1e7472cf73f` |
| `backend/tests/test_evaluation_platform.py` | untracked | 2.1 evaluación (plantillas ranking anteriores: 1/2) | 0644 | `93e60f05c830a2d9e4325681ffdb4be2a795d5bcfc08cd57ea5aaeb6a79a192a` |
| `backend/tests/test_feedback.py` | modified | 1/1.2/1.3 integración y regresión | 0644 | `788865a474d0936a70f2af52818de92e0c5cbe735c70a44f52778c78e665a3cb` |
| `backend/tests/test_flow.py` | modified | 1/1.2/1.3 integración y regresión | 0644 | `e747cbf6aa2121e3a71c845aaf82fe4bf1eaaa9765dd94ae17131d47f924a9ca` |
| `backend/tests/test_incremental_sync.py` | untracked | 1.1 sincronización incremental y SECOP I | 0644 | `fbee2bedfa855e9c3ea1c6d3b12502ac37afa36d32723c6f2b0665717db8230e` |
| `backend/tests/test_landing_visits.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `1f5522584e905bb849c1eec040b3cd2a9a5d7945be1a0ec243111cfc714bdb89` |
| `backend/tests/test_match_api.py` | untracked | 1.2 recálculo / 1.3 estabilización | 0644 | `40e88cf2540618a291c51bca03eb1cece2ada03bdae2277c5837fb50b426664c` |
| `backend/tests/test_match_celery.py` | untracked | 1.2 recálculo / 1.3 estabilización | 0644 | `af254c02f65d3e0778bc5091b00cd7a4b687b9d0a9cd78020f4e8848143e5dbb` |
| `backend/tests/test_match_jobs.py` | untracked | 1.2 recálculo / 1.3 estabilización | 0644 | `a126cda7f8ec92ebc9a26de8a4bc36d6c4fbe54c0f39d1ace180f60a6a38c29d` |
| `backend/tests/test_match_stabilization.py` | untracked | 1.2 recálculo / 1.3 estabilización | 0644 | `dfbdf7bb299dda54f5e81c50259fa0f01e81ae42bc3881e651e2c14c29794ab3` |
| `backend/tests/test_matching.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `f9fc6eb41620fe7f6d224bed428ee4a7146f3a0927694bee0e3c72f222cc9644` |
| `backend/tests/test_nlq.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `22c0010c430125e91f5d35fabf2a5f217fa31177dc65d62ae6e896fd024b914a` |
| `backend/tests/test_opportunities_search.py` | modified | 1 filtros, vigencia y alertas | 0644 | `118bf3da1ac5deac0294eb6f1d4790628d8eb9961f36a9bdab0d17cf0aacc8c8` |
| `backend/tests/test_opportunity_status.py` | untracked | 1 filtros, vigencia y alertas | 0644 | `909f6d38cbff4a6a3d5326cbad14fdebd4e20faa6552a445694e3d1c4d5052a0` |
| `backend/tests/test_pliegos.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `c30f41f8b62e6783c9a80bc2131205ff0cca1146f4c1a73a6a2d287dbde6782d` |
| `backend/tests/test_postgresql_compatibility.py` | untracked | 2 modelo V2 / guardias 2.1 | 0644 | `1f3ca1ac23e7213ebb80dd1ac56bb04600be27ab9eb9deaa93b2dc2b602665c5` |
| `backend/tests/test_postgresql_evaluation.py` | untracked | 2.1 evaluación (plantillas ranking anteriores: 1/2) | 0644 | `4a71e04f6e507dd309cd8dc2a3a677a5fc3bd0e24cc3cb3ce03e5ae9504683a1` |
| `backend/tests/test_postgresql_matches.py` | untracked | 1.2 recálculo / 1.3 estabilización | 0644 | `ae3a4e137c0c15de19e50fb841ba56817db4957ea4028a8c89def21805a21dd2` |
| `backend/tests/test_postgresql_sync.py` | untracked | 1.1 sincronización incremental y SECOP I | 0644 | `bca3c1bc2faffbe2e1ed31697cd9d85f52b234a55fb149cf0ff8ea83ec4ec50e` |
| `backend/tests/test_profile.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `835c5b3d271d4b09724141981b8628b0945fd6b0e61b958959d61f1b90bc798e` |
| `backend/tests/test_quota.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `792ac97d6c21ef8715674287e6c314f4c98d5e54f039642e673aa7b42ade393c` |
| `backend/tests/test_ranking_evaluation.py` | untracked | 2.1 evaluación (plantillas ranking anteriores: 1/2) | 0644 | `61f37d5b90ef09bce7e2e2a39f30ebc8e687e42db84406ad46d4660a05edc219` |
| `backend/tests/test_redis_compatibility.py` | untracked | 2 modelo V2 / guardias 2.1 | 0644 | `715891b4a2c5c1af6d94067bbb62b9923e8ee79cdfcafbc84327ba40b0daa1ca` |
| `backend/tests/test_redis_evaluation.py` | untracked | 2.1 evaluación (plantillas ranking anteriores: 1/2) | 0644 | `382d716320b2d860caf91d0ad143488ebaa2a29926357e681217265f71291762` |
| `backend/tests/test_redis_operations.py` | untracked | 1.2 recálculo / 1.3 estabilización | 0644 | `b29d9cde756292fb103b3ea1461b5ad802500909f11898fb35872059d16ec2ee` |
| `backend/tests/test_release_security.py` | untracked | Consolidación RC: seguridad, dependencias o entrega | 0644 | `a692a6c598c818d089f263b732f51033c99ced3fda159d0575f9c736ff7ef3bd` |
| `backend/tests/test_secop.py` | modified | 1.1 sincronización incremental y SECOP I | 0644 | `5367a9fa02fcb66d395875fd382bf1966462920eec268e9a1da611bf3a53be0e` |
| `backend/tests/test_viability.py` | HEAD | Base comercial preexistente, sin cambios | 0644 | `1b4cd118569b5423700f9ba40bea83769256a0ca6fdaf7a9f07f4f1e385047b3` |
| `deploy/nginx/licitaia-http.conf` | HEAD | Base comercial preexistente, sin cambios | 0644 | `d040060285fd07626d17f8976ea26a25a05480ac369997e3f9f3c891c05d4bd9` |
| `deploy/nginx/licitaia.conf` | HEAD | Base comercial preexistente, sin cambios | 0644 | `77c880e26505d5dfce67c6a725c77387228934f994d3d686f68412339437f5b1` |
| `docker-compose.dev-rc.yml` | untracked | Consolidación RC: seguridad, dependencias o entrega | 0644 | `0488f42aa1307b8cd2287927c34dacf59246c3e5b61986968b69cd19999d606c` |
| `docker-compose.prod.yml` | HEAD | Base comercial preexistente, sin cambios | 0644 | `c9060aa69999e246df4c7a64aac7be43a6e1748ef0d81c237fe6c1fef3e02606` |
| `docker-compose.yml` | HEAD | Base comercial preexistente, sin cambios | 0644 | `1baad9f7904a6badcf3a98a8cfe86321ec6ea3418feb0f339a214c9dabdf782f` |
| `docs/brief-estrategia-marketing-mysecop.md` | HEAD | Base comercial preexistente, sin cambios | 0644 | `c537b3a6f9dca59db0f237ea16f7292d794d72a53b62ede99d23edfb2c29137b` |
| `docs/configuracion-gmail-smtp.md` | HEAD | Base comercial preexistente, sin cambios | 0644 | `a3014c15b6143c51dfa708dd7cc1233aaf1e7593cdbe9681dbee01c6b75c291b` |
| `docs/decisiones-arquitectonicas.md` | HEAD | Base comercial preexistente, sin cambios | 0644 | `e8ff50914db7c98e4978fec318712b964025d222594a2dd93b3ddff501a1aaaa` |
| `docs/fuentes-secop.md` | HEAD | Base comercial preexistente, sin cambios | 0644 | `7143e2402aacc3bb6605e9bdb68edf9f5eb7adf29a34ebc3420b326111f3bbbc` |
| `docs/guia-diligenciamiento-perfil.md` | HEAD | Base comercial preexistente, sin cambios | 0644 | `6500e63b9ca97c77a6bb62d48a521df06ad3b5e6e79258608d87bf8cfa47cac7` |
| `docs/variables-entorno.md` | HEAD | Base comercial preexistente, sin cambios | 0644 | `de79b116cd8ff9b3e6dce71cd8bbe4324f81edd8f8e3c41bd7a756ffea631749` |
| `frontend/.dockerignore` | modified | Consolidación RC: seguridad, dependencias o entrega | 0644 | `6d5ee80d000ea48ce2f583893f5f69238d46cd9268ca46466dc2eb25da88ac1f` |
| `frontend/Dockerfile` | modified | Consolidación RC: seguridad, dependencias o entrega | 0644 | `23f524339e76fec24a379f335850187569caa8159f0d9fb1d2c08a5303097a6c` |
| `frontend/app/(private)/app/admin/layout.tsx` | HEAD | Base comercial preexistente, sin cambios | 0644 | `71027148599a353eeaad81f01db868aca183f42a723d89a8ab4ecc87d2b5811e` |
| `frontend/app/(private)/app/admin/page.tsx` | HEAD | Base comercial preexistente, sin cambios | 0644 | `e71c135781a86e1b53f17d65666e6042e2564ba4af2bf5c8038f3d039b34b7de` |
| `frontend/app/(private)/app/alertas/page.tsx` | HEAD | Base comercial preexistente, sin cambios | 0644 | `0e919c0386fe3280370f62d0c3692706446482d224173775dfebabeadfa5c4e2` |
| `frontend/app/(private)/app/ayuda/page.tsx` | HEAD | Base comercial preexistente, sin cambios | 0644 | `12c90e94115001f8deb6a220861d2b98e4586beff8f7b63763ac8dee936052a1` |
| `frontend/app/(private)/app/diagnostico-compatibilidad/page.tsx` | untracked | 2 modelo V2 / guardias 2.1 | 0644 | `aedc3b402acd363b3b87c458126cd76accaec3e673bd7ae08791574340237773` |
| `frontend/app/(private)/app/evaluacion-interna/page.tsx` | untracked | 2.1 evaluación (plantillas ranking anteriores: 1/2) | 0644 | `c4290563a778ccb03d7fbbe0f27d2e951d917ebd0d017e526f6b9c8330211de8` |
| `frontend/app/(private)/app/layout.tsx` | HEAD | Base comercial preexistente, sin cambios | 0644 | `fc3f4b330c406d7ad2e62a0304607df24ea94a55ca3e12fd7b13f2439fa00f29` |
| `frontend/app/(private)/app/licencia-comercial/page.tsx` | HEAD | Base comercial preexistente, sin cambios | 0644 | `3368e978985d0f69c44ed1325d2534f3bfda642c56c0991bc7e5b3eab5081f81` |
| `frontend/app/(private)/app/manuales/page.tsx` | modified | 1/1.2/1.3 integración y regresión | 0644 | `afc85b42655f4f151f054c8a424160c8327b68ef0cba23c780143245876ee42c` |
| `frontend/app/(private)/app/ofertas/page.tsx` | HEAD | Base comercial preexistente, sin cambios | 0644 | `b56c44f53138ba64c1451e9a72b0f54e3c50617bd71a593d6f5862f36508a357` |
| `frontend/app/(private)/app/oportunidades/[id]/page.tsx` | modified | 1/1.2/1.3 integración y regresión | 0644 | `63c081c17e2fd8164501bfd45f441dbf670ebc3dcfe493334e7cd24f6e132419` |
| `frontend/app/(private)/app/oportunidades/page.tsx` | modified | 1/1.2/1.3 integración y regresión | 0644 | `13849acf67e0df66573e001b5642d45866e76686deb6d9c400f2a61ae1e9a20c` |
| `frontend/app/(private)/app/page.tsx` | modified | 1/1.2/1.3 integración y regresión | 0644 | `7398e6060c1fbfda5c3d84aa96115551d0f9d7c3e099bd9d3a21f6dd3c60a7b6` |
| `frontend/app/(private)/app/perfil/page.tsx` | modified | 1/1.2/1.3 integración y regresión | 0644 | `b0b45d24615a78fe1dfa1321bf13067ef9045ab2512e2d786e09bea2bd63e581` |
| `frontend/app/(private)/app/plan/page.tsx` | HEAD | Base comercial preexistente, sin cambios | 0644 | `1ce49343a863b8f657c2e4e8190dca91eb1693945103e614400e3a227d58fa04` |
| `frontend/app/(private)/app/sincronizacion/page.tsx` | HEAD | Base comercial preexistente, sin cambios | 0644 | `f715de5256d9445d4cf97bcc711bcb85972f7f19c385347225161c33d648f426` |
| `frontend/app/contacto/page.tsx` | HEAD | Base comercial preexistente, sin cambios | 0644 | `b8267590e555516aebe65f867c57687025e062b6269d9a566390b030d389085d` |
| `frontend/app/globals.css` | HEAD | Base comercial preexistente, sin cambios | 0644 | `114ee39077f72669e1809e3eb5c4842d7010ea0b5a7a8f92e5759b74df97ce2e` |
| `frontend/app/icon.svg` | HEAD | Base comercial preexistente, sin cambios | 0644 | `409371383029f33746fbd9487b1419d05ee1b43d6d11eaa106f73aff6c7260c4` |
| `frontend/app/iniciar-sesion/layout.tsx` | HEAD | Base comercial preexistente, sin cambios | 0644 | `c66c718c691ade9a2870d8427a6fa3ce7bc58c5883b7ae5c05c4ba3f819b7733` |
| `frontend/app/iniciar-sesion/page.tsx` | HEAD | Base comercial preexistente, sin cambios | 0644 | `2de069e0f4d8afe4820437800ffcd51acacd86642aebb2c104090398516c2a26` |
| `frontend/app/layout.tsx` | HEAD | Base comercial preexistente, sin cambios | 0644 | `c230a842ed262283f5bc0a8c326bf70a7717d721a9bd554355309648675a17d7` |
| `frontend/app/not-found.tsx` | HEAD | Base comercial preexistente, sin cambios | 0644 | `7c8419517286b345c2417f2f2e81b72170163ac4a6dc483cc1ab3aeec44950b5` |
| `frontend/app/page.tsx` | HEAD | Base comercial preexistente, sin cambios | 0644 | `289f677124737a292809e58895cfbb7ee3fb41668af75442ace8fa45a3c89dfc` |
| `frontend/app/registro/layout.tsx` | HEAD | Base comercial preexistente, sin cambios | 0644 | `7556d92946f27a5e2fe7e92fce555b40b799004cfd6606948eb3347ee05ad8cc` |
| `frontend/app/registro/page.tsx` | HEAD | Base comercial preexistente, sin cambios | 0644 | `9806a61cc21671b15ab438c12561a4eff15d6c56621071bba17d34c1afa195ee` |
| `frontend/app/restablecer-contrasena/page.tsx` | HEAD | Base comercial preexistente, sin cambios | 0644 | `47a7f6ab3183fb7be587ce96c3ea01be0eed6ae0e325753fcbfe662b9e37a2cf` |
| `frontend/app/robots.ts` | HEAD | Base comercial preexistente, sin cambios | 0644 | `85e3d652243ed63a3c13ccd80207f5675af1cb75a9e1eb798190abca96e2eab0` |
| `frontend/app/sitemap.ts` | HEAD | Base comercial preexistente, sin cambios | 0644 | `55839e812cf2aedca2508a3c8868d88dac4e99aa93a7f01eb4d8946e28cb707a` |
| `frontend/app/verificar-correo/page.tsx` | HEAD | Base comercial preexistente, sin cambios | 0644 | `49b501098f1a8faa1e8f53866ff50e83a0d397c973efc4fc9c5e39fdca606473` |
| `frontend/components/auth.tsx` | HEAD | Base comercial preexistente, sin cambios | 0644 | `3dabcdefbdad6c498b9fe8f4c9dc457bdc2abc758b6bbfe94eba67a17a2e020d` |
| `frontend/components/contact-form.tsx` | HEAD | Base comercial preexistente, sin cambios | 0644 | `a81848077c33488cd197adfd2f7f99770d5aa8bf51d6defca09fef1a7a00b896` |
| `frontend/components/landing-visit.tsx` | HEAD | Base comercial preexistente, sin cambios | 0644 | `c1d8e335ea957377b884eca05b1374019945738761581b4d254e2998df9d1e46` |
| `frontend/components/match-progress.tsx` | untracked | 1.2 recálculo / 1.3 estabilización | 0644 | `966b2946c2af1b53e861c9f1536db6c431c7ed4994a0125b8c0501b528002f34` |
| `frontend/components/theme.tsx` | HEAD | Base comercial preexistente, sin cambios | 0644 | `964370bc543d5e5991d40151df51295c3d3d8142d3c103c63e7bf347d348579d` |
| `frontend/components/ui.tsx` | HEAD | Base comercial preexistente, sin cambios | 0644 | `6d97c5e9bca10be0b72bcd68fcc77ec060da6ce89c17bcc6bc24b4983f74017a` |
| `frontend/lib/api.ts` | HEAD | Base comercial preexistente, sin cambios | 0644 | `394fb270bda8b9f598dd72ec819d14e12643e89c6aeda500010091ab9bf53ec1` |
| `frontend/next-env.d.ts` | modified | Consolidación RC: seguridad, dependencias o entrega | 0644 | `85ae5aee75f011967cf2d25cbc342f62d69314e9d925f7f4aa3456fc2cffcca6` |
| `frontend/next.config.mjs` | HEAD | Base comercial preexistente, sin cambios | 0644 | `e1c0bc1a16e5d9e24f545c7c14418faedd0bc7dba8cdbe90b5ff710f4f8bf0af` |
| `frontend/package-lock.json` | modified | Consolidación RC: seguridad, dependencias o entrega | 0644 | `2e9cad4e1eb556a4f86bb832b88c46e573ef31ee4ed8861dde2e314e09ab3e74` |
| `frontend/package.json` | modified | Consolidación RC: seguridad, dependencias o entrega | 0644 | `487ba69ac8fb1063e0179ce5dda1f1f739fae81b79dd62f89ffd1fc8b51877d4` |
| `frontend/postcss.config.mjs` | HEAD | Base comercial preexistente, sin cambios | 0644 | `efa65c65e17d51d58570edce9d702b0604fdf6a9b8db65afaed8f075af8867c7` |
| `frontend/public/characters/enemigos-01.png` | HEAD | Base comercial preexistente, sin cambios | 0644 | `1075afa657dfab3ece2df01e4eb218d360e212ebc78cbef3a1785dab8fcf72ba` |
| `frontend/public/characters/enemigos-02.png` | HEAD | Base comercial preexistente, sin cambios | 0644 | `4470e525264cbe0847a1b898697c271fe81ac8ef738ad13e925f117fe58ad7d1` |
| `frontend/public/characters/kato.png` | HEAD | Base comercial preexistente, sin cambios | 0644 | `ccdfbdf32f99c121da6d5a6d0db6869a059dfe32e9ce4ae098a6d11b568a73a3` |
| `frontend/public/characters/mongo.png` | HEAD | Base comercial preexistente, sin cambios | 0644 | `5b9ae26693cd4d2a829b2ae8f9377a83d42c07c49d66c96d1fe70194d8ec9a53` |
| `frontend/public/characters/osun.png` | HEAD | Base comercial preexistente, sin cambios | 0644 | `a33276ca84c02a525ad1c58e719d0d98ca44d3a455f777c32b6fd6c344a3e3a8` |
| `frontend/public/characters/quanchi.png` | HEAD | Base comercial preexistente, sin cambios | 0644 | `49643ec8a98d6d036c6e617d1d690f6b4a8f755c32ba378fbd615bb5beeb2edf` |
| `frontend/tailwind.config.ts` | HEAD | Base comercial preexistente, sin cambios | 0644 | `74b13d0e7440d109010c1a734744e0c26fa828a85c55621e26bd618f093df214` |
| `frontend/tsconfig.json` | HEAD | Base comercial preexistente, sin cambios | 0644 | `04e6cd483e62ab091dc82f116bdf8017c3013b5929d662b58e526acaa9815e77` |
| `scripts/deploy.sh` | HEAD | Base comercial preexistente, sin cambios | 0755 | `50d57cb4d732a360958c3c9fb9ba0ec43516b298804b00a1c699e17fe24da929` |
| `scripts/provision-vps.sh` | HEAD | Base comercial preexistente, sin cambios | 0644 | `d59ffdb83ecfe6eca5e59af82c922d9fbe17bb85ce3de6a7b9593cc05ad8e163` |
| `scripts/test-smtp-all.sh` | HEAD | Base comercial preexistente, sin cambios | 0644 | `4d4ceb81d88f804ea0e3a22ee1cc2f495b0a50d7ec67216ed41881c2b1ab7cb5` |

## Archivos excluidos

| Archivo | Motivo |
|---|---|
| `MYSECOP_COMPATIBILITY_V2_RELEASE_MANIFEST.md` | Manifiesto externo al payload para evitar hash autorreferente |
| `backend/benchmarks/phase13/e2e-dashboard.png` | Evidencia QA, no imagen de aplicación; conservada localmente |
| `backend/benchmarks/phase13/e2e-mobile.png` | Evidencia QA, no imagen de aplicación; conservada localmente |
| `backend/benchmarks/phase13/e2e-oportunidades.png` | Evidencia QA, no imagen de aplicación; conservada localmente |
| `backend/benchmarks/phase13/e2e-result.json` | Evidencia QA, no imagen de aplicación; conservada localmente |
| `backend/benchmarks/phase13/plans-1000-1.json` | Evidencia QA, no imagen de aplicación; conservada localmente |
| `backend/benchmarks/phase13/plans-1000-10.json` | Evidencia QA, no imagen de aplicación; conservada localmente |
| `backend/benchmarks/phase13/plans-10000-1.json` | Evidencia QA, no imagen de aplicación; conservada localmente |
| `backend/benchmarks/phase13/plans-10000-10.json` | Evidencia QA, no imagen de aplicación; conservada localmente |
| `backend/benchmarks/phase13/plans-50000-1.json` | Evidencia QA, no imagen de aplicación; conservada localmente |
| `backend/benchmarks/phase13/plans-50000-10.json` | Evidencia QA, no imagen de aplicación; conservada localmente |
| `backend/benchmarks/phase13/results.json` | Evidencia QA, no imagen de aplicación; conservada localmente |
| `backend/benchmarks/phase2/synthetic-20.json` | Evidencia QA, no imagen de aplicación; conservada localmente |
| `backend/benchmarks/phase2/v2-desktop.png` | Evidencia QA, no imagen de aplicación; conservada localmente |
| `backend/benchmarks/phase2/v2-mobile.png` | Evidencia QA, no imagen de aplicación; conservada localmente |
| `backend/benchmarks/phase2/validation.json` | Evidencia QA, no imagen de aplicación; conservada localmente |
| `backend/benchmarks/phase21/evaluation-ADJUDICATION-2.png` | Evidencia QA, no imagen de aplicación; conservada localmente |
| `backend/benchmarks/phase21/evaluation-REVIEW-0.png` | Evidencia QA, no imagen de aplicación; conservada localmente |
| `backend/benchmarks/phase21/evaluation-REVIEW-3.png` | Evidencia QA, no imagen de aplicación; conservada localmente |
| `backend/benchmarks/phase21/evaluation-admin.png` | Evidencia QA, no imagen de aplicación; conservada localmente |
| `backend/benchmarks/phase21/evaluation-mobile.png` | Evidencia QA, no imagen de aplicación; conservada localmente |
| `backend/benchmarks/phase21/evaluation-report-synthetic.json` | Evidencia QA, no imagen de aplicación; conservada localmente |
| `backend/benchmarks/phase21/v2-desktop.png` | Evidencia QA, no imagen de aplicación; conservada localmente |
| `backend/benchmarks/phase21/v2-mobile.png` | Evidencia QA, no imagen de aplicación; conservada localmente |
| `backend/benchmarks/phase21/validation.json` | Evidencia QA, no imagen de aplicación; conservada localmente |

También se excluyen por Git ignore: `.git`, venvs, node_modules, `.next`, caches, logs, archivos de entorno y temporales. No se borran. El backup de código previo no incluye PNG ni benchmarks; el paquete final sí incluye los assets públicos tracked necesarios.

## Dependencias, migraciones y configuración

Python 3.12: `backend/requirements.txt` con `backend/constraints-release-candidate.txt`, más `psycopg2-binary==2.9.13`. QA: `backend/requirements-isolated-tests.txt` con las mismas constraints; Chromium Playwright se provisiona aparte. Frontend: `npm ci`, lockfile incluido, Next 15.5.29 y PostCSS 8.5.33 con override. El build local usa Node 20.11.0/npm 10.2.4; Docker/CI declaran Node 22, aún sin prueba de imagen Linux. Las constraints fijan las versiones observadas, no hashes de wheels ni digest de imagen; no equivale a build binario hermético.

Cadena única 0001 → 0002…0009 → 0010_sync_cursor → 0011_match_jobs → 0012_failed_match_inputs → 0013_compatibility_shadow → 0014_evaluation_platform. No stamp. Ver evidencia PostgreSQL y estrategia histórica en el documento principal. Variables, workers y orden de instalación en DEV_RUNBOOK. Flags experimentales false, llamadas externas cero.

## Riesgos de reproducibilidad y publicación

El checkout Git por sí solo NO reproduce este snapshot: hay modificaciones y archivos sin seguimiento inventariados. El tar y hashes permiten reconstruir el código local exacto. No existe commit/tag RC autorizado, rama nueva ni imagen OCI identificada por digest. El paquete excluye configuraciones privadas y requiere provisión separada de secretos/destinos. Las dependencias de sistema y contenedores usan tags sin digest; instalación Linux/Compose no verificada. Los workflows existentes en develop despliegan al hacer push: no usarlos para publicar el RC sin una orden operativa y una revisión explícita del flujo.

La búsqueda de credenciales por patrones tuvo cero hallazgos; no sustituye un escáner completo de secretos o una auditoría de todo el historial Git. La evidencia QA está separada del payload en `/private/tmp/mysecop-rc-preparation-20261116/evidence/`; nunca se incluye una base de pruebas ni datos operativos.
