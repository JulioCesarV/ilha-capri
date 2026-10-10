# 📋 Contexto do Projeto — Sistema de Reservas Ilha de Capri

Documento de transferência e contexto para desenvolvedores, mantenedores
e para o próprio autor no futuro. **Não contém informações sensíveis.**

---

## 🏢 Sobre o condomínio

- **Nome**: Residencial Ilha de Capri
- **Total de unidades**: 32
- **Área gerenciada pelo sistema**: Área Gourmet
- **Finalidade do sistema**: gestão de reservas da área gourmet, acessível
  por links compartilhados no WhatsApp, com foco em uso mobile.

---

## 👨‍💻 Sobre o autor

- **GitHub**: [JulioCesarV](https://github.com/JulioCesarV)
- **Repositório**: [JulioCesarV/ilha-capri](https://github.com/JulioCesarV/ilha-capri)
- **Papel**: desenvolvedor voluntário e único mantenedor do código

---

## 🛠️ Stack técnica

| Camada | Tecnologia |
|--------|-----------|
| Backend | Python 3.12 (Flask) |
| Banco de dados | Supabase (PostgreSQL + Auth) |
| Frontend | HTML5 + Tailwind CSS (via CDN, mobile-first) |
| Hospedagem | Vercel (deploy automático via GitHub) |
| Automação de keep-alive | Supabase Cron (`pg_cron`) |

### Estrutura de arquivos

```
ilha-capri/
├── api/
│   └── index.py        # Backend Flask (rotas + lógica)
├── templates/          # Templates HTML (Jinja2)
│   ├── admin_edit_user.html
│   ├── base.html
│   ├── editar.html
│   ├── index.html
│   ├── login.html
│   ├── reservar.html
│   ├── signup.html
│   └── usuarios.html
├── requirements.txt    # Dependências Python
├── vercel.json         # Configuração de deploy
├── .gitignore          # Arquivos ignorados (.env, venv/, *.bak)
├── README.md           # Visão geral do projeto
└── CONTEXTO.md         # Este arquivo
```

---

## 📏 Regras de negócio

### Reservas

- **Horário permitido**: 08:00 às 22:00
- **Dias permitidos**: segunda a sábado (domingos bloqueados para limpeza)
- **Conflito de horário**: sistema impede duas reservas no mesmo intervalo
- **Regra dos 15 dias**: uma reserva por **unidade** a cada 15 dias
  (a regra é por unidade, não por conta — evita burla com múltiplas contas)
- **Cancelamento/edição**: morador pode editar/excluir suas próprias reservas
- **Bloqueio**: moradores inadimplentes (marcados como `is_blocked`) não
  podem reservar nem editar reservas

### Cadastro

- **Uma conta por e-mail**
- **Múltiplas contas por unidade**: permitido atualmente (casais, família)
  - Futuro: avaliar bloqueio para 1 conta por unidade
- **Campos**: nome completo, e-mail, WhatsApp, unidade, senha

### Administrador

- **Síndico** tem acesso admin (`is_admin = true`)
- **Pode**: ver todos os moradores, editar dados, bloquear/desbloquear,
  criar/editar/excluir reservas de qualquer morador
- **Não pode**: remover seu próprio acesso de admin (proteção dupla:
  frontend + backend)

### Segurança

- Rotas de ação (delete, toggle_block) exigem **POST** (não GET)
- Sessão isolada por request (cliente Supabase recriado a cada chamada)
- RLS do Supabase ativo (Row Level Security)
- Chaves de API apenas em variáveis de ambiente (nunca no código)

---

## 🔑 Decisões de negócio tomadas

| Decisão | Status |
|---------|--------|
| Regra dos 15 dias por **unidade** (não por conta) | ✅ Implementado |
| Bloquear vs deletar morador | ✅ **Só bloquear**. Deleção é feita direto no Supabase |
| Domingos bloqueados | ✅ Implementado |
| Horário 08h-22h | ✅ Implementado |
| Múltiplas contas por unidade | ⚠️ Permitido por ora; futuro avaliar 1 conta por unidade |
| Taxa/caução | ❌ Não há |

---

## 🗂️ Variáveis de ambiente necessárias

Configuradas no `.env` (local) e nas **Environment Variables** da Vercel
(produção). **Nunca commitar no Git.**

| Variável | Descrição |
|----------|-----------|
| `FLASK_SECRET_KEY` | Chave aleatória para sessões Flask (gerar com `secrets.token_hex(32)`) |
| `SUPABASE_URL` | URL do projeto Supabase |
| `SUPABASE_KEY` | Chave `anon public` do Supabase (respeita RLS) |

---

## 🤖 Automações

### Keep-alive do Supabase

O plano Free do Supabase pausa projetos após 7 dias sem atividade no banco.
Para evitar isso, há um **cron job** (`pg_cron`) que insere uma linha na
tabela `bd_ativo` a cada 3 dias:

```sql
SELECT cron.schedule(
  'projetoAtivo',
  '0 0 */3 * *',
  $$ INSERT INTO bd_ativo(num) VALUES(1); $$
);
```

Para verificar:
```sql
SELECT jobid, jobname, schedule, active FROM cron.job;
SELECT * FROM cron.job_run_details ORDER BY start_time DESC LIMIT 10;
```

---

## 🐛 Histórico de correções

### PRs mergeados

| PR | Descrição |
|----|-----------|
| #1 | Delete de reserva exigia apenas estar logado — corrigido para POST + validação de dono/admin |
| #2 | Validações no backend (senhas, datas, horários) + refactor do cliente Supabase (isolamento por request) |
| #3 | Regra dos 15 dias por unidade + rotas admin POST + proteção admin auto-rebaixar + WhatsApp vazio + logging |

### Bugs corrigidos (referência)

- `/delete/<id>` sem verificação de dono
- Bloqueado conseguia editar reservas
- Secret key com fallback inseguro
- Falta de validação `fim > inicio` (reservar e editar)
- Permitia reservas em datas passadas
- WhatsApp vazio gerava link quebrado
- `except:` nu escondia erros reais
- Ações destrutivas via GET (vulnerável a CSRF)
- `confirm_password` ignorado no signup
- Admin podia se rebaixar sem querer
- Regra dos 15 dias era por conta, não por unidade

---

## 📝 Bugs conhecidos / melhorias pendentes

### 🔴 Alta prioridade

- **Perfil duplicado em e-mail repetido**: se o Supabase Auth estiver sem
  "Confirm email", pode gerar `profiles` duplicados com mesmo e-mail
- **Alterar e-mail só no profile**: a função de admin altera o e-mail em
  `profiles`, mas não em `auth.users` — pode causar divergência

### 🟡 Média prioridade

- `formatTime` no JS aceita "0" e passa pro backend → erro 500
- Contagem "total de usos" no painel admin inclui reservas de hoje
- `<input type="date">` sem atributo `min` (permite selecionar datas passadas no front)
- Todas as mensagens `flash` usam o mesmo estilo visual (sem diferenciação
  entre sucesso/erro)
- Frontend não valida senhas iguais no signup (backend valida)

### 🟢 Baixa prioridade / arquitetura

- **Sem CSRF protection**: formulários POST não têm token CSRF
  (mitigado por sessão isolada + validações de backend, mas ideal adicionar Flask-WTF)
- **Sem testes automatizados**
- **Sem error handler global** (`@app.errorhandler`)
- **Logging estruturado**: hoje usa `app.logger.error` simples
- **Rodar com gunicorn em produção** (hoje usa `app.run()`)

---

## 🚀 Processo de desenvolvimento

### Setup local

```bash
git clone https://github.com/JulioCesarV/ilha-capri.git
cd ilha-capri
py -m venv venv                    # Windows (ou python3 -m venv venv)
venv\Scripts\Activate.ps1          # Windows (ou source venv/bin/activate)
pip install -r requirements.txt
```

Criar `.env` na raiz com as 3 variáveis.

Rodar:
```bash
py api\index.py
```

Acessar: http://127.0.0.1:5000

### Fluxo de trabalho

1. Criar branch: `git checkout -b fix/nome-da-correcao`
2. Aplicar mudanças
3. Testar localmente
4. Commit: `git commit -m "fix: descrição"`
5. Push: `git push origin fix/nome-da-correcao`
6. Abrir PR no GitHub
7. Merge → Vercel deploya automaticamente
8. Testar em produção

### Rollback em produção

Se algo quebrar:

1. Vercel → **Deployments**
2. Encontrar o deploy anterior estável
3. Menu **"..."** → **Promote to Production**

Isso reverte instantaneamente.

---

## 🆘 Situações de emergência

### Banco fora do ar

1. Verificar status do Supabase: https://status.supabase.com/
2. Se o projeto estiver pausado (Free tier), restaurar no painel

### Site fora do ar

1. Vercel → **Deployments** → verificar logs do último deploy
2. Se o último estiver com erro, fazer rollback pro anterior

### Erro em produção que não aparece em local

1. Vercel → **Deployments** → último deploy → **Functions** → **Logs**
2. Como o código tem `app.logger.error`, os erros reais aparecem nos logs

### Usuário preso no sistema

- **Deletar perfil**: Supabase → Table Editor → `profiles` → apagar linha
- **Deletar usuário do Auth**: Supabase → Authentication → Users → apagar
  ⚠️ Deletar do Auth sem deletar o profile deixa o perfil órfão

### Reserva presa / conflito

- Supabase → Table Editor → `reservations` → apagar ou editar linha

---

## 🔐 Acessos e contas

**Este documento é público. Não inclui credenciais.**

Para informações de acesso (Supabase, Vercel, GitHub), consulte o
mantenedor do projeto: [@JulioCesarV](https://github.com/JulioCesarV).

---

## 🎯 Recomendações para o futuro

### Curto prazo (quando houver tempo)

1. **Adicionar CSRF protection** com Flask-WTF — proteção contra ataques
   CSRF em formulários POST
2. **Impedir contas duplicadas por unidade** — decidir com o síndico se
   passa a ser 1 conta por unidade (bloqueio no signup + aviso aos moradores)
3. **Unificar e-mail entre `profiles` e `auth.users`** — decidir se o
   e-mail é editável pelo admin e sincronizar os dois lados
4. **`<input type="date">` com `min`** — impedir seleção de datas passadas
   no frontend
5. **Diferenciar visualmente `flash` de sucesso/erro** — cores diferentes
   no `base.html`

### Médio prazo

6. **Notificações por e-mail** — avisar moradores sobre confirmação,
   cancelamento e lembretes de reserva
7. **Testes automatizados** — pelo menos dos fluxos críticos (login,
   reserva, delete)
8. **Painel de admin com relatórios** — reservas do mês, unidades mais
   ativas, inadimplentes
9. **Rodar com gunicorn em produção** — em vez do servidor de dev do Flask

### Longo prazo

10. **PWA (Progressive Web App)** — permitir instalação no celular
11. **Notificações push** — lembretes automáticos
12. **Histórico de auditoria** — registrar quem alterou o quê
13. **Logs estruturados** — enviar para serviço externo (Sentry, etc)
14. **Multi-área** — suportar outras áreas (salão de festas, churrasqueira)

---

## 📄 Licença

Projeto desenvolvido para fins **não lucrativos** e de uso **exclusivo**
do Residencial Ilha de Capri.

---

**Última atualização**: 10/10/2026
**Mantenedor**: [@JulioCesarV](https://github.com/JulioCesarV)