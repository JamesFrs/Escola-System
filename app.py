from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from db import query_db, execute_db
from config import SECRET_KEY
from init_db import init_db
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = SECRET_KEY

DISCIPLINAS = ['Matemática', 'Português', 'História', 'Geografia', 'Ciências', 'Inglês', 'Física', 'Química', 'Biologia', 'Educação Física', 'Artes']


def get_turmas():
    return [r['nome'] for r in query_db("SELECT nome FROM turmas ORDER BY nome")]


def log_historico(professor, acao, aluno=None):
    execute_db("INSERT INTO historico (professor, acao, aluno) VALUES (?, ?, ?)",
               (professor, acao, aluno))


@app.before_request
def before_request():
    if request.endpoint in ('login', 'login_professor', 'login_aluno', 'static_file', 'api_buscar'):
        return
    if 'user_type' not in session:
        return redirect(url_for('login'))


@app.route('/')
def index():
    if 'user_type' in session:
        if session['user_type'] == 'professor':
            return redirect(url_for('dashboard'))
        else:
            return redirect(url_for('portal_aluno'))
    return redirect(url_for('login'))


@app.route('/login')
def login():
    return render_template('login.html')


@app.route('/login/professor', methods=['POST'])
def login_professor():
    email = request.form.get('email', '').strip()
    senha = request.form.get('senha', '')
    user = query_db("SELECT * FROM professores WHERE email=?", [email], one=True)
    if user and check_password_hash(user['senha'], senha):
        session['user_type'] = 'professor'
        session['user_id'] = user['id']
        session['user_name'] = user['nome']
        return redirect(url_for('dashboard'))
    flash('Email ou senha incorretos', 'error')
    return redirect(url_for('login'))


