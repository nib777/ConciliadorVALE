from flask import Flask, request, jsonify, send_from_directory, session, redirect, url_for
from flask_cors import CORS
import os
import json
from datetime import datetime
from werkzeug.utils import secure_filename
import threading # Importante para a fila
import time

# --- IMPORTAÇÃO DOS SEUS MÓDULOS ---
# Certifique-se que esses arquivos existem na pasta backend
from custom_pdf import processar_pdf_e_sped

app = Flask(__name__)
# Chave secreta para criptografar o cookie de login (pode ser qualquer texto aleatório)
app.secret_key = 'segredo_da_vale_conciliador_2025' 
CORS(app)

# --- CONFIGURAÇÕES ---
# Senha de acesso (Você pode mudar aqui)
SENHA_DO_SISTEMA = "vale123" 

# Configura caminhos
basedir = os.path.abspath(os.path.dirname(__file__))
frontend_dir = os.path.join(basedir, '..', 'frontend')
HISTORICO_DIR = os.path.join(basedir, 'historico_json')
if not os.path.exists(HISTORICO_DIR):
    os.makedirs(HISTORICO_DIR)

# --- A MÁGICA DA FILA (LOCK) ---
# Isso cria um "cadeado". Só uma pessoa pode segurar o cadeado por vez.
processamento_lock = threading.Lock()

# --- VERIFICAÇÃO DE LOGIN ---
def esta_logado():
    return session.get('logado') == True

# --- ROTAS ---

# 1. Rota Principal (Serve o Site ou o Login)
@app.route('/')
def index():
    if not esta_logado():
        return send_from_directory(frontend_dir, 'login.html') # Manda pro login
    return send_from_directory(frontend_dir, 'index.html') # Manda pro sistema

# 2. Rota de Fazer Login (POST)
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    senha_recebida = data.get('senha')
    if senha_recebida == SENHA_DO_SISTEMA:
        session['logado'] = True
        return jsonify({"status": "ok"})
    else:
        return jsonify({"status": "erro", "msg": "Senha incorreta"}), 401

# 3. Rota de Logout
@app.route('/logout')
def logout():
    session.pop('logado', None)
    return redirect('/')

# 4. Servir Arquivos Estáticos (CSS, JS, Imagens)
@app.route('/<path:filename>')
def serve_static(filename):
    # Se pedir login.html, libera. Se pedir outros e não tiver logado, bloqueia (exceto CSS/JS/Assets para a tela de login não ficar feia)
    if not esta_logado() and filename not in ['login.html', 'style.css', 'app.js', 'assets/logo-vale.png']:
         # Se for tentar acessar o HTML principal sem logar, manda pro login
         if filename == 'index.html':
             return send_from_directory(frontend_dir, 'login.html')
    
    return send_from_directory(frontend_dir, filename)

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory(os.path.join(frontend_dir, 'assets'), filename)

# 5. Processamento (COM FILA DE ESPERA)
@app.route('/upload-e-processar/', methods=['POST'])
def upload_e_processar():
    if not esta_logado():
        return jsonify({"erro": "Acesso negado. Faça login."}), 401

    # Tenta pegar o cadeado. Se alguém já tiver usando, ele ESPERA aqui até liberar.
    # Isso impede que a memória exploda.
    with processamento_lock:
        try:
            # --- SEU CÓDIGO ORIGINAL DE PROCESSAMENTO COMEÇA AQUI ---
            if 'file_sped' not in request.files:
                return jsonify({"erro": "Arquivo SPED não enviado"}), 400
            
            file_sped = request.files['file_sped']
            file_pdf = request.files.get('file_pdf') # PDF é opcional agora? Se for obrigatório, ajuste.

            # Salva temporariamente
            sped_path = os.path.join(basedir, secure_filename(file_sped.filename))
            file_sped.save(sped_path)
            
            pdf_path = None
            if file_pdf:
                pdf_path = os.path.join(basedir, secure_filename(file_pdf.filename))
                file_pdf.save(pdf_path)

            # Chama sua função de análise
            # (Assumindo que sua função retorna um dicionário JSON pronto)
            resultado = processar_pdf_e_sped(sped_path, pdf_path)
            
            # Limpeza
            if os.path.exists(sped_path): os.remove(sped_path)
            if pdf_path and os.path.exists(pdf_path): os.remove(pdf_path)

            # Salvar no Histórico
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            status_res = resultado.get("entradas", {}).get("status", "Check") 
            nome_arq = f"{timestamp}__{status_res}__{secure_filename(file_sped.filename)}.json"
            caminho_json = os.path.join(HISTORICO_DIR, nome_arq)
            
            with open(caminho_json, 'w', encoding='utf-8') as f:
                json.dump(resultado, f, ensure_ascii=False, indent=4)
            
            return jsonify(resultado)
            # --- FIM DO CÓDIGO DE PROCESSAMENTO ---

        except Exception as e:
            return jsonify({"erro": f"Erro interno: {str(e)}"}), 500

# 6. Histórico (Listar)
@app.route('/historico/', methods=['GET'])
def listar_historico():
    if not esta_logado(): return jsonify([]), 401
    try:
        arquivos = []
        for f in sorted(os.listdir(HISTORICO_DIR), reverse=True):
            if f.endswith(".json"):
                parts = f.split("__")
                data_hora = parts[0] if len(parts) > 0 else "???"
                status = parts[1] if len(parts) > 1 else "???"
                nome_orig = parts[2] if len(parts) > 2 else f
                
                # Formata data visual
                dt_obj = datetime.strptime(data_hora, "%Y-%m-%d_%H-%M-%S")
                data_vis = dt_obj.strftime("%d/%m/%Y")
                hora_vis = dt_obj.strftime("%H:%M")

                arquivos.append({
                    "arquivo": f,
                    "data": data_vis,
                    "hora": hora_vis,
                    "status": status,
                    "nome_visual": nome_orig
                })
        return jsonify(arquivos)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

# 7. Histórico (Ler um arquivo)
@app.route('/historico/<filename>', methods=['GET'])
def ler_historico(filename):
    if not esta_logado(): return jsonify({"erro":"Login required"}), 401
    try:
        safe_name = secure_filename(filename)
        return send_from_directory(HISTORICO_DIR, safe_name)
    except Exception as e:
        return jsonify({"erro": str(e)}), 404

# 8. Histórico (Deletar)
@app.route('/historico/<filename>', methods=['DELETE'])
def deletar_historico(filename):
    if not esta_logado(): return jsonify({"erro":"Login required"}), 401
    try:
        caminho = os.path.join(HISTORICO_DIR, secure_filename(filename))
        if os.path.exists(caminho):
            os.remove(caminho)
            return jsonify({"status": "deletado"})
        return jsonify({"erro": "Arquivo não encontrado"}), 404
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
