import os
import re
import json
import hashlib
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import custom_pdf 

basedir = os.path.abspath(os.path.dirname(__file__))
template_dir = os.path.join(basedir, '..', 'frontend')
history_dir = os.path.join(basedir, 'historico_json')
app = Flask(__name__, static_folder=template_dir, static_url_path='')
CORS(app)

if not os.path.exists(history_dir): os.makedirs(history_dir)

def conv_num(v):
    try: return float(v.replace('.', '').replace(',', '.'))
    except: return 0.0

def fmt_br(v):
    if isinstance(v, str): return v
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def calcular_hash_arquivo(f):
    h = hashlib.md5()
    for c in iter(lambda: f.read(4096), b""): h.update(c)
    f.seek(0)
    return h.hexdigest()

def determinar_status_geral(res):
    if (res['entradas']['status']!='OK' or res['saidas']['status']!='OK' or res['apuracao']['status_recolher']!='OK'):
        return "DIVERGENTE"
    return "OK"

def salvar_analise(dados, nome, hash_val):
    try:
        agora = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        st = determinar_status_geral(dados)
        dados['meta_data'] = datetime.now().strftime("%d/%m/%Y %H:%M")
        dados['meta_nome_original'] = nome
        dados['meta_status_geral'] = st
        dados['meta_hash_sped'] = hash_val
        
        destino = None
        for arq in os.listdir(history_dir):
            if arq.endswith(".json"):
                try:
                    p = os.path.join(history_dir, arq)
                    with open(p, 'r', encoding='utf-8') as fr:
                        if json.load(fr).get('meta_hash_sped') == hash_val:
                            destino = p; break
                except: continue
        
        if not destino:
            clean = re.sub(r'[\\/*?:"<>|]', "", nome)
            destino = os.path.join(history_dir, f"{agora}__{st}__{clean}.json")
            
        with open(destino, 'w', encoding='utf-8') as fw:
            json.dump(dados, fw, ensure_ascii=False, indent=2)
    except Exception as e: print(f"Erro salvar: {e}")

def processar_sped_txt(path):
    ent = {"vl_total":0.0, "bc_icms":0.0, "vl_icms":0.0}
    sai = {"vl_total":0.0, "bc_icms":0.0, "vl_icms":0.0}
    apu = {}
    soma_e116 = 0.0
    txt_e = []
    codes = set()
    validas = ['00','01','06','07','08']
    nota_valida = False
    
    try:
        with open(path, 'r', encoding='latin-1', errors='replace') as f:
            for l in f:
                r = l.strip()
                if not r.startswith('|'): continue
                c = r.split('|')
                reg = c[1]
                
                if reg.startswith('E'):
                    txt_e.append(r)
                    if reg=='E110':
                        apu = {"recolher": c[13], "saldo_credor": c[14], "vl_tot_debitos": c[2], "vl_aj_debitos": c[3], "vl_tot_aj_debitos": c[4], "vl_estornos_cred": c[5], "vl_tot_creditos": c[6], "vl_aj_creditos": c[7], "vl_tot_aj_creditos": c[8], "vl_estornos_deb": c[9], "vl_sld_anterior": c[10], "vl_sld_devedor": c[11], "vl_deducoes": c[12], "vl_recolher": c[13], "vl_sld_transportar": c[14], "vl_extra": c[15] if len(c)>15 else "0,00"}
                    if reg=='E111' and len(c)>2: codes.add(c[2])
                    if reg=='E116': soma_e116 += conv_num(c[3])
                
                if reg in ['C100','C500','C600','D100','D500','D600']:
                    nota_valida = (len(c)>6 and c[6] in validas)
                elif reg in ['C001','D001','E001']: nota_valida = False
                elif reg in ['C190','C590','C690','D190','D590','D690'] and nota_valida and len(c)>=8:
                    vals = [conv_num(c[5]), conv_num(c[6]), conv_num(c[7])]
                    if c[3].startswith(('1','2','3')):
                        ent['vl_total']+=vals[0]; ent['bc_icms']+=vals[1]; ent['vl_icms']+=vals[2]
                    elif c[3].startswith(('5','6','7')):
                        sai['vl_total']+=vals[0]; sai['bc_icms']+=vals[1]; sai['vl_icms']+=vals[2]
        return ent, sai, apu, soma_e116, txt_e, list(codes)
    except: return None

