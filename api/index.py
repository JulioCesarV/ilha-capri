import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from supabase import create_client, Client
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, template_folder='../templates')

app.secret_key = os.environ.get('FLASK_SECRET_KEY')
if not app.secret_key:
    raise RuntimeError("FLASK_SECRET_KEY não definida. Configure no .env (local) ou nas Environment Variables (Vercel).")

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

# --- CLIENTE SUPABASE ISOLADO POR REQUEST ---
# Não usamos mais um cliente global, pois o SDK do Supabase guarda a sessão
# do último login dentro do cliente, causando vazamento de sessão entre
# requisições de usuários diferentes.
def get_supabase():
    """Cria um cliente Supabase novo por request, autenticado com o JWT
    do usuário logado (se houver). Isso faz o RLS funcionar corretamente."""
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    token = session.get('supabase_token')
    if token:
        try:
            client.postgrest.auth(token)
        except Exception:
            # Token inválido/expirado — segue como anon; o get_logged_user
            # vai retornar None e a rota redireciona pro login.
            pass
    return client

def get_logged_user():
    token = session.get('supabase_token')
    if not token:
        return None
    try:
        db = get_supabase()
        user_res = db.auth.get_user(token)
        if not user_res.user:
            return None
        profile = db.table('profiles').select('*').eq('id', user_res.user.id).maybe_single().execute()
        return profile.data
    except Exception as e:
        app.logger.error(f"Erro em get_logged_user: {e}")
        return None

def verificar_conflito(data, inicio, fim, reserva_id=None):
    db = get_supabase()
    res = db.table('reservations').select('*')\
        .eq('reservation_date', data)\
        .lt('start_time', fim)\
        .gt('end_time', inicio).execute()

    if reserva_id:
        conflitos = [r for r in res.data if str(r['id']) != str(reserva_id)]
        return len(conflitos) > 0
    return len(res.data) > 0

# --- FUNÇÃO AUXILIAR: VALIDAÇÃO DA REGRA DE 15 DIAS ---
def validar_regra_15_dias(unit_number, data_escolhida_str, reserva_id_atual=None):
    data_nova = datetime.strptime(data_escolhida_str, '%Y-%m-%d').date()

    db = get_supabase()
    res = db.table('reservations').select('id, reservation_date').eq('unit_number', unit_number).execute()

    for r in res.data:
        if reserva_id_atual and str(r['id']) == str(reserva_id_atual):
            continue

        data_existente = datetime.strptime(r['reservation_date'], '%Y-%m-%d').date()
        diferenca = abs((data_nova - data_existente).days)

        if diferenca < 15:
            return False, data_existente.strftime('%d/%m/%Y')

    return True, None

@app.route('/')
def index():
    user = get_logged_user()
    hoje = datetime.now().strftime('%Y-%m-%d')

    db = get_supabase()
    res = db.table('reservations').select('*')\
        .gte('reservation_date', hoje)\
        .order('reservation_date', desc=False)\
        .order('start_time', desc=False)\
        .execute()

    for r in res.data:
        dt_obj = datetime.strptime(r['reservation_date'], '%Y-%m-%d')
        r['display_date'] = dt_obj.strftime('%d/%m/%y')
        r['display_start'] = r['start_time'][:5]
        r['display_end'] = r['end_time'][:5]

    return render_template('index.html', reservations=res.data, user=user)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            flash("⚠️ As senhas não coincidem. Tente novamente.")
            return redirect(url_for('signup'))

        try:
            db = get_supabase()
            auth_res = db.auth.sign_up({"email": email, "password": password})
            if auth_res.user:
                db.table('profiles').insert({
                    "id": auth_res.user.id,
                    "email": email,
                    "full_name": f"{request.form.get('nome')} {request.form.get('sobrenome')}",
                    "whatsapp": request.form.get('whatsapp'),
                    "unit_number": request.form.get('unidade'),
                    "is_admin": False
                }).execute()
                flash("✅ Conta criada! Faça o login.")
                return redirect(url_for('login'))
        except Exception as e:
            flash(f"Erro no cadastro: {str(e)}")
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            db = get_supabase()
            res = db.auth.sign_in_with_password({
                "email": request.form.get('email'),
                "password": request.form.get('password')
            })
            session['supabase_token'] = res.session.access_token
            return redirect(url_for('index'))
        except Exception as e:
            app.logger.error(f"Erro em login: {e}")
            flash("❌ E-mail ou senha incorretos.")
    return render_template('login.html')

