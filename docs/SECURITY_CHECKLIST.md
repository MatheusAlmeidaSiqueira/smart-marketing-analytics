# Checklist de segurança para publicação

- [x] Dataset de demonstração reconstruído com nomes de empresas fictícias.
- [x] Nenhuma credencial MySQL incluída no código, no Excel ou no PBIX.
- [x] Configuração do banco feita por variáveis de ambiente.
- [x] Arquivos `.env`, DPAPI, logs, bancos locais e caches ignorados pelo Git.
- [x] Logs operacionais e histórico interno não foram copiados.
- [x] Caminhos absolutos e nomes de usuário removidos dos arquivos públicos.
- [x] PBIX verificado por busca binária de padrões sensíveis antes da cópia.
- [x] Três capturas revisadas visualmente, sem e-mail, nome pessoal, caminho local ou credencial.
- [x] Metadados das imagens verificados antes da publicação.
- [x] SQL idempotente, sem `DROP`, `TRUNCATE` ou exclusão de registros.
- [x] Pipeline testado em SQLite em duas execuções para validar UPSERT sem duplicação.
- [x] Licença MIT escolhida pelo autor e adicionada como `LICENSE`.
- [ ] Revisão do proprietário do repositório antes de `git add`.
- [ ] Verificação final com ferramenta de detecção de segredos no histórico Git.

## Verificação sugerida antes do primeiro push

```powershell
git init
git add --dry-run .
git diff --no-index -- NUL .env.example
```

Após criar o primeiro commit, ferramentas como `gitleaks` ou GitHub Secret Scanning
podem complementar esta auditoria local. Não faça commit de credenciais reais, mesmo
que o repositório seja privado.
