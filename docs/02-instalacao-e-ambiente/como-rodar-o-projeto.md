# Instalacao e homologacao reproduzivel — Sprint 1 de producao

## Ambiente de referencia

Python 3.12.12 / Linux, PostgreSQL 16, Docker Engine e Compose v2+ com suporte a `--wait`. No Windows, use Docker Desktop com containers Linux. Execute na raiz do checkout. Nao e necessario Python no host para a verificacao Docker.

`requirements.in` declara dependencias diretas; `requirements.txt` fixa todas as transitivas com hashes. O par `requirements-dev.in` / `requirements-dev.txt` inclui a mesma stack e pytest, cobertura e ferramentas de resolucao. Instale com `--require-hashes`. As imagens Python e PostgreSQL estao fixadas por digest; o Dockerfile nao instala pacotes de sistema de repositorios mutaveis.

O ambiente homologado dos locks e Python 3.12 em Linux. Python nativo Windows e outras versoes nao fazem parte desta evidencia; Gunicorn requer Unix. `tzdata` e explicito para America/Sao_Paulo. WeasyPrint e MercadoPago foram retirados porque nenhum codigo do projeto os importa ou usa; nao representam funcionalidades PDF/pagamento implementadas.

## Checkout limpo: verificacao completa

Sem `.env`, certificados, chaves externas ou banco existente:

```sh
docker compose -f compose.test.yml up --build --abort-on-container-exit --exit-code-from test
```

Cria PostgreSQL descartavel, instala o lock, executa `pip check`, verifica o inventario, percorre as 19 revisions, faz downgrade ate base, reaplica head, compara tabelas/colunas com modelos e executa todos os testes. Um tenant sentinela verifica preservacao no upgrade. O pytest mede linhas e ramificacoes de todo `app`, inclusive os modulos legados fiscal/bancario. O limite inicial do CI e 50% combinado; nao e meta final de cobertura do produto.

O banco `oceanblue_test` usa `tmpfs`, rede interna e nenhuma porta publicada. As credenciais do compose sao exclusivas e descartaveis. Parar/recriar o banco perde seus dados. Os testes fazem TRUNCATE apenas nesse banco e usam schema migrado, nunca `create_all`. Nao execute contra copia de banco produtivo renomeada.

Para repetir integralmente, descarte somente os servicos deste compose:

```sh
docker compose -f compose.test.yml --profile smoke down -v
docker compose -f compose.test.yml up --build --abort-on-container-exit --exit-code-from test
```

Para diagnostico focal com banco migrado: `docker compose -f compose.test.yml run --rm test python -m pytest tests/test_produto_service.py --no-cov`. O gate de cobertura integral nao se aplica a esse diagnostico.

## Evidencias e imagem de producao

Copie os resultados antes de remover os containers:

```sh
docker compose -f compose.test.yml cp test:/app/coverage.xml coverage.xml
docker compose -f compose.test.yml cp test:/tmp/junit.xml junit.xml
docker compose -f compose.test.yml logs --no-color
docker compose -f compose.test.yml --profile smoke up -d --build --wait --wait-timeout 120 smoke
docker compose -f compose.test.yml --profile smoke ps
docker compose -f compose.test.yml --profile smoke down -v
```

O smoke inicia a imagem de producao com usuario sem privilegios, validacao de segredos, espera do banco, `flask db upgrade`, Gunicorn e `/api/ready`. Usa segredos artificiais e banco descartavel; nao publica servidor no host. O CI em `.github/workflows/ci.yml` executa esse caminho em push/PR e publica logs, JUnit e cobertura mesmo em falha. Nenhum deploy remoto e feito.

## Desenvolvimento Python (Linux)

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements-dev.txt
python -m pip check
```

Para testar fora do Docker, providencie outro PostgreSQL descartavel chamado `oceanblue_test` e exporte `TEST_DATABASE_URL`, por exemplo `export TEST_DATABASE_URL='postgresql+psycopg2://oceanblue_test:senha-local@127.0.0.1:5432/oceanblue_test'`. Esse exemplo exige banco local separado: a porta do compose nao e publicada.

```sh
python -m scripts.validate_migrations
python -m pytest
python -m scripts.inventory --check
```

A configuracao de testes substitui variaveis herdadas antes de importar a aplicacao, ignora `.env`, desativa debug/proxy/HTTPS local e mantem CSRF ativo. O pytest bloqueia conexoes Python de saida; adaptadores legados usam mocks. PostgreSQL usa psycopg2 nativo. A rede Docker interna fornece isolamento adicional.

Atualize os locks intencionalmente no ambiente instalado, revise o diff e repita todo o CI:

```sh
pip-compile --generate-hashes --allow-unsafe --strip-extras --resolver=backtracking -o requirements.txt requirements.in
pip-compile --generate-hashes --allow-unsafe --strip-extras --resolver=backtracking -o requirements-dev.txt requirements-dev.in
python -m scripts.inventory
```

## Homologacao funcional

Copie `.env.example` para `.env`, configure `DATABASE_URL` para homologacao separada e gere tres segredos distintos de pelo menos 32 caracteres (`SECRET_KEY`, `JWT_SECRET_KEY`, `FIELD_ENCRYPTION_KEY`). Para HTTP local, use `FLASK_ENV=development`, `FORCE_HTTPS=false`, `TRUST_PROXY_HEADERS=false`. Para producao, mantenha HTTPS e configure proxy explicitamente. Nao reutilize credenciais de teste.

```sh
python -m pip install --require-hashes -r requirements.txt
python -m flask --app wsgi:app db upgrade
python -m flask --app wsgi:app run --host 127.0.0.1
```

O legado `flask seed` cria dados demonstrativos com senha fixa e imprime credenciais. Utilize somente em demonstracao isolada; nao e um bootstrap produtivo seguro. Sua reformulacao permanece pendente. O compose principal depende da infraestrutura/rede externa `blueocean_network`; o compose de testes e autocontido.

Homologacao manual complementar: login, permissoes por perfil/tenant, produto, venda, baixa de estoque, lancamento financeiro, cancelamento integral/parcial, carteira/cashback, importacao/exportacao. O inventario registra lacunas HTTP. Esta Sprint valida instalacao e suite; nao homologa integralmente todos os requisitos.

Boleto/Asaas e Nota Fiscal/Focus/SEFAZ reais permanecem fora do escopo. Suas migrations pertencem ao historico indivisivel e foram verificadas estruturalmente. Os testes existentes de adaptadores permanecem locais e simulados.
