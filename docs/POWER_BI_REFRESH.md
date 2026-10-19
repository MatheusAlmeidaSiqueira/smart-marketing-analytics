# Atualização do Power BI

## Power BI Desktop

O relatório está em modo de importação. Salvar o Excel e sincronizar o MySQL não
atualiza automaticamente o cache de um PBIX fechado. No Desktop, o fluxo é:

1. o pipeline conclui a carga no MySQL;
2. o usuário abre o PBIX;
3. o usuário seleciona **Página Inicial > Atualizar**;
4. o modelo importa os dados atuais do MySQL e recalcula as medidas DAX.

O Power BI Desktop não é um serviço de agendamento autônomo. Para atualização sem
interação, use o Power BI Service ou uma solução corporativa suportada. O monitor
Python atualiza o banco, não o cache interno de um PBIX aberto ou fechado.

## Power BI Service

Este repositório não publica o relatório. Para uma implantação autorizada:

1. instale o **On-premises data gateway** em modo padrão em uma máquina que alcance o MySQL;
2. mantenha essa máquina ligada nos horários de atualização;
3. configure no Service uma fonte MySQL correspondente ao servidor e banco usados pelo modelo;
4. associe o modelo semântico à fonte do gateway;
5. armazene as credenciais no gateway, nunca no repositório;
6. agende a atualização para depois da conclusão esperada do ETL;
7. valide histórico, duração e falhas de atualização.

Como `127.0.0.1` é relativo à máquina que executa a conexão, no Service ele deve
representar o MySQL visto pela máquina do gateway. Em ambientes distribuídos,
substitua-o por um nome DNS ou host permitido pela rede e atualize a fonte no PBIX.

Disponibilidade de atualização agendada, frequência, capacidade e autenticação
dependem da licença e das políticas do tenant. Uma conta do Power BI, acesso ao
workspace e um gateway configurado são requisitos externos a este repositório.

## Ordem recomendada

```text
Excel salvo → pipeline validado → commit MySQL → atualização Power BI → auditoria
```

Essa ordem impede que o relatório importe uma transação incompleta.
