"""
Orquestrador de Fila de Execução (Job Queue / Process Trigger).

Responsabilidade:
- Monitorar a conclusão do processo de perecíveis (PID alvo).
- Assim que o processo anterior liberar a CPU e os recursos, disparar automaticamente
  o pipeline de Não Perecíveis (src/extrator_nao_perecivel.py).
- Salvar log de execução em fila_execucao.log.
"""

import ctypes
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Configurar UTF-8
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent
ARQUIVO_LOG = BASE_DIR / "fila_execucao.log"


def log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"[{timestamp}] {msg}"
    print(linha, flush=True)
    with open(ARQUIVO_LOG, "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def is_pid_running(pid: int) -> bool:
    """Verifica de forma nativa no Windows se o PID ainda está em execução."""
    if pid <= 0:
        return False
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h_process = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h_process:
        return False
    exit_code = ctypes.c_ulong()
    ctypes.windll.kernel32.GetExitCodeProcess(h_process, ctypes.byref(exit_code))
    ctypes.windll.kernel32.CloseHandle(h_process)
    STILL_ACTIVE = 259
    return exit_code.value == STILL_ACTIVE


def aguardar_e_executar(pid_alvo: int):
    log("=" * 70)
    log(f"🎯 ORQUESTRADOR DE FILA ATIVADO: Monitorando PID {pid_alvo}")
    log("=" * 70)

    # 1. Loop de monitoramento do processo de perecíveis
    while is_pid_running(pid_alvo):
        log(f"⏳ Processo de perecíveis (PID {pid_alvo}) ainda em execução. Aguardando 20 segundos...")
        time.sleep(20)

    log("=" * 70)
    log(f"🏁 Processo {pid_alvo} (Perecíveis) CONCLUÍDO com sucesso! Liberando CPU.")
    log("🚀 DISPARANDO GATILHO: Iniciando pipeline de NÃO PERECÍVEIS...")
    log("=" * 70)

    # 2. Executar o pipeline de não perecíveis
    script_nao_perecivel = BASE_DIR / "src" / "extrator_nao_perecivel.py"
    if not script_nao_perecivel.exists():
        log(f"❌ Script não encontrado: {script_nao_perecivel}")
        return

    cmd = [sys.executable, "-u", str(script_nao_perecivel)]
    log(f"Executando comando: {' '.join(cmd)}")

    inicio = time.time()
    proc = subprocess.Popen(
        cmd,
        cwd=str(BASE_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    for line in iter(proc.stdout.readline, ""):
        if line:
            log(line.strip())

    proc.stdout.close()
    return_code = proc.wait()
    duracao = (time.time() - inicio) / 60

    log("=" * 70)
    log(f"🎉 Pipeline de NÃO PERECÍVEIS finalizado com código {return_code} em {duracao:.1f} minutos!")
    log("=" * 70)


if __name__ == "__main__":
    pid_monitorado = 15692
    if len(sys.argv) > 1:
        pid_monitorado = int(sys.argv[1])
    aguardar_e_executar(pid_monitorado)
