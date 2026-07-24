import os
import sqlite3
import hashlib
import json
import flet as ft

DB_FILE = "morincoin_local.db"

def init_local_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS carteira (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, email TEXT, senha TEXT NOT NULL, saldo INTEGER NOT NULL, is_admin INTEGER DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS arquivos_processados (id_transacao TEXT PRIMARY KEY)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS configuracoes (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT UNIQUE NOT NULL, tema TEXT DEFAULT 'escuro', idioma TEXT DEFAULT 'portugues', som INTEGER DEFAULT 1, pin TEXT, anonimo INTEGER DEFAULT 0, limite_transacao INTEGER DEFAULT 10000)''')
    try:
        cursor.execute("INSERT INTO carteira (username, email, senha, saldo, is_admin) VALUES ('admin', 'admin@morin.com', '002WEGGLzxc', 300000, 1)")
    except: pass
    try:
        cursor.execute("INSERT INTO configuracoes (usuario, tema, idioma, som, pin, anonimo, limite_transacao) VALUES ('admin', 'escuro', 'portugues', 1, NULL, 0, 10000)")
    except: pass
    conn.commit()
    conn.close()

init_local_db()

def gerar_hash_seguro(dados_string):
    return hashlib.sha256(dados_string.encode('utf-8')).hexdigest()

def exportar_moeda(remetente, valor, destino_fake, modo_anonimo=False):
    id_transacao = hashlib.md5(os.urandom(16)).hexdigest()[:12].upper()
    if modo_anonimo:
        codigo_unico = hashlib.sha256(f"{id_transacao}{valor}{os.urandom(16)}".encode()).hexdigest()[:16].upper()
        dados_transacao = {"codigo": codigo_unico, "valor": int(valor), "id_transacao": id_transacao}
    else:
        dados_transacao = {"remetente": remetente, "destinatario": destino_fake, "valor": int(valor), "id_transacao": id_transacao}
    string_para_hash = json.dumps(dados_transacao, sort_keys=True)
    assinatura = gerar_hash_seguro(string_para_hash)
    dados_transacao["assinatura"] = assinatura
    return dados_transacao, valor

def main(page: ft.Page):
    page.title = "MorinCoin Offline"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0b0f19"
    page.window_width = 380
    page.window_height = 680
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.scroll = "adaptive"
    sessao = {"usuario": "", "is_admin": 0}

    def focus_scroll(e): page.update()

    def processar_importacao_texto(e):
        texto_json = input_json_importar.value.strip()
        if not texto_json:
            page.snack_bar = ft.SnackBar(ft.Text("Cole o conteúdo do arquivo primeiro!"))
            page.snack_bar.open = True
            page.update()
            return
        try:
            dados = json.loads(texto_json)
        except:
            page.snack_bar = ft.SnackBar(ft.Text("Texto inválido!"))
            page.snack_bar.open = True
            page.update()
            return
        string_validacao = json.dumps({k: v for k, v in dados.items() if k != "assinatura"}, sort_keys=True)
        hash_calculado = gerar_hash_seguro(string_validacao)
        if hash_calculado != dados["assinatura"]:
            page.snack_bar = ft.SnackBar(ft.Text("🚨 FRAUDE! Assinatura não bate."))
            page.snack_bar.open = True
            page.update()
            return
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM arquivos_processados WHERE id_transacao = ?", (dados["id_transacao"],))
        if cursor.fetchone():
            page.snack_bar = ft.SnackBar(ft.Text("❌ Essa moeda já foi resgatada!"))
            page.snack_bar.open = True
            conn.close()
            page.update()
            return
        cursor.execute("UPDATE carteira SET saldo = saldo + ? WHERE username = ?", (dados["valor"], sessao["usuario"]))
        cursor.execute("INSERT INTO arquivos_processados (id_transacao) VALUES (?)", (dados["id_transacao"],))
        conn.commit()
        cursor.execute("SELECT saldo FROM carteira WHERE username = ?", (sessao["usuario"],))
        txt_saldo.value = f"{cursor.fetchone()[0]} MRN"
        conn.close()
        page.snack_bar = ft.SnackBar(ft.Text(f"✅ +{dados['valor']} MRN importados!"))
        page.snack_bar.open = True
        input_json_importar.value = ""
        view_importar_container.visible = False
        page.update()

    def alternar_painel_importar(e):
        view_importar_container.visible = not view_importar_container.visible
        transacao_json_display.visible = False
        btn_copiar_transacao.visible = False
        page.update()

    def processar_registro(e):
        user = user_reg.value.lower().strip()
        mail = mail_reg.value.strip()
        pwd = pwd_reg.value
        if not user or not pwd:
            page.snack_bar = ft.SnackBar(ft.Text("Preencha os campos!"))
            page.snack_bar.open = True
            page.update()
            return
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO carteira (username, email, senha, saldo, is_admin) VALUES (?, ?, ?, 0, 0)", (user, mail, pwd))
            cursor.execute("INSERT INTO configuracoes (usuario, tema, idioma, som, pin, anonimo, limite_transacao) VALUES (?, 'escuro', 'portugues', 1, NULL, 0, 10000)", (user,))
            conn.commit()
            page.snack_bar = ft.SnackBar(ft.Text("Conta criada! Faça o Login."))
            page.snack_bar.open = True
            ir_para_login(None)
        except sqlite3.IntegrityError:
            page.snack_bar = ft.SnackBar(ft.Text("Usuário já existe!"))
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
        if resultado:
            sessao["usuario"] = resultado[0]
            sessao["is_admin"] = resultado[2]
            txt_saldo.value = f"{resultado[1]} MRN"
            txt_user_painel.value = f"Olá, {resultado[0]} {'(ADMIN)' if resultado[2] == 1 else ''}"
            card_admin.visible = True if resultado[2] == 1 else False
            view_importar_container.visible = False
            transacao_json_display.visible = False
            btn_copiar_transacao.visible = False
            cursor.execute("SELECT tema FROM configuracoes WHERE usuario = ?", (user,))
            config = cursor.fetchone()
            if config and config[0] == "claro":
                page.theme_mode = ft.ThemeMode.LIGHT
                page.bgcolor = "#34d399"
            else:
                page.theme_mode = ft.ThemeMode.DARK
                page.bgcolor = "#0b0f19"
            conn.close()
            ir_para_painel()
        else:
            page.snack_bar = ft.SnackBar(ft.Text("Usuário ou senha incorretos!"))
            page.snack_bar.open = True
            conn.close()
        page.update()

    def confirmar_envio(e):
        def confirmar_sim(e):
            dialog.open = False
            page.update()
            executar_envio(None)
        def confirmar_nao(e):
            dialog.open = False
            page.update()
        dialog = ft.AlertDialog(title=ft.Text("⚠️ Confirmar Envio"), content=ft.Text(f"Enviar {input_qtd.value} MRN para {input_dest.value}?"), actions=[ft.TextButton("❌ Não", on_click=confirmar_nao), ft.Button("✅ Sim", on_click=confirmar_sim, bgcolor=ft.colors.GREEN, color="white")], actions_alignment=ft.MainAxisAlignment.END)
        page.dialog = dialog
        dialog.open = True
        page.update()

    def executar_envio(e):
        if not input_qtd.value or not input_dest.value:
            page.snack_bar = ft.SnackBar(ft.Text("Preencha destino e quantidade!"))
            page.snack_bar.open = True
            page.update()
            return
        try:
            qtd = int(input_qtd.value)
            dest = input_dest.value.lower().strip()
        except:
            page.snack_bar = ft.SnackBar(ft.Text("Quantidade inválida!"))
            page.snack_bar.open = True
            page.update()
            return
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT saldo FROM carteira WHERE username = ?", (sessao["usuario"],))
        if cursor.fetchone()[0] < qtd:
            page.snack_bar = ft.SnackBar(ft.Text("Saldo Insuficiente!"))
            page.snack_bar.open = True
            conn.close()
            page.update()
            return
        cursor.execute("SELECT anonimo FROM configuracoes WHERE usuario = ?", (sessao["usuario"],))
        config = cursor.fetchone()
        modo_anonimo = config[0] == 1 if config else False
        cursor.execute("UPDATE carteira SET saldo = saldo - ? WHERE username = ?", (qtd, sessao["usuario"]))
        conn.commit()
        dados_transacao, valor_env = exportar_moeda(sessao["usuario"], qtd, dest, modo_anonimo)
        cursor.execute("SELECT saldo FROM carteira WHERE username = ?", (sessao["usuario"],))
        txt_saldo.value = f"{cursor.fetchone()[0]} MRN"
        conn.close()
        json_pretty = json.dumps(dados_transacao, indent=4, ensure_ascii=False)
        transacao_json_display.value = json_pretty
        transacao_json_display.visible = True
        btn_copiar_transacao.visible = True
        input_qtd.value = ""
        input_dest.value = ""
        page.snack_bar = ft.SnackBar(ft.Text(f"✅ Transação gerada! -{valor_env} MRN"))
        page.snack_bar.open = True
        page.update()

    def copiar_json_transacao(e):
        try:
            page.set_clipboard(transacao_json_display.value)
            page.snack_bar = ft.SnackBar(ft.Text("📋 JSON copiado!"))
            page.snack_bar.open = True
            page.update()
        except Exception as ex:
            page.snack_bar = ft.SnackBar(ft.Text(f"Erro: {ex}"))
            page.snack_bar.open = True
            page.update()

    def admin_gerar_moedas_do_nada(e):
        try:
            qtd_injecao = int(input_admin_qtd.value)
        except:
            page.snack_bar = ft.SnackBar(ft.Text("Digite um valor válido!"))
            page.snack_bar.open = True
            page.update()
            return
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE carteira SET saldo = saldo + ? WHERE username = 'admin'", (qtd_injecao,))
        conn.commit()
        cursor.execute("SELECT saldo FROM carteira WHERE username = 'admin'")
        txt_saldo.value = f"{cursor.fetchone()[0]} MRN"
        conn.close()
        page.snack_bar = ft.SnackBar(ft.Text(f"⚡ +{qtd_injecao} MRN injetados."))
        page.snack_bar.open = True
        input_admin_qtd.value = ""
        page.update()

    def abrir_minha_conta():
        page.drawer.open = False
        page.update()
        novo_nome = ft.TextField(label="Novo Nome", value=sessao["usuario"])
        nova_senha = ft.TextField(label="Nova Senha", password=True)
        confirmar_senha = ft.TextField(label="Confirmar Senha", password=True)
        def salvar_alteracoes(e):
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            if novo_nome.value and novo_nome.value != sessao["usuario"]:
                cursor.execute("UPDATE carteira SET username = ? WHERE username = ?", (novo_nome.value, sessao["usuario"]))
                cursor.execute("UPDATE configuracoes SET usuario = ? WHERE usuario = ?", (novo_nome.value, sessao["usuario"]))
                sessao["usuario"] = novo_nome.value
                txt_user_painel.value = f"Olá, {sessao['usuario']}"
            if nova_senha.value and nova_senha.value == confirmar_senha.value:
                cursor.execute("UPDATE carteira SET senha = ? WHERE username = ?", (nova_senha.value, sessao["usuario"]))
                page.snack_bar = ft.SnackBar(ft.Text("✅ Senha alterada!"))
                page.snack_bar.open = True
            elif nova_senha.value:
                page.snack_bar = ft.SnackBar(ft.Text("❌ Senhas não coincidem!"))
                page.snack_bar.open = True
            conn.commit()
            conn.close()
            dialog.open = False
            page.update()
        dialog = ft.AlertDialog(title=ft.Text("👤 Minha Conta"), content=ft.Column([novo_nome, nova_senha, confirmar_senha], width=300), actions=[ft.TextButton("Cancelar", on_click=lambda e: (setattr(dialog, 'open', False), page.update())), ft.Button("Salvar", on_click=salvar_alteracoes, bgcolor="green", color="white")])
        page.dialog = dialog
        dialog.open = True
        page.update()

    def alternar_tema(e):
        if page.theme_mode == ft.ThemeMode.DARK:
            page.theme_mode = ft.ThemeMode.LIGHT
            page.bgcolor = "#f3f4f6"
        else:
            page.theme_mode = ft.ThemeMode.DARK
            page.bgcolor = "#0b0f19"
        page.update()
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE configuracoes SET tema = ? WHERE usuario = ?", ("claro" if page.theme_mode == ft.ThemeMode.LIGHT else "escuro", sessao["usuario"]))
        conn.commit()
        conn.close()

    def alternar_som(e):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE configuracoes SET som = ? WHERE usuario = ?", (1 if e.control.value else 0, sessao["usuario"]))
        conn.commit()
        conn.close()
        page.snack_bar = ft.SnackBar(ft.Text(f"🔊 Sons {'ativados' if e.control.value else 'desativados'}"))
        page.snack_bar.open = True
        page.update()

    def alternar_anonimo(e):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE configuracoes SET anonimo = ? WHERE usuario = ?", (1 if e.control.value else 0, sessao["usuario"]))
        conn.commit()
        conn.close()
        page.snack_bar = ft.SnackBar(ft.Text(f"🕵️ Anônimo {'ativado' if e.control.value else 'desativado'}"))
        page.snack_bar.open = True
        page.update()

    def abrir_idioma():
        page.drawer.open = False
        page.update()
        idiomas = ["Português", "English", "Русский", "日本語"]
        def selecionar_idioma(e, idioma):
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("UPDATE configuracoes SET idioma = ? WHERE usuario = ?", (idioma.lower(), sessao["usuario"]))
            conn.commit()
            conn.close()
            page.snack_bar = ft.SnackBar(ft.Text(f"🌐 Idioma: {idioma}"))
            page.snack_bar.open = True
            dialog.open = False
            page.update()
        dialog = ft.AlertDialog(title=ft.Text("🌐 Idioma"), content=ft.Column([ft.Button(idioma, on_click=lambda e, i=idioma: selecionar_idioma(e, i), width=200) for idioma in idiomas]), actions=[ft.TextButton("Fechar", on_click=lambda e: (setattr(dialog, 'open', False), page.update()))])
        page.dialog = dialog
        dialog.open = True
        page.update()

    def abrir_pin():
        page.drawer.open = False
        page.update()
        pin_input = ft.TextField(label="PIN (6 dígitos)", max_length=6, keyboard_type=ft.KeyboardType.NUMBER)
        def salvar_pin(e):
            if len(pin_input.value) == 6:
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("UPDATE configuracoes SET pin = ? WHERE usuario = ?", (pin_input.value, sessao["usuario"]))
                conn.commit()
                conn.close()
                page.snack_bar = ft.SnackBar(ft.Text("🔒 PIN definido!"))
                page.snack_bar.open = True
                dialog.open = False
                page.update()
            else:
                page.snack_bar = ft.SnackBar(ft.Text("❌ 6 dígitos!"))
                page.snack_bar.open = True
                page.update()
        dialog = ft.AlertDialog(title=ft.Text("🔒 PIN"), content=pin_input, actions=[ft.TextButton("Cancelar", on_click=lambda e: (setattr(dialog, 'open', False), page.update())), ft.Button("Salvar", on_click=salvar_pin, bgcolor="green", color="white")])
        page.dialog = dialog
        dialog.open = True
        page.update()

    def abrir_limite():
        page.drawer.open = False
        page.update()
        limite_input = ft.TextField(label="Limite (MRN)", value="10000", keyboard_type=ft.KeyboardType.NUMBER)
        def salvar_limite(e):
            try:
                valor = int(limite_input.value)
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("UPDATE configuracoes SET limite_transacao = ? WHERE usuario = ?", (valor, sessao["usuario"]))
                conn.commit()
                conn.close()
                page.snack_bar = ft.SnackBar(ft.Text(f"✅ Limite: {valor} MRN"))
                page.snack_bar.open = True
                dialog.open = False
                page.update()
            except:
                page.snack_bar = ft.SnackBar(ft.Text("❌ Número válido!"))
                page.snack_bar.open = True
                page.update()
        dialog = ft.AlertDialog(title=ft.Text("💰 Limite"), content=limite_input, actions=[ft.TextButton("Cancelar", on_click=lambda e: (setattr(dialog, 'open', False), page.update())), ft.Button("Salvar", on_click=salvar_limite, bgcolor="green", color="white")])
        page.dialog = dialog
        dialog.open = True
        page.update()

    def exportar_backup():
        page.drawer.open = False
        page.update()
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM carteira WHERE username = ?", (sessao["usuario"],))
        dados = cursor.fetchone()
        conn.close()
        if dados:
            backup = {"usuario": dados[1], "email": dados[2], "senha": dados[3], "saldo": dados[4], "is_admin": dados[5]}
            backup_json = json.dumps(backup, indent=4, ensure_ascii=False)
            backup_text = ft.TextField(label="📋 Backup", value=backup_json, multiline=True, read_only=True, min_lines=8)
            def copiar_backup(e):
                page.set_clipboard(backup_json)
                page.snack_bar = ft.SnackBar(ft.Text("📋 Backup copiado!"))
                page.snack_bar.open = True
                page.update()
            dialog = ft.AlertDialog(title=ft.Text("💾 Backup"), content=ft.Column([ft.Text("⚠️ Copie e guarde em local seguro"), backup_text, ft.Button("📋 Copiar", on_click=copiar_backup, bgcolor="#34d399", color="black")], width=350), actions=[ft.TextButton("Fechar", on_click=lambda e: (setattr(dialog, 'open', False), page.update()))])
            page.dialog = dialog
            dialog.open = True
            page.update()

    def abrir_historico():
        page.drawer.open = False
        page.update()
        historico_text = f"📜 HISTÓRICO - {sessao['usuario']}\n{'='*40}\n\n"
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM arquivos_processados ORDER BY rowid DESC LIMIT 20")
        transacoes = cursor.fetchall()
        conn.close()
        if transacoes:
            for i, t in enumerate(transacoes, 1):
                historico_text += f"#{i} - {t[0]}\n"
        else:
            historico_text += "Nenhuma transação.\n"
        historico_text += f"\n{'='*40}\nTotal: {len(transacoes)}"
        def copiar_historico(e):
            page.set_clipboard(historico_text)
            page.snack_bar = ft.SnackBar(ft.Text("📋 Histórico copiado!"))
            page.snack_bar.open = True
            page.update()
        def salvar_historico(e):
            try:
                with open(f"historico_{sessao['usuario']}.txt", "w", encoding="utf-8") as f:
                    f.write(historico_text)
                page.snack_bar = ft.SnackBar(ft.Text("✅ Histórico salvo!"))
                page.snack_bar.open = True
                page.update()
            except Exception as ex:
                page.snack_bar = ft.SnackBar(ft.Text(f"❌ Erro: {ex}"))
                page.snack_bar.open = True
                page.update()
        dialog = ft.AlertDialog(title=ft.Text("📜 Histórico"), content=ft.Column([ft.TextField(value=historico_text, multiline=True, read_only=True, min_lines=12), ft.Row([ft.Button("📋 Copiar", on_click=copiar_historico, bgcolor="#34d399", color="black"), ft.Button("⬇️ TXT", on_click=salvar_historico, bgcolor="#0284c7", color="white")])], width=350), actions=[ft.TextButton("Fechar", on_click=lambda e: (setattr(dialog, 'open', False), page.update()))])
        page.dialog = dialog
        dialog.open = True
        page.update()

    def abrir_tutorial():
        page.drawer.open = False
        page.update()
        tutorial = "📖 TUTORIAL\n\n1️⃣ CRIAR CONTA - Registre-se\n2️⃣ RECEBER - Importar JSON\n3️⃣ ENVIAR - Assinar e Exportar\n4️⃣ ADMIN - admin / 002WEGGLzxc\n5️⃣ SEGURANÇA - SHA-256 + anti-gasto duplo\n\n🔒 100% OFFLINE!"
        dialog = ft.AlertDialog(title=ft.Text("📖 Tutorial"), content=ft.Column([ft.TextField(value=tutorial, multiline=True, read_only=True, min_lines=12)], width=350), actions=[ft.TextButton("Fechar", on_click=lambda e: (setattr(dialog, 'open', False), page.update()))])
        page.dialog = dialog
        dialog.open = True
        page.update()

    def abrir_termos():
        page.drawer.open = False
        page.update()
        termos = "📜 TERMOS\n\n🔒 100% OFFLINE\n🔑 SHA-256\n⚠️ Responsabilidade do usuário\n📱 Privacidade total\n🔄 Backup é único\n👑 admin / 002WEGGLzxc\n\nVersão 1.0.0"
        dialog = ft.AlertDialog(title=ft.Text("📜 Termos"), content=ft.Column([ft.TextField(value=termos, multiline=True, read_only=True, min_lines=12)], width=350), actions=[ft.TextButton("Fechar", on_click=lambda e: (setattr(dialog, 'open', False), page.update()))])
        page.dialog = dialog
        dialog.open = True
        page.update()

    def abrir_contato():
        page.drawer.open = False
        page.update()
        contato = "📱 SUPORTE\n\n📧 suporte@morincoin.com\n📱 @MorinCoinSuporte\n\n💬 24/7\n📌 Resposta em até 24h"
        dialog = ft.AlertDialog(title=ft.Text("📱 Suporte"), content=ft.Column([ft.TextField(value=contato, multiline=True, read_only=True, min_lines=8)], width=350), actions=[ft.TextButton("Fechar", on_click=lambda e: (setattr(dialog, 'open', False), page.update()))])
        page.dialog = dialog
        dialog.open = True
        page.update()

    def sair_conta():
        page.drawer.open = False
        page.update()
        def confirmar(e):
            dialog.open = False
            page.update()
            ir_para_login(None)
            page.snack_bar = ft.SnackBar(ft.Text("👋 Até logo!"))
            page.snack_bar.open = True
            page.update()
        dialog = ft.AlertDialog(title=ft.Text("👋 Sair"), content=ft.Text("Sair da conta?"), actions=[ft.TextButton("Cancelar", on_click=lambda e: (setattr(dialog, 'open', False), page.update())), ft.Button("✅ Sair", on_click=confirmar, bgcolor="red", color="white")])
        page.dialog = dialog
        dialog.open = True
        page.update()

    def excluir_conta():
        page.drawer.open = False
        page.update()
        def confirmar(e):
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM carteira WHERE username = ?", (sessao["usuario"],))
            cursor.execute("DELETE FROM configuracoes WHERE usuario = ?", (sessao["usuario"],))
            conn.commit()
            conn.close()
            dialog.open = False
            page.update()
            ir_para_login(None)
            page.snack_bar = ft.SnackBar(ft.Text("🗑️ Conta excluída!"))
            page.snack_bar.open = True
            page.update()
        dialog = ft.AlertDialog(title=ft.Text("⚠️ EXCLUIR CONTA"), content=ft.Text(f"Excluir '{sessao['usuario']}'?\n\n⚠️ IRREVERSÍVEL!\nSem backup = perda total!"), actions=[ft.TextButton("Cancelar", on_click=lambda e: (setattr(dialog, 'open', False), page.update())), ft.Button("🗑️ EXCLUIR", on_click=confirmar, bgcolor="red", color="white")])
        page.dialog = dialog
        dialog.open = True
        page.update()

    def abrir_configuracoes(e):
        drawer = ft.NavigationDrawer(controls=[
            ft.Container(height=20),
            ft.Text("⚙️ CONFIGURAÇÕES", size=18, weight=ft.FontWeight.BOLD, color="#38bdf8"),
            ft.Divider(),
            ft.ListTile(leading=ft.Icon(ft.icons.PERSON), title=ft.Text("Minha Conta"), on_click=lambda _: abrir_minha_conta()),
            ft.ListTile(leading=ft.Icon(ft.icons.BRIGHTNESS_4), title=ft.Text("Tema"), trailing=ft.Switch(value=page.theme_mode == ft.ThemeMode.LIGHT, on_change=alternar_tema)),
            ft.ListTile(leading=ft.Icon(ft.icons.LANGUAGE), title=ft.Text("Idioma"), on_click=lambda _: abrir_idioma()),
            ft.ListTile(leading=ft.Icon(ft.icons.VOLUME_UP), title=ft.Text("Sons"), trailing=ft.Switch(value=True, on_change=alternar_som)),
            ft.ListTile(leading=ft.Icon(ft.icons.LOCK), title=ft.Text("PIN"), on_click=lambda _: abrir_pin()),
            ft.ListTile(leading=ft.Icon(ft.icons.ANONYMOUS), title=ft.Text("Anônimo"), trailing=ft.Switch(value=False, on_change=alternar_anonimo)),
            ft.ListTile(leading=ft.Icon(ft.icons.ATTACH_MONEY), title=ft.Text("Limite"), on_click=lambda _: abrir_limite()),
            ft.Divider(),
            ft.ListTile(leading=ft.Icon(ft.icons.BACKUP), title=ft.Text("Backup"), on_click=lambda _: exportar_backup()),
            ft.ListTile(leading=ft.Icon(ft.icons.HISTORY), title=ft.Text("Histórico"), on_click=lambda _: abrir_historico()),
            ft.Divider(),
            ft.ListTile(leading=ft.Icon(ft.icons.HELP), title=ft.Text("Tutorial"), on_click=lambda _: abrir_tutorial()),
            ft.ListTile(leading=ft.Icon(ft.icons.GAVEL), title=ft.Text("Termos"), on_click=lambda _: abrir_termos()),
            ft.Divider(),
            ft.ListTile(leading=ft.Icon(ft.icons.INFO), title=ft.Text("Versão 1.0.0")),
            ft.ListTile(leading=ft.Icon(ft.icons.CONTACT_MAIL), title=ft.Text("Suporte"), on_click=lambda _: abrir_contato()),
            ft.Divider(),
            ft.ListTile(leading=ft.Icon(ft.icons.LOGOUT, color="red"), title=ft.Text("Sair", color="red"), on_click=lambda _: sair_conta()),
            ft.ListTile(leading=ft.Icon(ft.icons.DELETE_FOREVER, color="red"), title=ft.Text("Excluir Conta", color="red"), on_click=lambda _: excluir_conta()),
        ])
        page.drawer = drawer
        drawer.open = True
        page.update()

    # ========== COMPONENTES ==========
    user_login = ft.TextField(label="Usuário", border_color="#374151", on_focus=focus_scroll)
    pwd_login = ft.TextField(label="Senha", password=True, can_reveal_password=True, border_color="#374151", on_focus=focus_scroll)
    view_login = ft.Column([ft.Text("🪙 MorinCoin", size=26, color="#38bdf8", weight=ft.FontWeight.BOLD), user_login, pwd_login, ft.Button("Entrar", on_click=processar_login, bgcolor="#0284c7", color="white", width=300), ft.TextButton("Criar conta", on_click=lambda _: ir_para_registro())], horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    user_reg = ft.TextField(label="Usuário", border_color="#374151", on_focus=focus_scroll)
    mail_reg = ft.TextField(label="E-mail", border_color="#374151", on_focus=focus_scroll)
    pwd_reg = ft.TextField(label="Senha", password=True, border_color="#374151", on_focus=focus_scroll)
    view_register = ft.Column([ft.Text("🔑 Cadastro", size=24, color="#34d399", weight=ft.FontWeight.BOLD), user_reg, mail_reg, pwd_reg, ft.Button("Criar", on_click=processar_registro, bgcolor="#34d399", color="black", width=300), ft.TextButton("Voltar", on_click=lambda _: ir_para_login(None))], horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    txt_user_painel = ft.Text(size=14, color="#9ca3af", weight=ft.FontWeight.BOLD)
    txt_saldo = ft.Text(size=36, weight=ft.FontWeight.BOLD, color="#f3f4f6")
    input_dest = ft.TextField(label="Para quem?", border_color="#374151", on_focus=focus_scroll)
    input_qtd = ft.TextField(label="Quantidade MRN", border_color="#374151", on_focus=focus_scroll)
    input_admin_qtd = ft.TextField(label="Injetar MRN", border_color="#eab308", on_focus=focus_scroll)

    card_admin = ft.Container(content=ft.Column([ft.Text("🛠️ Admin", size=16, color="#eab308", weight=ft.FontWeight.BOLD), input_admin_qtd, ft.Button("Gerar MRN", on_click=admin_gerar_moedas_do_nada, bgcolor="#eab308", color="black", width=280)]), padding=15, visible=False)

    input_json_importar = ft.TextField(label="Cole o JSON aqui", multiline=True, min_lines=3, max_lines=5, border_color="#34d399", on_focus=focus_scroll)
    view_importar_container = ft.Container(content=ft.Column([input_json_importar, ft.Button("Confirmar Depósito", on_click=processar_importacao_texto, bgcolor="#34d399", color="black", width=280)]), padding=10, visible=False)
