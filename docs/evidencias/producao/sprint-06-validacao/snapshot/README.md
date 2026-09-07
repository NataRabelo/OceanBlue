# Sprint 06 — snapshot adversarial independente

Escopo exclusivo: `scripts/operational_snapshot.ps1`, `scripts/validate_snapshot_adversarial.ps1` e esta pasta de evidências. Nenhum commit, integração externa, alteração de outro runner ou parada de recursos de outro projeto. Todos os containers de prova têm projeto `oceanblue-s06-snapshot-*`, rede `none`, sem portas publicadas; Postgres 16 real é acessado por `docker exec`. As imagens existentes release-smoke/release-test e postgres:16 foram identificadas em `images.txt`. Não usamos Compose nem a subrede operacional 172.30.62.

**Resultado final: 32/32 casos aceitos e 3/3 provas suplementares passaram**, após red com 12 falhas em 22 casos. `accepted-summary.json` consolida resultados, tempos e hashes. Em 2026-09-07 07:51 UTC, a inspeção final encontrou zero containers, volumes ou redes com labels dos projetos exclusivos desta frente. Os dois arquivos de código mantiveram exatamente os hashes congelados, sem commit.

## Fonte congelada

- Snapshot SHA-256: `167D282F7CCDE31A73F0DC659A2A704C1D8549FFCD531F61EFF8B97EB1F90A15`.
- Runner SHA-256: `7911958AA76919263D3A2F1AF8277226BF6D683CC243F3563AD433EF8A3F001C`.
- `accepted/green` é a execução integral da fonte congelada. `supplemental-final` acrescenta provas de revisão real dentro do dump e custódia. Os resultados finais são escritos em `results.json` e `summary.json` de cada execução.

## Red antes da correção

`red/summary.json`: 22 casos, 10 passaram e 12 falharam. A execução terminou antes de qualquer edição no snapshot. O script original tinha SHA-256 `BBCF69C13B02C647D3A82439EA258E45BA399B0A50192CB08D39C2ECFB83F305`.

Defeitos reproduzidos: backup aceitou revisão Alembic errada; restore aceitou versão de manifesto desconhecida; reordenar somente chaves do fingerprint causou falso negativo depois do commit; fingerprint adulterado deixou o banco populado; schemas fora de public, sequências e funções preexistentes não impediram restore; falhas/interrupção na cópia deixaram banco confirmado; escritor compartilhando storage passou; junction na raiz do snapshot passou. Hash de arquivo inválido, traversal simples, tabela pública existente, arquivo de destino e aplicação/cliente de banco ativos já eram recusados.

## Correções

- Manifesto v2 declara revisão Alembic da imagem e major do PostgreSQL. Backup confere o banco; restore confere metadados antes de importar e a revisão real dentro da transação.
- Fingerprints são comparados por conjunto de chaves e valores, sem dependência da ordem de serialização JSON. Os valores de linhas e sequências continuam sendo confrontados com o banco real.
- Restore exige banco novo sem objetos de usuário e storage vazio; aceita somente a estrutura inicial opcional `storage/` vazia. Verifica junctions/reparse points na raiz/ancestrais, links simbólicos e arquivos especiais no volume, caminhos do manifesto e SHA-256 de cada arquivo.
- O banco só recebe COMMIT depois da cópia, ajuste de permissões e comparação dos arquivos. Falhas anteriores tentam ROLLBACK e remoção dos arquivos copiados. Se a limpeza não puder ser comprovada, mantém `.oceanblue-restore-incomplete`. Se COMMIT tiver sido tentado, mantém arquivos e exige reconciliação; não presume rollback.
- Interrupção forçada do processo fecha a sessão; há timeout de transação ociosa de 60 s, reaplicado depois das configurações carregadas pelo dump. O marcador é durável no volume. A aplicação deve honrá-lo; a alteração da aplicação pertence à frente de dados/operacional, não a esta prova com imagem release antiga.
- Publicação do backup usa diretório privado temporário e rename que falha se o destino existir. Interrupção antes da publicação não produz snapshot final válido.
- Verifica aplicação parada, clientes de banco, transações preparadas e containers com mount gravável compartilhado. Usa lock consultivo entre snapshots e limpa o cache de estatísticas antes de cada consulta de clientes; a prova intermediária detectou que `pg_stat_activity` podia manter informação antiga na transação. Tolera containers descartáveis que desapareçam durante a inspeção global, sem ignorar os que continuam ativos.

## Migração do CLI e custódia

Todo `restore` agora exige `-ExpectedManifestSha256 <64-hex>`. `backup` não exige esse argumento e imprime o SHA-256 do manifesto final. O operador deve guardar esse valor por canal separado e confiável na captura, e fornecê-lo na recuperação. Calcular o hash a partir de um snapshot recebido/adulterado para satisfazer o argumento não estabelece custódia. Manifestos v1 não são promovidos automaticamente: recapture um snapshot v2 com banco e imagem compatíveis.

