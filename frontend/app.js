// frontend/app.js - Versão Render (Caminhos Relativos)
document.addEventListener("DOMContentLoaded", () => {
    window.scrollTo(0, 0);
    const viewDashboard = document.getElementById("view-dashboard");
    const viewHistorico = document.getElementById("view-historico");
    const btnNavDashboard = document.getElementById("btn-nav-dashboard");
    const btnNavHistorico = document.getElementById("btn-nav-historico");
    const logos = document.querySelectorAll(".logo-sidebar, .logo-top-bar");

    const irParaDashboard = (e) => { if(e) e.preventDefault(); viewDashboard.classList.remove("hidden"); viewHistorico.classList.add("hidden"); window.scrollTo(0, 0); };
    const irParaHistorico = async (e) => { if(e) e.preventDefault(); viewDashboard.classList.add("hidden"); viewHistorico.classList.remove("hidden"); window.scrollTo(0, 0); await carregarListaHistorico(); };

    if(btnNavDashboard) btnNavDashboard.addEventListener("click", irParaDashboard);
    if(btnNavHistorico) btnNavHistorico.addEventListener("click", irParaHistorico);
    logos.forEach(logo => logo.addEventListener("click", irParaDashboard));
    
    const btnCollapse = document.getElementById("btn-collapse");
    if(btnCollapse) btnCollapse.addEventListener("click", () => { document.body.classList.toggle("sidebar-collapsed"); const arrow = btnCollapse.querySelector(".arrow-icon"); if(arrow) arrow.textContent = document.body.classList.contains("sidebar-collapsed") ? "»" : "«"; });

    const manualModeCheckbox = document.getElementById("manual-mode-checkbox");
    const manualUploadArea = document.getElementById("manual-upload-area");
    if(manualModeCheckbox) manualModeCheckbox.addEventListener("change", () => { if(manualModeCheckbox.checked) manualUploadArea.classList.remove("hidden"); else manualUploadArea.classList.add("hidden"); });
    
    const btnImprimir = document.getElementById("btn-imprimir");
    if(btnImprimir) btnImprimir.addEventListener("click", () => window.print());

    const filtroBtns = document.querySelectorAll('.filtro-btn');
    filtroBtns.forEach(btn => { btn.addEventListener('click', () => { filtroBtns.forEach(b => b.classList.remove('active')); btn.classList.add('active'); const filtro = btn.getAttribute('data-filtro'); document.querySelectorAll('#bloco-e-table-body tr').forEach(tr => { if (filtro === 'todos') tr.style.display = ''; else tr.style.display = tr.classList.contains(filtro) ? '' : 'none'; }); }); });

    // --- PROCESSAMENTO (CORRIGIDO) ---
    const btnProcessar = document.getElementById("btn-processar-tudo");
    if (btnProcessar) {
        btnProcessar.addEventListener("click", async (e) => {
            if(e) e.preventDefault();
            const statusGeral = document.getElementById("status-message-geral");
            const loader = document.getElementById("loader-processar");
            const fileSped = document.getElementById("file_sped").files[0];
            const fileLivro = document.getElementById("file_livro").files[0];
            if (!fileSped) { alert("Selecione o SPED."); return; }
            limparResultados();
            btnProcessar.disabled = true;
            statusGeral.textContent = "Processando... e Salvando no Histórico.";
            statusGeral.style.display = "block"; statusGeral.style.color = "#00786c";
            if(loader) loader.classList.remove("hidden");
            const formData = new FormData();
            formData.append("file_sped", fileSped);
            if(fileLivro) formData.append("file_pdf", fileLivro);
            try {
                // AQUI ESTAVA O ERRO: Agora usa caminho relativo
                const response = await fetch('/upload-e-processar/', { method: 'POST', body: formData });
                if(!response.ok) throw new Error(await response.text());
                const data = await response.json();
                statusGeral.textContent = "Análise Concluída e Salva!"; statusGeral.style.color = "green";
                preencherDashboard(data);
            } catch (erro) { console.error(erro); statusGeral.textContent = "Erro: " + erro.message; statusGeral.style.color = "red"; } finally { btnProcessar.disabled = false; if(loader) loader.classList.add("hidden"); }
        });
    }
});

