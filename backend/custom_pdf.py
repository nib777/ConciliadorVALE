import fitz  # PyMuPDF
import re
import sys
import os
from decimal import Decimal, InvalidOperation
from collections import defaultdict
from werkzeug.utils import secure_filename

#CONFIGURAÇÕES GLOBAIS
MARCADOR_SECAO_APURACAO_LIVRO = "Apuração do Saldo"
MARCADOR_PARADA_LIVRO = "Observações"
CODIGOS_APURACAO_LIVRO = ["013", "014"]
MARCADOR_SECAO_INF_COMP = "INFORMAÇÕES COMPLEMENTARES"
ETIQUETA_TOTAIS_LIVRO = "Totais"
MARCADOR_PAGINA_ENTRADAS = "ENTRADAS"
MARCADOR_PAGINA_SAIDAS = "SAÍDAS"

CHAVES_COMPLETAS_ES = ["total_operacao", "base_de_calculo_icms", "total_icms", "base_de_calculo_icms_st", "total_icms_st", "total_ipi"]
CHAVES_LAYOUT_HORIZONTAL_SAIDAS = ["total_operacao", "base_de_calculo_icms", "total_icms", "isentas_nao_trib", "outras"]

#FUNÇÕES UTILITÁRIAS
def limpar_e_converter_numero(texto_numero):
    if not texto_numero or "," not in texto_numero: return 0.0
    try:
        texto = texto_numero.strip().replace(" ", "").replace(".", "").replace(",", ".")
        texto = re.sub(r"[^0-9\.]", "", texto)
        return float(texto) if texto else 0.0
    except: return 0.0

def _limpar_valor_decimal(valor_str):
    try:
        v = valor_str.replace('.', '').replace(',', '.')
        return Decimal(re.sub(r"[^0-9\.]", "", v))
    except: return Decimal('0.0')

#BUSCAS
def encontrar_e_extrair_totais_es(caminho_pdf, marcador_pagina, etiqueta_valor, chaves):
    if not caminho_pdf or not os.path.exists(caminho_pdf): return {}
    valores = {}
    regex_valor = r'(\d{1,3}(?:\.\d{3})*,\d{2})'
    try:
        doc = fitz.open(caminho_pdf)
        texto_pag = ""
        for pagina in doc:
            t = pagina.get_text()
            if marcador_pagina.upper() in t.upper():
                texto_pag = t
                if etiqueta_valor in t: break
        doc.close()
        if not texto_pag: return {}
        
        for linha in texto_pag.split('\n'):
            if linha.strip().startswith(etiqueta_valor):
                vals = re.findall(regex_valor, linha)
                if len(vals) >= 3:
                    for i, k in enumerate(chaves):
                        if i < len(vals): valores[k] = vals[i]
                    return valores
        return {}
    except: return {}

def encontrar_apuracao_LIVRO(caminho_pdf, marcador_secao, codigos_alvo):
    if not caminho_pdf or not os.path.exists(caminho_pdf): return {}
    valores = {}
    regex_valor = r'(\d{1,3}(?:\.\d{3})*,\d{2})'
    try:
        doc = fitz.open(caminho_pdf)
        texto = "".join([p.get_text() for p in doc])
        doc.close()
        match = re.search(f"{marcador_secao}(.*?)(?={MARCADOR_PARADA_LIVRO}|$)", texto, re.DOTALL | re.IGNORECASE)
        if match:
            for linha in match.group(1).split('\n'):
                parts = linha.strip().split()
                if parts and parts[0] in codigos_alvo:
                    v = re.search(regex_valor, linha)
                    if v: valores[parts[0]] = v.group(0)
        return valores
    except: return {}

def somar_informacoes_complementares(caminho_pdf, marcador_secao, marcador_parada):
    if not caminho_pdf or not os.path.exists(caminho_pdf): return 0.0
    soma = 0.0
    try:
        doc = fitz.open(caminho_pdf)
        texto = "".join([p.get_text() for p in doc])
        doc.close()
        match = re.search(f"{marcador_secao}(.*?)(?={marcador_parada}|$)", texto, re.DOTALL | re.IGNORECASE)
        if match:
            for p in match.group(1).split():
                val = limpar_e_converter_numero(p)
                if val > 0: soma += val
        return soma
    except: return 0.0

