"""
Adaptador de Entrada de Automação / Fila de Execução (Driving Adapter).

Responsabilidade:
- Monitorar a conclusão do processo anterior (PID alvo).
- Disparar automaticamente o pipeline de Não Perecíveis via `app.py nao_perecivel`.
- Salvar log de execução em `logs/fila_execucao.log`.
"""

import ctypes
from datetime import datetime
from pathlib import Path
import subprocess
import sys
import time

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DIR_LOGS = BASE_DIR / "logs"
DIR_LOGS.mkdir(parents=True, exist_ok=True)
ARQUIVO_LOG = DIR_LOGS / "fila_execucao.log"


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

    while is_pid_running(pid_alvo):
        log(f"⏳ Processo (PID {pid_alvo}) ainda em execução. Aguardando 20 segundos...")
        time.sleep(20)

    log("=" * 70)
    log(f"🏁 Processo {pid_alvo} CONCLUÍDO com sucesso! Liberando CPU.")
    log("🚀 DISPARANDO GATILHO: Iniciando pipeline de NÃO PERECÍVEIS...")
    log("=" * 70)

    entrypoint = BASE_DIR / "app.py"
    cmd = [sys.executable, "-u", str(entrypoint), "nao_perecivel"]
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

    if proc.stdout:
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
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    aguardar_e_executar(pid)
