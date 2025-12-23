import os
import fitz  # PyMuPDF
import re
import sys
from decimal import Decimal, InvalidOperation
from collections import defaultdict

# --- CONFIGURAÇÕES GLOBAIS ---
MARCADOR_SECAO_APURACAO_LIVRO = "Apuração do Saldo"
MARCADOR_PARADA_LIVRO = "Observações"
CODIGOS_APURACAO_LIVRO = ["013", "014"]
MARCADOR_SECAO_INF_COMP = "INFORMAÇÕES COMPLEMENTARES"
ETIQUETA_TOTAIS_LIVRO = "Totais"
MARCADOR_PAGINA_ENTRADAS = "ENTRADAS"
MARCADOR_PAGINA_SAIDAS = "SAÍDAS"

CHAVES_COMPLETAS_ES = ["total_operacao", "base_de_calculo_icms", "total_icms", "base_de_calculo_icms_st", "total_icms_st", "total_ipi"]
CHAVES_LAYOUT_HORIZONTAL_SAIDAS = ["total_operacao", "base_de_calculo_icms", "total_icms", "isentas_nao_trib", "outras"]

# --- FUNÇÕES UTILITÁRIAS ---
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

# --- BUSCAS ---
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

# --- MESTRA ---
def processar_livro_completo(caminho_pdf, lista_codigos_sped=[]):
    return {
        "entradas": encontrar_e_extrair_totais_es(caminho_pdf, MARCADOR_PAGINA_ENTRADAS, ETIQUETA_TOTAIS_LIVRO, CHAVES_COMPLETAS_ES),
        "saidas": encontrar_e_extrair_totais_es(caminho_pdf, MARCADOR_PAGINA_SAIDAS, ETIQUETA_TOTAIS_LIVRO, CHAVES_LAYOUT_HORIZONTAL_SAIDAS),
        "apuracao": encontrar_apuracao_LIVRO(caminho_pdf, MARCADOR_SECAO_APURACAO_LIVRO, CODIGOS_APURACAO_LIVRO),
        "soma_inf_complementares": somar_informacoes_complementares(caminho_pdf, MARCADOR_SECAO_INF_COMP, MARCADOR_PARADA_LIVRO),
        "detalhamento_codigos": {k: f"{v:.2f}" for k,v in analisar_detalhamento_por_codigo(caminho_pdf).items()},
        "codigos_ausentes": verificar_codigos_no_livro(caminho_pdf, lista_codigos_sped)
    }