Nas provas, o runner cria fixtures sintéticas e fornece seus digests como emissor confiável, inclusive fixtures semanticamente inválidas, para atingir validações além da custódia. `manifest-pinned` e `forged-custody` preservam deliberadamente o digest anterior à adulteração. `custody-unpinned` omite o parâmetro e deve ser recusado antes de qualquer operação Docker. Não há assinatura digital nem serviço externo de custódia.

## Métricas e limites

O conjunto mínimo tem duas linhas sintéticas, uma tabela vazia, a revisão Alembic, uma sequência e um recibo de texto. A prova independente lê contagem, valor da sequência e conteúdo do recibo fora do script de snapshot. Os tempos do processo incluem preflight, chamadas Docker, hashing e limpeza; não incluem provisionamento do destino nem readiness da aplicação.

Na fonte congelada, `accepted/green/results.json` registrou backup em **23,677 s** e restore em **24,929 s**, recuperando duas linhas, sequência em 2 e recibo idêntico. Esses são os tempos observados desta prova mínima, não o RTO completo do serviço. A frente operacional informou separadamente 50,985 s até smoke com três vendas, aplicação anterior, retorno do banco e downgrade/reupgrade; essa medição não foi executada nem incorporada como prova própria deste runner.

Após encerramento forçado do processo, depois da cópia real dos arquivos e antes do COMMIT, o runner observou zero sessões SQL e banco vazio em **1,603 s**, com marcador de recuperação preservado. É tempo de observação do rollback, não RTO para disponibilizar novamente a aplicação. A prova de escritor tardio foi recusada em 18,209 s e não publicou manifesto final.

RPO observado é zero registros capturados perdidos. Isso não significa RPO temporal contínuo zero: não há WAL/PITR nem agendamento, e alterações posteriores ao snapshot não são recuperadas. O RTO medido com esse conjunto pequeno não é previsão para bases grandes. Fingerprint agrega hashes ordenados de todas as linhas, com custo de varredura/ordenação e limites de memória/tamanho do PostgreSQL. Timeouts deliberadamente falham de forma conservadora em operações muito lentas.

Requer exclusividade operacional: estas verificações não impedem um administrador/cliente privilegiado de escrever entre verificações, substituir arquivos após hashing ou ignorar locks consultivos. Diretório do snapshot, digest externo, daemon Docker, imagem e credenciais precisam estar sob custódia confiável e sem alterações concorrentes. Um dump PostgreSQL é conteúdo executável; pin válido não torna um emissor malicioso seguro. MD5 serve ao fingerprint de conteúdo; a integridade do arquivo de dump usa SHA-256 com manifesto fixado externamente.

Os testes de links cobrem symlink de origem/destino e junction na raiz; hardlinks são tratados como arquivos regulares e não recebem rejeição específica por contagem de links. Não foi simulada troca maliciosa de inode entre hashing e cópia. As permissões do storage restaurado usam UID/GID 1000 e diretórios privados, de acordo com a imagem da aplicação.

O suporte de fingerprint é para schema público e storage de filesystem; schemas adicionais e large objects são recusados no backup. Não é backup de roles, credenciais, tablespaces ou configuração do cluster. Não há transação distribuída atômica entre Postgres e filesystem: depois de COMMIT sem confirmação ou falha ao remover marcador, o destino fica em quarentena para inspeção/recuperação. Mesmo quando o banco fez rollback, falha de limpeza pode deixar arquivos que não devem ser servidos. Não remova o marcador nem inicie a aplicação sem reconciliar esse estado; em destino descartável, recrie banco e volume.

## Histórico de iteração

`green` e `final-source/green` são iterações intermediárias, não aceitação final. Registram o defeito do cache de estatísticas e uma falha transitória de inspeção; a exigência de pin foi introduzida durante sua execução e invalidou chamadas antigas restantes. `acceptance/green` falhou no preflight do driver ao misturar stderr de inspeção com JSON, corrigido antes da fonte congelada. `supplemental` é uma tentativa de harness com caminho de workspace incorreto; não executou o snapshot e seus recursos foram removidos. Não se deve apresentar essas execuções como verdes.

Os scripts sintéticos gerados e logs permitem reproduzir as injeções: falha depois de cópia real, helper de rollback indisponível, término real do backend PostgreSQL e encerramento forçado do processo PowerShell depois da cópia. Não há flags de injeção no script operacional. Os snapshots preservados são pequenos e contêm somente dados sintéticos.

Para repetir a suite congelada, a partir da raiz do workspace, use `pwsh -NoProfile -File scripts/validate_snapshot_adversarial.ps1 -Phase green -EvidenceDirectory docs/evidencias/producao/sprint-06-validacao/snapshot/nova-execucao`. O destino de evidência deve ser novo. O projeto isolado é gerado automaticamente; `-ExtendedOnly` limita a execução ao roundtrip independente e aos cenários adicionais de interrupção/escritor tardio. A prova suplementar é descartável e usa os fixtures preservados da captura red e da aceitação; seu destino também deve ser novo ao repetir.
