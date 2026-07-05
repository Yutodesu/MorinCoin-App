import os
import sqlite3
import hashlib
import json
import flet as ft

DB_FILE = "morincoin_local.db"

# === 1. BANCO DE DADOS LOCAL E CONTA DO ADMIN ===
def init_local_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS carteira (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            senha TEXT NOT NULL,
            saldo INTEGER NOT NULL,
            is_admin INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS arquivos_processados (
            id_transacao TEXT PRIMARY KEY
        )
    ''')
    
    try:
        cursor.execute("""
            INSERT INTO carteira (username, email, senha, saldo, is_admin) 
            VALUES ('admin', 'admin@morin.com', 'admin123', 300000, 1)
        """)
    except sqlite3.IntegrityError:
        pass
        
    conn.commit()
    conn.close()

init_local_db()

# === 2. CRIPTOGRAFIA E GERAÇÃO DO ARQUIVO .MORENCOIN ===
def gerar_hash_seguro(dados_string):
    return hashlib.sha256(dados_string.encode('utf-8')).hexdigest()

def exportar_moeda(remetente, valor, destino_fake):
    id_transacao = hashlib.md5(os.urandom(16)).hexdigest()[:12].upper()
    dados_transacao = {
        "remetente": remetente,
        "destinatario": destino_fake,
        "valor": int(valor),
        "id_transacao": id_transacao
    }
    
    string_para_hash = f"{dados_transacao['remetente']}-{dados_transacao['valor']}-{dados_transacao['id_transacao']}"
    assinatura = gerar_hash_seguro(string_para_hash)
    dados_transacao["assinatura"] = assinatura
    
    nome_arquivo = f"transacao_{id_transacao}.morencoin"
    with open(nome_arquivo, "w", encoding="utf-8") as f:
        json.dump(dados_transacao, f, indent=4)
        
    return nome_arquivo, valor

# === 3. INTERFACE VISUAL ACESSÍVEL E MOBILE-READY ===
def main(page: ft.Page):
    page.title = "MorinCoin Offline Network"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0b0f19"
    
    # --- MUDANÇA MOBILE AQUI ---
    # Removemos o tamanho de janela fixo de PC.
    # Ativamos rolagem automática e espaçamento elástico de 20px para não espremer nas bordas físicas do celular.
    page.scroll = ft.ScrollMode.AUTO
    page.padding = 20
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    
    sessao = {"usuario": "", "is_admin": 0}

    # --- FUNÇÃO QUE PROCESSA O TEXTO DO ARQUIVO COPIADO ---
    def processar_importacao_texto(e):
        texto_json = input_json_importar.value.strip()
        if not texto_json:
            page.snack_bar = ft.SnackBar(ft.Text("Cole o conteúdo do arquivo primeiro!"))
            page.snack_bar.open = True
            page.update()
            return
            
        try:
            dados = json.loads(texto_json)
        except Exception:
            page.snack_bar = ft.SnackBar(ft.Text("Texto inválido! Copie todo o conteúdo do arquivo."))
            page.snack_bar.open = True
            page.update()
            return
            
        # VALIDAÇÃO CRIPTOGRÁFICA
        string_validacao = f"{dados['remetente']}-{dados['valor']}-{dados['id_transacao']}"
        hash_calculado = gerar_hash_seguro(string_validacao)
        
        if hash_calculado != dados["assinatura"]:
            page.snack_bar = ft.SnackBar(ft.Text("🚨 FRAUDE! A assinatura digital não bate."))
            page.snack_bar.open = True
            page.update()
            return
            
        # VALIDAÇÃO DE GASTO DUPLO
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM arquivos_processados WHERE id_transacao = ?", (dados["id_transacao"],))
        ja_usado = cursor.fetchone()
        
        if ja_usado:
            page.snack_bar = ft.SnackBar(ft.Text("❌ ERRO: Essa moeda já foi resgatada!"))
            page.snack_bar.open = True
            conn.close()
            page.update()
            return
            
        # Deposita o saldo na conta atual
        cursor.execute("UPDATE carteira SET saldo = saldo + ? WHERE username = ?", (dados["valor"], sessao["usuario"]))
        cursor.execute("INSERT INTO arquivos_processados (id_transacao) VALUES (?)", (dados["id_transacao"],))
        conn.commit()
        
        cursor.execute("SELECT saldo FROM carteira WHERE username = ?", (sessao["usuario"],))
        txt_saldo.value = f"{cursor.fetchone()[0]} MRN"
        conn.close()
        
        page.snack_bar = ft.SnackBar(ft.Text(f"✅ Sucesso! +{dados['valor']} MRN importados."))
        page.snack_bar.open = True
        input_json_importar.value = ""
        view_importar_container.visible = False
        page.update()

    # --- FUNÇÕES DE NAVEGAÇÃO DE TELAS ---
    def alternar_painel_importar(e):
        view_importar_container.visible = not view_importar_container.visible
        page.update()

    # --- FUNÇÕES DE INTERAÇÃO ---
    def processar_registro(e):
        user = user_reg.value.lower().strip()
        mail = mail_reg.value.strip()
        pwd = pwd_reg.value
        
        if not user or not pwd:
            page.snack_bar = ft.SnackBar(ft.Text("Preencha os campos obrigatórios!"))
            page.snack_bar.open = True
            page.update()
            return
            
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO carteira (username, email, senha, saldo, is_admin) VALUES (?, ?, ?, 0, 0)", (user, mail, pwd))
            conn.commit()
            page.snack_bar = ft.SnackBar(ft.Text("Conta local criada! Faça o Login."))
            page.snack_bar.open = True
            ir_para_login(None)
        except sqlite3.IntegrityError:
            page.snack_bar = ft.SnackBar(ft.Text("Usuário já existente neste dispositivo."))
            page.snack_bar.open = True
        finally:
            conn.close()
        page.update()

    def processar_login(e):
        user = user_login.value.lower().strip()
        pwd = pwd_login.value
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT username, saldo, is_admin FROM carteira WHERE username = ? AND senha = ?", (user, pwd))
        resultado = cursor.fetchone()
        conn.close()
        
        if resultado:
            sessao["usuario"] = resultado[0]
            sessao["is_admin"] = resultado[2]
            
            txt_saldo.value = f"{resultado[1]} MRN"
            txt_user_painel.value = f"Olá, {resultado[0]} {'(ADMIN)' if resultado[2] == 1 else ''}"
            
            card_admin.visible = True if resultado[2] == 1 else False
            view_importar_container.visible = False
            ir_para_painel()
        else:
            page.snack_bar = ft.SnackBar(ft.Text("Usuário ou senha incorretos!"))
            page.snack_bar.open = True
        page.update()

    def executar_envio(e):
        if not input_qtd.value or not input_dest.value:
            page.snack_bar = ft.SnackBar(ft.Text("Preencha o destino e a quantidade!"))
            page.snack_bar.open = True
            page.update()
            return

        try:
            qtd = int(input_qtd.value)
            dest = input_dest.value.lower().strip()
        except ValueError:
            page.snack_bar = ft.SnackBar(ft.Text("Quantidade deve ser um número inteiro!"))
            page.snack_bar.open = True
            page.update()
            return
            
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT saldo FROM carteira WHERE username = ?", (sessao["usuario"],))
        saldo_atual = cursor.fetchone()[0]
        
        if saldo_atual < qtd:
            page.snack_bar = ft.SnackBar(ft.Text("Saldo Insuficiente para assinar moeda!"))
            page.snack_bar.open = True
            conn.close()
            page.update()
            return
            
        cursor.execute("UPDATE carteira SET saldo = saldo - ? WHERE username = ?", (qtd, sessao["usuario"]))
        conn.commit()
        
        nome_arq, valor_env = exportar_moeda(sessao["usuario"], qtd, dest)
        
        cursor.execute("SELECT saldo FROM carteira WHERE username = ?", (sessao["usuario"],))
        txt_saldo.value = f"{cursor.fetchone()[0]} MRN"
        conn.close()
        
        page.snack_bar = ft.SnackBar(ft.Text(f"Arquivo gerado: {nome_arq} (-{valor_env} MRN)"))
        page.snack_bar.open = True
        input_qtd.value = ""
        input_dest.value = ""
        page.update()

    def admin_gerar_moedas_do_nada(e):
        try:
            qtd_injecao = int(input_admin_qtd.value)
        except ValueError:
            return
            
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE carteira SET saldo = saldo + ? WHERE username = 'admin'", (qtd_injecao,))
        conn.commit()
        
        cursor.execute("SELECT saldo FROM carteira WHERE username = 'admin'")
        txt_saldo.value = f"{cursor.fetchone()[0]} MRN"
        conn.close()
        
        page.snack_bar = ft.SnackBar(ft.Text(f"⚡ Injeção concluída: +{qtd_injecao} MRN."))
        page.snack_bar.open = True
        input_admin_qtd.value = ""
        page.update()

    # --- COMPONENTES DE INTERFACE RESPONSIVOS ---
    user_login = ft.TextField(label="Nome de Usuário", border_color="#374151")
    pwd_login = ft.TextField(label="Senha", password=True, can_reveal_password=True, border_color="#374151")
    view_login = ft.Column([
        ft.Text("🪙 MorinCoin Offline", size=26, color="#38bdf8", weight=ft.FontWeight.BOLD),
        user_login, pwd_login,
        ft.ElevatedButton("Entrar no App", on_click=processar_login, bgcolor="#0284c7", color="white", width=300),
        ft.TextButton("Criar nova conta offline", on_click=lambda _: ir_para_registro())
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    user_reg = ft.TextField(label="Escolha seu Usuário", border_color="#374151")
    mail_reg = ft.TextField(label="E-mail", border_color="#374151")
    pwd_reg = ft.TextField(label="Crie uma Senha", password=True, border_color="#374151")
    view_register = ft.Column([
        ft.Text("🔑 Novo Cadastro", size=24, color="#34d399", weight=ft.FontWeight.BOLD),
        user_reg, mail_reg, pwd_reg,
        ft.ElevatedButton("Criar Carteira", on_click=processar_registro, bgcolor="#34d399", color="black", width=300),
        ft.TextButton("Voltar para o Login", on_click=lambda _: ir_para_login(None))
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    txt_user_painel = ft.Text(size=14, color="#9ca3af", weight=ft.FontWeight.BOLD)
    txt_saldo = ft.Text(size=36, weight=ft.FontWeight.BOLD, color="#f3f4f6")
    input_dest = ft.TextField(label="Para quem? (Username)", border_color="#374151")
    input_qtd = ft.TextField(label="Quantidade de MRN", border_color="#374151")
    
    input_admin_qtd = ft.TextField(label="Quantidade para Injetar", border_color="#eab308")
    
    card_admin = ft.Container(
        content=ft.Column([
            ft.Text("🛠️ Painel Mestre (Admin)", size=16, color="#eab308", weight=ft.FontWeight.BOLD),
            input_admin_qtd,
            ft.ElevatedButton("Gerar e Adicionar MRN", on_click=admin_gerar_moedas_do_nada, bgcolor="#eab308", color="black", width=280)
        ]),
        padding=15,
        visible=False
    )

    input_json_importar = ft.TextField(label="Cole o texto do arquivo .morencoin aqui", multiline=True, min_lines=3, max_lines=5, border_color="#34d399")
    view_importar_container = ft.Container(
        content=ft.Column([
            input_json_importar,
            ft.ElevatedButton("Confirmar Depósito", on_click=processar_importacao_texto, bgcolor="#34d399", color="black", width=280)
        ]),
        padding=10,
        visible=False
    )
    
    view_painel = ft.Column([
        ft.Row([
            txt_user_painel,
            ft.Row([
                ft.TextButton("Importar", on_click=alternar_painel_importar, style=ft.ButtonStyle(color="#34d399")),
                ft.TextButton("Sair", on_click=lambda _: ir_para_login(None), style=ft.ButtonStyle(color="#ef4444")),
            ], spacing=5)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Text("Saldo Atual:", size=16, color="#38bdf8"),
        txt_saldo,
        ft.Divider(color="#1f2937"),
        
        view_importar_container,
        card_admin,
        
        ft.Text("💸 Gerar Moeda Offline", size=18, weight=ft.FontWeight.BOLD),
        input_dest, input_qtd,
        ft.ElevatedButton("Assinar e Exportar .morencoin", on_click=executar_envio, bgcolor="#0284c7", color="white", width=300)
    ], horizontal_alignment=ft.CrossAxisAlignment.START, visible=False)

    # --- GERENCIADOR DE TELAS ---
    def ir_para_login(e):
        view_login.visible = True
        view_register.visible = False
        view_painel.visible = False
        page.update()

    def ir_para_registro():
        view_login.visible = False
        view_register.visible = True
        view_painel.visible = False
        page.update()

    def ir_para_painel():
        view_login.visible = False
        view_register.visible = False
        view_painel.visible = True
        page.update()

    view_register.visible = False
    page.add(view_login, view_register, view_painel)

if __name__ == "__main__":
    ft.app(target=main)
