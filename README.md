# FEMSA · Painel de chamados comerciais

Aplicação Streamlit em português, somente para visualização. Autenticação por senha antes de qualquer consulta à API ou ao cache. Indicadores, filtros, busca, gráficos Plotly e tabela paginada com chamados recentes primeiro.

## Executar localmente

Requer Python 3.11 ou superior.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .streamlit/secrets.example.toml .streamlit/secrets.toml
# Preencha os três secrets antes de iniciar.
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Em Linux/macOS, utilize `.venv/bin/python`. Nunca versione `.streamlit/secrets.toml`.

## Configurar a planilha e a API

1. Na planilha de origem, crie/use a aba **Base_Painel**. A primeira linha deve conter cabeçalhos únicos e sem células vazias dentro da área de dados.
2. Use os cabeçalhos `Data`, `Aplicativo`, `Tipo`, `Status`, `Supervisor`, `Vendedor`, `Matrícula`, `Validade`. Para Data também são aceitos `Carimbo de data/hora`, `Data/Hora` e `Data de abertura`. Variações de maiúsculas e acentos nos cabeçalhos são aceitas. Colunas adicionais não são exibidas.
3. Use datas reais do Sheets ou textos `dd/mm/aaaa HH:mm:ss` ou `aaaa-mm-ddTHH:mm:ss`. Datas reais são serializadas no fuso da planilha. Formate matrícula como texto ou com a máscara desejada: a API preserva o valor exibido, incluindo zeros à esquerda.
4. Abra **Extensões → Apps Script**, na própria planilha, e cole `apps-script/Code.gs`.
5. Em **Configurações do projeto → Propriedades do script**, cadastre `API_TOKEN` com um token longo e aleatório e `SPREADSHEET_ID` com o ID da **mesma planilha vinculada** (trecho entre `/d/` e `/edit` na URL). O ID explícito é necessário porque os métodos de planilha ativa não estão disponíveis em aplicações web. O código não grava propriedades nem modifica a planilha.
6. Para limitar também a permissão OAuth a leitura, habilite a exibição do manifesto `appsscript.json` nas configurações e inclua `"oauthScopes": ["https://www.googleapis.com/auth/spreadsheets.readonly"]` no objeto existente, preservando seus outros campos.
7. Em **Implantar → Nova implantação → Aplicativo da Web**, execute como o proprietário e permita acesso à aplicação conforme a política da organização. Para a chamada servidor a servidor usando apenas o token, a implantação precisa aceitar acesso sem login Google (opção **Qualquer pessoa**, se disponível). O código valida o token antes de abrir a planilha.
8. Copie a URL terminada em `/exec` para `DATA_API_URL`. Configure `DATA_API_TOKEN` com o mesmo valor de `API_TOKEN` e `DASHBOARD_PASSWORD` com uma senha forte e diferente do token.
9. Ao alterar o script, publique uma nova versão da implantação. Não use a URL `/dev`.

O POST envia JSON `{"token":"..."}`. O retorno de sucesso é `{"ok":true,"records":[...]}`; falhas retornam `{"ok":false,"error":"..."}`. GET nunca retorna registros. Como ContentService não fornece controle normal do status HTTP, o cliente verifica o campo `ok`, além do status HTTP. Requests segue o redirecionamento do ContentService para obter a resposta; a consulta inicial é sempre POST.

## Regras do painel

- Somente `Validade = VÁLIDO` entra nos indicadores, filtros, gráficos e tabela; espaços externos e caixa são normalizados. `VALIDO` sem acento não é considerado o marcador `VÁLIDO`.
- Status vazio vira `SEM STATUS`. `CONCLUÍDO`/`CONCLUIDO`/`CONCLUÍDOS`, `PENDENTE`/`PENDENTES` e `EM ATENDIMENTO` alimentam os respectivos cards. Outros status permanecem visíveis no gráfico, filtros e total.
- Taxa de conclusão = concluídos / total filtrado. Sem chamados, a taxa é zero.
- O período é inclusivo. Sem seleção, inclui todos os registros. Com intervalo completo, registros sem data válida são excluídos. A evolução mostra aberturas por dia, incluindo dias intermediários sem chamados, e exclui datas inválidas.
- Busca literal, parcial, sem distinção de caixa ou acentos, por vendedor ou matrícula. Filtros vazios significam todos.
- Cache no servidor por 60 segundos. A próxima interação após o vencimento refaz a consulta; não há atualização automática em segundo plano. **Atualizar dados** limpa o cache e consulta novamente. Cache compartilhado entre sessões autenticadas da mesma configuração; **Sair** limpa o estado da sessão.
- A tabela usa HTML escapado, sem edição e sem botão de download. A barra de ferramentas dos gráficos é desativada. Como em qualquer visualização web, não é possível impedir cópia manual ou captura de tela dos dados já exibidos.
- Falhas de conexão, token, esquema ou configuração bloqueiam a apresentação dos dados e mostram uma mensagem sem expor os secrets.

## Publicar o Streamlit

Configure o repositório e `app.py` no seu serviço Streamlit, instale `requirements.txt` e cadastre os três secrets no gerenciador da hospedagem. Mantenha HTTPS habilitado. A configuração local do tema está em `.streamlit/config.toml`. Não existe escrita na base nem funcionalidade de exportação.

## Verificações

```powershell
python -m compileall app.py
python -m pip check
```

Teste senha incorreta/correta, saída, filtros sem resultados, período, paginação e atualização com uma base de homologação. A conexão real depende da implantação e dos secrets fornecidos pelo administrador.

Referências: [cache Streamlit](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_data), [Apps Script Web Apps](https://developers.google.com/apps-script/guides/web), [restrições de scripts vinculados](https://developers.google.com/apps-script/guides/bound).