async function carregarListaHistorico() {
    const tbody = document.getElementById("tabela-historico-body");
    if(!tbody) return;
    tbody.innerHTML = "<tr><td colspan='4'>Carregando...</td></tr>";
    try {
        const res = await fetch('/historico/');
        const lista = await res.json();
        tbody.innerHTML = "";
        if(lista.length === 0) { tbody.innerHTML = "<tr><td colspan='4'>Vazio (Render reiniciou ou histórico limpo).</td></tr>"; return; }
        lista.forEach(item => {
            const tr = document.createElement("tr"); const cor = item.status === "OK" ? "green" : "red";
            tr.innerHTML = `<td>${item.data} ${item.hora}</td><td>${item.nome_visual}</td><td style="color:${cor};font-weight:bold">${item.status}</td><td style="display:flex;gap:10px"><button class="btn-carregar-hist" data-arquivo="${item.arquivo}" style="background:var(--primary-green);color:white;border:none;padding:5px 10px;border-radius:4px;cursor:pointer">Abrir</button><button class="btn-deletar-hist" data-arquivo="${item.arquivo}" style="background:#dc3545;color:white;border:none;padding:5px 10px;border-radius:4px;cursor:pointer">🗑️</button></td>`;
            tbody.appendChild(tr);
        });
        document.querySelectorAll(".btn-carregar-hist").forEach(btn => btn.addEventListener("click", () => abrirAnaliseSalva(btn.getAttribute("data-arquivo"))));
        document.querySelectorAll(".btn-deletar-hist").forEach(btn => btn.addEventListener("click", async (e) => { if(confirm("Apagar?")) { await fetch(`/historico/${btn.getAttribute("data-arquivo")}`, {method:'DELETE'}); e.target.closest("tr").remove(); } }));
    } catch { tbody.innerHTML = "<tr><td colspan='4'>Erro.</td></tr>"; }
}

async function abrirAnaliseSalva(f) {
    try {
        document.getElementById("view-dashboard").classList.remove("hidden"); document.getElementById("view-historico").classList.add("hidden"); window.scrollTo(0,0); limparResultados();
        const res = await fetch(`/historico/${f}`);
        preencherDashboard(await res.json());
    } catch (e) { alert("Erro: " + e.message); }
}

