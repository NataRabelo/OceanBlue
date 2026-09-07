# Seguranca e operacao — Sprint 2

## Atualizacao

A Sprint 2 parte do GO da Sprint 1, main `8f8c3b3`. Instale os locks com hashes, aplique `flask db upgrade` e reinicie todos os workers. A migration valida os vinculos existentes; inconsistencias entre tenants/empresas abortam a transacao e exigem saneamento antes de nova tentativa. Nenhum vinculo e movido automaticamente.

Os JWTs anteriores nao possuem versao de sessao e identificador da chave; todos os usuarios devem entrar novamente. A migration inicializa trials sem data usando a criacao do tenant, acrescida de 14 dias: contas antigas podem ficar expiradas, sem concessao de um novo trial.

## Acesso e senhas

- No login operacional, informe o nome exato da organizacao (nome do tenant), usuario e senha. No acesso global, selecione Administracao da plataforma. Nao existe procura alternativa entre tenants nem fallback para o dono da plataforma.
- O formulario de login exige CSRF de sessao. Escritas autenticadas exigem o token CSRF do cookie no cabecalho `X-CSRF-TOKEN` ou no campo `csrf_token`. Logout e POST, remove cookies e revoga o JWT no PostgreSQL.
- Troque sua senha em `/senha`. Senhas novas possuem 12 a 128 caracteres e nao podem ser padroes previsiveis. Senhas legadas ainda funcionam para entrada, permitindo a troca.
- O administrador do tenant pode emitir um codigo pela acao Redefinir senha em Funcionarios. O codigo dura 15 minutos, e armazenado apenas como SHA-256 e deve ser entregue por canal seguro; use-o em `/redefinir-senha`. Nao ha recuperacao publica baseada apenas em nome ou e-mail.
- Para recuperar o dono da plataforma, um operador com acesso ao ambiente executa `flask reset-platform-password --usuario NOME`. Esse comando imprime exclusivamente um codigo temporario, nunca a senha.
- Troca/redefinicao, alteracao administrativa de senha e desativacao do usuario invalidam todas as suas sessoes. Exclusao, desativacao de perfil e alteracao de permissoes sao verificadas contra o estado atual a cada requisicao. Tokens de redefinicao anteriores a uma troca de senha deixam de funcionar.
- Criar/editar/excluir perfis, permissoes e funcionarios, inclusive importar funcionarios, exige administrador do tenant com acesso a todas as empresas, alem da permissao especifica. Perfis e contas sao compartilhados no tenant; um administrador limitado a empresas nao pode alterar esses acessos globais.

## Tentativas e proxy

O PostgreSQL compartilha os contadores entre workers e instancias. Por padrao, sao cinco tentativas por conta/organizacao/ambiente em uma janela fixa de 300 segundos, e cinquenta por IP. Tentativas bem-sucedidas tambem contam; o login nao limpa o contador. A resposta 429 inclui `Retry-After`. Falha do armazenamento bloqueia o login.

O endereco usado e `request.remote_addr`. Headers enviados pelo cliente nao sao aceitos diretamente. `TRUST_PROXY_HEADERS=false` e o padrao. Somente ative ProxyFix quando a aplicacao estiver acessivel exclusivamente pelo proxy confiavel; ajuste a quantidade de proxies e bloqueie acesso direto ao backend. O proxy deve substituir os headers de encaminhamento.

Comunicacoes SMTP/WhatsApp/SMS exigem hosts confiaveis cadastrados pelo operador em `OUTBOUND_ALLOWED_HOSTS`, separados por virgula; vazio bloqueia envios. Hosts internos, loopback e metadata sao recusados na resolucao DNS. SMTP exige TLS; webhooks exigem HTTPS na porta 443 e nao seguem redirecionamentos. Nunca inclua dominios controlados por tenants nessa lista.

## Isolamento e cotas

Consultas ORM autenticadas recebem filtro de tenant e, para registros empresariais, de empresas autorizadas, inclusive registros filhos de vendas, boletos e notas. Cadastros compartilhados (clientes, produtos base, categorias, perfis, permissoes) pertencem ao tenant; dados operacionais pertencem a empresas. A permissao de todas as empresas nao concede acesso a outro tenant.

