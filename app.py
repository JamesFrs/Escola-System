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


def log_atividade_rep(codigo, turma, acao, detalhes=''):
    execute_db("INSERT INTO atividade_representante (representante, turma, acao, detalhes) VALUES (?, ?, ?, ?)",
               (codigo, turma, acao, detalhes))


def criar_notificacao(destinatario, titulo, mensagem, link=''):
    execute_db("INSERT INTO notificacoes (destinatario, titulo, mensagem, link) VALUES (?, ?, ?, ?)",
               (destinatario, titulo, mensagem, link))


def get_representante(turma):
    return query_db("SELECT * FROM representantes WHERE turma=?", [turma], one=True)


def is_representante(codigo):
    return query_db("SELECT * FROM representantes WHERE codigo_aluno=?", [codigo], one=True)


@app.before_request
def before_request():
    if request.endpoint in ('login', 'login_professor', 'login_aluno', 'static_file', 'api_buscar'):
        return
    if 'user_type' not in session:
        return redirect(url_for('login'))


@app.route('/')
def index():
    if 'user_type' in session:
        t = session['user_type']
        if t == 'professor':
            return redirect(url_for('dashboard'))
        elif t == 'representante':
            return redirect(url_for('rep_dashboard'))
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
        rep = is_representante(codigo)
        if rep:
            session['user_type'] = 'representante'
            session['user_codigo'] = codigo
            session['user_turma'] = aluno['turma']
            session['user_funcao'] = rep['funcao']
        else:
            session['user_type'] = 'aluno'
        session['user_id'] = aluno['id']
        session['user_name'] = aluno['nome']
        session['user_codigo'] = codigo
        session['user_turma'] = aluno['turma']
        return redirect(url_for('index'))
    flash('Nome ou código incorretos', 'error')
    return redirect(url_for('login'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/notificacoes')
def notificacoes():
    if 'user_type' not in session:
        return redirect(url_for('login'))
    codigo = session.get('user_codigo', '')
    notifs = query_db("SELECT * FROM notificacoes WHERE destinatario=? ORDER BY data DESC LIMIT 50", [codigo])
    execute_db("UPDATE notificacoes SET lida=1 WHERE destinatario=?", [codigo])
    return render_template('notificacoes.html', notificacoes=notifs)


# ==================== PROFESSOR ====================

@app.route('/dashboard')
def dashboard():
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    total_alunos = query_db("SELECT COUNT(*) as c FROM alunos", one=True)['c']
    total_turmas = query_db("SELECT COUNT(*) as c FROM turmas", one=True)['c']
    today = datetime.now().strftime('%Y-%m-%d')
    provas_semana = query_db(
        "SELECT COUNT(*) as c FROM provas WHERE data >= ? AND data <= ? AND status='confirmada'",
        [today, (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')], one=True)['c']
    pendencias_abertas = query_db("SELECT COUNT(*) as c FROM pendencias", one=True)['c']
    media_geral = query_db("SELECT ROUND(AVG(nota),1) as m FROM notas WHERE nota > 0", one=True)['m'] or 0
    freq_pendente = query_db("SELECT COUNT(*) as c FROM frequencia_pendente WHERE status='pendente'", one=True)['c']
    provas_pendentes = query_db("SELECT COUNT(*) as c FROM provas WHERE status='pendente'", one=True)['c']

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

    atividades = query_db("""
        SELECT a.*, al.nome as aluno_nome FROM atividade_representante a
        LEFT JOIN alunos al ON a.representante = al.codigo
        ORDER BY a.data DESC LIMIT 10
    """)

    return render_template('professor/dashboard.html',
                           total_alunos=total_alunos, total_turmas=total_turmas,
                           provas_semana=provas_semana, pendencias_abertas=pendencias_abertas,
                           media_geral=media_geral, freq_media=freq_media,
                           freq_por_disc=freq_por_disc, notas_por_disc=notas_por_disc,
                           freq_pendente=freq_pendente, provas_pendentes=provas_pendentes,
                           atividades=atividades)


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
        rep = get_representante(td['nome'])
        td['representante'] = rep['codigo_aluno'] if rep else None
        td['funcao_rep'] = rep['funcao'] if rep else None
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
    execute_db("UPDATE frequencia_pendente SET turma=? WHERE turma=?", (novo_nome, turma['nome']))
    execute_db("UPDATE provas SET turma=? WHERE turma=?", (novo_nome, turma['nome']))
    execute_db("UPDATE avisos SET turma=? WHERE turma=?", (novo_nome, turma['nome']))
    execute_db("UPDATE agenda SET turma=? WHERE turma=?", (novo_nome, turma['nome']))
    execute_db("UPDATE representantes SET turma=? WHERE turma=?", (novo_nome, turma['nome']))
    execute_db("UPDATE demandas SET turma=? WHERE turma=?", (novo_nome, turma['nome']))
    execute_db("UPDATE sugestoes SET turma=? WHERE turma=?", (novo_nome, turma['nome']))
    execute_db("UPDATE enquetes SET turma=? WHERE turma=?", (novo_nome, turma['nome']))
    execute_db("UPDATE reunioes SET turma=? WHERE turma=?", (novo_nome, turma['nome']))
    execute_db("UPDATE atividade_representante SET turma=? WHERE turma=?", (novo_nome, turma['nome']))
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
    rep = get_representante(turma['nome'])
    return render_template('professor/turma_alunos.html', turma=turma, alunos=alunos_turma,
                           outros=outros_alunos, todas_turmas=todas_turmas, representante=rep)


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
    execute_db("DELETE FROM frequencia_pendente WHERE codigo_aluno=?", [codigo])
    execute_db("DELETE FROM pendencias WHERE codigo_aluno=?", [codigo])
    execute_db("DELETE FROM representantes WHERE codigo_aluno=?", [codigo])
    execute_db("DELETE FROM votos_enquete WHERE codigo_aluno=?", [codigo])
    execute_db("DELETE FROM alunos WHERE codigo=?", [codigo])
    log_historico(session['user_name'], f'Aluno removido da turma {turma["nome"]}: {aluno["nome"]} ({codigo})', aluno['nome'])
    flash(f'{aluno["nome"]} removido(a) do sistema!', 'success')
    return redirect(url_for('turma_alunos', id=id))


# ==================== REPRESENTANTES ====================

@app.route('/turmas/<int:id>/representantes', methods=['GET', 'POST'])
def turma_representantes(id):
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    turma = query_db("SELECT * FROM turmas WHERE id=?", [id], one=True)
    if not turma:
        flash('Turma não encontrada', 'error')
        return redirect(url_for('turmas_lista'))
    if request.method == 'POST':
        acao = request.form.get('acao')
        if acao == 'definir':
            funcao = request.form.get('funcao')
            codigo = request.form.get('codigo_aluno')
            aluno = query_db("SELECT nome FROM alunos WHERE codigo=? AND turma=?", [codigo, turma['nome']], one=True)
            if not aluno:
                flash('Aluno não encontrado nesta turma', 'error')
                return redirect(url_for('turma_representantes', id=id))
            execute_db("DELETE FROM representantes WHERE turma=?", [turma['nome']])
            execute_db("INSERT INTO representantes (turma, codigo_aluno, funcao) VALUES (?, ?, ?)",
                       (turma['nome'], codigo, funcao))
            log_historico(session['user_name'], f'{funcao.title()} definido(a): {aluno["nome"]} na turma {turma["nome"]}', aluno['nome'])
            flash(f'{aluno["nome"]} agora é {funcao} de {turma["nome"]}!', 'success')
        elif acao == 'remover':
            execute_db("DELETE FROM representantes WHERE turma=?", [turma['nome']])
            log_historico(session['user_name'], f'Representante removido da turma {turma["nome"]}')
            flash('Representante removido!', 'success')
        return redirect(url_for('turma_representantes', id=id))

    alunos_turma = query_db("SELECT * FROM alunos WHERE turma=? ORDER BY nome", [turma['nome']])
    rep = get_representante(turma['nome'])
    return render_template('professor/representantes.html', turma=turma, alunos=alunos_turma, representante=rep)


# ==================== FREQUÊNCIA (PROFESSOR) ====================

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
            execute_db("DELETE FROM frequencia_pendente WHERE codigo_aluno=? AND disciplina=? AND turma=? AND data=?",
                       (a['codigo'], disciplina, turma, data))
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
    if disc_sel:
        registros = query_db("SELECT * FROM frequencia WHERE codigo_aluno=? AND disciplina=? ORDER BY data DESC", [codigo, disc_sel])
    else:
        registros = query_db("SELECT * FROM frequencia WHERE codigo_aluno=? ORDER BY disciplina, data DESC", [codigo])
    freq_por_disc = query_db("""
        SELECT disciplina, COUNT(*) as total,
               SUM(CASE WHEN presente=1 THEN 1 ELSE 0 END) as presencas,
               SUM(CASE WHEN presente=0 THEN 1 ELSE 0 END) as faltas
        FROM frequencia WHERE codigo_aluno=? GROUP BY disciplina ORDER BY disciplina
    """, [codigo])
    total_geral = query_db("SELECT COUNT(*) as t, SUM(CASE WHEN presente=0 THEN 1 ELSE 0 END) as f FROM frequencia WHERE codigo_aluno=?", [codigo], one=True)
    return render_template('professor/freq_historico.html', aluno=aluno, registros=registros,
                           freq_por_disc=freq_por_disc, total_geral=total_geral,
                           disc_sel=disc_sel, disciplinas=DISCIPLINAS)


@app.route('/frequencia/pendente')
def frequencia_pendente():
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    pendentes = query_db("""
        SELECT fp.*, a.nome as aluno_nome FROM frequencia_pendente fp
        LEFT JOIN alunos a ON fp.codigo_aluno = a.codigo
        WHERE fp.status='pendente' ORDER BY fp.data DESC
    """)
    return render_template('professor/freq_pendente.html', pendentes=pendentes)


@app.route('/frequencia/pendente/confirmar/<int:id>', methods=['POST'])
def frequencia_confirmar(id):
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    reg = query_db("SELECT * FROM frequencia_pendente WHERE id=?", [id], one=True)
    if reg:
        execute_db("""
            INSERT INTO frequencia (codigo_aluno, disciplina, turma, data, presente)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(codigo_aluno, disciplina, turma, data) DO UPDATE SET presente=?
        """, (reg['codigo_aluno'], reg['disciplina'], reg['turma'], reg['data'], reg['presente'], reg['presente']))
        execute_db("UPDATE frequencia_pendente SET status='confirmada' WHERE id=?", [id])
        criar_notificacao(reg['codigo_aluno'], 'Frequência confirmada',
                         f'Sua frequência de {reg["disciplina"]} em {reg["data"]} foi confirmada pelo professor.')
        log_historico(session['user_name'], f'Frequência confirmada: {reg["disciplina"]} em {reg["data"]} ({reg["registrado_por"]})')
        flash('Frequência confirmada!', 'success')
    return redirect(url_for('frequencia_pendente'))


@app.route('/frequencia/pendente/recusar/<int:id>', methods=['POST'])
def frequencia_recusar(id):
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    reg = query_db("SELECT * FROM frequencia_pendente WHERE id=?", [id], one=True)
    if reg:
        execute_db("UPDATE frequencia_pendente SET status='recusada' WHERE id=?", [id])
        criar_notificacao(reg['codigo_aluno'], 'Frequência recusada',
                         f'Sua frequência de {reg["disciplina"]} em {reg["data"]} foi recusada pelo professor.')
        log_historico(session['user_name'], f'Frequência recusada: {reg["disciplina"]} em {reg["data"]} ({reg["registrado_por"]})')
        flash('Frequência recusada.', 'success')
    return redirect(url_for('frequencia_pendente'))


# ==================== PROVAS (PROFESSOR) ====================

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
        conteudo = request.form.get('conteudo', '')
        observacao = request.form.get('observacao', '')
        execute_db("INSERT INTO provas (turma, disciplina, data, tipo, conteudo, observacao, criado_por, criado_por_funcao, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'professor', 'confirmada')",
                   (turma, disciplina, data, tipo, conteudo, observacao, session['user_name']))
        log_historico(session['user_name'], f'Prova agendada: {disciplina} - {turma} em {data}')
        flash('Prova agendada com sucesso!', 'success')
        return redirect(url_for('provas'))
    lista = query_db("SELECT * FROM provas WHERE status='confirmada' ORDER BY data")
    pendentes = query_db("SELECT * FROM provas WHERE status='pendente' ORDER BY data")
    return render_template('professor/provas.html', provas=lista, pendentes=pendentes, turmas=turmas, disciplinas=DISCIPLINAS)


@app.route('/provas/confirmar/<int:id>', methods=['POST'])
def prova_confirmar(id):
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    p = query_db("SELECT * FROM provas WHERE id=?", [id], one=True)
    if p:
        execute_db("UPDATE provas SET status='confirmada' WHERE id=?", [id])
        alunos_turma = query_db("SELECT codigo FROM alunos WHERE turma=?", [p['turma']])
        for a in alunos_turma:
            criar_notificacao(a['codigo'], 'Prova confirmada',
                             f'Prova de {p["disciplina"]} em {p["data"]} confirmada pelo professor.')
        log_historico(session['user_name'], f'Prova confirmada: {p["disciplina"]} - {p["turma"]}')
        flash('Prova confirmada!', 'success')
    return redirect(url_for('provas'))


@app.route('/provas/recusar/<int:id>', methods=['POST'])
def prova_recusar(id):
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    p = query_db("SELECT * FROM provas WHERE id=?", [id], one=True)
    if p:
        execute_db("DELETE FROM provas WHERE id=?", [id])
        criar_notificacao(p['criado_por'], 'Prova recusada',
                         f'Prova de {p["disciplina"]} em {p["data"]} foi recusada pelo professor.')
        log_historico(session['user_name'], f'Prova recusada: {p["disciplina"]} - {p["turma"]}')
        flash('Prova recusada e removida.', 'success')
    return redirect(url_for('provas'))


@app.route('/provas/excluir/<int:id>')
def prova_excluir(id):
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    execute_db("DELETE FROM provas WHERE id=?", [id])
    log_historico(session['user_name'], 'Prova excluída')
    flash('Prova excluída!', 'success')
    return redirect(url_for('provas'))


# ==================== PENDÊNCIAS, AVISOS, AGENDA, HISTÓRICO ====================

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
    lista = query_db("SELECT p.*, a.nome as aluno_nome FROM pendencias p LEFT JOIN alunos a ON p.codigo_aluno = a.codigo ORDER BY p.data DESC")
    return render_template('professor/pendencias.html', pendencias=lista)


@app.route('/pendencias/excluir/<int:id>')
def pendencia_excluir(id):
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    execute_db("DELETE FROM pendencias WHERE id=?", [id])
    log_historico(session['user_name'], 'Pendência excluída')
    flash('Pendência removida!', 'success')
    return redirect(url_for('pendencias'))


@app.route('/avisos', methods=['GET', 'POST'])
def avisos():
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    turmas = get_turmas()
    if request.method == 'POST':
        titulo = request.form['titulo'].strip()
        descricao = request.form['descricao'].strip()
        turma = request.form['turma']
        execute_db("INSERT INTO avisos (titulo, descricao, turma, criado_por, criado_por_funcao) VALUES (?, ?, ?, ?, 'professor')",
                   (titulo, descricao, turma, session['user_name']))
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
        execute_db("INSERT INTO agenda (titulo, tipo, turma, data, criado_por) VALUES (?, ?, ?, ?, ?)",
                   (titulo, tipo, turma, data, session['user_name']))
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


@app.route('/historico')
def historico():
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    registros = query_db("SELECT * FROM historico ORDER BY data_hora DESC LIMIT 200")
    return render_template('professor/historico.html', registros=registros)


# ==================== DEMANDAS/SUGESTÕES (PROFESSOR) ====================

@app.route('/demandas')
def demandas_prof():
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    lista = query_db("SELECT d.*, a.nome as autor_nome FROM demandas d LEFT JOIN alunos a ON d.criado_por = a.codigo ORDER BY d.data DESC")
    return render_template('professor/demandas.html', demandas=lista)


@app.route('/demandas/responder/<int:id>', methods=['POST'])
def demanda_responder(id):
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    status = request.form.get('status')
    resposta = request.form.get('resposta', '')
    d = query_db("SELECT * FROM demandas WHERE id=?", [id], one=True)
    if d:
        execute_db("UPDATE demandas SET status=?, resposta=? WHERE id=?", (status, resposta, id))
        criar_notificacao(d['criado_por'], f'Demanda {status.lower()}', f'Sua demanda "{d["titulo"]}" foi {status.lower()} pelo professor. Resposta: {resposta}')
        log_historico(session['user_name'], f'Demanda {status}: {d["titulo"]}')
        flash(f'Demanda {status.lower()}!', 'success')
    return redirect(url_for('demandas_prof'))


@app.route('/sugestoes')
def sugestoes_prof():
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    lista = query_db("SELECT s.*, a.nome as autor_nome FROM sugestoes s LEFT JOIN alunos a ON s.criado_por = a.codigo ORDER BY s.data DESC")
    return render_template('professor/sugestoes.html', sugestoes=lista)


@app.route('/sugestoes/responder/<int:id>', methods=['POST'])
def sugestao_responder(id):
    if session.get('user_type') != 'professor':
        return redirect(url_for('login'))
    status = request.form.get('status')
    resposta = request.form.get('resposta', '')
    s = query_db("SELECT * FROM sugestoes WHERE id=?", [id], one=True)
    if s:
        execute_db("UPDATE sugestoes SET status=?, resposta=? WHERE id=?", (status, resposta, id))
        criar_notificacao(s['criado_por'], f'Sugestão {status.lower()}', f'Sua sugestão "{s["titulo"]}" foi {status.lower()} pelo professor. Resposta: {resposta}')
        log_historico(session['user_name'], f'Sugestão {status}: {s["titulo"]}')
        flash(f'Sugestão {status.lower()}!', 'success')
    return redirect(url_for('sugestoes_prof'))


# ==================== ALUNOS (PROFESSOR) ====================

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
        execute_db("INSERT INTO alunos (codigo, nome, turma, nascimento) VALUES (?, ?, ?, ?)", (codigo, nome, turma, nascimento))
        for disc in DISCIPLINAS:
            execute_db("INSERT OR IGNORE INTO notas (codigo_aluno, disciplina, nota) VALUES (?, ?, 0)", (codigo, disc))
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
        execute_db("UPDATE alunos SET nome=?, turma=?, nascimento=? WHERE id=?", (nome, turma, nascimento, id))
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
        execute_db("DELETE FROM frequencia_pendente WHERE codigo_aluno=?", [aluno['codigo']])
        execute_db("DELETE FROM pendencias WHERE codigo_aluno=?", [aluno['codigo']])
        execute_db("DELETE FROM representantes WHERE codigo_aluno=?", [aluno['codigo']])
        execute_db("DELETE FROM votos_enquete WHERE codigo_aluno=?", [aluno['codigo']])
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
    provas_turma = query_db("SELECT * FROM provas WHERE turma=? AND status='confirmada' ORDER BY data", [aluno['turma']])
    avisos_turma = query_db("SELECT * FROM avisos WHERE turma=? ORDER BY data DESC", [aluno['turma']])
    freq_por_disc = query_db("""
        SELECT disciplina, COUNT(*) as total,
               SUM(CASE WHEN presente=1 THEN 1 ELSE 0 END) as presencas,
               SUM(CASE WHEN presente=0 THEN 1 ELSE 0 END) as faltas
        FROM frequencia WHERE codigo_aluno=? GROUP BY disciplina ORDER BY disciplina
    """, [aluno['codigo']])
    total_geral = query_db("SELECT COUNT(*) as t, SUM(CASE WHEN presente=0 THEN 1 ELSE 0 END) as f FROM frequencia WHERE codigo_aluno=?", [aluno['codigo']], one=True)
    media_geral = 0
    for n in notas:
        if n['nota'] > 0:
            media_geral += n['nota']
    count_notas = len([n for n in notas if n['nota'] > 0])
    if count_notas > 0:
        media_geral = round(media_geral / count_notas, 1)
    situacao = 'Aprovado' if media_geral >= 7 else ('Recuperação' if media_geral >= 5 else 'Reprovado')
    return render_template('professor/perfil_aluno.html', aluno=aluno, notas=notas,
                           pendencias=pendencias, provas=provas_turma, avisos=avisos_turma,
                           media_geral=media_geral, situacao=situacao,
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
        execute_db("INSERT OR REPLACE INTO notas (codigo_aluno, disciplina, nota) VALUES (?, ?, ?)", (codigo, disc, nota))
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
        SELECT disciplina, COUNT(*) as total,
               SUM(CASE WHEN presente=1 THEN 1 ELSE 0 END) as presencas,
               SUM(CASE WHEN presente=0 THEN 1 ELSE 0 END) as faltas
        FROM frequencia WHERE codigo_aluno=? GROUP BY disciplina ORDER BY disciplina
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
        SELECT disciplina, COUNT(*) as total,
               SUM(CASE WHEN presente=1 THEN 1 ELSE 0 END) as presencas,
               SUM(CASE WHEN presente=0 THEN 1 ELSE 0 END) as faltas
        FROM frequencia WHERE codigo_aluno=? GROUP BY disciplina ORDER BY disciplina
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


# ==================== REPRESENTANTE - PAINEL ====================

@app.route('/representante')
def rep_dashboard():
    if session.get('user_type') != 'representante':
        return redirect(url_for('login'))
    codigo = session['user_codigo']
    turma = session['user_turma']
    funcao = session.get('user_funcao', 'representante')
    aluno = query_db("SELECT * FROM alunos WHERE codigo=?", [codigo], one=True)
    rep = get_representante(turma)

    freq_pendente = query_db("SELECT COUNT(*) as c FROM frequencia_pendente WHERE turma=? AND registrado_por=? AND status='pendente'", [turma, codigo], one=True)['c']
    provas_pendentes = query_db("SELECT COUNT(*) as c FROM provas WHERE turma=? AND criado_por=? AND status='pendente'", [turma, codigo], one=True)['c']
    demandas_abertas = query_db("SELECT COUNT(*) as c FROM demandas WHERE turma=? AND status IN ('Enviada','Em análise')", [turma], one=True)['c']
    enquetes_ativas = query_db("SELECT COUNT(*) as c FROM enquetes WHERE turma=? AND ativa=1", [turma], one=True)['c']

    return render_template('representante/dashboard.html', aluno=aluno, turma=turma, funcao=funcao,
                           freq_pendente=freq_pendente, provas_pendentes=provas_pendentes,
                           demandas_abertas=demandas_abertas, enquetes_ativas=enquetes_ativas)


@app.route('/representante/frequencia', methods=['GET', 'POST'])
def rep_frequencia():
    if session.get('user_type') != 'representante':
        return redirect(url_for('login'))
    turma = session['user_turma']
    codigo = session['user_codigo']
    if request.method == 'POST':
        disciplina = request.form.get('disciplina')
        data = request.form.get('data')
        if not disciplina or not data:
            flash('Selecione disciplina e data', 'error')
            return redirect(url_for('rep_frequencia'))
        alunos_turma = query_db("SELECT * FROM alunos WHERE turma=? ORDER BY nome", [turma])
        for a in alunos_turma:
            presente = 1 if request.form.get(f'presenca_{a["codigo"]}') == 'on' else 0
            execute_db("""
                INSERT INTO frequencia_pendente (codigo_aluno, disciplina, turma, data, presente, registrado_por, registrado_por_funcao)
                VALUES (?, ?, ?, ?, ?, ?, 'representante')
                ON CONFLICT(codigo_aluno, disciplina, turma, data) DO UPDATE SET presente=?, registrado_por=?
            """, (a['codigo'], disciplina, turma, data, presente, codigo, presente, codigo))
        log_atividade_rep(codigo, turma, f'Registrou frequência: {disciplina} em {data}')
        flash('Frequência enviada para aprovação do professor!', 'success')
        return redirect(url_for('rep_frequencia'))
    return render_template('representante/frequencia.html', turma=turma, disciplinas=DISCIPLINAS)


@app.route('/representante/avisos', methods=['GET', 'POST'])
def rep_avisos():
    if session.get('user_type') != 'representante':
        return redirect(url_for('login'))
    turma = session['user_turma']
    codigo = session['user_codigo']
    if request.method == 'POST':
        titulo = request.form['titulo'].strip()
        descricao = request.form['descricao'].strip()
        execute_db("INSERT INTO avisos (titulo, descricao, turma, criado_por, criado_por_funcao) VALUES (?, ?, ?, ?, 'representante')",
                   (titulo, descricao, turma, codigo))
        log_atividade_rep(codigo, turma, f'Publicou aviso: {titulo}')
        flash('Aviso publicado!', 'success')
        return redirect(url_for('rep_avisos'))
    lista = query_db("SELECT * FROM avisos WHERE turma=? ORDER BY data DESC", [turma])
    return render_template('representante/avisos.html', avisos=lista, turma=turma)


@app.route('/representante/provas', methods=['GET', 'POST'])
def rep_provas():
    if session.get('user_type') != 'representante':
        return redirect(url_for('login'))
    turma = session['user_turma']
    codigo = session['user_codigo']
    if request.method == 'POST':
        disciplina = request.form['disciplina']
        data = request.form['data']
        conteudo = request.form.get('conteudo', '')
        observacao = request.form.get('observacao', '')
        execute_db("INSERT INTO provas (turma, disciplina, data, tipo, conteudo, observacao, criado_por, criado_por_funcao, status) VALUES (?, ?, ?, 'Prova', ?, ?, ?, 'representante', 'pendente')",
                   (turma, disciplina, data, conteudo, observacao, codigo))
        log_atividade_rep(codigo, turma, f'Informou prova: {disciplina} em {data}')
        flash('Prova enviada para confirmação do professor!', 'success')
        return redirect(url_for('rep_provas'))
    lista = query_db("SELECT * FROM provas WHERE turma=? AND (status='confirmada' OR (criado_por=? AND status='pendente')) ORDER BY data", [turma, codigo])
    return render_template('representante/provas.html', provas=lista, turma=turma, disciplinas=DISCIPLINAS)


@app.route('/representante/demandas', methods=['GET', 'POST'])
def rep_demandas():
    if session.get('user_type') != 'representante':
        return redirect(url_for('login'))
    turma = session['user_turma']
    codigo = session['user_codigo']
    if request.method == 'POST':
        titulo = request.form['titulo'].strip()
        descricao = request.form['descricao'].strip()
        categoria = request.form.get('categoria', 'Infraestrutura')
        execute_db("INSERT INTO demandas (turma, titulo, descricao, categoria, criado_por) VALUES (?, ?, ?, ?, ?)",
                   (turma, titulo, descricao, categoria, codigo))
        log_atividade_rep(codigo, turma, f'Criou demanda: {titulo}')
        flash('Demanda enviada!', 'success')
        return redirect(url_for('rep_demandas'))
    lista = query_db("SELECT * FROM demandas WHERE turma=? AND criado_por=? ORDER BY data DESC", [turma, codigo])
    return render_template('representante/demandas.html', demandas=lista, turma=turma)


@app.route('/representante/sugestoes', methods=['GET', 'POST'])
def rep_sugestoes():
    if session.get('user_type') != 'representante':
        return redirect(url_for('login'))
    turma = session['user_turma']
    codigo = session['user_codigo']
    if request.method == 'POST':
        titulo = request.form['titulo'].strip()
        descricao = request.form['descricao'].strip()
        execute_db("INSERT INTO sugestoes (turma, titulo, descricao, criado_por) VALUES (?, ?, ?, ?)",
                   (turma, titulo, descricao, codigo))
        log_atividade_rep(codigo, turma, f'Criou sugestão: {titulo}')
        flash('Sugestão enviada!', 'success')
        return redirect(url_for('rep_sugestoes'))
    lista = query_db("SELECT * FROM sugestoes WHERE turma=? AND criado_por=? ORDER BY data DESC", [turma, codigo])
    return render_template('representante/sugestoes.html', sugestoes=lista, turma=turma)


@app.route('/representante/enquetes', methods=['GET', 'POST'])
def rep_enquetes():
    if session.get('user_type') != 'representante':
        return redirect(url_for('login'))
    turma = session['user_turma']
    codigo = session['user_codigo']
    if request.method == 'POST':
        titulo = request.form['titulo'].strip()
        opcoes_list = [o.strip() for o in request.form.getlist('opcoes') if o.strip()]
        if len(opcoes_list) < 2:
            flash('Adicione pelo menos 2 opções', 'error')
            return redirect(url_for('rep_enquetes'))
        import json
        execute_db("INSERT INTO enquetes (turma, titulo, opcoes, criado_por) VALUES (?, ?, ?, ?)",
                   (turma, titulo, json.dumps(opcoes_list), codigo))
        log_atividade_rep(codigo, turma, f'Criou enquete: {titulo}')
        flash('Enquete criada!', 'success')
        return redirect(url_for('rep_enquetes'))
    lista_raw = query_db("SELECT * FROM enquetes WHERE turma=? ORDER BY data DESC", [turma])
    import json
    lista = []
    for e in lista_raw:
        ed = dict(e)
        opcoes = json.loads(ed['opcoes'])
        votos = query_db("SELECT opcao, COUNT(*) as c FROM votos_enquete WHERE enquete_id=? GROUP BY opcao", [ed['id']])
        total = sum(v['c'] for v in votos)
        ed['opcoes_data'] = [{'texto': opcoes[i], 'votos': next((v['c'] for v in votos if v['opcao']==i), 0)} for i in range(len(opcoes))]
        ed['total_votos'] = total
        lista.append(ed)
    return render_template('representante/enquetes.html', enquetes=lista, turma=turma)


@app.route('/representante/reunioes', methods=['GET', 'POST'])
def rep_reunioes():
    if session.get('user_type') != 'representante':
        return redirect(url_for('login'))
    turma = session['user_turma']
    codigo = session['user_codigo']
    if request.method == 'POST':
        data = request.form['data']
        assuntos = request.form['assuntos'].strip()
        resumo = request.form.get('resumo', '').strip()
        execute_db("INSERT INTO reunioes (turma, data, assuntos, resumo, criado_por) VALUES (?, ?, ?, ?, ?)",
                   (turma, data, assuntos, resumo, codigo))
        log_atividade_rep(codigo, turma, f'Registrou reunião em {data}')
        flash('Reunião registrada!', 'success')
        return redirect(url_for('rep_reunioes'))
    lista = query_db("SELECT * FROM reunioes WHERE turma=? ORDER BY data DESC", [turma])
    return render_template('representante/reunioes.html', reunioes=lista, turma=turma)


@app.route('/representante/alunos')
def rep_alunos():
    if session.get('user_type') != 'representante':
        return redirect(url_for('login'))
    turma = session['user_turma']
    alunos = query_db("SELECT * FROM alunos WHERE turma=? ORDER BY nome", [turma])
    return render_template('representante/alunos.html', alunos=alunos, turma=turma)


@app.route('/representante/calendario')
def rep_calendario():
    if session.get('user_type') != 'representante':
        return redirect(url_for('login'))
    turma = session['user_turma']
    provas = query_db("SELECT * FROM provas WHERE turma=? AND status='confirmada' ORDER BY data", [turma])
    agenda = query_db("SELECT * FROM agenda WHERE turma=? ORDER BY data", [turma])
    reunioes = query_db("SELECT * FROM reunioes WHERE turma=? ORDER BY data", [turma])
    return render_template('representante/calendario.html', provas=provas, agenda=agenda, reunioes=reunioes, turma=turma)


# ==================== ALUNO PORTAL ====================

@app.route('/portal')
def portal_aluno():
    if session.get('user_type') != 'aluno':
        return redirect(url_for('login'))
    codigo = session['user_codigo']
    aluno = query_db("SELECT * FROM alunos WHERE codigo=?", [codigo], one=True)
    notas = query_db("SELECT * FROM notas WHERE codigo_aluno=? ORDER BY disciplina", [codigo])
    pendencias = query_db("SELECT * FROM pendencias WHERE codigo_aluno=? ORDER BY data DESC", [codigo])
    provas = query_db("SELECT * FROM provas WHERE turma=? AND status='confirmada' ORDER BY data", [aluno['turma']])
    avisos = query_db("SELECT * FROM avisos WHERE turma=? ORDER BY data DESC", [aluno['turma']])
    agenda = query_db("SELECT * FROM agenda WHERE turma=? ORDER BY data", [aluno['turma']])
    enquetes = query_db("SELECT * FROM enquetes WHERE turma=? AND ativa=1 ORDER BY data DESC", [aluno['turma']])

    freq_por_disc = query_db("""
        SELECT disciplina, COUNT(*) as total,
               SUM(CASE WHEN presente=1 THEN 1 ELSE 0 END) as presencas,
               SUM(CASE WHEN presente=0 THEN 1 ELSE 0 END) as faltas
        FROM frequencia WHERE codigo_aluno=? GROUP BY disciplina ORDER BY disciplina
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

    import json
    enquetes_com_votos = []
    for e in enquetes:
        opcoes = json.loads(e['opcoes'])
        votos = query_db("SELECT opcao, COUNT(*) as c FROM votos_enquete WHERE enquete_id=? GROUP BY opcao", [e['id']])
        meu_voto = query_db("SELECT opcao FROM votos_enquete WHERE enquete_id=? AND codigo_aluno=?", [e['id'], codigo], one=True)
        enquetes_com_votos.append({
            'enquete': e, 'opcoes': opcoes,
            'votos': {v['opcao']: v['c'] for v in votos},
            'meu_voto': meu_voto['opcao'] if meu_voto else None
        })

    return render_template('aluno/portal.html', aluno=aluno, notas=notas,
                           pendencias=pendencias, provas=provas, avisos=avisos, agenda=agenda,
                           media_geral=media_geral, situacao=situacao,
                           freq_por_disc=freq_por_disc, total_geral=total_geral,
                           enquetes=enquetes_com_votos)


@app.route('/portal/votar/<int:enquete_id>', methods=['POST'])
def portal_votar(enquete_id):
    if session.get('user_type') != 'aluno':
        return redirect(url_for('login'))
    codigo = session['user_codigo']
    opcao = int(request.form.get('opcao', -1))
    existing = query_db("SELECT id FROM votos_enquete WHERE enquete_id=? AND codigo_aluno=?", [enquete_id, codigo], one=True)
    if existing:
        execute_db("UPDATE votos_enquete SET opcao=? WHERE enquete_id=? AND codigo_aluno=?", (opcao, enquete_id, codigo))
    else:
        execute_db("INSERT INTO votos_enquete (enquete_id, codigo_aluno, opcao) VALUES (?, ?, ?)", (enquete_id, codigo, opcao))
    flash('Voto registrado!', 'success')
    return redirect(url_for('portal_aluno'))


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
