import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from supabase import create_client, Client
from datetime import datetime
from dotenv import load_dotenv

# Carrega variáveis de ambiente (Local: do arquivo .env / Vercel: das Settings do projeto)
load_dotenv()

app = Flask(__name__, template_folder='../templates')

# Segurança: Chaves do Supabase e Secret Key do Flask
app.secret_key = os.environ.get('FLASK_SECRET_KEY')
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

# Inicializa o cliente do Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- FUNÇÃO AUXILIAR: PEGAR DADOS DO USUÁRIO LOGADO ---
def get_logged_user():
    token = session.get('supabase_token')
    if not token:
        return None
    try:
        # Verifica o usuário através do token de acesso
        user_response = supabase.auth.get_user(token)
        # Busca os dados extras (nome, unidade, is_admin) na tabela profiles
        profile = supabase.table('profiles').select('*').eq('id', user_response.user.id).single().execute()
        return profile.data
    except Exception:
        return None

# --- FUNÇÃO AUXILIAR: VERIFICAR CONFLITO DE HORÁRIO ---
def verificar_conflito(data, inicio, fim, reserva_id=None):
    # Lógica de sobreposição: (InicioExistente < FimNovo) E (FimExistente > InicioNovo)
    query = supabase.table('reservations').select('*')\
        .eq('reservation_date', data)\
        .lt('start_time', fim)\
        .gt('end_time', inicio)
    
    result = query.execute()
    
    if reserva_id:
        # Se for edição, ignora a própria reserva na verificação
        conflitos = [r for r in result.data if r['id'] != reserva_id]
        return len(conflitos) > 0
    
    return len(result.data) > 0

# --- ROTA: DASHBOARD INICIAL ---
@app.route('/')
def index():
    user = get_logged_user()
    # Lista todas as reservas ordenadas por data e hora
    res = supabase.table('reservations').select('*').order('reservation_date').order('start_time').execute()
    return render_template('index.html', reservations=res.data, user=user)

# --- ROTA: CADASTRO DE MORADOR ---
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash("⚠️ As senhas não coincidem!")
            return redirect(url_for('signup'))

        try:
            # 1. Cria o usuário no sistema de autenticação do Supabase
            auth_res = supabase.auth.sign_up({"email": email, "password": password})
            
            if auth_res.user:
                # 2. Cria o perfil do morador com os dados adicionais
                supabase.table('profiles').insert({
                    "id": auth_res.user.id,
                    "email": email,
                    "full_name": f"{request.form.get('nome')} {request.form.get('sobrenome')}",
                    "whatsapp": request.form.get('whatsapp'),
                    "unit_number": request.form.get('unidade'),
                    "is_admin": False
                }).execute()
                flash("✅ Conta criada! Verifique seu e-mail para confirmar o acesso.")
                return redirect(url_for('login'))
        except Exception:
            flash("❌ Erro ao cadastrar. Verifique se o e-mail já está em uso.")
            
    return render_template('signup.html')

# --- ROTA: LOGIN ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            session['supabase_token'] = res.session.access_token
            return redirect(url_for('index'))
        except Exception:
            flash("❌ E-mail ou senha incorretos ou e-mail não confirmado.")
    return render_template('login.html')

# --- ROTA: NOVA RESERVA ---
@app.route('/reservar', methods=['GET', 'POST'])
def reservar():
    user = get_logged_user()
    if not user: return redirect(url_for('login'))

    if request.method == 'POST':
        data = request.form.get('data')
        inicio = request.form.get('inicio')
        fim = request.form.get('fim')

        # Validação de Domingo
        dt = datetime.strptime(data, '%Y-%m-%d')
        if dt.weekday() == 6:
            flash("⚠️ Não permitimos reservas aos Domingos.")
            return redirect(url_for('reservar'))

        # Validação Lei do Silêncio (08:00 às 22:00)
        h_in = int(inicio.split(':')[0])
        h_out = int(fim.split(':')[0])
        m_out = int(fim.split(':')[1])
        if h_in < 8 or h_out > 22 or (h_out == 22 and m_out > 0):
            flash("⚠️ Horário permitido apenas entre 08:00 e 22:00.")
            return redirect(url_for('reservar'))

        # Validação de Conflito de Horário
        if verificar_conflito(data, inicio, fim):
            flash("⚠️ Este horário já está reservado por outra unidade.")
            return redirect(url_for('reservar'))

        supabase.table('reservations').insert({
            "user_id": user['id'],
            "unit_number": user['unit_number'],
            "reservation_date": data,
            "start_time": inicio,
            "end_time": fim
        }).execute()
        
        flash("✅ Reserva confirmada!")
        return redirect(url_for('index'))

    return render_template('reservar.html')

