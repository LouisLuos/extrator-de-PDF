/**
 * Lógica de Interação do Cliente (Front-end) — Extrator de Guias Prisionais (SERES-PE / CEASA).
 * Responsabilidades:
 * - Gerenciar seleção e Drag & Drop de arquivos/pastas PDF.
 * - Enviar lote via Fetch API para `/api/processar`.
 * - Controlar barra de progresso visual e renderizar indicadores (KPIs) e tabela de resultados.
 */

let selectedFiles = [];

// Detecção automática de host (Live Server :5500, file:///, ou Flask nativo :5000)
const API_BASE = (window.location.protocol === 'file:' || (window.location.port && window.location.port !== '5000'))
    ? 'http://127.0.0.1:5000'
    : '';

const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');
const folderInput = document.getElementById('folderInput');
const fileListBox = document.getElementById('fileListBox');
const fileItemsContainer = document.getElementById('fileItemsContainer');
const fileCountLabel = document.getElementById('fileCountLabel');
const btnProcessar = document.getElementById('btnProcessar');
const btnSpinner = document.getElementById('btnSpinner');
const btnText = document.getElementById('btnText');
const progressBox = document.getElementById('progressBox');
const progressBarFill = document.getElementById('progressBarFill');
const progressPercent = document.getElementById('progressPercent');
const progressStatus = document.getElementById('progressStatus');
const kpiGrid = document.getElementById('kpiGrid');
const resultsSection = document.getElementById('resultsSection');
const tableBody = document.getElementById('tableBody');
const btnDownloadExcel = document.getElementById('btnDownloadExcel');

// Eventos de Drag & Drop
['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });
});

['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
    });
});

dropzone.addEventListener('drop', (e) => {
    const files = Array.from(e.dataTransfer.files).filter(f => f.name.toLowerCase().endsWith('.pdf'));
    adicionarArquivos(files);
});

fileInput.addEventListener('change', (e) => {
    const files = Array.from(e.target.files);
    adicionarArquivos(files);
});

folderInput.addEventListener('change', (e) => {
    const files = Array.from(e.target.files).filter(f => f.name.toLowerCase().endsWith('.pdf'));
    adicionarArquivos(files);
});

function adicionarArquivos(files) {
    if (!files.length) return;
    selectedFiles = [...selectedFiles, ...files];
    atualizarListaArquivos();
}

function limparArquivos() {
    selectedFiles = [];
    fileInput.value = '';
    folderInput.value = '';
    atualizarListaArquivos();
    resultsSection.style.display = 'none';
    kpiGrid.style.display = 'none';
}

function atualizarListaArquivos() {
    if (selectedFiles.length === 0) {
        fileListBox.style.display = 'none';
        btnProcessar.disabled = true;
        return;
    }

    fileListBox.style.display = 'block';
    btnProcessar.disabled = false;
    fileCountLabel.textContent = `${selectedFiles.length} arquivo(s) PDF selecionado(s)`;

    fileItemsContainer.innerHTML = '';
    selectedFiles.slice(0, 10).forEach(f => {
        const item = document.createElement('div');
        item.className = 'file-item';
        item.innerHTML = `
            <div class="file-name">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
                <span>${f.name}</span>
            </div>
            <span style="color: var(--text-muted); font-size: 0.78rem;">${(f.size / 1024).toFixed(1)} KB</span>
        `;
        fileItemsContainer.appendChild(item);
    });

    if (selectedFiles.length > 10) {
        const item = document.createElement('div');
        item.style.textAlign = 'center';
        item.style.color = 'var(--text-muted)';
        item.style.fontSize = '0.8rem';
        item.style.padding = '4px';
        item.textContent = `... e mais ${selectedFiles.length - 10} arquivo(s)`;
        fileItemsContainer.appendChild(item);
    }
}

async function iniciarProcessamento() {
    if (!selectedFiles.length) return;

    btnProcessar.disabled = true;
    btnSpinner.style.display = 'inline-block';
    btnText.textContent = 'Processando...';
    progressBox.style.display = 'block';
    progressBarFill.style.width = '15%';
    progressPercent.textContent = '15%';
    progressStatus.textContent = 'Enviando arquivos e iniciando OCR paralelo...';

    const formData = new FormData();
    selectedFiles.forEach(f => formData.append('files', f));
    formData.append('categoria', document.getElementById('categoriaSelect').value);

    const startTime = Date.now();

    try {
        let prog = 15;
        const timer = setInterval(() => {
            const elapsed = Math.round((Date.now() - startTime) / 1000);
            if (prog < 90) {
                prog += Math.floor(Math.random() * 5) + 2;
            }
            progressBarFill.style.width = `${Math.min(prog, 90)}%`;
            progressPercent.textContent = `${Math.min(prog, 90)}%`;
            progressStatus.textContent = `⚡ Executando OCR paralelo & segmentando guias (${elapsed}s decorridos)...`;
        }, 500);

        const response = await fetch(`${API_BASE}/api/processar`, {
            method: 'POST',
            body: formData
        });

        clearInterval(timer);

        if (!response.ok) {
            throw new Error('Falha no processamento do servidor.');
        }

        const result = await response.json();
        const totalTime = ((Date.now() - startTime) / 1000).toFixed(1);

        progressBarFill.style.width = '100%';
        progressPercent.textContent = '100%';
        progressStatus.textContent = `🎉 Concluído em ${totalTime}s! ${result.total_guias} guias prisionais auditadas.`;

        exibirResultados(result);

    } catch (err) {
        alert('Erro durante o processamento: ' + err.message);
        progressStatus.textContent = 'Erro ao processar.';
    } finally {
        btnProcessar.disabled = false;
        btnSpinner.style.display = 'none';
        btnText.textContent = 'Processar Guias';
    }
}

function exibirResultados(data) {
    kpiGrid.style.display = 'grid';
    resultsSection.style.display = 'block';

    document.getElementById('kpiTotal').textContent = data.total_guias;
    document.getElementById('kpiRegulares').textContent = data.total_regulares;
    document.getElementById('kpiReposicoes').textContent = data.total_reposicoes;

    btnDownloadExcel.href = `${API_BASE}/api/download/${data.arquivo_excel}`;

    tableBody.innerHTML = '';
    data.registros.forEach(r => {
        const tr = document.createElement('tr');
        const badgeClass = r.reposicao === 'SIM' ? 'badge-sim' : 'badge-nao';
        tr.innerHTML = `
            <td style="font-weight: 500;">${r.arquivo}</td>
            <td>${r.pagina}</td>
            <td style="color: var(--accent-cyan); font-weight: 500;">${r.lugar}</td>
            <td>${r.data}</td>
            <td>${r.mes}</td>
            <td><span class="${badgeClass}">${r.reposicao}</span></td>
        `;
        tableBody.appendChild(tr);
    });

    resultsSection.scrollIntoView({ behavior: 'smooth' });
}