function preencherDashboard(res) {
    const fmt = (v) => { if (!v || v === "" || v === "0" || v === "0,00") return "R$ 0,00"; let n = parseFloat(String(v).replace("R$ ", "").replace(/\./g, '').replace(',', '.')); if (isNaN(n)) return "--"; return n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' }); };
    const setTxt = (id, val) => { const el = document.getElementById(id); if(el) el.textContent = fmt(val); };
    const setStatus = (idCard, idLabel, status) => { const card = document.getElementById(idCard); const label = document.getElementById(idLabel); if(card) { card.classList.remove("aguardando","ok","divergente"); card.classList.add(status==="OK"?"ok":"divergente"); } if(label) { label.className = status==="OK"?"status-box ok":"status-box divergente"; label.textContent = status==="OK"?"Conciliado":"Divergente"; } };
    const ent = res.entradas; const sai = res.saidas;
    setTxt("sped-e-total", ent.sped.total_operacao); setTxt("sped-e-bc", ent.sped.base_de_calculo_icms); setTxt("sped-e-icms", ent.sped.total_icms); if(ent.livro.total_operacao) { setTxt("livro-e-total", ent.livro.total_operacao); setTxt("livro-e-bc", ent.livro.base_de_calculo_icms); setTxt("livro-e-icms", ent.livro.total_icms); setStatus("card-entradas", "resultado-entradas", ent.status); }
    setTxt("sped-s-total", sai.sped.total_operacao); setTxt("sped-s-bc", sai.sped.base_de_calculo_icms); setTxt("sped-s-icms", sai.sped.total_icms); if(sai.livro.total_operacao) { setTxt("livro-s-total", sai.livro.total_operacao); setTxt("livro-s-bc", sai.livro.base_de_calculo_icms); setTxt("livro-s-icms", sai.livro.total_icms); setStatus("card-saidas", "resultado-saidas", sai.status); }
    const apu = res.apuracao; setTxt("sped-a1", apu.sped_recolher); setTxt("sped-a2", apu.sped_saldo_credor); if(apu.livro_valores) { setTxt("livro-a1", apu.livro_valores["013"]); setTxt("livro-a2", apu.livro_valores["014"]); setStatus("card-apuracao", null, (apu.status_recolher==="OK" && apu.status_saldo_credor==="OK")?"OK":"Divergente"); }
    const e110 = apu.detalhe_e110; if(e110) { document.getElementById("card-e110-destaque").classList.remove("hidden","aguardando"); setTxt("e110-vl-tot-debitos", e110.vl_tot_debitos); setTxt("e110-vl-aj-debitos", e110.vl_aj_debitos); setTxt("e110-vl-tot-aj-debitos", e110.vl_tot_aj_debitos); setTxt("e110-vl-estornos-cred", e110.vl_estornos_cred); setTxt("e110-vl-tot-creditos", e110.vl_tot_creditos); setTxt("e110-vl-aj-creditos", e110.vl_aj_creditos); setTxt("e110-vl-tot-aj-creditos", e110.vl_tot_aj_creditos); setTxt("e110-vl-estornos-deb", e110.vl_estornos_deb); setTxt("e110-vl-sld-anterior", e110.vl_sld_anterior); setTxt("e110-vl-sld-devedor", e110.vl_sld_devedor); setTxt("e110-vl-deducoes", e110.vl_deducoes); setTxt("e110-vl-recolher", e110.vl_recolher); setTxt("e110-vl-sld-transportar", e110.vl_sld_transportar); setTxt("e110-vl-extra", e110.vl_extra); }
    if(res.soma_e116) { document.getElementById("card-detalhe-e116").classList.remove("aguardando"); setTxt("sped-e116-soma", res.soma_e116); setTxt("livro-infcomp-soma", res.soma_livro_inf_comp); }
    const tbody = document.getElementById("bloco-e-table-body"); if(tbody && res.bloco_e_texto) { tbody.innerHTML=""; res.bloco_e_texto.split('\n').forEach(l=>{ if(!l.trim())return; const tr=document.createElement("tr"); const c=l.split('|'); if(c[1]) tr.classList.add('reg-'+c[1].toLowerCase()); if(c[0]==='') c.shift(); if(c[c.length-1]==='') c.pop(); c.forEach(d=>{ const td=document.createElement("td"); td.textContent=d; if(d.includes(',') && !isNaN(d.replace(/\./g,'').replace(',','.'))) { td.textContent=fmt(d); td.classList.add("valor-monetario"); td.style.textAlign="right"; } tr.appendChild(td); }); tbody.appendChild(tr); }); }
    const tDet = document.getElementById("detalhamento-table-body"); if(tDet && res.detalhamento_codigos) { tDet.innerHTML=""; Object.entries(res.detalhamento_codigos).forEach(([k,v])=>{ const tr=document.createElement("tr"); tr.innerHTML=`<td style="font-weight:bold">${k}</td><td class="valor-monetario" style="text-align:right">${fmt(v)}</td>`; tDet.appendChild(tr); }); document.getElementById("card-detalhamento").classList.remove("aguardando"); }
    const listaA = document.getElementById("lista-alertas-codigos"); const cardA = document.getElementById("card-alertas"); if(cardA && listaA) { listaA.innerHTML=""; let err=false; const txt=res.bloco_e_texto||""; ['E110','E111','E113','E116'].forEach(b=>{ if(!txt.includes(`|${b}|`)) { listaA.innerHTML+=`<li style="color:#856404;background:rgba(255,193,7,0.1);padding:5px">⚠️ Falta bloco ${b}</li>`; err=true; } }); (res.codigos_ausentes_livro||[]).forEach(c=>{ listaA.innerHTML+=`<li style="color:#721c24;background:#f8d7da;padding:5px">🚨 Cód ${c} não achado no PDF</li>`; err=true; }); if(err) { cardA.classList.remove("ok"); cardA.classList.add("divergente"); } else { cardA.classList.remove("divergente"); cardA.classList.add("ok"); listaA.innerHTML=`<li style="color:#155724;background:#d4edda;padding:5px">✓ Tudo certo!</li>`; } }
}

function limparResultados() { document.querySelectorAll(".card-resultado").forEach(c=>{ if(c.id!=="card-extracao-avancada")c.className="card-resultado aguardando"; }); document.querySelectorAll('span[id^="sped-"], span[id^="livro-"], span[id^="e110-"]').forEach(s=>s.textContent="--"); const t=document.getElementById("bloco-e-table-body"); if(t)t.innerHTML=""; const td=document.getElementById("detalhamento-table-body"); if(td)td.innerHTML=""; }