@app.route('/reservar', methods=['GET', 'POST'])
def reservar():
    user = get_logged_user()
    if not user: return redirect(url_for('login'))

    if user.get('is_blocked'):
        flash("⚠️ Sua unidade possui pendências. A reserva não pode ser efetuada. Procure o síndico.")
        return redirect(url_for('index'))

    if request.method == 'POST':
        data = request.form.get('data')
        inicio_str = request.form.get('inicio')
        fim_str = request.form.get('fim')

        # REGRA DE 15 DIAS (Admins estão isentos)
        if not user['is_admin']:
            passou_regra, data_conflito = validar_regra_15_dias(user['unit_number'], data)
            if not passou_regra:
                flash(f"⚠️ Regimento: Sua unidade já possui uma reserva em {data_conflito}. O intervalo mínimo entre agendamentos é de 15 dias.")
                return redirect(url_for('reservar'))

        form_inicio = datetime.strptime(inicio_str, '%H:%M').time()
        form_fim = datetime.strptime(fim_str, '%H:%M').time()
        limite_inicio = datetime.strptime('08:00', '%H:%M').time()
        limite_fim = datetime.strptime('22:00', '%H:%M').time()

        if form_inicio < limite_inicio or form_fim > limite_fim:
            flash("⚠️ Erro: Horário permitido apenas das 08:00 às 22:00.")
            return redirect(url_for('reservar'))

        dt = datetime.strptime(data, '%Y-%m-%d')
        if dt.weekday() == 6:
            flash("⚠️ Erro: Não são permitidas reservas aos domingos.")
            return redirect(url_for('reservar'))

        if form_fim <= form_inicio:
            flash("⚠️ Erro: O horário final deve ser depois do horário inicial.")
            return redirect(url_for('reservar'))

        if dt.date() < datetime.now().date():
            flash("⚠️ Erro: Não é possível reservar para datas passadas.")
            return redirect(url_for('reservar'))

        if verificar_conflito(data, inicio_str, fim_str):
            flash("⚠️ Erro: Este horário já está ocupado.")
            return redirect(url_for('reservar'))

        db = get_supabase()
        db.table('reservations').insert({
            "user_id": user['id'], "unit_number": user['unit_number'],
            "reservation_date": data, "start_time": inicio_str, "end_time": fim_str
        }).execute()
        flash("✅ Reserva realizada!")
        return redirect(url_for('index'))
    return render_template('reservar.html')

@app.route('/editar/<id>', methods=['GET', 'POST'])
def editar(id):
    user = get_logged_user()
    db = get_supabase()
    res_data = db.table('reservations').select('*').eq('id', id).maybe_single().execute().data

    if not user or not res_data: return redirect(url_for('index'))

    if not (user['is_admin'] or str(user['unit_number']) == str(res_data['unit_number'])):
        flash("⚠️ Sem permissão para editar.")
        return redirect(url_for('index'))

    if user.get('is_blocked'):
        flash("⚠️ Sua unidade possui pendências. Não é possível editar reservas. Procure o síndico.")
        return redirect(url_for('index'))

    if request.method == 'POST':
        data = request.form.get('data')
        inicio_str = request.form.get('inicio')
        fim_str = request.form.get('fim')

        # REGRA DE 15 DIAS NA EDIÇÃO
        if not user['is_admin']:
            passou_regra, data_conflito = validar_regra_15_dias(user['unit_number'], data, id)
            if not passou_regra:
                flash(f"⚠️ Intervalo insuficiente: você possui outra reserva em {data_conflito}. O mínimo é 15 dias entre usos.")
                return redirect(url_for('editar', id=id))

        form_inicio = datetime.strptime(inicio_str, '%H:%M').time()
        form_fim = datetime.strptime(fim_str, '%H:%M').time()
        limite_inicio = datetime.strptime('08:00', '%H:%M').time()
        limite_fim = datetime.strptime('22:00', '%H:%M').time()

        if form_inicio < limite_inicio or form_fim > limite_fim:
            flash("⚠️ Erro: Horário permitido apenas das 08:00 às 22:00.")
            return redirect(url_for('editar', id=id))

        dt = datetime.strptime(data, '%Y-%m-%d')
        if dt.weekday() == 6:
            flash("⚠️ Erro: Não são permitidas reservas aos domingos.")
            return redirect(url_for('editar', id=id))

        if form_fim <= form_inicio:
            flash("⚠️ Erro: O horário final deve ser depois do horário inicial.")
            return redirect(url_for('editar', id=id))

        if dt.date() < datetime.now().date():
            flash("⚠️ Erro: Não é possível reservar para datas passadas.")
            return redirect(url_for('editar', id=id))

        if verificar_conflito(data, inicio_str, fim_str, id):
            flash("⚠️ Erro: Conflito de horário.")
            return redirect(url_for('editar', id=id))

        db.table('reservations').update({
            "reservation_date": data, "start_time": inicio_str, "end_time": fim_str
        }).eq('id', id).execute()
        flash("✅ Atualizado com sucesso!")
        return redirect(url_for('index'))
    return render_template('editar.html', r=res_data)

