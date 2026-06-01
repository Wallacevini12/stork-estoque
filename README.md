# Stork Estoque — Sistema de estoque com rastreabilidade por código de barras
# Stack: Flask 3 + MySQL 8 + PWA (QuaggaJS)
# Deploy: Railway.app

## Variáveis de ambiente (configurar no Railway)

| Variável         | Descrição                                        |
|------------------|--------------------------------------------------|
| `SECRET_KEY`     | Chave secreta Flask (gere com `python -c "import secrets; print(secrets.token_hex())"`) |
| `DB_HOST`        | Host do MySQL (Railway injeta automaticamente)   |
| `DB_PORT`        | Porta MySQL (padrão: 3306)                       |
| `DB_NAME`        | Nome do banco (padrão: `estoque`)                |
| `DB_USER`        | Usuário MySQL                                    |
| `DB_PASS`        | Senha MySQL                                      |
| `STORK_ERP_URL`  | URL base do Stork ERP (`https://erpstork-production.up.railway.app`) |
| `STORK_API_KEY`  | Chave de API para autenticar no Stork ERP        |

## Estrutura de rotas

| Rota                    | Método | Descrição                               |
|-------------------------|--------|-----------------------------------------|
| `/`                     | GET    | Dashboard com KPIs                      |
| `/entrada`              | GET    | Tela de entrada de item (mobile)        |
| `/retirada`             | GET    | Tela de retirada com câmera (mobile)    |
| `/itens`                | GET    | Lista de itens com busca                |
| `/historico`            | GET    | Histórico de movimentos                 |
| `/etiqueta/<id>`        | GET    | PDF da etiqueta (100×50mm, Code128)     |
| `/api/entrada`          | POST   | Registra entrada + retorna item_id      |
| `/api/retirada`         | POST   | Valida saldo e registra saída           |
| `/api/item/<codigo>`    | GET    | Busca item por código (pós-scan)        |
| `/api/pecas-erp`        | GET    | Proxy para API do Stork ERP             |

## Login padrão
- Usuário: `admin`
- Senha: `stork123`
- **Alterar após o primeiro acesso!**

## Deploy no Railway
1. Crie um novo projeto no Railway
2. Adicione serviço MySQL e copie as variáveis de conexão
3. Conecte o repositório GitHub
4. Configure as variáveis de ambiente acima
5. O banco é inicializado automaticamente no primeiro acesso à rota `/`