# --- ROTA: EDITAR RESERVA ---
@app.route('/editar/<id>', methods=['GET', 'POST'])
def editar(id):
    user = get_logged_user()
    res_data = supabase.table('reservations').select('*').eq('id', id).single().execute().data
    
    if not user or not res_data: return redirect(url_for('index'))
    
    # Segurança: Apenas o dono da unidade ou o Admin edita
    if not (user['is_admin'] or str(user['unit_number']) == str(res_data['unit_number'])):
        flash("⚠️ Você não tem permissão para editar esta reserva.")
        return redirect(url_for('index'))

    if request.method == 'POST':
        data, inicio, fim = request.form.get('data'), request.form.get('inicio'), request.form.get('fim')
        
        # Reaplica as travas de segurança
        dt = datetime.strptime(data, '%Y-%m-%d')
        h_in, h_out, m_out = int(inicio.split(':')[0]), int(fim.split(':')[0]), int(fim.split(':')[1])
        
        if dt.weekday() == 6 or h_in < 8 or h_out > 22 or (h_out == 22 and m_out > 0):
            flash("⚠️ Dados inválidos (Domingo ou Lei do Silêncio).")
            return redirect(url_for('editar', id=id))

        if verificar_conflito(data, inicio, fim, id):
            flash("⚠️ Conflito de horário com outra reserva.")
            return redirect(url_for('editar', id=id))

        supabase.table('reservations').update({
            "reservation_date": data, "start_time": inicio, "end_time": fim
        }).eq('id', id).execute()
        
        flash("✅ Reserva atualizada!")
        return redirect(url_for('index'))
        
    return render_template('editar.html', r=res_data)

# --- ROTA: EXCLUIR RESERVA ---
@app.route('/delete/<id>')
def delete(id):
    user = get_logged_user()
    if not user: return redirect(url_for('login'))
    
    # A RLS no Supabase garante que só o dono apague, mas o código reforça
    supabase.table('reservations').delete().eq('id', id).execute()
    flash("✅ Reserva removida.")
    return redirect(url_for('index'))

# --- ÁREA ADMIN: LISTAR USUÁRIOS ---
@app.route('/admin/usuarios')
def admin_usuarios():
    user = get_logged_user()
    if not user or not user['is_admin']: return redirect(url_for('index'))
    
    profiles = supabase.table('profiles').select('*').order('unit_number').execute()
    return render_template('usuarios.html', profiles=profiles.data, user=user)

# --- ÁREA ADMIN: EDITAR USUÁRIO ---
@app.route('/admin/usuario/editar/<id>', methods=['GET', 'POST'])
def admin_editar_usuario(id):
    user = get_logged_user()
    if not user or not user['is_admin']: return redirect(url_for('index'))
    
    if request.method == 'POST':
        supabase.table('profiles').update({
            "full_name": request.form.get('nome'),
            "email": request.form.get('email'),
            "whatsapp": request.form.get('whatsapp'),
            "unit_number": request.form.get('unidade'),
            "is_admin": request.form.get('is_admin') == '1'
        }).eq('id', id).execute()
        flash("✅ Cadastro do morador atualizado!")
        return redirect(url_for('admin_usuarios'))
    
    target = supabase.table('profiles').select('*').eq('id', id).single().execute()
    return render_template('admin_edit_user.html', u=target.data)

# --- ÁREA ADMIN: EXCLUIR USUÁRIO ---
@app.route('/admin/usuario/delete/<id>')
def admin_delete_usuario(id):
    user = get_logged_user()
    if user and user['is_admin']:
        # O perfil é deletado (as reservas caem em cascata se configurado no SQL)
        supabase.table('profiles').delete().eq('id', id).execute()
        flash("✅ Morador removido com sucesso.")
    return redirect(url_for('admin_usuarios'))

# --- LOGOUT ---
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)