def analisar_detalhamento_por_codigo(caminho_pdf):
    if not caminho_pdf or not os.path.exists(caminho_pdf): return {}
    somas = defaultdict(Decimal)
    try:
        doc = fitz.open(caminho_pdf)
        for page in doc:
            for linha in page.get_text().split('\n'):
                cod = re.search(r'\b([A-Z]{2}\d{5,12})\b', linha)
                if cod:
                    vals = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})', linha)
                    if vals:
                        d = _limpar_valor_decimal(vals[-1])
                        if d > 0: somas[cod.group(1)] += d
        doc.close()
        return dict(somas)
    except: return {}

def verificar_codigos_no_livro(caminho_pdf, lista_codigos):
    if not caminho_pdf or not os.path.exists(caminho_pdf): return []
    try:
        doc = fitz.open(caminho_pdf)
        texto = "".join([p.get_text() for p in doc])
        doc.close()
        return [c for c in lista_codigos if c not in texto]
    except: return []

def processar_livro_completo(caminho_pdf, lista_codigos_sped=[]):
    return {
        "entradas": encontrar_e_extrair_totais_es(caminho_pdf, MARCADOR_PAGINA_ENTRADAS, ETIQUETA_TOTAIS_LIVRO, CHAVES_COMPLETAS_ES),
        "saidas": encontrar_e_extrair_totais_es(caminho_pdf, MARCADOR_PAGINA_SAIDAS, ETIQUETA_TOTAIS_LIVRO, CHAVES_LAYOUT_HORIZONTAL_SAIDAS),
        "apuracao": encontrar_apuracao_LIVRO(caminho_pdf, MARCADOR_SECAO_APURACAO_LIVRO, CODIGOS_APURACAO_LIVRO),
        "soma_inf_complementares": somar_informacoes_complementares(caminho_pdf, MARCADOR_SECAO_INF_COMP, MARCADOR_PARADA_LIVRO),
        "detalhamento_codigos": {k: f"{v:.2f}" for k,v in analisar_detalhamento_por_codigo(caminho_pdf).items()},
        "codigos_ausentes": verificar_codigos_no_livro(caminho_pdf, lista_codigos_sped)
    }
    
#PARTE 2: LEITURA DO SPED E INTEGRAÇÃO

def formata_valor(valor):
    """Converte float/string para visual R$ 0,00"""
    try:
        if isinstance(valor, str):
            # Se ja vier formatado, só adiciona R$
            if "," in valor and "R$" not in valor: return f"R$ {valor}"
            return valor
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"

def parse_valor_sped(txt):
    """Lê número do arquivo SPED (formato inglês com vírgula)"""
    try:
        return float(txt.replace(",", "."))
    except:
        return 0.0

