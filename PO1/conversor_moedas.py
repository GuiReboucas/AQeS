"""
╔══════════════════════════════════════════════════════════╗
║           CONVERSOR DE MOEDAS — CLI                      ║
║  Suporta taxas via API (exchangerate-api) ou offline     ║
╚══════════════════════════════════════════════════════════╝
"""

import sys
import time
import urllib.request
import urllib.error
import json
from datetime import datetime

# ──────────────────────────────────────────────────────────
#  CONFIGURAÇÕES
# ──────────────────────────────────────────────────────────

# Chave gratuita da exchangerate-api.com (plano free, sem cadastro)
# Substitua por uma chave própria em https://www.exchangerate-api.com/
API_KEY = "API_KEY"
API_URL = f"https://v6.exchangerate-api.com/v6/{API_KEY}/latest/"

# Taxas de câmbio pré-definidas (fallback quando API indisponível)
# Base: USD — atualizadas manualmente
TAXAS_FALLBACK = {
    "USD": 1.0000,
    "BRL": 5.7800,
    "EUR": 0.9250,
    "GBP": 0.7920,
    "JPY": 149.500,
    "CAD": 1.3640,
    "AUD": 1.5380,
    "CHF": 0.8960,
    "CNY": 7.2400,
    "ARS": 870.00,
    "MXN": 17.150,
    "CLP": 930.00,
    "COP": 3940.0,
    "PEN": 3.7500,
    "UYU": 39.500,
}

NOMES_MOEDAS = {
    "USD": "Dólar Americano",
    "BRL": "Real Brasileiro",
    "EUR": "Euro",
    "GBP": "Libra Esterlina",
    "JPY": "Iene Japonês",
    "CAD": "Dólar Canadense",
    "AUD": "Dólar Australiano",
    "CHF": "Franco Suíço",
    "CNY": "Yuan Chinês",
    "ARS": "Peso Argentino",
    "MXN": "Peso Mexicano",
    "CLP": "Peso Chileno",
    "COP": "Peso Colombiano",
    "PEN": "Sol Peruano",
    "UYU": "Peso Uruguaio",
}

SIMBOLOS = {
    "USD": "US$", "BRL": "R$",  "EUR": "€",   "GBP": "£",
    "JPY": "¥",   "CAD": "CA$", "AUD": "A$",  "CHF": "Fr",
    "CNY": "¥",   "ARS": "$",   "MXN": "$",   "CLP": "$",
    "COP": "$",   "PEN": "S/",  "UYU": "$U",
}

# ──────────────────────────────────────────────────────────
#  CORES ANSI (funciona em terminais Unix e Windows 10+)
# ──────────────────────────────────────────────────────────

class Cor:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    AZUL    = "\033[34m"
    CIANO   = "\033[96m"
    VERDE   = "\033[92m"
    AMARELO = "\033[93m"
    VERMELHO= "\033[91m"
    CINZA   = "\033[90m"
    BRANCO  = "\033[97m"
    BG_AZUL = "\033[44m"

def c(texto, cor):
    return f"{cor}{texto}{Cor.RESET}"

# ──────────────────────────────────────────────────────────
#  UTILITÁRIOS DE EXIBIÇÃO
# ──────────────────────────────────────────────────────────

LARGURA = 58

def linha(char="─", cor=Cor.CIANO):
    print(c(char * LARGURA, cor))

def cabecalho():
    print()
    linha("═")
    titulo = "  💱  CONVERSOR DE MOEDAS"
    print(c(titulo.center(LARGURA), Cor.BOLD + Cor.CIANO))
    linha("═")
    print()

def rodape():
    print()
    linha("─", Cor.CINZA)
    print(c("  Obrigado por usar o Conversor de Moedas!", Cor.CINZA))
    linha("─", Cor.CINZA)
    print()

def msg_info(texto):
    print(c(f"  ℹ  {texto}", Cor.CIANO))

def msg_ok(texto):
    print(c(f"  ✔  {texto}", Cor.VERDE))

def msg_aviso(texto):
    print(c(f"  ⚠  {texto}", Cor.AMARELO))

def msg_erro(texto):
    print(c(f"  ✖  {texto}", Cor.VERMELHO))

def spinner(msg, duracao=1.2):
    frames = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
    fim = time.time() + duracao
    i = 0
    while time.time() < fim:
        print(f"\r  {c(frames[i % len(frames)], Cor.CIANO)}  {msg}", end="", flush=True)
        time.sleep(0.1)
        i += 1
    print("\r" + " " * (len(msg) + 10) + "\r", end="")

# ──────────────────────────────────────────────────────────
#  BUSCA DE TAXAS
# ──────────────────────────────────────────────────────────

def buscar_taxas_api(moeda_base: str) -> dict | None:
    """Tenta buscar taxas em tempo real via exchangerate-api."""
    if API_KEY == "SUA_CHAVE_AQUI":
        return None  # Sem chave configurada
    try:
        url = API_URL + moeda_base
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            if data.get("result") == "success":
                return data["conversion_rates"]
    except Exception:
        pass
    return None

