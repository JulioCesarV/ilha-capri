import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from supabase import create_client, Client
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, template_folder='../templates')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'capri_secret_key')

supabase: Client = create_client(
    os.environ.get('SUPABASE_URL'), 
    os.environ.get('SUPABASE_KEY')
)

def get_logged_user():
    token = session.get('supabase_token')
    if not token: return None
    try:
        user_res = supabase.auth.get_user(token)
        if not user_res.user: return None
        profile = supabase.table('profiles').select('*').eq('id', user_res.user.id).maybe_single().execute()
        return profile.data
    except: return None

def verificar_conflito(data, inicio, fim, reserva_id=None):
    res = supabase.table('reservations').select('*')\
        .eq('reservation_date', data)\
        .lt('start_time', fim)\
        .gt('end_time', inicio).execute()
    
    if reserva_id:
        conflitos = [r for r in res.data if str(r['id']) != str(reserva_id)]
        return len(conflitos) > 0
    return len(res.data) > 0

@app.route('/')
def index():
    user = get_logged_user()
    
    hoje = datetime.now().strftime('%Y-%m-%d')
    
    res = supabase.table('reservations').select('*')\
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
        try:
            auth_res = supabase.auth.sign_up({"email": email, "password": password})
            if auth_res.user:
                supabase.table('profiles').insert({
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
            res = supabase.auth.sign_in_with_password({"email": request.form.get('email'), "password": request.form.get('password')})
            session['supabase_token'] = res.session.access_token
            return redirect(url_for('index'))
        except:
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

        # Conversão para objetos de tempo para validação rigorosa
        form_inicio = datetime.strptime(inicio_str, '%H:%M').time()
        form_fim = datetime.strptime(fim_str, '%H:%M').time()
        limite_inicio = datetime.strptime('08:00', '%H:%M').time()
        limite_fim = datetime.strptime('22:00', '%H:%M').time()

        # TRAVA: Lei do Silêncio
        if form_inicio < limite_inicio or form_fim > limite_fim:
            flash("⚠️ Erro: Horário permitido apenas das 08:00 às 22:00.")
            return redirect(url_for('reservar'))

        # TRAVA: Domingo
        dt = datetime.strptime(data, '%Y-%m-%d')
        if dt.weekday() == 6:
            flash("⚠️ Erro: Não são permitidas reservas aos domingos.")
            return redirect(url_for('reservar'))

        # TRAVA: Conflito
        if verificar_conflito(data, inicio_str, fim_str):
            flash("⚠️ Erro: Este horário já está ocupado.")
            return redirect(url_for('reservar'))

        supabase.table('reservations').insert({
            "user_id": user['id'], "unit_number": user['unit_number'],
            "reservation_date": data, "start_time": inicio_str, "end_time": fim_str
        }).execute()
        flash("✅ Reserva realizada!")
        return redirect(url_for('index'))
    return render_template('reservar.html')

@app.route('/editar/<id>', methods=['GET', 'POST'])
def editar(id):
    user = get_logged_user()
    res_data = supabase.table('reservations').select('*').eq('id', id).maybe_single().execute().data
    
    if not user or not res_data: return redirect(url_for('index'))
    
    if not (user['is_admin'] or str(user['unit_number']) == str(res_data['unit_number'])):
        flash("⚠️ Sem permissão para editar.")
        return redirect(url_for('index'))

    if request.method == 'POST':
        data = request.form.get('data')
        inicio_str = request.form.get('inicio')
        fim_str = request.form.get('fim')

        form_inicio = datetime.strptime(inicio_str, '%H:%M').time()
        form_fim = datetime.strptime(fim_str, '%H:%M').time()
        limite_inicio = datetime.strptime('08:00', '%H:%M').time()
        limite_fim = datetime.strptime('22:00', '%H:%M').time()

        # TRAVA: Lei do Silêncio na edição
        if form_inicio < limite_inicio or form_fim > limite_fim:
            flash("⚠️ Erro: Horário permitido apenas das 08:00 às 22:00.")
            return redirect(url_for('editar', id=id))

        # TRAVA: Domingo na edição
        dt = datetime.strptime(data, '%Y-%m-%d')
        if dt.weekday() == 6:
            flash("⚠️ Erro: Não são permitidas reservas aos domingos.")
            return redirect(url_for('editar', id=id))

        # TRAVA: Conflito na edição
        if verificar_conflito(data, inicio_str, fim_str, id):
            flash("⚠️ Erro: Conflito de horário.")
            return redirect(url_for('editar', id=id))

        supabase.table('reservations').update({
            "reservation_date": data, "start_time": inicio_str, "end_time": fim_str
        }).eq('id', id).execute()
        flash("✅ Atualizado com sucesso!")
        return redirect(url_for('index'))
    return render_template('editar.html', r=res_data)

@app.route('/delete/<id>')
def delete(id):
    user = get_logged_user()
    if user:
        supabase.table('reservations').delete().eq('id', id).execute()
        flash("✅ Removida.")
    return redirect(url_for('index'))

@app.route('/admin/usuarios')
def admin_usuarios():
    user = get_logged_user()
    if not user or not user['is_admin']: return redirect(url_for('index'))
    
    profiles = supabase.table('profiles').select('*').order('unit_number').execute()
    for p in profiles.data:
        raw_phone = ''.join(filter(str.isdigit, p['whatsapp']))
        if not raw_phone.startswith('55'): raw_phone = '55' + raw_phone
        p['wa_link'] = f"https://wa.me/{raw_phone}"
        
    return render_template('usuarios.html', profiles=profiles.data, user=user)

@app.route('/admin/usuario/toggle_block/<id>')
def toggle_block(id):
    user = get_logged_user()
    if not user or not user['is_admin']: return redirect(url_for('index'))
    target = supabase.table('profiles').select('is_blocked').eq('id', id).single().execute()
    novo_status = not target.data['is_blocked']
    supabase.table('profiles').update({"is_blocked": novo_status}).eq('id', id).execute()
    return redirect(url_for('admin_usuarios'))

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
        flash("✅ Morador atualizado!")
        return redirect(url_for('admin_usuarios'))
    target = supabase.table('profiles').select('*').eq('id', id).maybe_single().execute()
    return render_template('admin_edit_user.html', u=target.data)

@app.route('/admin/usuario/delete/<id>')
def admin_delete_usuario(id):
    user = get_logged_user()
    if user and user['is_admin']:
        supabase.table('profiles').delete().eq('id', id).execute()
        flash("✅ Morador removido.")
    return redirect(url_for('admin_usuarios'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)