Triggers verificam todas as FKs empresariais/tenant nas 45 tabelas do schema (tabelas globais de autenticacao nao carregam empresa). Relacoes de tenant, empresa, venda e boleto ja persistidas sao imutaveis. Parcelas e eventos herdam tenant/empresa do boleto. A migration verifica os dados existentes ao instalar a protecao.

Cotas contam registros, incluindo inativos, de empresas, funcionarios e produtos; vendas contam o mes corrente de Sao Paulo, incluindo canceladas. Nao ha limite zero/negativo como sinônimo de ilimitado. A trava transacional por tenant serializa cadastros concorrentes antes da contagem. Cadastros, API e linhas de importacao usam a mesma protecao. Importacoes preservam o contrato de sucesso parcial por linha: uma linha recusada nao cria parte de seus dados, e atualizacoes de registros existentes nao gastam nova cota.

Trial sem data ou com data anterior ao dia atual de Sao Paulo fica bloqueado. O ultimo dia e inclusivo. Troca de plano durante trial preserva sua data; prorrogacao deve ser explicita pela administracao da plataforma.

## Segredos e campos criptografados

Gere segredos aleatorios distintos com pelo menos 32 caracteres para `SECRET_KEY`, `JWT_SECRET_KEY` e `FIELD_ENCRYPTION_KEY`. Valores de desenvolvimento, repetitivos e reutilizados entre essas finalidades sao recusados em producao.

Para rotacionar JWT, altere `JWT_SECRET_KEY` e `JWT_SIGNING_KEY_ID` e reinicie todos os workers de forma coordenada. Para sessao Flask, altere `SECRET_KEY`. Nao ha periodo de aceitacao de chave antiga: a rotacao encerra os respectivos tokens/sessoes.

Novos campos sensiveis usam Fernet autenticado, envelope `enc:v2:IDENTIFICADOR:TOKEN`; valores legados `enc:v1:` e texto simples podem ser lidos durante a migracao. A chave de `FIELD_ENCRYPTION_KEY` deve permanecer disponivel para o formato v1 ate sua conversao.

1. Configure `FIELD_ENCRYPTION_KEYS` como JSON de identificador para segredo, contendo a chave antiga em `primary` e a nova sob outro identificador. Defina `FIELD_ENCRYPTION_ACTIVE_KEY_ID` para a nova chave e reinicie os workers. Nao inclua segredos em comandos gravados no historico.
2. Execute `flask rotate-field-keys`: valida todos os campos sem persistir mudancas.
3. Execute `flask rotate-field-keys --apply`: recriptografa SMTP, WhatsApp, SMS, Asaas/webhook, CSC e Focus em uma transacao; um campo corrompido cancela tudo.
4. Confirme a leitura, preserve as chaves exigidas pela politica de backups e so entao retire a chave antiga do mapa. Atualize a chave legada obrigatoria para um novo segredo quando nao houver mais registros v1.

Chaves ausentes, identificadores desconhecidos, envelopes invalidos e adulteracao falham sem retornar os valores. A rotina de rotacao pode bloquear os registros enquanto trabalha; execute em janela adequada ao volume de dados.

## Auditoria e manutencao

Alteracoes em perfis, permissoes, associacoes perfil/permissao e funcionarios/vinculos geram auditoria na mesma transacao, inclusive operacoes em lote. Os registros contem ator quando a operacao veio de requisicao autenticada, identificadores, operacao e estado anterior/posterior sem hashes de senha. Eventos de login, bloqueio, logout e senha tambem sao registrados.

Execute periodicamente `flask cleanup-auth-state` para remover revogacoes e codigos expirados. O contador de tentativas tambem limpa suas janelas vencidas. Nao ha agendamento criado por esta entrega.

Boleto/Asaas, Fiscal/Focus/SEFAZ reais permanecem bloqueados no seletor de provider, no transporte e no webhook Asaas. Configuracoes existentes nao habilitam chamadas reais. Os testes de protocolo usam somente transportes simulados.

Referencias de implementacao: [Fernet e rotacao](https://cryptography.io/en/stable/fernet/), [travas transacionais PostgreSQL 16](https://www.postgresql.org/docs/16/explicit-locking.html#ADVISORY-LOCKS).
