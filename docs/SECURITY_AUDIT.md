# Auditoria de segurança local

Data da revisão: 18 de outubro de 2026.

## Escopo

Foram revisados os arquivos de código, SQL, documentação, dataset demonstrativo e
PBIX incluídos nesta pasta pública. O ambiente operacional, o banco MySQL real e os
arquivos de credenciais não foram copiados nem modificados.

## Verificações executadas

| Controle | Resultado |
|---|---|
| E-mails, nome de usuário e caminhos absolutos pessoais em texto | Nenhuma ocorrência |
| Chaves privadas, tokens comuns e credenciais de alta confiança | Nenhuma ocorrência |
| Padrões sensíveis legíveis no XLSX e PBIX | Nenhuma ocorrência |
| Arquivos DPAPI, `.env`, logs, SQLite ou bancos locais | Nenhum arquivo incluído |
| `DROP`, `TRUNCATE` ou `DELETE FROM` nos scripts SQL | Nenhuma ocorrência |
| Credenciais hardcoded no código Python | Nenhuma ocorrência |
| Dataset com nomes de empresas reais | Não; nomes sintéticos padronizados |
| Teste de UPSERT repetido | Aprovado, sem duplicações e sem exclusões |
| Capturas do dashboard | Três imagens revisadas, sem dados pessoais ou credenciais |
| Metadados JPEG | Sem EXIF, comentários ou identificação pessoal |

## Integridade do PBIX

SHA-256 da cópia pública:

```text
5CE988F39DC5E26372F9B663EF6191EF8E14749D7B369F93D14E0994D0185397
```

O hash coincide com o arquivo final usado como origem da cópia, confirmando que o
PBIX não foi alterado durante o empacotamento. A inspeção do projeto associado
identificou somente o endpoint local `127.0.0.1:3306` e o banco
`smart_marketing`; usuário e senha não estavam declarados no modelo.

## Limites da auditoria

A busca local por padrões não substitui análise forense nem secret scanning do
histórico Git. Antes de publicar, recomenda-se:

1. executar `gitleaks` ou o GitHub Secret Scanning após iniciar o repositório;
2. confirmar que somente os arquivos listados no README entrarão no primeiro commit;
3. revalidar o PBIX e as capturas se o relatório for atualizado ou salvo novamente.
