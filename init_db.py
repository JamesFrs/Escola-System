import os
import sqlite3
from config import DATABASE
from werkzeug.security import generate_password_hash


def init_db():
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS professores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        senha TEXT NOT NULL,
        disciplina TEXT DEFAULT '',
        turmas TEXT DEFAULT '',
        turnos TEXT DEFAULT 'vespertino',
        bio TEXT DEFAULT ''
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS turmas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL,
        turno TEXT DEFAULT 'vespertino'
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS alunos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo TEXT UNIQUE NOT NULL,
        nome TEXT NOT NULL,
        turma TEXT NOT NULL,
        nascimento TEXT,
        deficiencia TEXT DEFAULT 'nao',
        desc_deficiencia TEXT DEFAULT ''
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS representantes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        turma TEXT NOT NULL,
        codigo_aluno TEXT NOT NULL,
        funcao TEXT NOT NULL DEFAULT 'representante',
        UNIQUE(turma, funcao)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS notas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo_aluno TEXT NOT NULL,
        disciplina TEXT NOT NULL,
        nota REAL DEFAULT 0,
        bimestre INTEGER DEFAULT 1,
        UNIQUE(codigo_aluno, disciplina, bimestre)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS frequencia (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo_aluno TEXT NOT NULL,
        disciplina TEXT NOT NULL,
        turma TEXT NOT NULL,
        data TEXT NOT NULL,
        presente INTEGER DEFAULT 1,
        atestado INTEGER DEFAULT 0,
        bimestre INTEGER DEFAULT 1,
        UNIQUE(codigo_aluno, disciplina, turma, data)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS frequencia_pendente (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo_aluno TEXT NOT NULL,
        disciplina TEXT NOT NULL,
        turma TEXT NOT NULL,
        data TEXT NOT NULL,
        presente INTEGER DEFAULT 1,
        registrado_por TEXT NOT NULL,
        registrado_por_funcao TEXT NOT NULL,
        status TEXT DEFAULT 'pendente',
        bimestre INTEGER DEFAULT 1,
        UNIQUE(codigo_aluno, disciplina, turma, data)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS provas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        turma TEXT NOT NULL,
        disciplina TEXT NOT NULL,
        data TEXT NOT NULL,
        tipo TEXT DEFAULT 'Prova',
        conteudo TEXT DEFAULT '',
        observacao TEXT DEFAULT '',
        criado_por TEXT DEFAULT '',
        criado_por_funcao TEXT DEFAULT '',
        status TEXT DEFAULT 'confirmada',
        bimestre INTEGER DEFAULT 1
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS pendencias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo_aluno TEXT NOT NULL,
        professor TEXT NOT NULL,
        descricao TEXT NOT NULL,
        data TEXT DEFAULT (datetime('now','localtime'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS avisos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo TEXT NOT NULL,
        descricao TEXT NOT NULL,
        turma TEXT NOT NULL,
        data TEXT DEFAULT (datetime('now','localtime')),
        criado_por TEXT DEFAULT '',
        criado_por_funcao TEXT DEFAULT ''
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS agenda (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo TEXT NOT NULL,
        tipo TEXT NOT NULL,
        turma TEXT NOT NULL,
        data TEXT NOT NULL,
        criado_por TEXT DEFAULT ''
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS historico (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        professor TEXT NOT NULL,
        acao TEXT NOT NULL,
        aluno TEXT,
        data_hora TEXT DEFAULT (datetime('now','localtime'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS demandas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        turma TEXT NOT NULL,
        titulo TEXT NOT NULL,
        descricao TEXT NOT NULL,
        categoria TEXT DEFAULT 'Infraestrutura',
        status TEXT DEFAULT 'Enviada',
        criado_por TEXT NOT NULL,
        data TEXT DEFAULT (datetime('now','localtime')),
        resposta TEXT DEFAULT ''
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS sugestoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        turma TEXT NOT NULL,
        titulo TEXT NOT NULL,
        descricao TEXT NOT NULL,
        status TEXT DEFAULT 'Enviada',
        criado_por TEXT NOT NULL,
        data TEXT DEFAULT (datetime('now','localtime')),
        resposta TEXT DEFAULT ''
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS enquetes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        turma TEXT NOT NULL,
        titulo TEXT NOT NULL,
        opcoes TEXT NOT NULL,
        criado_por TEXT NOT NULL,
        data TEXT DEFAULT (datetime('now','localtime')),
        ativa INTEGER DEFAULT 1
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS votos_enquete (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        enquete_id INTEGER NOT NULL,
        codigo_aluno TEXT NOT NULL,
        opcao INTEGER NOT NULL,
        UNIQUE(enquete_id, codigo_aluno)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS reunioes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        turma TEXT NOT NULL,
        data TEXT NOT NULL,
        assuntos TEXT NOT NULL,
        resumo TEXT DEFAULT '',
        criado_por TEXT NOT NULL,
        data_registro TEXT DEFAULT (datetime('now','localtime'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS notificacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        destinatario TEXT NOT NULL,
        titulo TEXT NOT NULL,
        mensagem TEXT NOT NULL,
        lida INTEGER DEFAULT 0,
        data TEXT DEFAULT (datetime('now','localtime')),
        link TEXT DEFAULT ''
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS atividade_representante (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        representante TEXT NOT NULL,
        turma TEXT NOT NULL,
        acao TEXT NOT NULL,
        detalhes TEXT DEFAULT '',
        data TEXT DEFAULT (datetime('now','localtime'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS horarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        turma TEXT NOT NULL,
        disciplina TEXT NOT NULL,
        dia TEXT NOT NULL,
        tempo INTEGER NOT NULL DEFAULT 1,
        hora_inicio TEXT NOT NULL,
        hora_fim TEXT NOT NULL,
        professor TEXT DEFAULT '',
        sala TEXT DEFAULT '',
        criado_por TEXT DEFAULT ''
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS horarios_oficiais (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        turno TEXT NOT NULL DEFAULT 'vespertino',
        tempo INTEGER NOT NULL,
        hora_inicio TEXT NOT NULL,
        hora_fim TEXT NOT NULL,
        UNIQUE(turno, tempo)
    )""")

    # Migracoes - adicionar colunas que podem nao existir em bancos antigos
    migracoes = [
        ("turmas", "turno", "TEXT DEFAULT 'vespertino'"),
        ("alunos", "deficiencia", "TEXT DEFAULT 'nao'"),
        ("alunos", "desc_deficiencia", "TEXT DEFAULT ''"),
        ("notas", "bimestre", "INTEGER DEFAULT 1"),
        ("frequencia", "bimestre", "INTEGER DEFAULT 1"),
        ("frequencia", "atestado", "INTEGER DEFAULT 0"),
        ("provas", "bimestre", "INTEGER DEFAULT 1"),
        ("frequencia_pendente", "bimestre", "INTEGER DEFAULT 1"),
        ("professores", "turnos", "TEXT DEFAULT 'vespertino'"),
        ("horarios_oficiais", "turno", "TEXT DEFAULT 'vespertino'"),
        ("horarios", "tempo", "INTEGER DEFAULT 1"),
        ("horarios", "professor", "TEXT DEFAULT ''"),
    ]
    for tabela, coluna, tipo in migracoes:
        try:
            cols = [col[1] for col in c.execute(f"PRAGMA table_info({tabela})").fetchall()]
            if coluna not in cols:
                c.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
                print(f"Migracao: adicionada coluna {coluna} na tabela {tabela}")
        except Exception as e:
            print(f"Erro na migracao {tabela}.{coluna}: {e}")
            pass

    # Seed professor
    existing = c.execute("SELECT id FROM professores WHERE email='admin@escola.com'").fetchone()
    if not existing:
        senha_hash = generate_password_hash('123456')
        c.execute("INSERT INTO professores (nome, email, senha, disciplina, turmas, bio) VALUES (?, ?, ?, ?, ?, ?)",
                  ('Administrador', 'admin@escola.com', senha_hash, 'Matemática', '1º Ano A, 2º Ano B', 'Professor administrador do sistema'))

    # Seed turmas
    default_turmas = ['1º Ano A', '1º Ano B', '2º Ano A', '2º Ano B', '3º Ano A', '3º Ano B']
    for t in default_turmas:
        c.execute("INSERT OR IGNORE INTO turmas (nome, turno) VALUES (?, 'vespertino')", (t,))

    # Seed horarios oficiais - Turno Vespertino
    horarios_oficiais = [
        (1, '13:00', '13:48'),
        (2, '13:48', '14:36'),
        (3, '14:36', '15:24'),
        (4, '15:39', '16:27'),
        (5, '16:27', '17:15'),
    ]
    for tempo, inicio, fim in horarios_oficiais:
        c.execute("INSERT OR IGNORE INTO horarios_oficiais (turno, tempo, hora_inicio, hora_fim) VALUES (?, ?, ?, ?)",
                  ('vespertino', tempo, inicio, fim))

    # Seed alunos (3 por turma: 1 rep, 1 vice, 1 normal)
    alunos_seed = {
        '1º Ano A': [
            ('20260101', 'Ana Beatriz Silva'),
            ('20260102', 'Carlos Eduardo Santos'),
            ('20260103', 'Maria Fernanda Lima'),
        ],
        '1º Ano B': [
            ('20260104', 'Pedro Henrique Oliveira'),
            ('20260105', 'Juliana Costa Souza'),
            ('20260106', 'Lucas Almeida Pereira'),
        ],
        '2º Ano A': [
            ('20260201', 'Fernanda Rodrigues'),
            ('20260202', 'Rafael Mendes Silva'),
            ('20260203', 'Camila Santos Lima'),
        ],
        '2º Ano B': [
            ('20260204', 'Gabriel Ferreira Costa'),
            ('20260205', 'Isabela Martins'),
            ('20260206', 'Thiago Ribeiro Alves'),
        ],
        '3º Ano A': [
            ('20260301', 'Bruno Costa Lima'),
            ('20260302', 'Maria Souza Pereira'),
            ('20260303', 'James Farias'),
        ],
        '3º Ano B': [
            ('20260304', 'Ricardo Santos'),
            ('20260305', 'Ana Clara Oliveira'),
            ('20260306', 'Gustavo Lima'),
        ],
    }
    for turma, alunos in alunos_seed.items():
        for codigo, nome in alunos:
            exists = c.execute("SELECT id FROM alunos WHERE codigo=?", (codigo,)).fetchone()
            if not exists:
                c.execute("INSERT INTO alunos (codigo, nome, turma, nascimento, deficiencia, desc_deficiencia) VALUES (?, ?, ?, '', 'nao', '')",
                          (codigo, nome, turma))

    # Seed representantes (1 rep + 1 vice por turma)
    for turma in default_turmas:
        rep = c.execute("SELECT id FROM representantes WHERE turma=? AND funcao='representante'", (turma,)).fetchone()
        if not rep:
            aluno = c.execute("SELECT codigo FROM alunos WHERE turma=? ORDER BY nome LIMIT 1", (turma,)).fetchone()
            if aluno:
                c.execute("INSERT OR IGNORE INTO representantes (turma, codigo_aluno, funcao) VALUES (?, ?, 'representante')",
                          (turma, aluno[0]))
        vice = c.execute("SELECT id FROM representantes WHERE turma=? AND funcao='vice'", (turma,)).fetchone()
        if not vice:
            aluno = c.execute("SELECT codigo FROM alunos WHERE turma=? AND codigo NOT IN (SELECT codigo_aluno FROM representantes WHERE turma=?) ORDER BY nome LIMIT 1",
                              (turma, turma)).fetchone()
            if aluno:
                c.execute("INSERT OR IGNORE INTO representantes (turma, codigo_aluno, funcao) VALUES (?, ?, 'vice')",
                          (turma, aluno[0]))

    # Seed professores (1 por disciplina)
    professores_seed = [
        ('Ricardo Almeida', 'ricardo@escola.com', 'Matemática', '1º Ano A, 2º Ano A, 3º Ano A', 'matutino,vespertino'),
        ('Mariana Costa', 'mariana@escola.com', 'Português', '1º Ano B, 2º Ano B, 3º Ano B', 'matutino,vespertino'),
        ('Fernando Oliveira', 'fernando@escola.com', 'História', '1º Ano A, 1º Ano B, 3º Ano A', 'vespertino'),
        ('Patrícia Santos', 'patricia@escola.com', 'Geografia', '2º Ano A, 2º Ano B, 3º Ano B', 'vespertino'),
        ('Carlos Mendes', 'carlos@escola.com', 'Ciências', '1º Ano A, 2º Ano A, 3º Ano A', 'matutino,vespertino'),
        ('Luciana Ferreira', 'luciana@escola.com', 'Inglês', '1º Ano B, 2º Ano B, 3º Ano B', 'vespertino'),
        ('Roberto Lima', 'roberto@escola.com', 'Educação Física', '1º Ano A, 1º Ano B, 2º Ano A, 2º Ano B, 3º Ano A, 3º Ano B', 'matutino,vespertino'),
        ('Ana Paula Ribeiro', 'anapaula@escola.com', 'Artes', '1º Ano A, 1º Ano B, 2º Ano A, 2º Ano B, 3º Ano A, 3º Ano B', 'vespertino'),
    ]
    for nome, email, disc, turmas_prof, turnos in professores_seed:
        exists = c.execute("SELECT id FROM professores WHERE email=?", (email,)).fetchone()
        if not exists:
            c.execute("INSERT INTO professores (nome, email, senha, disciplina, turmas, turnos, bio) VALUES (?, ?, ?, ?, ?, ?, '')",
                      (nome, email, generate_password_hash('123456'), disc, turmas_prof, turnos))

    # Seed: nascimento, notas e frequencia dos alunos
    import random as _random
    _random.seed(42)
    disciplinas = ['Matemática', 'Português', 'História', 'Geografia', 'Ciências', 'Inglês', 'Educação Física', 'Artes']
    alunos_rows = c.execute("SELECT codigo, turma FROM alunos ORDER BY turma, nome").fetchall()

    # Nascimento
    for codigo, turma in alunos_rows:
        existe = c.execute("SELECT nascimento FROM alunos WHERE codigo=? AND nascimento IS NOT NULL AND nascimento != ''", (codigo,)).fetchone()
        if not existe or not existe[0]:
            ano_num = int(turma[0]) if turma and turma[0].isdigit() else 1
            idade = _random.randint(11 + (ano_num-1)*2, 13 + (ano_num-1)*2)
            nasc = f"{2026 - idade}-{_random.randint(1,12):02d}-{_random.randint(1,28):02d}"
            c.execute("UPDATE alunos SET nascimento=? WHERE codigo=?", (nasc, codigo))

    # Notas
    notas_existentes = c.execute("SELECT COUNT(*) FROM notas").fetchone()[0]
    if notas_existentes == 0:
        for codigo, turma in alunos_rows:
            for bimestre in [1, 2]:
                for disc in disciplinas:
                    nota = round(_random.uniform(3.0, 10.0), 1)
                    c.execute("INSERT OR REPLACE INTO notas (codigo_aluno, disciplina, nota, bimestre) VALUES (?, ?, ?, ?)",
                              (codigo, disc, nota, bimestre))

    # Frequencia - 20 dias uteis atras
    freq_existentes = c.execute("SELECT COUNT(*) FROM frequencia").fetchone()[0]
    if freq_existentes == 0:
        dias_uteis = []
        from datetime import datetime, timedelta
        data_atual = datetime(2026, 8, 28)
        while len(dias_uteis) < 20:
            data_atual -= timedelta(days=1)
            if data_atual.weekday() < 5:
                dias_uteis.append(data_atual.strftime('%Y-%m-%d'))
        dias_uteis.reverse()

        turmas_map = {}
        for codigo, turma in alunos_rows:
            turmas_map.setdefault(turma, []).append(codigo)

        for turma, codigos in turmas_map.items():
            for codigo in codigos:
                for disc in _random.sample(disciplinas, 3):
                    for dia in dias_uteis:
                        r = _random.random()
                        presente = 1 if r < 0.85 else 0
                        atestado = 1 if 0.85 <= r < 0.90 else 0
                        c.execute("INSERT OR REPLACE INTO frequencia (codigo_aluno, disciplina, turma, data, presente, atestado, bimestre) VALUES (?, ?, ?, ?, ?, ?, 1)",
                                  (codigo, disc, turma, dia, presente, atestado))

    conn.commit()
    conn.close()
    print("Banco de dados inicializado com sucesso!")


if __name__ == '__main__':
    init_db()
