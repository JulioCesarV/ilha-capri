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
    res = supabase.table('reservations').select('*').order('reservation_date').order('start_time').execute()
    
    for r in res.data:
        # Formata Data para DD/MM/YY
        dt_obj = datetime.strptime(r['reservation_date'], '%Y-%m-%d')
        r['display_date'] = dt_obj.strftime('%d/%m/%y')
        # Formata Hora para HH:MM
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
    if request.method == 'POST':
        data, inicio, fim = request.form.get('data'), request.form.get('inicio'), request.form.get('fim')
        dt = datetime.strptime(data, '%Y-%m-%d')
        if dt.weekday() == 6:
            flash("⚠️ Domingos não são permitidos.")
            return redirect(url_for('reservar'))
        if verificar_conflito(data, inicio, fim):
            flash("⚠️ Horário já ocupado.")
            return redirect(url_for('reservar'))
        
        supabase.table('reservations').insert({
            "user_id": user['id'], "unit_number": user['unit_number'],
            "reservation_date": data, "start_time": inicio, "end_time": fim
        }).execute()
        return redirect(url_for('index'))
    return render_template('reservar.html')

@app.route('/editar/<id>', methods=['GET', 'POST'])
def editar(id):
    user = get_logged_user()
    res_data = supabase.table('reservations').select('*').eq('id', id).maybe_single().execute().data
    if not user or not res_data: return redirect(url_for('index'))
    if request.method == 'POST':
        data, inicio, fim = request.form.get('data'), request.form.get('inicio'), request.form.get('fim')
        if verificar_conflito(data, inicio, fim, id):
            flash("⚠️ Conflito de horário.")
            return redirect(url_for('editar', id=id))
        supabase.table('reservations').update({"reservation_date": data, "start_time": inicio, "end_time": fim}).eq('id', id).execute()
        return redirect(url_for('index'))
    return render_template('editar.html', r=res_data)

@app.route('/delete/<id>')
def delete(id):
    user = get_logged_user()
    if user:
        supabase.table('reservations').delete().eq('id', id).execute()
    return redirect(url_for('index'))

@app.route('/admin/usuarios')
def admin_usuarios():
    user = get_logged_user()
    if not user or not user['is_admin']: return redirect(url_for('index'))
    profiles = supabase.table('profiles').select('*').order('unit_number').execute()
    return render_template('usuarios.html', profiles=profiles.data, user=user)

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
        return redirect(url_for('admin_usuarios'))
    target = supabase.table('profiles').select('*').eq('id', id).maybe_single().execute()
    return render_template('admin_edit_user.html', u=target.data)

@app.route('/admin/usuario/delete/<id>')
def admin_delete_usuario(id):
    user = get_logged_user()
    if user and user['is_admin']:
        supabase.table('profiles').delete().eq('id', id).execute()
    return redirect(url_for('admin_usuarios'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)