@app.route('/login/aluno', methods=['POST'])
def login_aluno():
    nome = request.form.get('nome', '').strip()
    codigo = request.form.get('codigo', '').strip()
    aluno = query_db("SELECT * FROM alunos WHERE nome=? AND codigo=?", [nome, codigo], one=True)
    if aluno:
        session['user_type'] = 'aluno'
        session['user_id'] = aluno['id']
        session['user_name'] = aluno['nome']
        session['user_codigo'] = aluno['codigo']
        session['user_turma'] = aluno['turma']
        return redirect(url_for('portal_aluno'))
    flash('Nome ou código incorretos', 'error')
    return redirect(url_for('login'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ==================== PROFESSOR ====================

@app.route('/dashboard')
def dashboard():
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    total_alunos = query_db("SELECT COUNT(*) as c FROM alunos", one=True)['c']
    total_turmas = query_db("SELECT COUNT(*) as c FROM turmas", one=True)['c']
    today = datetime.now().strftime('%Y-%m-%d')
    provas_semana = query_db(
        "SELECT COUNT(*) as c FROM provas WHERE data >= ? AND data <= ?",
        [today, (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')], one=True)['c']
    pendencias_abertas = query_db("SELECT COUNT(*) as c FROM pendencias", one=True)['c']
    media_geral = query_db("SELECT ROUND(AVG(nota),1) as m FROM notas WHERE nota > 0", one=True)['m'] or 0

    total_freq = query_db("SELECT COUNT(*) as ta, SUM(CASE WHEN presente=0 THEN 1 ELSE 0 END) as tf FROM frequencia", one=True)
    freq_media = 0
    if total_freq['ta'] and total_freq['ta'] > 0:
        freq_media = round(((total_freq['ta'] - (total_freq['tf'] or 0)) / total_freq['ta']) * 100, 1)

    freq_por_disc = query_db("""
        SELECT disciplina, COUNT(*) as total,
               SUM(CASE WHEN presente=0 THEN 1 ELSE 0 END) as faltas
        FROM frequencia GROUP BY disciplina ORDER BY disciplina
    """)

    notas_por_disc = query_db("""
        SELECT disciplina, ROUND(AVG(nota),1) as media
        FROM notas WHERE nota > 0 GROUP BY disciplina ORDER BY media DESC
    """)

    return render_template('professor/dashboard.html',
                           total_alunos=total_alunos, total_turmas=total_turmas,
                           provas_semana=provas_semana, pendencias_abertas=pendencias_abertas,
                           media_geral=media_geral, freq_media=freq_media,
                           freq_por_disc=freq_por_disc, notas_por_disc=notas_por_disc)


# ==================== TURMAS ====================

@app.route('/turmas')
def turmas_lista():
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    turmas_raw = query_db("SELECT * FROM turmas ORDER BY nome")
    turmas = []
    for t in turmas_raw:
        td = dict(t)
        td['total_alunos'] = query_db("SELECT COUNT(*) as c FROM alunos WHERE turma=?", [td['nome']], one=True)['c']
        turmas.append(td)
    return render_template('professor/turmas.html', turmas=turmas)


@app.route('/turmas/nova', methods=['POST'])
def turma_nova():
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    nome = request.form['nome'].strip()
    if not nome:
        flash('Nome da turma é obrigatório', 'error')
        return redirect(url_for('turmas_lista'))
    existing = query_db("SELECT id FROM turmas WHERE nome=?", [nome], one=True)
    if existing:
        flash('Esta turma já existe', 'error')
        return redirect(url_for('turmas_lista'))
    execute_db("INSERT INTO turmas (nome) VALUES (?)", (nome,))
    log_historico(session['user_name'], f'Turma criada: {nome}')
    flash(f'Turma "{nome}" criada com sucesso!', 'success')
    return redirect(url_for('turmas_lista'))


@app.route('/turmas/editar/<int:id>', methods=['POST'])
def turma_editar(id):
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    turma = query_db("SELECT * FROM turmas WHERE id=?", [id], one=True)
    if not turma:
        flash('Turma não encontrada', 'error')
        return redirect(url_for('turmas_lista'))
    novo_nome = request.form['nome'].strip()
    if not novo_nome:
        flash('Nome é obrigatório', 'error')
        return redirect(url_for('turmas_lista'))
    existing = query_db("SELECT id FROM turmas WHERE nome=? AND id!=?", [novo_nome, id], one=True)
    if existing:
        flash('Já existe uma turma com esse nome', 'error')
        return redirect(url_for('turmas_lista'))
    execute_db("UPDATE turmas SET nome=? WHERE id=?", (novo_nome, id))
    execute_db("UPDATE alunos SET turma=? WHERE turma=?", (novo_nome, turma['nome']))
    execute_db("UPDATE frequencia SET turma=? WHERE turma=?", (novo_nome, turma['nome']))
    execute_db("UPDATE provas SET turma=? WHERE turma=?", (novo_nome, turma['nome']))
    execute_db("UPDATE avisos SET turma=? WHERE turma=?", (novo_nome, turma['nome']))
    execute_db("UPDATE agenda SET turma=? WHERE turma=?", (novo_nome, turma['nome']))
    log_historico(session['user_name'], f'Turma renomeada: {turma["nome"]} → {novo_nome}')
    flash(f'Turma renomeada para "{novo_nome}"!', 'success')
    return redirect(url_for('turmas_lista'))


@app.route('/turmas/excluir/<int:id>')
def turma_excluir(id):
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    turma = query_db("SELECT * FROM turmas WHERE id=?", [id], one=True)
    if turma:
        execute_db("DELETE FROM turmas WHERE id=?", [id])
        log_historico(session['user_name'], f'Turma excluída: {turma["nome"]}')
        flash(f'Turma "{turma["nome"]}" excluída!', 'success')
    return redirect(url_for('turmas_lista'))


@app.route('/turmas/<int:id>/alunos')
def turma_alunos(id):
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    turma = query_db("SELECT * FROM turmas WHERE id=?", [id], one=True)
    if not turma:
        flash('Turma não encontrada', 'error')
        return redirect(url_for('turmas_lista'))
    alunos_turma = query_db("SELECT * FROM alunos WHERE turma=? ORDER BY nome", [turma['nome']])
    outros_alunos = query_db("SELECT * FROM alunos WHERE turma!=? ORDER BY nome", [turma['nome']])
    todas_turmas = query_db("SELECT nome FROM turmas ORDER BY nome")
    return render_template('professor/turma_alunos.html', turma=turma, alunos=alunos_turma,
                           outros=outros_alunos, todas_turmas=todas_turmas)


@app.route('/turmas/<int:id>/alunos/adicionar', methods=['POST'])
def turma_adicionar_aluno(id):
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    turma = query_db("SELECT * FROM turmas WHERE id=?", [id], one=True)
    if not turma:
        return redirect(url_for('turmas_lista'))
    codigo = request.form.get('codigo', '').strip()
    aluno = query_db("SELECT * FROM alunos WHERE codigo=?", [codigo], one=True)
    if not aluno:
        flash('Aluno não encontrado', 'error')
        return redirect(url_for('turma_alunos', id=id))
    execute_db("UPDATE alunos SET turma=? WHERE codigo=?", (turma['nome'], codigo))
    execute_db("UPDATE frequencia SET turma=? WHERE codigo_aluno=? AND turma=?", (turma['nome'], codigo, aluno['turma']))
    log_historico(session['user_name'], f'Aluno movido para {turma["nome"]}: {aluno["nome"]} ({codigo})', aluno['nome'])
    flash(f'{aluno["nome"]} movido(a) para {turma["nome"]}!', 'success')
    return redirect(url_for('turma_alunos', id=id))


@app.route('/turmas/<int:id>/alunos/mover', methods=['POST'])
def turma_mover_aluno(id):
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    turma = query_db("SELECT * FROM turmas WHERE id=?", [id], one=True)
    if not turma:
        return redirect(url_for('turmas_lista'))
    codigo = request.form.get('codigo', '').strip()
    nova_turma = request.form.get('nova_turma', '').strip()
    aluno = query_db("SELECT * FROM alunos WHERE codigo=?", [codigo], one=True)
    if not aluno or not nova_turma:
        flash('Dados inválidos', 'error')
        return redirect(url_for('turma_alunos', id=id))
    execute_db("UPDATE alunos SET turma=? WHERE codigo=?", (nova_turma, codigo))
    execute_db("UPDATE frequencia SET turma=? WHERE codigo_aluno=? AND turma=?", (nova_turma, codigo, turma['nome']))
    log_historico(session['user_name'], f'Aluno movido: {aluno["nome"]} de {turma["nome"]} para {nova_turma}', aluno['nome'])
    flash(f'{aluno["nome"]} movido(a) para {nova_turma}!', 'success')
    return redirect(url_for('turma_alunos', id=id))


@app.route('/turmas/<int:id>/alunos/remover', methods=['POST'])
def turma_remover_aluno(id):
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    turma = query_db("SELECT * FROM turmas WHERE id=?", [id], one=True)
    if not turma:
        return redirect(url_for('turmas_lista'))
    codigo = request.form.get('codigo', '').strip()
    aluno = query_db("SELECT * FROM alunos WHERE codigo=?", [codigo], one=True)
    if not aluno:
        flash('Aluno não encontrado', 'error')
        return redirect(url_for('turma_alunos', id=id))
    execute_db("DELETE FROM notas WHERE codigo_aluno=?", [codigo])
    execute_db("DELETE FROM frequencia WHERE codigo_aluno=?", [codigo])
    execute_db("DELETE FROM pendencias WHERE codigo_aluno=?", [codigo])
    execute_db("DELETE FROM alunos WHERE codigo=?", [codigo])
    log_historico(session['user_name'], f'Aluno removido da turma {turma["nome"]}: {aluno["nome"]} ({codigo})', aluno['nome'])
    flash(f'{aluno["nome"]} removido(a) do sistema!', 'success')
    return redirect(url_for('turma_alunos', id=id))


# ==================== ALUNOS ====================

@app.route('/alunos')
def alunos():
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    busca = request.args.get('q', '').strip()
    turmas = get_turmas()
    if busca:
        lista = query_db("SELECT * FROM alunos WHERE nome LIKE ? OR codigo LIKE ? OR turma LIKE ? ORDER BY nome",
                         [f'%{busca}%', f'%{busca}%', f'%{busca}%'])
    else:
        lista = query_db("SELECT * FROM alunos ORDER BY nome")
    return render_template('professor/alunos.html', alunos=lista, busca=busca, turmas=turmas)


@app.route('/alunos/novo', methods=['GET', 'POST'])
def aluno_novo():
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    turmas = get_turmas()
    if request.method == 'POST':
        codigo = request.form['codigo'].strip()
        nome = request.form['nome'].strip()
        turma = request.form['turma']
        nascimento = request.form.get('nascimento', '')
        existing = query_db("SELECT id FROM alunos WHERE codigo=?", [codigo], one=True)
        if existing:
            flash('Este código já está em uso', 'error')
            return render_template('professor/aluno_form.html', aluno=None, turmas=turmas, disciplinas=DISCIPLINAS)
        execute_db("INSERT INTO alunos (codigo, nome, turma, nascimento) VALUES (?, ?, ?, ?)",
                   (codigo, nome, turma, nascimento))
        for disc in DISCIPLINAS:
            execute_db("INSERT OR IGNORE INTO notas (codigo_aluno, disciplina, nota) VALUES (?, ?, 0)",
                       (codigo, disc))
        log_historico(session['user_name'], f'Aluno cadastrado: {nome} ({codigo})', nome)
        flash('Aluno cadastrado com sucesso!', 'success')
        return redirect(url_for('alunos'))
    return render_template('professor/aluno_form.html', aluno=None, turmas=turmas, disciplinas=DISCIPLINAS)


@app.route('/alunos/editar/<int:id>', methods=['GET', 'POST'])
def aluno_editar(id):
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    turmas = get_turmas()
    aluno = query_db("SELECT * FROM alunos WHERE id=?", [id], one=True)
    if not aluno:
        flash('Aluno não encontrado', 'error')
        return redirect(url_for('alunos'))
    if request.method == 'POST':
        nome = request.form['nome'].strip()
        turma = request.form['turma']
        nascimento = request.form.get('nascimento', '')
        execute_db("UPDATE alunos SET nome=?, turma=?, nascimento=? WHERE id=?",
                   (nome, turma, nascimento, id))
        log_historico(session['user_name'], f'Aluno editado: {nome} ({aluno["codigo"]})', nome)
        flash('Aluno atualizado com sucesso!', 'success')
        return redirect(url_for('alunos'))
    return render_template('professor/aluno_form.html', aluno=aluno, turmas=turmas, disciplinas=DISCIPLINAS)


@app.route('/alunos/excluir/<int:id>')
def aluno_excluir(id):
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    aluno = query_db("SELECT * FROM alunos WHERE id=?", [id], one=True)
    if aluno:
        execute_db("DELETE FROM notas WHERE codigo_aluno=?", [aluno['codigo']])
        execute_db("DELETE FROM frequencia WHERE codigo_aluno=?", [aluno['codigo']])
        execute_db("DELETE FROM pendencias WHERE codigo_aluno=?", [aluno['codigo']])
        execute_db("DELETE FROM alunos WHERE id=?", [id])
        log_historico(session['user_name'], f'Aluno excluído: {aluno["nome"]} ({aluno["codigo"]})', aluno['nome'])
        flash('Aluno excluído com sucesso!', 'success')
    return redirect(url_for('alunos'))


@app.route('/alunos/perfil/<int:id>')
def aluno_perfil(id):
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    aluno = query_db("SELECT * FROM alunos WHERE id=?", [id], one=True)
    if not aluno:
        flash('Aluno não encontrado', 'error')
        return redirect(url_for('alunos'))
    notas = query_db("SELECT * FROM notas WHERE codigo_aluno=? ORDER BY disciplina", [aluno['codigo']])
    pendencias = query_db("SELECT * FROM pendencias WHERE codigo_aluno=? ORDER BY data DESC", [aluno['codigo']])
    provas_turma = query_db("SELECT * FROM provas WHERE turma=? ORDER BY data", [aluno['turma']])
    avisos_turma = query_db("SELECT * FROM avisos WHERE turma=? ORDER BY data DESC", [aluno['turma']])

    freq_por_disc = query_db("""
        SELECT disciplina,
               COUNT(*) as total,
               SUM(CASE WHEN presente=1 THEN 1 ELSE 0 END) as presencas,
               SUM(CASE WHEN presente=0 THEN 1 ELSE 0 END) as faltas
        FROM frequencia WHERE codigo_aluno=?
        GROUP BY disciplina ORDER BY disciplina
    """, [aluno['codigo']])

    total_geral = query_db("SELECT COUNT(*) as t, SUM(CASE WHEN presente=0 THEN 1 ELSE 0 END) as f FROM frequencia WHERE codigo_aluno=?", [aluno['codigo']], one=True)

    media_geral = 0
    aprovacoes = []
    for n in notas:
        if n['nota'] > 0:
            status = 'Aprovado' if n['nota'] >= 7 else ('Recuperação' if n['nota'] >= 5 else 'Reprovado')
            aprovacoes.append({'disciplina': n['disciplina'], 'nota': n['nota'], 'status': status})
            media_geral += n['nota']
    count_notas = len([n for n in notas if n['nota'] > 0])
    if count_notas > 0:
        media_geral = round(media_geral / count_notas, 1)
    situacao = 'Aprovado' if media_geral >= 7 else ('Recuperação' if media_geral >= 5 else 'Reprovado')

    return render_template('professor/perfil_aluno.html', aluno=aluno, notas=notas,
                           pendencias=pendencias, provas=provas_turma, avisos=avisos_turma,
                           media_geral=media_geral, situacao=situacao, aprovacoes=aprovacoes,
                           freq_por_disc=freq_por_disc, total_geral=total_geral)


# ==================== NOTAS ====================

@app.route('/notas', methods=['GET', 'POST'])
def notas():
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    if request.method == 'POST':
        codigo = request.form.get('codigo_aluno')
        disc = request.form.get('disciplina')
        nota = request.form.get('nota', 0)
        try:
            nota = float(nota)
        except:
            nota = 0
        aluno = query_db("SELECT nome FROM alunos WHERE codigo=?", [codigo], one=True)
        execute_db("INSERT OR REPLACE INTO notas (codigo_aluno, disciplina, nota) VALUES (?, ?, ?)",
                   (codigo, disc, nota))
        log_historico(session['user_name'], f'Nota alterada: {disc} = {nota}', aluno['nome'] if aluno else codigo)
        flash('Nota salva com sucesso!', 'success')
        return redirect(url_for('notas'))

    aluno_sel = request.args.get('aluno', '')
    notas_aluno = []
    aluno_obj = None
    if aluno_sel:
        aluno_obj = query_db("SELECT * FROM alunos WHERE codigo=?", [aluno_sel], one=True)
        if aluno_obj:
            notas_aluno = query_db("SELECT * FROM notas WHERE codigo_aluno=? ORDER BY disciplina", [aluno_sel])

    lista_alunos = query_db("SELECT * FROM alunos ORDER BY nome")
    return render_template('professor/notas.html', alunos=lista_alunos, aluno_sel=aluno_sel,
                           notas=notas_aluno, aluno_obj=aluno_obj, disciplinas=DISCIPLINAS)


# ==================== FREQUÊNCIA (POR DISCIPLINA + DATA) ====================

@app.route('/frequencia', methods=['GET', 'POST'])
def frequencia():
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    turmas = get_turmas()

    if request.method == 'POST':
        turma = request.form.get('turma')
        disciplina = request.form.get('disciplina')
        data = request.form.get('data')
        if not turma or not disciplina or not data:
            flash('Selecione turma, disciplina e data', 'error')
            return redirect(url_for('frequencia'))
        alunos_turma = query_db("SELECT * FROM alunos WHERE turma=? ORDER BY nome", [turma])
        for a in alunos_turma:
            presente = 1 if request.form.get(f'presenca_{a["codigo"]}') == 'on' else 0
            execute_db("""
                INSERT INTO frequencia (codigo_aluno, disciplina, turma, data, presente)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(codigo_aluno, disciplina, turma, data) DO UPDATE SET presente=?
            """, (a['codigo'], disciplina, turma, data, presente, presente))
            if not presente:
                log_historico(session['user_name'], f'Falta registrada: {disciplina} em {data}', a['nome'])
        flash('Frequência salva com sucesso!', 'success')
        return redirect(url_for('frequencia'))

    turma_sel = request.args.get('turma', '')
    disc_sel = request.args.get('disciplina', '')
    data_sel = request.args.get('data', datetime.now().strftime('%Y-%m-%d'))
    alunos_freq = []

    if turma_sel and disc_sel and data_sel:
        alunos_freq = query_db("""
            SELECT a.*,
                   (SELECT presente FROM frequencia f
                    WHERE f.codigo_aluno=a.codigo AND f.disciplina=? AND f.turma=? AND f.data=?) as status
            FROM alunos a WHERE a.turma=? ORDER BY a.nome
        """, [disc_sel, turma_sel, data_sel, turma_sel])

    return render_template('professor/frequencia.html', turmas=turmas, turma_sel=turma_sel,
                           disc_sel=disc_sel, data_sel=data_sel, alunos=alunos_freq, disciplinas=DISCIPLINAS)


@app.route('/frequencia/historico/<codigo>')
def frequencia_historico(codigo):
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    aluno = query_db("SELECT * FROM alunos WHERE codigo=?", [codigo], one=True)
    if not aluno:
        flash('Aluno não encontrado', 'error')
        return redirect(url_for('frequencia'))

    disc_sel = request.args.get('disciplina', '')
    registros = []
    if disc_sel:
        registros = query_db("""
            SELECT * FROM frequencia
            WHERE codigo_aluno=? AND disciplina=?
            ORDER BY data DESC
        """, [codigo, disc_sel])
    else:
        registros = query_db("""
            SELECT * FROM frequencia
            WHERE codigo_aluno=?
            ORDER BY disciplina, data DESC
        """, [codigo])

    freq_por_disc = query_db("""
        SELECT disciplina,
               COUNT(*) as total,
               SUM(CASE WHEN presente=1 THEN 1 ELSE 0 END) as presencas,
               SUM(CASE WHEN presente=0 THEN 1 ELSE 0 END) as faltas
        FROM frequencia WHERE codigo_aluno=?
        GROUP BY disciplina ORDER BY disciplina
    """, [codigo])

    total_geral = query_db("""
        SELECT COUNT(*) as t,
               SUM(CASE WHEN presente=0 THEN 1 ELSE 0 END) as f
        FROM frequencia WHERE codigo_aluno=?
    """, [codigo], one=True)

    return render_template('professor/freq_historico.html', aluno=aluno, registros=registros,
                           freq_por_disc=freq_por_disc, total_geral=total_geral,
                           disc_sel=disc_sel, disciplinas=DISCIPLINAS)


# ==================== PROVAS ====================

@app.route('/provas', methods=['GET', 'POST'])
def provas():
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    turmas = get_turmas()
    if request.method == 'POST':
        turma = request.form['turma']
        disciplina = request.form['disciplina']
        data = request.form['data']
        tipo = request.form.get('tipo', 'Prova')
        execute_db("INSERT INTO provas (turma, disciplina, data, tipo) VALUES (?, ?, ?, ?)",
                   (turma, disciplina, data, tipo))
        log_historico(session['user_name'], f'Prova agendada: {disciplina} - {turma} em {data}')
        flash('Prova agendada com sucesso!', 'success')
        return redirect(url_for('provas'))

    lista = query_db("SELECT * FROM provas ORDER BY data")
    return render_template('professor/provas.html', provas=lista, turmas=turmas, disciplinas=DISCIPLINAS)


@app.route('/provas/excluir/<int:id>')
def prova_excluir(id):
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    execute_db("DELETE FROM provas WHERE id=?", [id])
    log_historico(session['user_name'], 'Prova excluída')
    flash('Prova excluída!', 'success')
    return redirect(url_for('provas'))


# ==================== PENDÊNCIAS ====================

@app.route('/pendencias', methods=['GET', 'POST'])
def pendencias():
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    if request.method == 'POST':
        codigo = request.form['codigo_aluno'].strip()
        descricao = request.form['descricao'].strip()
        aluno = query_db("SELECT nome FROM alunos WHERE codigo=?", [codigo], one=True)
        if not aluno:
            flash('Código de aluno não encontrado', 'error')
            return redirect(url_for('pendencias'))
        execute_db("INSERT INTO pendencias (codigo_aluno, professor, descricao) VALUES (?, ?, ?)",
                   (codigo, session['user_name'], descricao))
        log_historico(session['user_name'], f'Pendência criada: {descricao}', aluno['nome'])
        flash('Pendência registrada!', 'success')
        return redirect(url_for('pendencias'))

    lista = query_db("""
        SELECT p.*, a.nome as aluno_nome FROM pendencias p
        LEFT JOIN alunos a ON p.codigo_aluno = a.codigo
        ORDER BY p.data DESC
    """)
    return render_template('professor/pendencias.html', pendencias=lista)


@app.route('/pendencias/excluir/<int:id>')
def pendencia_excluir(id):
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    execute_db("DELETE FROM pendencias WHERE id=?", [id])
    log_historico(session['user_name'], 'Pendência excluída')
    flash('Pendência removida!', 'success')
    return redirect(url_for('pendencias'))


# ==================== AVISOS ====================

@app.route('/avisos', methods=['GET', 'POST'])
def avisos():
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    turmas = get_turmas()
    if request.method == 'POST':
        titulo = request.form['titulo'].strip()
        descricao = request.form['descricao'].strip()
        turma = request.form['turma']
        execute_db("INSERT INTO avisos (titulo, descricao, turma) VALUES (?, ?, ?)",
                   (titulo, descricao, turma))
        log_historico(session['user_name'], f'Aviso publicado: {titulo} para {turma}')
        flash('Aviso publicado com sucesso!', 'success')
        return redirect(url_for('avisos'))

    lista = query_db("SELECT * FROM avisos ORDER BY data DESC")
    return render_template('professor/avisos.html', avisos=lista, turmas=turmas)


@app.route('/avisos/excluir/<int:id>')
def aviso_excluir(id):
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    execute_db("DELETE FROM avisos WHERE id=?", [id])
    log_historico(session['user_name'], 'Aviso excluído')
    flash('Aviso removido!', 'success')
    return redirect(url_for('avisos'))


# ==================== AGENDA ====================

@app.route('/agenda', methods=['GET', 'POST'])
def agenda():
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    turmas = get_turmas()
    if request.method == 'POST':
        titulo = request.form['titulo'].strip()
        tipo = request.form['tipo']
        turma = request.form['turma']
        data = request.form['data']
        execute_db("INSERT INTO agenda (titulo, tipo, turma, data) VALUES (?, ?, ?, ?)",
                   (titulo, tipo, turma, data))
        log_historico(session['user_name'], f'Evento agendado: {titulo} ({tipo}) para {turma}')
        flash('Evento agendado com sucesso!', 'success')
        return redirect(url_for('agenda'))

    lista = query_db("SELECT * FROM agenda ORDER BY data")
    return render_template('professor/agenda.html', eventos=lista, turmas=turmas)


@app.route('/agenda/excluir/<int:id>')
def agenda_excluir(id):
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    execute_db("DELETE FROM agenda WHERE id=?", [id])
    log_historico(session['user_name'], 'Evento excluído da agenda')
    flash('Evento removido!', 'success')
    return redirect(url_for('agenda'))


# ==================== HISTÓRICO ====================

@app.route('/historico')
def historico():
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    registros = query_db("SELECT * FROM historico ORDER BY data_hora DESC LIMIT 200")
    return render_template('professor/historico.html', registros=registros)


# ==================== BOLETIM ====================

@app.route('/boletim/<codigo>')
def boletim(codigo):
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    aluno = query_db("SELECT * FROM alunos WHERE codigo=?", [codigo], one=True)
    if not aluno:
        flash('Aluno não encontrado', 'error')
        return redirect(url_for('alunos'))
    notas = query_db("SELECT * FROM notas WHERE codigo_aluno=? ORDER BY disciplina", [codigo])

    freq_por_disc = query_db("""
        SELECT disciplina,
               COUNT(*) as total,
               SUM(CASE WHEN presente=1 THEN 1 ELSE 0 END) as presencas,
               SUM(CASE WHEN presente=0 THEN 1 ELSE 0 END) as faltas
        FROM frequencia WHERE codigo_aluno=?
        GROUP BY disciplina ORDER BY disciplina
    """, [codigo])

    total_geral = query_db("SELECT COUNT(*) as t, SUM(CASE WHEN presente=0 THEN 1 ELSE 0 END) as f FROM frequencia WHERE codigo_aluno=?", [codigo], one=True)

    media_geral = 0
    count = 0
    for n in notas:
        if n['nota'] > 0:
            media_geral += n['nota']
            count += 1
    if count > 0:
        media_geral = round(media_geral / count, 1)
    situacao = 'Aprovado' if media_geral >= 7 else ('Recuperação' if media_geral >= 5 else 'Reprovado')
    return render_template('professor/boletim.html', aluno=aluno, notas=notas,
                           media_geral=media_geral, situacao=situacao,
                           freq_por_disc=freq_por_disc, total_geral=total_geral)


@app.route('/boletim/<codigo>/pdf')
def boletim_pdf(codigo):
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    aluno = query_db("SELECT * FROM alunos WHERE codigo=?", [codigo], one=True)
    if not aluno:
        return redirect(url_for('alunos'))
    notas = query_db("SELECT * FROM notas WHERE codigo_aluno=? ORDER BY disciplina", [codigo])
    freq_por_disc = query_db("""
        SELECT disciplina,
               COUNT(*) as total,
               SUM(CASE WHEN presente=1 THEN 1 ELSE 0 END) as presencas,
               SUM(CASE WHEN presente=0 THEN 1 ELSE 0 END) as faltas
        FROM frequencia WHERE codigo_aluno=?
        GROUP BY disciplina ORDER BY disciplina
    """, [codigo])
    total_geral = query_db("SELECT COUNT(*) as t, SUM(CASE WHEN presente=0 THEN 1 ELSE 0 END) as f FROM frequencia WHERE codigo_aluno=?", [codigo], one=True)
    media_geral = 0
    count = 0
    for n in notas:
        if n['nota'] > 0:
            media_geral += n['nota']
            count += 1
    if count > 0:
        media_geral = round(media_geral / count, 1)
    situacao = 'Aprovado' if media_geral >= 7 else ('Recuperação' if media_geral >= 5 else 'Reprovado')

    pdf_content = generate_boletim_pdf(aluno, notas, freq_por_disc, total_geral, media_geral, situacao)
    response = make_response(pdf_content)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=boletim_{codigo}.pdf'
    return response


def generate_boletim_pdf(aluno, notas, freq_por_disc, total_geral, media_geral, situacao):
    lines = []
    lines.append("=" * 60)
    lines.append("           E.E.G. - BOLETIM ESCOLAR")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"  Aluno: {aluno['nome']}")
    lines.append(f"  Código: {aluno['codigo']}")
    lines.append(f"  Turma: {aluno['turma']}")
    lines.append(f"  Data de Nascimento: {aluno['nascimento'] or 'Não informado'}")
    lines.append("")
    lines.append("-" * 60)
    lines.append("  NOTAS POR DISCIPLINA")
    lines.append("-" * 60)
    lines.append(f"  {'Disciplina':<25} {'Nota':>6}  {'Situação':<12}")
    lines.append("-" * 60)
    for n in notas:
        if n['nota'] > 0:
            sit = 'Aprovado' if n['nota'] >= 7 else ('Recuperação' if n['nota'] >= 5 else 'Reprovado')
            lines.append(f"  {n['disciplina']:<25} {n['nota']:>6.1f}  {sit:<12}")
        else:
            lines.append(f"  {n['disciplina']:<25} {'--':>6}  {'--':<12}")
    lines.append("-" * 60)
    lines.append(f"  {'Média Geral:':<25} {media_geral:>6.1f}  {situacao}")
    lines.append("")
    if freq_por_disc:
        lines.append("-" * 60)
        lines.append("  FREQUÊNCIA POR DISCIPLINA")
        lines.append("-" * 60)
        lines.append(f"  {'Disciplina':<25} {'Aulas':>6} {'Pres.':>6} {'Faltas':>6} {'%':>6}")
        lines.append("-" * 60)
        for f in freq_por_disc:
            pct = round((f['presencas'] / f['total']) * 100, 1) if f['total'] > 0 else 0
            lines.append(f"  {f['disciplina']:<25} {f['total']:>6} {f['presencas']:>6} {f['faltas'] or 0:>6} {pct:>5}%")
    if total_geral and total_geral['t'] and total_geral['t'] > 0:
        faltas_geral = total_geral['f'] or 0
        pres_geral = total_geral['t'] - faltas_geral
        pct_geral = round((pres_geral / total_geral['t']) * 100, 1)
        lines.append("-" * 60)
        lines.append(f"  {'TOTAL GERAL:':<25} {total_geral['t']:>6} {pres_geral:>6} {faltas_geral:>6} {pct_geral:>5}%")
    lines.append("")
    lines.append("=" * 60)
    lines.append(f"  Emitido em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    lines.append("=" * 60)
    return "\n".join(lines).encode('utf-8')


# ==================== ALUNO PORTAL ====================

@app.route('/portal')
def portal_aluno():
    if session.get('user_type') != 'aluno':
        return redirect(url_for('login'))
    codigo = session['user_codigo']
    aluno = query_db("SELECT * FROM alunos WHERE codigo=?", [codigo], one=True)
    notas = query_db("SELECT * FROM notas WHERE codigo_aluno=? ORDER BY disciplina", [codigo])
    pendencias = query_db("SELECT * FROM pendencias WHERE codigo_aluno=? ORDER BY data DESC", [codigo])
    provas = query_db("SELECT * FROM provas WHERE turma=? ORDER BY data", [aluno['turma']])
    avisos = query_db("SELECT * FROM avisos WHERE turma=? ORDER BY data DESC", [aluno['turma']])
    agenda = query_db("SELECT * FROM agenda WHERE turma=? ORDER BY data", [aluno['turma']])

    freq_por_disc = query_db("""
        SELECT disciplina,
               COUNT(*) as total,
               SUM(CASE WHEN presente=1 THEN 1 ELSE 0 END) as presencas,
               SUM(CASE WHEN presente=0 THEN 1 ELSE 0 END) as faltas
        FROM frequencia WHERE codigo_aluno=?
        GROUP BY disciplina ORDER BY disciplina
    """, [codigo])

    total_geral = query_db("SELECT COUNT(*) as t, SUM(CASE WHEN presente=0 THEN 1 ELSE 0 END) as f FROM frequencia WHERE codigo_aluno=?", [codigo], one=True)

    media_geral = 0
    count = 0
    for n in notas:
        if n['nota'] > 0:
            media_geral += n['nota']
            count += 1
    if count > 0:
        media_geral = round(media_geral / count, 1)
    situacao = 'Aprovado' if media_geral >= 7 else ('Recuperação' if media_geral >= 5 else 'Reprovado')

    return render_template('aluno/portal.html', aluno=aluno, notas=notas,
                           pendencias=pendencias, provas=provas, avisos=avisos, agenda=agenda,
                           media_geral=media_geral, situacao=situacao,
                           freq_por_disc=freq_por_disc, total_geral=total_geral)


# ==================== API ====================

@app.route('/api/buscar')
def api_buscar():
    q = request.args.get('q', '').strip()
    if len(q) < 1:
        return jsonify([])
    results = query_db(
        "SELECT id, nome, codigo, turma FROM alunos WHERE nome LIKE ? OR codigo LIKE ? OR turma LIKE ? LIMIT 20",
        [f'%{q}%', f'%{q}%', f'%{q}%'])
    return jsonify([dict(r) for r in results])


if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
else:
    init_db()
