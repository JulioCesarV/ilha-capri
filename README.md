# 🏢 Residencial Ilha de Capri - Sistema de Reservas

Este é um sistema web minimalista e funcional desenvolvido para a gestão de reservas da **Área Gourmet** do Residencial Ilha de Capri. O projeto foi desenhado com foco total na experiência do usuário via smartphone, facilitando o acesso através de links compartilhados no WhatsApp.

---

## 🚀 Funcionalidades

### 👤 Para os Condôminos
- **Cadastro Simples:** Registro através de e-mail pessoal, nome, sobrenome, WhatsApp e número da unidade.
- **Reserva Inteligente:** Calendário interativo para seleção de datas e horários.
- **Regras Automáticas:** O sistema impede reservas aos domingos e fora do horário permitido (08h às 22h - Lei do Silêncio).
- **Meus Agendamentos:** Possibilidade de editar ou excluir suas próprias reservas.
- **Dashboard Público:** Visualização em tempo real das datas ocupadas e horários.

### 🔐 Para o Administrador
- **Painel de Controle:** Visualização de todos os moradores cadastrados.
- **Gestão de Moradores:** Editar dados de qualquer morador ou excluí-los se necessário.
- **Gestão de Reservas:** Criar, editar ou excluir reservas de qualquer unidade.
- **Sistema de Bloqueio:** Botão para bloquear usuários inadimplentes, impedindo-os de realizar novas reservas até a regularização com o síndico.
- **WhatsApp Direto:** Link integrado para iniciar conversas com os moradores com apenas um clique.

---

## 🛠️ Tecnologias Utilizadas

- **Linguagem:** [Python](https://www.python.org/) (Flask)
- **Banco de Dados:** [Supabase](https://supabase.com/) (PostgreSQL)
- **Autenticação:** Supabase Auth
- **Frontend:** HTML5, [Tailwind CSS](https://tailwindcss.com/) (Mobile-First)
- **Hospedagem:** [Vercel](https://vercel.com/)
- **Integração:** Links diretos do WhatsApp (`wa.me`) — sem uso de API oficial

---

## 📏 Regras de Negócio Implementadas

1. **Horário de Funcionamento:** Reservas permitidas apenas das 08:00 às 22:00.
2. **Dias Permitidos:** De segunda a sábado. Domingos são bloqueados para manutenção/limpeza.
3. **Conflito de Horário:** O sistema impede automaticamente duas reservas no mesmo intervalo de tempo.
4. **Regra dos 15 dias:** Cada unidade pode ter apenas uma reserva a cada 15 dias. Vale para todas as contas da mesma unidade.
5. **Segurança (RLS):** Tabelas protegidas por *Row Level Security* no banco de dados, garantindo que um morador não altere dados de outro.
6. **Privacidade:** O Dashboard oculta reservas que já passaram, mantendo a tela inicial sempre limpa e atualizada.

---

## 📦 Como configurar o ambiente

### 1. Requisitos
- Conta no GitHub.
- Conta no Supabase.
- Conta na Vercel.

### 2. Variáveis de Ambiente
No ambiente local (arquivo `.env`) ou na Vercel, configure as seguintes chaves:
- `SUPABASE_URL`: URL do seu projeto Supabase.
- `SUPABASE_KEY`: Chave `anon public` do seu projeto.
- `FLASK_SECRET_KEY`: Uma senha aleatória para proteger as sessões do site.

### 3. Estrutura de Pastas
```text
├── api/
│   └── index.py        # Lógica principal do servidor
├── templates/          # Arquivos HTML (Frontend)
├── requirements.txt    # Dependências do Python
├── vercel.json         # Configuração de deploy da Vercel
├── .gitignore          # Arquivos ignorados pelo Git (.env)
├── README.md           # Este arquivo (visão geral)
└── CONTEXTO.md         # Contexto técnico completo
```

---

## 📄 Licença
Este projeto foi desenvolvido para fins não lucrativos e de uso exclusivo do condomínio **Residencial Ilha de Capri**.

---

### 👨‍💻 Autor
Desenvolvido para organizar e facilitar a convivência entre os condôminos.

---

## 📚 Documentação adicional

- [CONTEXTO.md](./CONTEXTO.md) — contexto técnico completo, decisões,
  histórico de correções, bugs conhecidos e processo de desenvolvimento.
- [README.md](./README.md) — este arquivo (visão geral).

---

### Última atualização

**10/10/2026** — [ver contexto completo](./CONTEXTO.md)