def obter_taxas(moeda_base: str) -> tuple[dict, bool]:
    """
    Retorna (taxas, online).
    taxas: dicionário {CODIGO: taxa_relativa_a_base}
    online: True se veio da API, False se é fallback.
    """
    spinner("Buscando cotações...")
    taxas_api = buscar_taxas_api(moeda_base)
    if taxas_api:
        # Filtra apenas as moedas suportadas
        taxas = {m: taxas_api[m] for m in TAXAS_FALLBACK if m in taxas_api}
        return taxas, True

    # Converte as taxas fallback para a base escolhida
    base_usd = TAXAS_FALLBACK[moeda_base]
    taxas = {m: v / base_usd for m, v in TAXAS_FALLBACK.items()}
    return taxas, False

# ──────────────────────────────────────────────────────────
#  LISTAGEM DE MOEDAS
# ──────────────────────────────────────────────────────────

def exibir_moedas():
    moedas = list(TAXAS_FALLBACK.keys())
    print()
    linha()
    print(c("  MOEDAS DISPONÍVEIS".center(LARGURA), Cor.BOLD + Cor.AZUL))
    linha()
    colunas = 3
    por_coluna = (len(moedas) + colunas - 1) // colunas
    for i in range(por_coluna):
        linha_txt = ""
        for col in range(colunas):
            idx = i + col * por_coluna
            if idx < len(moedas):
                cod = moedas[idx]
                nome = NOMES_MOEDAS[cod][:18]
                item = f"  {c(cod, Cor.AMARELO)}  {c(nome, Cor.CINZA)}"
                linha_txt += f"{item:<38}"
        print(linha_txt)
    linha()
    print()

# ──────────────────────────────────────────────────────────
#  LEITURA DE ENTRADAS
# ──────────────────────────────────────────────────────────

def ler_moeda(prompt: str) -> str:
    moedas_validas = list(TAXAS_FALLBACK.keys())
    while True:
        entrada = input(c(f"  {prompt}: ", Cor.BRANCO)).strip().upper()
        if entrada in moedas_validas:
            return entrada
        msg_erro(f"Moeda '{entrada}' não reconhecida. Use os códigos da lista acima.")

def ler_valor(prompt: str) -> float:
    while True:
        entrada = input(c(f"  {prompt}: ", Cor.BRANCO)).strip()
        entrada = entrada.replace(",", ".")
        try:
            valor = float(entrada)
            if valor < 0:
                msg_erro("O valor não pode ser negativo.")
                continue
            if valor == 0:
                msg_aviso("Valor zero informado — o resultado também será zero.")
            return valor
        except ValueError:
            msg_erro(f"'{entrada}' não é um número válido. Use ponto ou vírgula decimal.")

def ler_opcao(prompt: str, opcoes: list[str]) -> str:
    while True:
        entrada = input(c(f"  {prompt}: ", Cor.BRANCO)).strip().upper()
        if entrada in opcoes:
            return entrada
        msg_erro(f"Opção inválida. Escolha entre: {', '.join(opcoes)}")

# ──────────────────────────────────────────────────────────
#  CONVERSÃO
# ──────────────────────────────────────────────────────────

def converter(valor: float, origem: str, destino: str, taxas: dict) -> float:
    """Converte valor da moeda origem para destino usando taxas relativas à base."""
    # taxas[X] = quanto 1 unidade da base vale em X
    # Para converter origem -> destino:
    #   1. Normalizar para a base: valor / taxas[origem]
    #   2. Converter para destino: * taxas[destino]
    return (valor / taxas[origem]) * taxas[destino]

def formatar_valor(valor: float, moeda: str) -> str:
    simbolo = SIMBOLOS.get(moeda, "")
    if moeda == "JPY":
        return f"{simbolo} {valor:,.0f}"
    return f"{simbolo} {valor:,.2f}"

# ──────────────────────────────────────────────────────────
#  RESULTADO
# ──────────────────────────────────────────────────────────

def exibir_resultado(valor: float, origem: str, destino: str,
                     resultado: float, taxas: dict, online: bool):
    taxa_direta = taxas[destino] / taxas[origem]
    taxa_inversa = taxas[origem] / taxas[destino]

    print()
    linha("═")
    print(c("  RESULTADO DA CONVERSÃO".center(LARGURA), Cor.BOLD + Cor.VERDE))
    linha("═")
    print()
    print(f"  {c(formatar_valor(valor, origem), Cor.AMARELO + Cor.BOLD)}"
          f"  {c(NOMES_MOEDAS[origem], Cor.CINZA)}")
    print(f"  {c('↓', Cor.CIANO + Cor.BOLD)}")
    print(f"  {c(formatar_valor(resultado, destino), Cor.VERDE + Cor.BOLD)}"
          f"  {c(NOMES_MOEDAS[destino], Cor.CINZA)}")
    print()
    linha("─")
    print(f"  {c('Taxa de câmbio:', Cor.CINZA)}")
    print(f"    1 {c(origem, Cor.AMARELO)} = {c(f'{taxa_direta:.4f}', Cor.BRANCO)} {destino}")
    print(f"    1 {c(destino, Cor.AMARELO)} = {c(f'{taxa_inversa:.4f}', Cor.BRANCO)} {origem}")
    print()
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    fonte = c("API em tempo real", Cor.VERDE) if online else c("taxas pré-definidas (offline)", Cor.AMARELO)
    print(f"  {c('Fonte:', Cor.CINZA)} {fonte}")
    print(f"  {c('Data/hora:', Cor.CINZA)} {c(now, Cor.CINZA)}")
    linha("═")
    print()

