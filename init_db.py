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
        senha TEXT NOT NULL
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS turmas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS alunos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo TEXT UNIQUE NOT NULL,
        nome TEXT NOT NULL,
        turma TEXT NOT NULL,
        nascimento TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS representantes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        turma TEXT NOT NULL,
        codigo_aluno TEXT NOT NULL,
        funcao TEXT NOT NULL DEFAULT 'representante',
        UNIQUE(turma)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS notas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo_aluno TEXT NOT NULL,
        disciplina TEXT NOT NULL,
        nota REAL DEFAULT 0,
        UNIQUE(codigo_aluno, disciplina)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS frequencia (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo_aluno TEXT NOT NULL,
        disciplina TEXT NOT NULL,
        turma TEXT NOT NULL,
        data TEXT NOT NULL,
        presente INTEGER DEFAULT 1,
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
        status TEXT DEFAULT 'confirmada'
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

    # Seed professor
    existing = c.execute("SELECT id FROM professores WHERE email='admin@escola.com'").fetchone()
    if not existing:
        senha_hash = generate_password_hash('123456')
        c.execute("INSERT INTO professores (nome, email, senha) VALUES (?, ?, ?)",
                  ('Administrador', 'admin@escola.com', senha_hash))

    # Seed turmas
    default_turmas = ['1º Ano A', '1º Ano B', '2º Ano A', '2º Ano B', '3º Ano A', '3º Ano B']
    for t in default_turmas:
        c.execute("INSERT OR IGNORE INTO turmas (nome) VALUES (?)", (t,))

    conn.commit()
    conn.close()
    print("Banco de dados inicializado com sucesso!")


if __name__ == '__main__':
    init_db()
