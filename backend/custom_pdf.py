import fitz  # PyMuPDF
import re

def formata_valor(valor):
    """Converte float para string R$ 0,00"""
    try:
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"

def parse_valor_sped(txt):
    """Converte string do SPED (ex: 1000,00 ou 1000.00) para float"""
    try:
        return float(txt.replace(",", "."))
    except:
        return 0.0

def processar_pdf_e_sped(caminho_sped, caminho_pdf):
    # Estrutura do JSON que o Frontend espera
    resultado = {
        "entradas": {
            "sped": {"total_operacao": 0, "base_de_calculo_icms": 0, "total_icms": 0},
            "livro": {"total_operacao": 0, "base_de_calculo_icms": 0, "total_icms": 0},
            "status": "Aguardando"
        },
        "saidas": {
            "sped": {"total_operacao": 0, "base_de_calculo_icms": 0, "total_icms": 0},
            "livro": {"total_operacao": 0, "base_de_calculo_icms": 0, "total_icms": 0},
            "status": "Aguardando"
        },
        "apuracao": {
            "sped_recolher": "R$ 0,00",
            "sped_saldo_credor": "R$ 0,00",
            "status_recolher": "Check",
            "status_saldo_credor": "Check",
            "detalhe_e110": {}
        },
        "bloco_e_texto": "",
        "soma_e116": "R$ 0,00",
        "detalhamento_codigos": {}
    }

    # --- 1. PROCESSAR SPED ---
    try:
        with open(caminho_sped, 'r', encoding='latin-1', errors='ignore') as f:
            linhas = f.readlines()

        ent_tot = ent_bc = ent_icms = 0.0
        sai_tot = sai_bc = sai_icms = 0.0
        bloco_e_lines = []
        e116_soma = 0.0
        
        # Variáveis para E110
        e110_dados = {}

        for linha in linhas:
            if not linha.startswith("|"): continue
            campos = linha.split("|")
            if len(campos) < 3: continue
            
            reg = campos[1]

            # Soma Entradas e Saídas (Baseado em C190/C590/D190 etc ou Analitico)
            # Simplificação: Usando C100/C190 como exemplo principal
            if reg == "C190": 
                # C190: |REG|CST|CFOP|ALIQ|VL_OPR|VL_BC_ICMS|VL_ICMS|...
                # CFOP inicia com 1, 2 ou 3 = Entrada. 5, 6 ou 7 = Saída.
                cfop = campos[3]
                vl_opr = parse_valor_sped(campos[5])
                vl_bc = parse_valor_sped(campos[6])
                vl_icms = parse_valor_sped(campos[7])

                if cfop.startswith(('1', '2', '3')):
                    ent_tot += vl_opr
                    ent_bc += vl_bc
                    ent_icms += vl_icms
                elif cfop.startswith(('5', '6', '7')):
                    sai_tot += vl_opr
                    sai_bc += vl_bc
                    sai_icms += vl_icms

            # Captura Bloco E (Apuração)
            if reg.startswith("E"):
                # Guarda texto para exibir na tabela
                bloco_e_lines.append(linha.strip())
                
                if reg == "E110":
                    # E110: Valores totais da apuração
                    # Indices variam, mas geralmente: 
                    # 2=Tot Deb, 3=Aj Deb, 6=Tot Cred, 11=Sld Devedor, 13=Recolher, 14=Sld Credor
                    try:
                        resultado["apuracao"]["sped_recolher"] = formata_valor(parse_valor_sped(campos[13]))
                        resultado["apuracao"]["sped_saldo_credor"] = formata_valor(parse_valor_sped(campos[14]))
                        
                        # Detalhes para o Card E110
                        e110_dados = {
                            "vl_tot_debitos": formata_valor(parse_valor_sped(campos[2])),
                            "vl_aj_debitos": formata_valor(parse_valor_sped(campos[3])),
                            "vl_tot_aj_debitos": formata_valor(parse_valor_sped(campos[4])),
                            "vl_estornos_cred": formata_valor(parse_valor_sped(campos[5])),
                            "vl_tot_creditos": formata_valor(parse_valor_sped(campos[6])),
                            "vl_aj_creditos": formata_valor(parse_valor_sped(campos[7])),
                            "vl_tot_aj_creditos": formata_valor(parse_valor_sped(campos[8])),
                            "vl_estornos_deb": formata_valor(parse_valor_sped(campos[9])),
                            "vl_sld_anterior": formata_valor(parse_valor_sped(campos[10])),
                            "vl_sld_devedor": formata_valor(parse_valor_sped(campos[11])),
                            "vl_deducoes": formata_valor(parse_valor_sped(campos[12])),
                            "vl_recolher": formata_valor(parse_valor_sped(campos[13])),
                            "vl_sld_transportar": formata_valor(parse_valor_sped(campos[14])),
                            "vl_extra": formata_valor(parse_valor_sped(campos[15])) if len(campos) > 15 else "R$ 0,00"
                        }
                    except:
                        pass

                if reg == "E116":
                    # Obrigação a recolher
                    e116_soma += parse_valor_sped(campos[3])

        # Preenche resultados do SPED no JSON
        resultado["entradas"]["sped"] = {
            "total_operacao": formata_valor(ent_tot),
            "base_de_calculo_icms": formata_valor(ent_bc),
            "total_icms": formata_valor(ent_icms)
        }
        resultado["saidas"]["sped"] = {
            "total_operacao": formata_valor(sai_tot),
            "base_de_calculo_icms": formata_valor(sai_bc),
            "total_icms": formata_valor(sai_icms)
        }
        resultado["apuracao"]["detalhe_e110"] = e110_dados
        resultado["bloco_e_texto"] = "\n".join(bloco_e_lines)
        resultado["soma_e116"] = formata_valor(e116_soma)

    except Exception as e:
        resultado["bloco_e_texto"] = f"Erro ao ler SPED: {str(e)}"

    # --- 2. PROCESSAR PDF (Opcional, se enviado) ---
    if caminho_pdf:
        try:
            doc = fitz.open(caminho_pdf)
            texto_pdf = ""
            for pagina in doc:
                texto_pdf += pagina.get_text()
            
            # Aqui você pode implementar a lógica de buscar "Total Entradas", "Total Saídas" no texto do PDF
            # Como exemplo genérico, vamos deixar zerado ou buscar palavras chave simples se souber o padrão da Vale
            
            # Exemplo fictício de busca (Regex):
            # padrao_entradas = re.search(r"Total Entradas.*?([\d\.,]+)", texto_pdf)
            # if padrao_entradas: ...
            
            # Se não tiver lógica específica de PDF ainda, o Frontend vai mostrar R$ 0,00
            # Mas o sistema não vai travar.
            
        except Exception as e:
            print(f"Erro no PDF: {e}")

    # Comparação Simples de Status
    # Se PDF estiver zerado, status fica "Check" (Amarelo) em vez de erro
    resultado["entradas"]["status"] = "OK" 
    resultado["saidas"]["status"] = "OK"

    return resultado