# ──────────────────────────────────────────────────────────
#  HISTÓRICO DA SESSÃO
# ──────────────────────────────────────────────────────────

historico: list[dict] = []

def registrar_historico(valor, origem, destino, resultado):
    historico.append({
        "hora": datetime.now().strftime("%H:%M:%S"),
        "de": f"{formatar_valor(valor, origem)} {origem}",
        "para": f"{formatar_valor(resultado, destino)} {destino}",
    })

def exibir_historico():
    if not historico:
        msg_aviso("Nenhuma conversão realizada nesta sessão.")
        return
    print()
    linha()
    print(c("  HISTÓRICO DA SESSÃO".center(LARGURA), Cor.BOLD + Cor.AZUL))
    linha()
    print(f"  {c('Hora', Cor.CINZA):<20}{c('De', Cor.CINZA):<30}{c('Para', Cor.CINZA)}")
    linha("─")
    for h in historico:
        print(f"  {c(h['hora'], Cor.AMARELO):<20}{h['de']:<30}{c(h['para'], Cor.VERDE)}")
    linha()
    print()

# ──────────────────────────────────────────────────────────
#  MENU PRINCIPAL
# ──────────────────────────────────────────────────────────

def menu_principal():
    cabecalho()

    # Status de conexão com API
    if API_KEY == "SUA_CHAVE_AQUI":
        msg_aviso("API não configurada — usando taxas pré-definidas (offline).")
        msg_info("Configure sua chave gratuita em: https://www.exchangerate-api.com/")
    else:
        msg_info("API configurada. As cotações serão buscadas em tempo real.")
    print()

    while True:
        linha("─")
        print(c("  MENU".center(LARGURA), Cor.BOLD))
        linha("─")
        print(f"  {c('[1]', Cor.AMARELO)} Converter moeda")
        print(f"  {c('[2]', Cor.AMARELO)} Ver moedas disponíveis")
        print(f"  {c('[3]', Cor.AMARELO)} Histórico da sessão")
        print(f"  {c('[0]', Cor.VERMELHO)} Sair")
        linha("─")

        opcao = ler_opcao("Escolha uma opção [0-3]", ["0", "1", "2", "3"])

        if opcao == "1":
            fluxo_conversao()
        elif opcao == "2":
            exibir_moedas()
        elif opcao == "3":
            exibir_historico()
        elif opcao == "0":
            rodape()
            sys.exit(0)

# ──────────────────────────────────────────────────────────
#  FLUXO DE CONVERSÃO
# ──────────────────────────────────────────────────────────

def fluxo_conversao():
    print()
    linha()
    print(c("  NOVA CONVERSÃO".center(LARGURA), Cor.BOLD + Cor.CIANO))
    linha()
    print(c("  (Digite o código da moeda, ex: BRL, USD, EUR)", Cor.CINZA))
    print()

    origem  = ler_moeda(f"Moeda de ORIGEM  ({'/'.join(list(TAXAS_FALLBACK.keys())[:5])}...)")
    destino = ler_moeda(f"Moeda de DESTINO ({'/'.join(list(TAXAS_FALLBACK.keys())[:5])}...)")

    if origem == destino:
        msg_aviso("Origem e destino são iguais — o valor não será alterado.")

    valor = ler_valor(f"Valor em {origem}")

    # Busca taxas tendo a moeda de origem como base para melhor precisão
    taxas, online = obter_taxas(origem)

    if not online:
        msg_aviso("Usando taxas offline (pré-definidas). Podem não refletir cotações atuais.")

    resultado = converter(valor, origem, destino, taxas)
    exibir_resultado(valor, origem, destino, resultado, taxas, online)
    registrar_historico(valor, origem, destino, resultado)

    # Pergunta se quer fazer outra conversão com os mesmos valores invertidos
    print(f"  {c('Deseja converter o resultado de volta?', Cor.CINZA)} ", end="")
    resp = input(c("[S/N]: ", Cor.BRANCO)).strip().upper()
    if resp == "S":
        taxas2, online2 = obter_taxas(destino)
        resultado2 = converter(resultado, destino, origem, taxas2)
        exibir_resultado(resultado, destino, origem, resultado2, taxas2, online2)
        registrar_historico(resultado, destino, origem, resultado2)

# ──────────────────────────────────────────────────────────
#  PONTO DE ENTRADA
# ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        menu_principal()
    except KeyboardInterrupt:
        print()
        msg_aviso("Programa encerrado pelo usuário.")
        rodape()
        sys.exit(0)