@app.route('/delete/<id>', methods=['POST'])
def delete(id):
    user = get_logged_user()
    if not user:
        return redirect(url_for('login'))

    db = get_supabase()
    res = db.table('reservations').select('id, unit_number')\
        .eq('id', id).maybe_single().execute().data

    if not res:
        flash("⚠️ Reserva não encontrada.")
        return redirect(url_for('index'))

    if not (user['is_admin'] or str(user['unit_number']) == str(res['unit_number'])):
        flash("⚠️ Você não tem permissão para excluir esta reserva.")
        return redirect(url_for('index'))

    db.table('reservations').delete().eq('id', id).execute()
    flash("✅ Reserva removida.")
    return redirect(url_for('index'))

@app.route('/admin/usuarios')
def admin_usuarios():
    user = get_logged_user()
    if not user or not user['is_admin']:
        return redirect(url_for('index'))

    db = get_supabase()
    profiles_res = db.table('profiles').select('*').order('unit_number').execute()
    profiles = profiles_res.data
    reservations_res = db.table('reservations').select('*').execute()
    all_reservations = reservations_res.data
    hoje = datetime.now().date()

    for p in profiles:
        user_res = [r for r in all_reservations if r['user_id'] == p['id']]
        past_res = [r for r in user_res if datetime.strptime(r['reservation_date'], '%Y-%m-%d').date() <= hoje]
        p['total_uses'] = len(past_res)

        if past_res:
            past_res.sort(key=lambda x: x['reservation_date'], reverse=True)
            last_date_obj = datetime.strptime(past_res[0]['reservation_date'], '%Y-%m-%d')
            p['last_use'] = last_date_obj.strftime('%d/%m/%y')
        else:
            p['last_use'] = "Nenhuma"

        raw_phone = ''.join(filter(str.isdigit, p['whatsapp'] or ''))
        if not raw_phone:
            p['wa_link'] = None
        else:
            if not raw_phone.startswith('55'):
                raw_phone = '55' + raw_phone
            p['wa_link'] = f"https://wa.me/{raw_phone}"

    return render_template('usuarios.html', profiles=profiles, user=user)

@app.route('/admin/usuario/toggle_block/<id>', methods=['POST'])
def toggle_block(id):
    user = get_logged_user()
    if not user or not user['is_admin']: return redirect(url_for('index'))
    db = get_supabase()
    target = db.table('profiles').select('is_blocked').eq('id', id).single().execute()
    novo_status = not target.data['is_blocked']
    db.table('profiles').update({"is_blocked": novo_status}).eq('id', id).execute()
    return redirect(url_for('admin_usuarios'))

@app.route('/admin/usuario/editar/<id>', methods=['GET', 'POST'])
def admin_editar_usuario(id):
    user = get_logged_user()
    if not user or not user['is_admin']: return redirect(url_for('index'))
    db = get_supabase()
    if request.method == 'POST':
        # Não permite um admin se rebaixar
        if str(id) == str(user['id']) and request.form.get('is_admin') != '1':
            flash("⚠️ Você não pode remover seu próprio acesso de administrador.")
            return redirect(url_for('admin_editar_usuario', id=id))
        db.table('profiles').update({
            "full_name": request.form.get('nome'),
            "email": request.form.get('email'),
            "whatsapp": request.form.get('whatsapp'),
            "unit_number": request.form.get('unidade'),
            "is_admin": request.form.get('is_admin') == '1'
        }).eq('id', id).execute()
        flash("✅ Morador atualizado!")
        return redirect(url_for('admin_usuarios'))
    target = db.table('profiles').select('*').eq('id', id).maybe_single().execute()
    return render_template('admin_edit_user.html', u=target.data, current_user=user)

@app.route('/admin/usuario/delete/<id>', methods=['POST'])
def admin_delete_usuario(id):
    user = get_logged_user()
    if user and user['is_admin']:
        db = get_supabase()
        db.table('profiles').delete().eq('id', id).execute()
        flash("✅ Morador removido.")
    return redirect(url_for('admin_usuarios'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)