@app.route('/')
def index(): return send_from_directory(template_dir, 'index.html')
@app.route('/<path:path>')
def serve_static(path): return send_from_directory(template_dir, path)

@app.route('/historico/', methods=['GET'])
def listar():
    l = []
    try:
        for f in sorted(os.listdir(history_dir), reverse=True):
            if f.endswith(".json"):
                try:
                    with open(os.path.join(history_dir, f), 'r', encoding='utf-8') as j:
                        m = json.load(j)
                        l.append({"arquivo":f, "data":f[:10], "hora":f[11:19], "status":m.get('meta_status_geral','?'), "nome_visual":m.get('meta_nome_original',f)})
                except: pass
    except: pass
    return jsonify(l)

@app.route('/historico/<f>', methods=['GET'])
def ler_hist(f):
    try:
        with open(os.path.join(history_dir, f), 'r', encoding='utf-8') as j: return jsonify(json.load(j))
    except Exception as e: return jsonify({"detail":str(e)}), 404

@app.route('/historico/<f>', methods=['DELETE'])
def del_hist(f):
    try:
        os.remove(os.path.join(history_dir, f))
        return jsonify({"msg":"ok"})
    except: return jsonify({"error":"erro"}), 500

@app.route('/upload-e-processar/', methods=['POST'])
def proc():
    if 'file_sped' not in request.files: return jsonify({"detail":"Falta SPED"}), 400
    fs = request.files['file_sped']
    fp = request.files.get('file_pdf')
    
    h = calcular_hash_arquivo(fs)
    nm = fs.filename
    pt = os.path.join(basedir, "temp_sped.txt")
    pp = os.path.join(basedir, "temp_livro.pdf")
    fs.save(pt)
    if fp: fp.save(pp)

    try:
        dt = processar_sped_txt(pt)
        if not dt: raise Exception("Erro leitura TXT")
        ent, sai, apu, e116, txt, cods = dt
        
        # 2. SEM PARÂMETROS AVANÇADOS
        dp = {}
        if fp: dp = custom_pdf.processar_livro_completo(pp, cods)

        res = {
            "entradas": {"sped": {"total_operacao": fmt_br(ent['vl_total']), "base_de_calculo_icms": fmt_br(ent['bc_icms']), "total_icms": fmt_br(ent['vl_icms'])}, "livro": dp.get('entradas',{}), "status": "OK"},
            "saidas": {"sped": {"total_operacao": fmt_br(sai['vl_total']), "base_de_calculo_icms": fmt_br(sai['bc_icms']), "total_icms": fmt_br(sai['vl_icms'])}, "livro": dp.get('saidas',{}), "status": "OK"},
            "apuracao": {"sped_recolher": fmt_br(conv_num(apu.get('recolher'))), "sped_saldo_credor": fmt_br(conv_num(apu.get('saldo_credor'))), "livro_valores": dp.get('apuracao',{}), "status_recolher": "OK", "status_saldo_credor": "OK", "detalhe_e110": apu},
            "bloco_e_texto": "\n".join(txt),
            "codigos_ausentes_livro": dp.get('codigos_ausentes',[]),
            "detalhamento_codigos": dp.get('detalhamento_codigos',{}),
            "soma_e116": fmt_br(e116),
            "soma_livro_inf_comp": fmt_br(dp.get('soma_inf_complementares',0.0))
        }
        salvar_analise(res, nm, h)
        return jsonify(res)
    except Exception as e:
        print(e)
        return jsonify({"detail":str(e)}), 500
    finally:
        if os.path.exists(pt): os.remove(pt)
        if os.path.exists(pp): os.remove(pp)

if __name__ == '__main__': app.run(host='0.0.0.0', port=5000, debug=True)