def processar_pdf_e_sped(caminho_sped, caminho_pdf):
    #Estrutura JSON Final
    resultado = {
        "entradas": {"sped": {}, "livro": {}, "status": "Aguardando"},
        "saidas": {"sped": {}, "livro": {}, "status": "Aguardando"},
        "apuracao": {"sped_recolher": "0", "sped_saldo_credor": "0", "livro_valores": {}, "status_recolher": "Check", "status_saldo_credor": "Check"},
        "bloco_e_texto": "",
        "soma_e116": "R$ 0,00",
        "detalhamento_codigos": {},
        "codigos_ausentes_livro": [],
        "soma_livro_inf_comp": "R$ 0,00"
    }

    # 1. PROCESSAR SPED (Lógica Padrão)
    lista_codigos_para_checar = []
    try:
        with open(caminho_sped, 'r', encoding='latin-1', errors='ignore') as f:
            linhas = f.readlines()

        ent_tot = ent_bc = ent_icms = 0.0
        sai_tot = sai_bc = sai_icms = 0.0
        bloco_e_lines = []
        e116_soma = 0.0
        e110_dados = {}

        for linha in linhas:
            if not linha.startswith("|"): continue
            campos = linha.split("|")
            if len(campos) < 3: continue
            reg = campos[1]

            # Captura Codigos de Ajuste para checar no PDF depois (E111, E113, etc)
            if reg in ["E111", "E113", "1921", "1923"]:
                if len(campos) > 3: lista_codigos_para_checar.append(campos[3])

            if reg == "C190": 
                cfop = campos[3]
                vl_opr = parse_valor_sped(campos[5])
                vl_bc = parse_valor_sped(campos[6])
                vl_icms = parse_valor_sped(campos[7])

                if cfop.startswith(('1', '2', '3')):
                    ent_tot += vl_opr; ent_bc += vl_bc; ent_icms += vl_icms
                elif cfop.startswith(('5', '6', '7')):
                    sai_tot += vl_opr; sai_bc += vl_bc; sai_icms += vl_icms

            if reg.startswith("E"):
                bloco_e_lines.append(linha.strip())
                if reg == "E110":
                    try:
                        resultado["apuracao"]["sped_recolher"] = formata_valor(parse_valor_sped(campos[13]))
                        resultado["apuracao"]["sped_saldo_credor"] = formata_valor(parse_valor_sped(campos[14]))
                        # Detalhe E110
                        e110_dados = {
                            "vl_tot_debitos": formata_valor(parse_valor_sped(campos[2])),
                            "vl_tot_creditos": formata_valor(parse_valor_sped(campos[6])),
                            "vl_recolher": formata_valor(parse_valor_sped(campos[13])),
                            "vl_sld_transportar": formata_valor(parse_valor_sped(campos[14])),
                            "vl_sld_devedor": formata_valor(parse_valor_sped(campos[11]))
                        }
                    except: pass
                if reg == "E116":
                    e116_soma += parse_valor_sped(campos[3])

        resultado["entradas"]["sped"] = {"total_operacao": formata_valor(ent_tot), "base_de_calculo_icms": formata_valor(ent_bc), "total_icms": formata_valor(ent_icms)}
        resultado["saidas"]["sped"] = {"total_operacao": formata_valor(sai_tot), "base_de_calculo_icms": formata_valor(sai_bc), "total_icms": formata_valor(sai_icms)}
        resultado["apuracao"]["detalhe_e110"] = e110_dados
        resultado["bloco_e_texto"] = "\n".join(bloco_e_lines)
        resultado["soma_e116"] = formata_valor(e116_soma)

    except Exception as e:
        resultado["bloco_e_texto"] = f"Erro SPED: {e}"

    # 2. PROCESSAR PDF
    if caminho_pdf:
        try:
            #Chama a função mestre
            dados_pdf = processar_livro_completo(caminho_pdf, lista_codigos_para_checar)
            
            #Mapeia o resultado do código para o JSON do Dashboard
            #Entradas
            ent_pdf = dados_pdf.get("entradas", {})
            resultado["entradas"]["livro"] = {
                "total_operacao": formata_valor(ent_pdf.get("total_operacao", 0)),
                "base_de_calculo_icms": formata_valor(ent_pdf.get("base_de_calculo_icms", 0)),
                "total_icms": formata_valor(ent_pdf.get("total_icms", 0))
            }
            
            #Saidas
            sai_pdf = dados_pdf.get("saidas", {})
            resultado["saidas"]["livro"] = {
                "total_operacao": formata_valor(sai_pdf.get("total_operacao", 0)),
                "base_de_calculo_icms": formata_valor(sai_pdf.get("base_de_calculo_icms", 0)),
                "total_icms": formata_valor(sai_pdf.get("total_icms", 0))
            }

            #Apuração (013 e 014)
            apu_pdf = dados_pdf.get("apuracao", {})
            resultado["apuracao"]["livro_valores"] = {
                "013": formata_valor(apu_pdf.get("013", 0)),
                "014": formata_valor(apu_pdf.get("014", 0))
            }

            #Outros dados avançados
            resultado["detalhamento_codigos"] = dados_pdf.get("detalhamento_codigos", {})
            resultado["codigos_ausentes_livro"] = dados_pdf.get("codigos_ausentes", [])
            resultado["soma_livro_inf_comp"] = formata_valor(dados_pdf.get("soma_inf_complementares", 0))

            #Comparação de Status
            def get_float(v):
                if isinstance(v, str): return limpar_e_converter_numero(v)
                return float(v)
            
            #Compara valor total entrada
            val_sped = parse_valor_sped(str(ent_tot))
            val_livro = get_float(ent_pdf.get("total_operacao", "0"))
            resultado["entradas"]["status"] = "OK" if abs(val_sped - val_livro) < 1.0 else "Divergente"

            #Compara valor total saida
            val_sped_s = parse_valor_sped(str(sai_tot))
            val_livro_s = get_float(sai_pdf.get("total_operacao", "0"))
            resultado["saidas"]["status"] = "OK" if abs(val_sped_s - val_livro_s) < 1.0 else "Divergente"

        except Exception as e:
            print(f"Erro ao processar PDF com lógica nova: {e}")

    return resultado

